import csv
import io
import json
from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from .forms import NamedForm, PartForm, UserForm
from .importing import FIELDS, LABELS, auto_mapping, confirm, error_csv, headers, preview, template_bytes, workbook
from .models import Box, Change, Customer, Destination, ImportJob, Integration, Part, SheetColor
from .permissions import require_admin, require_edit, require_read
from .services import create_part, update_part

def catalog_query(request):
    qs = Part.objects.select_related('customer', 'destination', 'box', 'sheet_color')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(part_number__icontains=q) | Q(customer__name__icontains=q))
    if request.GET.get('customer'):
        qs = qs.filter(customer_id=request.GET['customer'])
    if request.GET.get('diameter'):
        qs = qs.filter(diameter=request.GET['diameter'])
    if request.GET.get('status') in ('active', 'inactive'):
        qs = qs.filter(active=request.GET['status'] == 'active')
    order = request.GET.get('order', 'part_number')
    if order not in ('part_number', '-part_number', 'customer__name', '-customer__name', 'updated_at', '-updated_at'):
        order = 'part_number'
    return qs.order_by(order, 'id'), order

@login_required
def part_list(request):
    require_read(request.user)
    qs, order = catalog_query(request)
    page = Paginator(qs, 25).get_page(request.GET.get('page'))
    return render(request, 'catalog/list.html', {'page': page, 'page_numbers': page.paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1), 'count': qs.count(), 'customers': Customer.objects.filter(active=True), 'diameters': Part.objects.exclude(diameter='').values_list('diameter', flat=True).distinct().order_by('diameter'), 'order': order, 'query': request.GET.copy(), 'excel_view': request.GET.get('view') == 'excel'})

@login_required
def export_parts(request):
    require_read(request.user)
    qs, _ = catalog_query(request)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="universo-ramos.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['UUID', 'Cliente', 'Destino', 'Número de parte', 'Diámetro', 'Pared', 'Peso', 'Caja', 'STD.', 'Hoja color', 'Cliente (segunda columna)', 'Planta', 'Activo', 'Versión'])
    for part in qs.iterator():
        writer.writerow([part.id, part.customer, part.destination or '', part.part_number, part.diameter, part.wall_note or (part.wall if part.wall is not None else ''), part.weight if part.weight is not None else '', part.box or '', part.std, part.sheet_color or '', part.reference_customer, part.reference_plant, part.active, part.version])
    return response

@login_required
def part_detail(request, pk):
    require_read(request.user)
    part = get_object_or_404(Part.objects.select_related('customer', 'destination', 'box', 'sheet_color'), pk=pk)
    return render(request, 'catalog/detail.html', {'part': part, 'history': part.changes.select_related('actor').order_by('-id')})

@login_required
def part_create(request):
    require_edit(request.user)
    form = PartForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            part = create_part({k: form.cleaned_data[k] for k in form.Meta.fields}, request.user)
            messages.success(request, 'Número de parte creado correctamente.')
            return redirect('catalog:create') if 'another' in request.POST else redirect('catalog:detail', pk=part.pk)
        except (ValidationError, IntegrityError) as exc:
            form.add_error('part_number', 'Ya existe este número de parte o sus datos no son válidos.')
    return render(request, 'catalog/form.html', {'form': form, 'heading': 'Nuevo número de parte', 'is_create': True})

@login_required
def part_edit(request, pk):
    require_edit(request.user)
    part = get_object_or_404(Part, pk=pk)
    form = PartForm(request.POST or None, instance=part)
    if request.method == 'POST' and form.is_valid():
        try:
            part = update_part(part.pk, {k: form.cleaned_data[k] for k in form.Meta.fields}, form.cleaned_data['version'], request.user)
            messages.success(request, 'Pieza actualizada.')
            return redirect('catalog:detail', pk=part.pk)
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        except IntegrityError:
            form.add_error('part_number', 'Ya existe este número de parte.')
    return render(request, 'catalog/form.html', {'form': form, 'part': part, 'heading': 'Editar número de parte', 'is_create': False})

@login_required
@require_POST
def part_toggle(request, pk):
    require_edit(request.user)
    part = get_object_or_404(Part, pk=pk)
    try:
        update_part(pk, {'active': not part.active}, request.POST.get('version'), request.user)
        messages.success(request, 'Estado actualizado.')
    except (ValidationError, ValueError, TypeError):
        messages.error(request, 'La pieza cambió. Revise sus datos actuales.')
    return redirect('catalog:detail', pk=pk)

CATALOG_MODELS = {'clientes': Customer, 'destinos': Destination, 'cajas': Box, 'colores': SheetColor}

@login_required
def related_values(request, kind):
    require_edit(request.user)
    model = CATALOG_MODELS.get(kind)
    if not model:
        return HttpResponseBadRequest('Catálogo no válido')
    form = NamedForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            model.objects.create(name=form.cleaned_data['name'].strip())
            messages.success(request, 'Valor registrado.')
            return redirect('catalog:related', kind=kind)
        except IntegrityError:
            form.add_error('name', 'Este valor ya existe.')
    return render(request, 'catalog/related.html', {'kind': kind, 'values': model.objects.all(), 'form': form})

@login_required
def import_list(request):
    require_edit(request.user)
    return render(request, 'catalog/import_list.html', {'jobs': ImportJob.objects.filter(actor=request.user).select_related('actor').order_by('-created_at')[:50]})

