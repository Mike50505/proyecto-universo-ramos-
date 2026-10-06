from django import template
register = template.Library()

@register.filter
def get_item(value, key):
    return value.get(key) if isinstance(value, dict) else None

@register.filter
def import_status(value):
    return {'new': 'Nueva', 'update': 'Con cambios', 'unchanged': 'Sin cambios', 'duplicate': 'Duplicado', 'error': 'Error', 'skipped': 'Omitida'}.get(value, value)

@register.filter
def import_job_status(value):
    return {'uploaded': 'Pendiente', 'preview': 'Vista previa', 'confirmed': 'Confirmada'}.get(value, value)

@register.filter
def import_label(value):
    from catalog.importing import LABELS
    return LABELS.get(value, value)
