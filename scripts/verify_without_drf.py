"""Local model/import checks where DRF and PostgreSQL cannot be installed."""
import os
import sys
import types
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'universo.settings')
os.environ['DJANGO_DEBUG'] = '1'
from django.conf import settings
settings.INSTALLED_APPS.remove('rest_framework')
settings.MIDDLEWARE.remove('whitenoise.middleware.WhiteNoiseMiddleware')
settings.STORAGES['staticfiles'] = {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}
settings.DATABASES['default'] = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}
temporary_media = TemporaryDirectory()
settings.MEDIA_ROOT = temporary_media.name
import django
django.setup()
from django.urls import include, path
from django.contrib.auth import views as auth_views
module = types.ModuleType('verify_urls')
module.urlpatterns = [path('logout/', auth_views.LogoutView.as_view(), name='logout'), path('login/', auth_views.LoginView.as_view(), name='login'), path('', include('catalog.urls'))]
sys.modules['verify_urls'] = module
settings.ROOT_URLCONF = 'verify_urls'
from django.core.management import call_command
call_command('makemigrations', 'catalog', check=True, dry_run=True, verbosity=0)
call_command('test',
    'catalog.tests.CatalogTests.test_create_duplicate_and_web_permissions',
    'catalog.tests.CatalogTests.test_optimistic_edit_and_toggle',
    'catalog.tests.CatalogTests.test_preview_confirm_repeat_and_conflict',
    'catalog.tests.CatalogTests.test_import_stale_preview_rolls_back',
    'catalog.tests.CatalogTests.test_numeric_code_and_formula_are_row_errors',
    'catalog.tests.CatalogTests.test_reference_header_ambiguity',
    'catalog.tests.CatalogTests.test_main_pages_render_and_actions_exist',
    'catalog.tests.CatalogTests.test_bootstrap_admin_once',
    verbosity=2)
temporary_media.cleanup()