@login_required
@require_POST
def import_delete(request, pk):
    require_edit(request.user)
    with transaction.atomic():
        job = get_object_or_404(ImportJob.objects.select_for_update(), pk=pk, actor=request.user)
        if job.status == 'confirmed':
            messages.error(request, 'Las importaciones confirmadas no se pueden eliminar.')
            return redirect('catalog:imports')
        storage = job.file.storage
        file_name = job.file.name
        job.delete()
    if file_name:
        storage.delete(file_name)
    messages.success(request, 'Importación pendiente eliminada.')
    return redirect('catalog:imports')

@login_required
def import_upload(request):
    require_edit(request.user)
    if request.method == 'POST':
        file = request.FILES.get('file')
        if not file or not file.name.lower().endswith('.xlsx') or file.size > 5 * 1024 * 1024 or file.size < 100:
            messages.error(request, 'Seleccione un archivo .xlsx válido de hasta 5 MB.')
        else:
            job = ImportJob.objects.create(actor=request.user, filename=file.name[:255], file=file)
            try:
                sheets = workbook(job).sheetnames
                if not sheets:
                    raise ValidationError('No hay hojas disponibles.')
                return redirect('catalog:import_map', pk=job.pk)
            except Exception:
                job.file.delete(save=False)
                job.delete()
                messages.error(request, 'No se pudo leer el archivo .xlsx.')
    return render(request, 'catalog/import_upload.html')

@login_required
def import_map(request, pk):
    require_edit(request.user)
    job = get_object_or_404(ImportJob, pk=pk, actor=request.user)
    if job.status == 'confirmed':
        return redirect('catalog:import_preview', pk=pk)
    wb = workbook(job)
    sheets = wb.sheetnames
    sheet = request.POST.get('sheet') or request.GET.get('sheet') or job.sheet or sheets[0]
    try:
        _, names = headers(job, sheet)
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        names = []
    detected = auto_mapping(names)
    if request.method == 'POST':
        job.sheet = sheet
        job.mapping = {field: request.POST.get(field) for field in FIELDS if request.POST.get(field)}
        job.mode = request.POST.get('mode', 'both')
        job.clear_blanks = request.POST.get('clear_blanks') == 'on'
        if job.mode not in ('add', 'update', 'both'):
            return HttpResponseBadRequest('Modo inválido')
        job.save()
        try:
            preview(job)
            return redirect('catalog:import_preview', pk=pk)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
    return render(request, 'catalog/import_map.html', {'job': job, 'sheets': sheets, 'sheet': sheet, 'names': list(enumerate(names, 1)), 'fields': FIELDS, 'labels': LABELS, 'detected': job.mapping if job.mapping and job.sheet == sheet else detected})

@login_required
def import_preview(request, pk):
    require_edit(request.user)
    job = get_object_or_404(ImportJob, pk=pk, actor=request.user)
    if request.method == 'POST':
        try:
            confirm(pk, request.user)
            messages.success(request, 'Importación confirmada.')
            return redirect('catalog:import_preview', pk=pk)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        except IntegrityError:
            messages.error(request, 'El catálogo cambió durante la confirmación. Genere otra vista previa.')
    rows = job.result.get('rows', [])
    page = Paginator(rows, 50).get_page(request.GET.get('page'))
    return render(request, 'catalog/import_preview.html', {'job': job, 'page': page, 'page_numbers': page.paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1), 'blocked': any(r['status'] in ('duplicate', 'error') for r in rows)})

@login_required
def import_errors(request, pk):
    require_edit(request.user)
    job = get_object_or_404(ImportJob, pk=pk, actor=request.user)
    response = HttpResponse(error_csv(job), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="errores-importacion.csv"'
    return response

@login_required
def import_template(request):
    require_edit(request.user)
    response = HttpResponse(template_bytes(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="plantilla-universo-ramos.xlsx"'
    return response

@login_required
def history(request):
    require_admin(request.user)
    page = Paginator(Change.objects.select_related('part', 'actor').order_by('-id'), 50).get_page(request.GET.get('page'))
    return render(request, 'catalog/history.html', {'page': page, 'page_numbers': page.paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1)})

@login_required
def users(request):
    require_admin(request.user)
    return render(request, 'catalog/users.html', {'users': User.objects.order_by('username')})

@login_required
def user_edit(request, pk=None):
    require_admin(request.user)
    user = get_object_or_404(User, pk=pk) if pk else None
    form = UserForm(request.POST or None, instance=user)
    if user and request.method != 'POST':
        form.fields['role'].initial = user.groups.values_list('name', flat=True).first()
    if request.method == 'POST' and form.is_valid():
        if not user and not form.cleaned_data['password']:
            form.add_error('password', 'La contraseña es obligatoria para una cuenta nueva.')
        else:
            form.save()
            messages.success(request, 'Usuario guardado.')
            return redirect('catalog:users')
    return render(request, 'catalog/user_form.html', {'form': form, 'editing': bool(user)})

@login_required
def integrations(request):
    require_admin(request.user)
    secret = None
    if request.method == 'POST':
        if request.POST.get('action') == 'create':
            name = request.POST.get('name', '').strip()
            if name and len(name) <= 120:
                try:
                    _, secret = Integration.create_key(name)
                except IntegrityError:
                    messages.error(request, 'Ya existe una integración con ese nombre.')
            else:
                messages.error(request, 'Ingrese un nombre válido.')
        elif request.POST.get('action') == 'revoke':
            from django.utils import timezone
            Integration.objects.filter(pk=request.POST.get('pk')).update(active=False, revoked_at=timezone.now())
            messages.success(request, 'Credencial revocada.')
    return render(request, 'catalog/integrations.html', {'integrations': Integration.objects.order_by('name'), 'secret': secret})
