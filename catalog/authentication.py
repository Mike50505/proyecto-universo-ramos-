import hashlib
import hmac

from rest_framework import authentication, exceptions

from .models import Integration


class IntegrationPrincipal:
    is_authenticated = True
    is_active = True

    def __init__(self, integration):
        self.integration = integration


class IntegrationAuthentication(authentication.BaseAuthentication):
    def authenticate_header(self, request):
        return 'Bearer'

    def authenticate(self, request):
        header = request.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            raise exceptions.AuthenticationFailed('Se requiere una credencial de integración.')
        token = header[7:]
        parts = token.split('_', 2)
        if len(parts) != 3 or parts[0] != 'ur':
            raise exceptions.AuthenticationFailed('Credencial inválida.')
        integration = Integration.objects.filter(key_prefix=parts[1], active=True).first()
        digest = hashlib.sha256(token.encode()).hexdigest()
        if integration is None or not hmac.compare_digest(integration.key_hash, digest):
            raise exceptions.AuthenticationFailed('Credencial inválida o revocada.')
        return IntegrationPrincipal(integration), integration
