import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create the initial administrator from a temporary password hash"

    @transaction.atomic
    def handle(self, *args, **kwargs):
        password_hash = os.environ.get('BOOTSTRAP_ADMIN_HASH', '')
        if not password_hash:
            self.stdout.write('No hay cuenta inicial pendiente.')
            return
        if not password_hash.startswith('pbkdf2_sha256$'):
            raise CommandError('El hash de la cuenta inicial no es valido.')

        User = get_user_model()
        if User.objects.filter(username='administrator').exists():
            raise CommandError('Ya existe administrator. No se cambio su contrasena.')

        user = User(
            username='administrator',
            password=password_hash,
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        user.full_clean()
        user.save()
        self.stdout.write(self.style.SUCCESS('Cuenta administrator creada.'))
