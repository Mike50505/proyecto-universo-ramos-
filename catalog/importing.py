import csv
import io
import unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from openpyxl import Workbook, load_workbook

from .models import Box, Customer, Destination, ImportJob, Part, SheetColor, normalize_code
from .services import create_part, lock_change_stream, update_part

FIELDS = ['customer', 'destination', 'part_number', 'diameter', 'wall', 'weight', 'box', 'std', 'sheet_color', 'reference_customer', 'reference_plant']
LABELS = {'customer': 'CLIENTE', 'destination': 'DESTINO', 'part_number': 'NÚMERO DE PARTE', 'diameter': 'DIÁMETRO', 'wall': 'PARED', 'weight': 'PESO', 'box': 'CAJA', 'std': 'STD.', 'sheet_color': 'HOJA COLOR', 'reference_customer': 'CLIENTE (segunda columna)', 'reference_plant': 'PLANTA'}
LABELS['wall_note'] = 'PARED (texto original)'
CATALOGS = {'customer': Customer, 'destination': Destination, 'box': Box, 'sheet_color': SheetColor}

def fold(value):
    text = ''.join(ch for ch in unicodedata.normalize('NFKD', str(value or '').upper()) if not unicodedata.combining(ch))
    return text.strip().replace('.', '').replace('�', 'U')

def workbook(job):
    job.file.open('rb')
    try:
        return load_workbook(io.BytesIO(job.file.read()), read_only=True, data_only=False, keep_links=False)
    finally:
        job.file.close()

def headers(job, sheet):
    wb = workbook(job)
    if sheet not in wb.sheetnames:
        raise ValidationError('La hoja seleccionada no existe.')
    ws = wb[sheet]
    for row_number, row in enumerate(ws.iter_rows(min_row=1, max_row=min(ws.max_row or 20, 20)), 1):
        names = [str(cell.value or '').strip() for cell in row]
        if any(fold(x) in ('NUMERO DE PARTE', 'NUMERO PARTE') for x in names):
            return row_number, names
    raise ValidationError('No se encontró una fila de encabezados en las primeras 20 filas.')

def auto_mapping(names):
    mapping = {}
    clients = [i + 1 for i, name in enumerate(names) if fold(name) == 'CLIENTE']
    if len(clients) in (1, 2):
        mapping['customer'] = clients[0]
    if len(clients) == 2:
        mapping['reference_customer'] = clients[1]
    for field in FIELDS:
        if field in ('customer', 'reference_customer'):
            continue
        matches = [i + 1 for i, name in enumerate(names) if fold(name) == fold(LABELS[field])]
        if len(matches) == 1:
            mapping[field] = matches[0]
    return mapping

def _value(cell):
    if cell.data_type == 'f':
        raise ValidationError('La fila contiene una fórmula; sustituya por un valor literal.')
    return '' if cell.value is None else str(cell.value).strip()

def parse_rows(job):
    wb = workbook(job)
    header_row, _ = headers(job, job.sheet)
    try:
        mapping = {key: int(value) for key, value in job.mapping.items() if key in FIELDS and value}
    except (TypeError, ValueError):
        raise ValidationError('El mapeo de columnas no es válido.')
    if not mapping.get('customer') or not mapping.get('part_number'):
        raise ValidationError('Mapee Cliente y Número de parte.')
    if len(set(mapping.values())) != len(mapping) or any(pos < 1 or pos > 100 for pos in mapping.values()):
        raise ValidationError('Cada campo debe corresponder a una columna distinta y válida.')
    ws = wb[job.sheet]
    if (ws.max_column or 0) > 100 or (ws.max_row or 0) > 10050:
        raise ValidationError('El archivo supera 100 columnas o 10,000 filas de datos.')
    result = []
    for row_number, cells in enumerate(ws.iter_rows(min_row=header_row + 1), header_row + 1):
        if not any(cell.value is not None for cell in cells):
            continue
        raw = {}
        for field in FIELDS:
            if field not in mapping:
                continue
            pos = mapping[field]
            cell = cells[pos - 1] if pos <= len(cells) else None
            try:
                raw[field] = _value(cell) if cell else ''
            except ValidationError as exc:
                raw['__error__'] = '; '.join(exc.messages)
                raw[field] = ''
            if field == 'part_number' and cell and cell.data_type == 'n' and cell.value is not None:
                raw['__error__'] = 'El número de parte es numérico en Excel; convierta la celda a texto para preservar ceros iniciales.'
        result.append((row_number, raw))
        if len(result) > 10000:
            raise ValidationError('El límite es 10,000 filas por archivo.')
    return result

def _validate_field(field, value):
    if field in CATALOGS:
        if len(value) > 150:
            raise ValidationError(f'{LABELS[field]} supera 150 caracteres.')
        return value
    if field in ('wall', 'weight'):
        if not value:
            return None
        try:
            decimal = Decimal(value)
        except InvalidOperation:
            if field == 'wall' and len(value) <= 120:
                return None
            raise ValidationError(f'{LABELS[field]} debe ser decimal.')
        if not decimal.is_finite() or decimal < 0 or (decimal and decimal.adjusted() >= 8) or -decimal.as_tuple().exponent > 6:
            raise ValidationError(f'{LABELS[field]} debe ser un decimal no negativo con hasta 6 decimales.')
        return str(decimal)
    max_length = Part._meta.get_field(field).max_length
    if max_length and len(value) > max_length:
        raise ValidationError(f'{LABELS[field]} supera {max_length} caracteres.')
    return value

