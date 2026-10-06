from .permissions import is_admin, can_edit

def navigation(request):
    return {"can_edit": can_edit(request.user), "is_catalog_admin": is_admin(request.user)}
