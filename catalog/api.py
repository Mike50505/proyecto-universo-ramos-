from django.core import signing
from django.db.models import Q
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import Box, Change, Customer, Destination, Part, SheetColor, normalize_code

class PartSerializer(serializers.ModelSerializer):
    customer = serializers.CharField(source='customer.name')
    destination = serializers.CharField(source='destination.name', allow_null=True)
    box = serializers.CharField(source='box.name', allow_null=True)
    sheet_color = serializers.CharField(source='sheet_color.name', allow_null=True)

    class Meta:
        model = Part
        fields = ['id', 'part_number', 'is_sample', 'customer', 'destination', 'diameter', 'wall', 'wall_note', 'weight', 'box', 'std', 'sheet_color', 'reference_customer', 'reference_plant', 'active', 'version', 'created_at', 'updated_at']


def filter_samples(queryset, request):
    if not request.auth.include_samples:
        queryset = queryset.filter(is_sample=False)
    value = request.query_params.get('is_sample')
    if value in ('true', 'false'):
        return queryset.filter(is_sample=value == 'true')
    return queryset


def changes_cursor(request, sequence):
    return signing.dumps({'sequence': sequence, 'integration': request.auth.pk, 'policy_version': request.auth.policy_version}, salt='catalog-changes')


def resync_required(request):
    return Response({'code': 'resync_required', 'detail': 'Cambió el permiso de muestras. Reconstruya el catálogo local desde bootstrap.', 'bootstrap_url': request.build_absolute_uri('/api/v1/bootstrap/')}, status=409)


def change_event(change, integration):
    snapshot = {'is_sample': False, **change.after}
    # A removal marker avoids exposing sample data and removes previously cached records.
    if not integration.include_samples and (snapshot['is_sample'] or change.part.is_sample):
        return {'sequence': change.pk, 'operation': 'deactivate', 'part_id': str(change.part_id), 'excluded': True,
                'part': {'id': str(change.part_id), 'is_sample': True, 'active': False, 'version': snapshot['version']}}
    return {'sequence': change.pk, 'operation': change.operation, 'part_id': str(change.part_id), 'excluded': False, 'part': snapshot}

class PartsPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200

@api_view(['GET'])
def parts(request):
    if request.query_params.get('policy_version') not in (None, str(request.auth.policy_version)):
        return resync_required(request)
    qs = Part.objects.select_related('customer', 'destination', 'box', 'sheet_color').order_by('id')
    if request.query_params.get('q'):
        q = request.query_params['q'].strip()
        qs = qs.filter(Q(part_number__icontains=q) | Q(customer__name__icontains=q))
    if request.query_params.get('customer'):
        qs = qs.filter(customer__name__iexact=request.query_params['customer'])
    if request.query_params.get('active') in ('true', 'false'):
        qs = qs.filter(active=request.query_params['active'] == 'true')
    paginator = PartsPagination()
    qs = filter_samples(qs, request)
    return paginator.get_paginated_response(PartSerializer(paginator.paginate_queryset(qs, request), many=True).data)

@api_view(['GET'])
def exact(request):
    code = normalize_code(request.query_params.get('code', ''))
    if not code:
        return Response({'detail': 'Indique code.'}, status=400)
    matches = Part.objects.select_related('customer', 'destination', 'box', 'sheet_color').filter(normalized_number=code)
    if request.query_params.get('customer'):
        matches = matches.filter(customer__name__iexact=request.query_params['customer'])
    data = PartSerializer(filter_samples(matches, request), many=True).data
    return Response({'count': len(data), 'multiple': len(data) > 1, 'results': data})

@api_view(['GET'])
def part_detail(request, pk):
    try:
        part = filter_samples(Part.objects.select_related('customer', 'destination', 'box', 'sheet_color'), request).get(pk=pk)
    except Part.DoesNotExist:
        return Response({'detail': 'No encontrada.'}, status=404)
    return Response(PartSerializer(part).data)

@api_view(['GET'])
def catalogs(request):
    return Response({key: list(model.objects.filter(active=True).values('id', 'name')) for key, model in [('customers', Customer), ('destinations', Destination), ('boxes', Box), ('sheet_colors', SheetColor)]})

@api_view(['GET'])
def changes(request):
    raw_cursor = request.query_params.get('cursor')
    if raw_cursor:
        try:
            payload = signing.loads(raw_cursor, salt='catalog-changes')
            if isinstance(payload, dict):
                if payload.get('integration') != request.auth.pk:
                    raise ValueError
                if payload.get('policy_version') != request.auth.policy_version:
                    return resync_required(request)
                last_id = payload['sequence']
            else:
                # Existing consumers keep their cursors until their policy first changes.
                if request.auth.policy_version != 1:
                    return resync_required(request)
                last_id = payload
            if type(last_id) is not int or last_id < 0:
                raise ValueError
        except (signing.BadSignature, ValueError, TypeError, KeyError):
            return Response({'detail': 'Cursor inválido.'}, status=400)
    else:
        last_id = 0
    try:
        limit = min(max(int(request.query_params.get('limit', 100)), 1), 200)
    except ValueError:
        return Response({'detail': 'Límite inválido.'}, status=400)
    selected = list(Change.objects.filter(pk__gt=last_id).select_related('part', 'part__customer', 'part__destination', 'part__box', 'part__sheet_color').order_by('pk')[:limit + 1])
    page = selected[:limit]
    cursor_id = page[-1].pk if page else last_id
    return Response({'results': [change_event(change, request.auth) for change in page], 'next_cursor': changes_cursor(request, cursor_id), 'has_more': len(selected) > limit})

@api_view(['GET'])
def bootstrap(request):
    # Replay from genesis after the paged snapshot: this closes any gaps from concurrent writes.
    return Response({'parts_url': request.build_absolute_uri(f'/api/v1/parts/?policy_version={request.auth.policy_version}'), 'changes_cursor': changes_cursor(request, 0), 'include_samples': request.auth.include_samples, 'policy_version': request.auth.policy_version, 'procedure': 'Replace the local catalog from parts, replay changes, and remove records when excluded is true. Restart bootstrap on HTTP 409 resync_required.'})