def evaluate(job):
    rows = parse_rows(job)
    counts = Counter(normalize_code(raw.get('part_number')) for _, raw in rows if raw.get('part_number'))
    output = []
    for number, raw in rows:
        code = normalize_code(raw.get('part_number'))
        item = {'row': number, 'code': raw.get('part_number', ''), 'raw': {field: raw.get(field, '') for field in FIELDS}, 'status': '', 'reason': '', 'before': {}, 'after': {}, 'catalog_new': [], 'version': None}
        if raw.get('__error__'):
            item.update(status='error', reason=raw['__error__'])
        elif not code or not raw.get('customer'):
            item.update(status='error', reason='Cliente y Número de parte son obligatorios.')
        elif counts[code] > 1:
            item.update(status='duplicate', reason='El código aparece más de una vez en esta hoja; revise las filas antes de importar.')
        else:
            try:
                data = {}
                for field, value in raw.items():
                    if field not in FIELDS:
                        continue
                    clean = _validate_field(field, value)
                    if field in CATALOGS and value:
                        related = CATALOGS[field].objects.filter(name__iexact=value).first()
                        if related and not related.active:
                            raise ValidationError(f'{LABELS[field]} está inactivo: {value}. Revíselo antes de importar.')
                        if not related:
                            item['catalog_new'].append(LABELS[field] + ': ' + value)
                        clean = related.name if related else value
                    data[field] = clean
                    if field == 'wall':
                        data['wall_note'] = value if clean is None and value else ''
                existing = Part.objects.select_related(*CATALOGS.keys()).filter(normalized_number=code).first()
                if existing:
                    item['version'] = existing.version
                    changed, before = {}, {}
                    for field, value in data.items():
                        if not raw.get('wall' if field == 'wall_note' else field) and not job.clear_blanks:
                            continue
                        old = getattr(existing, field)
                        old_value = str(old) if old is not None else None
                        new_value = value if value != '' or field not in CATALOGS else None
                        if field in ('wall', 'weight') and old is not None and new_value is not None and Decimal(new_value) == old:
                            continue
                        if old_value != new_value:
                            before[field] = old_value
                            changed[field] = new_value
                    item['before'], item['after'] = before, changed
                    item['status'] = 'update' if changed else 'unchanged'
                    if changed and job.mode == 'add':
                        item['status'] = 'skipped'
                else:
                    item['after'] = data
                    item['status'] = 'new' if job.mode != 'update' else 'skipped'
            except ValidationError as exc:
                item.update(status='error', reason='; '.join(exc.messages))
        output.append(item)
    return output

def preview(job):
    rows = evaluate(job)
    job.result = {'rows': rows, 'counts': dict(Counter(row['status'] for row in rows))}
    job.status = 'preview'
    job.save(update_fields=['result', 'status'])
    return rows

def materialize(values):
    data = {}
    for field, value in values.items():
        if field in CATALOGS:
            if value:
                related = CATALOGS[field].objects.filter(name__iexact=value).first()
                if related is None:
                    related = CATALOGS[field].objects.create(name=value)
                if not related.active:
                    raise ValidationError(f'{LABELS[field]} está inactivo: {value}.')
                data[field] = related
            else:
                data[field] = None
        elif field in ('wall', 'weight'):
            data[field] = Decimal(value) if value is not None else None
        else:
            data[field] = value
    return data

@transaction.atomic
def confirm(job_id, actor):
    lock_change_stream()
    job = ImportJob.objects.select_for_update().get(pk=job_id)
    if job.status == 'confirmed':
        return job
    if job.status != 'preview' or job.actor_id != actor.pk:
        raise ValidationError('La vista previa no está disponible para confirmar.')
    old = job.result['rows']
    new = evaluate(job)
    # Earlier previews may have recorded newly created catalogs in JSON key order.
    # Their order has no meaning, but PostgreSQL can reorder mapping keys.
    comparable = lambda rows: [{**row, 'catalog_new': sorted(row['catalog_new'])} for row in rows]
    if comparable(old) != comparable(new):
        raise ValidationError('El catálogo o el archivo cambió después de la vista previa. Genere otra vista previa.')
    if any(row['status'] in ('duplicate', 'error') for row in new):
        raise ValidationError('Resuelva los duplicados y errores antes de confirmar.')
    for row in new:
        if row['status'] == 'new':
            create_part(materialize(row['after']), actor, 'import')
        elif row['status'] == 'update':
            part = Part.objects.get(normalized_number=normalize_code(row['code']))
            update_part(part.pk, materialize(row['after']), row['version'], actor, 'import')
    job.status = 'confirmed'
    job.confirmed_at = timezone.now()
    job.result = {'rows': new, 'counts': dict(Counter(row['status'] for row in new))}
    job.save(update_fields=['status', 'confirmed_at', 'result'])
    return job

def template_bytes():
    wb = Workbook()
    ws = wb.active
    ws.title = 'Piezas'
    ws.append([LABELS[field] if field != 'reference_customer' else 'CLIENTE' for field in FIELDS])
    ws.freeze_panes = 'A2'
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = max(16, len(str(col[0].value)) + 3)
    stream = io.BytesIO()
    wb.save(stream)
    return stream.getvalue()

def error_csv(job):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(['Fila', 'Número de parte', 'Estado', 'Motivo'])
    for row in job.result.get('rows', []):
        if row['status'] in ('duplicate', 'error'):
            writer.writerow([row['row'], row['code'], row['status'], row['reason']])
    return '\ufeff' + stream.getvalue()
