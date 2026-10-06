from django.core.exceptions import PermissionDenied

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name="Administrador").exists())

def can_edit(user):
    return is_admin(user) or (user.is_authenticated and user.groups.filter(name="Editor").exists())

def can_read(user):
    return can_edit(user) or (user.is_authenticated and user.groups.filter(name="Consulta").exists())

def require_read(user):
    if not can_read(user):
        raise PermissionDenied

def require_edit(user):
    if not can_edit(user):
        raise PermissionDenied

def require_admin(user):
    if not is_admin(user):
        raise PermissionDenied
