import logging
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from .models import Change, Part

logger = logging.getLogger('catalog')

def lock_change_stream():
    # Serializes writers before their change IDs are allocated. A cursor never passes an uncommitted lower ID.
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(824703169)")

@transaction.atomic
def create_part(data, actor, source="form"):
    lock_change_stream()
    part = Part(**data, created_by=actor, updated_by=actor)
    part.full_clean()
    part.save()
    Change.objects.create(part=part, actor=actor, operation="create", source=source, after=part.snapshot())
    logger.info('part_created uuid=%s source=%s actor_id=%s', part.pk, source, actor.pk)
    return part

@transaction.atomic
def update_part(part_id, data, expected_version, actor, source="form"):
    lock_change_stream()
    part = Part.objects.select_for_update().get(pk=part_id)
    try:
        submitted_version = int(expected_version)
    except (TypeError, ValueError):
        raise ValidationError("Falta una versión válida. Recargue la pieza antes de guardar.")
    if part.version != submitted_version:
        raise ValidationError("La pieza cambió desde que abrió el formulario. Revise la versión actual.")
    before = part.snapshot()
    for key, value in data.items():
        setattr(part, key, value)
    part.version += 1
    part.updated_by = actor
    part.full_clean()
    part.save()
    operation = "reactivate" if not before["active"] and part.active else "deactivate" if before["active"] and not part.active else "update"
    Change.objects.create(part=part, actor=actor, operation=operation, source=source, before=before, after=part.snapshot())
    logger.info('part_changed uuid=%s operation=%s source=%s actor_id=%s', part.pk, operation, source, actor.pk)
    return part
