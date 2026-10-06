from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Create application role groups"

    def handle(self, *args, **kwargs):
        for name in ("Administrador", "Editor", "Consulta"):
            Group.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS("Roles listos"))
