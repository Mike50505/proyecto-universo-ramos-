from io import BytesIO
from collections import Counter
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.contrib.auth.models import Group, User
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from openpyxl import Workbook
from .importing import confirm, preview, headers, auto_mapping
from .models import Box, Customer, Destination, ImportJob, Integration, Part, Change, SheetColor
from .services import create_part, update_part

class CatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for role in ('Administrador', 'Editor', 'Consulta'):
            Group.objects.create(name=role)
        cls.editor = User.objects.create_user('editor', password='test-password')
        cls.editor.groups.add(Group.objects.get(name='Editor'))
        cls.reader = User.objects.create_user('reader', password='test-password')
        cls.reader.groups.add(Group.objects.get(name='Consulta'))
        cls.customer = Customer.objects.create(name='LENNOX 1')

    def test_create_duplicate_and_web_permissions(self):
        self.client.force_login(self.editor)
        response = self.client.post(reverse('catalog:create'), {'customer': self.customer.pk, 'part_number': '  ab-001  ', 'diameter': 'A - 3/8'})
        self.assertEqual(response.status_code, 302)
        part = Part.objects.get()
        self.assertEqual(part.part_number, 'ab-001')
        self.assertEqual(part.normalized_number, 'AB-001')
        self.assertEqual(Change.objects.count(), 1)
        response = self.client.post(reverse('catalog:create'), {'customer': self.customer.pk, 'part_number': 'AB-001'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Part.objects.count(), 1)
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(reverse('catalog:create')).status_code, 403)
        self.assertEqual(self.client.get(reverse('catalog:detail', args=[part.pk])).status_code, 200)

    def test_optimistic_edit_and_toggle(self):
        part = create_part({'customer': self.customer, 'part_number': 'P-1'}, self.editor)
        update_part(part.pk, {'diameter': 'A - 3/8'}, 1, self.editor)
        with self.assertRaises(ValidationError):
            update_part(part.pk, {'diameter': 'B'}, 1, self.editor)
        update_part(part.pk, {'active': False}, 2, self.editor)
        update_part(part.pk, {'active': True}, 3, self.editor)
        self.assertEqual(list(Change.objects.values_list('operation', flat=True)), ['create', 'update', 'deactivate', 'reactivate'])

    def make_job(self, rows):
        wb = Workbook()
        ws = wb.active
        ws.title = 'Piezas'
        ws.append(['CLIENTE', 'NÚMERO DE PARTE', 'PARED'])
        for row in rows:
            ws.append(row)
        stream = BytesIO()
        wb.save(stream)
        return ImportJob.objects.create(actor=self.editor, filename='parts.xlsx', file=SimpleUploadedFile('parts.xlsx', stream.getvalue()), sheet='Piezas', mapping={'customer': 1, 'part_number': 2, 'wall': 3}, mode='both')

    def test_preview_confirm_repeat_and_conflict(self):
        job = self.make_job([['LENNOX 1', 'P-10', 0], ['LENNOX 1', 'P-11', 0.42]])
        rows = preview(job)
        self.assertEqual([row['status'] for row in rows], ['new', 'new'], rows)
        self.assertEqual(Part.objects.count(), 0)
        confirm(job.pk, self.editor)
        self.assertEqual(Part.objects.count(), 2)
        confirm(job.pk, self.editor)
        self.assertEqual(Part.objects.count(), 2)
        self.assertEqual(Part.objects.get(part_number='P-10').wall, 0)
        duplicate = self.make_job([['LENNOX 1', 'P-10', 1], ['LENNOX 1', 'P-10', 2]])
        self.assertEqual([r['status'] for r in preview(duplicate)], ['duplicate', 'duplicate'])
        with self.assertRaises(ValidationError):
            confirm(duplicate.pk, self.editor)

    def test_mapping_key_order_does_not_invalidate_preview(self):
        wb = Workbook()
        ws = wb.active
        ws.title = 'Piezas'
        ws.append(['CLIENTE', 'DESTINO', 'NÚMERO DE PARTE', 'CAJA'])
        ws.append(['NEW CUSTOMER', 'NEW DESTINATION', 'P-12', 'NEW BOX'])
        stream = BytesIO()
        wb.save(stream)
        job = ImportJob.objects.create(
            actor=self.editor,
            filename='parts.xlsx',
            file=SimpleUploadedFile('parts.xlsx', stream.getvalue()),
            sheet='Piezas',
            mapping={'customer': 1, 'destination': 2, 'part_number': 3, 'box': 4},
            mode='both',
        )
        preview(job)
        job.result['rows'][0]['catalog_new'].reverse()
        job.save(update_fields=['result'])
        job.mapping = dict(reversed(list(job.mapping.items())))
        job.save(update_fields=['mapping'])
        confirm(job.pk, self.editor)
        part = Part.objects.get(part_number='P-12')
        self.assertEqual(part.customer.name, 'NEW CUSTOMER')
        self.assertEqual(part.destination.name, 'NEW DESTINATION')
        self.assertEqual(part.box.name, 'NEW BOX')

    def test_only_owner_can_delete_unconfirmed_import(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            job = self.make_job([['LENNOX 1', 'DELETE-1', 1]])
            preview(job)
            file_name = job.file.name
            url = reverse('catalog:import_delete', args=[job.pk])
            other_editor = User.objects.create_user('other-editor', password='test-password')
            other_editor.groups.add(Group.objects.get(name='Editor'))
            self.client.force_login(other_editor)
            self.assertEqual(self.client.post(url).status_code, 404)
            self.assertTrue(ImportJob.objects.filter(pk=job.pk).exists())

            self.client.force_login(self.editor)
            self.assertEqual(self.client.get(url).status_code, 405)
            self.assertEqual(self.client.post(url).status_code, 302)
            self.assertFalse(ImportJob.objects.filter(pk=job.pk).exists())
            self.assertFalse(job.file.storage.exists(file_name))
            self.assertFalse(Part.objects.filter(part_number='DELETE-1').exists())

            confirmed = self.make_job([['LENNOX 1', 'KEEP-1', 1]])
            preview(confirmed)
            confirm(confirmed.pk, self.editor)
            confirmed_url = reverse('catalog:import_delete', args=[confirmed.pk])
            self.assertEqual(self.client.post(confirmed_url).status_code, 302)
            self.assertTrue(ImportJob.objects.filter(pk=confirmed.pk).exists())
            self.assertTrue(Part.objects.filter(part_number='KEEP-1').exists())

    def test_import_stale_preview_rolls_back(self):
        part = create_part({'customer': self.customer, 'part_number': 'P-20'}, self.editor)
        job = self.make_job([['LENNOX 1', 'P-20', 1], ['LENNOX 1', 'P-21', 2]])
        preview(job)
        update_part(part.pk, {'wall': 3}, 1, self.editor)
        with self.assertRaises(ValidationError):
            confirm(job.pk, self.editor)
        self.assertFalse(Part.objects.filter(part_number='P-21').exists())
        self.assertEqual(Part.objects.get(pk=part.pk).wall, 3)

    def test_numeric_code_and_formula_are_row_errors(self):
        job = self.make_job([['LENNOX 1', 123, 1], ['LENNOX 1', 'SAFE-1', '=1+1']])
        rows = preview(job)
        self.assertEqual([row['status'] for row in rows], ['error', 'error'])
        with self.assertRaises(ValidationError):
            confirm(job.pk, self.editor)
        self.assertEqual(Part.objects.count(), 0)

    def test_reference_header_ambiguity(self):
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / 'UNIVERSO RAMOS.XLSX'
        if not path.exists():
            self.skipTest('Reference workbook is not present')
        job = ImportJob.objects.create(actor=self.editor, filename=path.name, file=SimpleUploadedFile(path.name, path.read_bytes()), sheet='Sheet1')
        _, names = headers(job, 'Sheet1')
        mapping = auto_mapping(names)
        self.assertEqual(mapping['part_number'], 4)
        self.assertEqual(mapping['customer'], 2)
        self.assertEqual(mapping['reference_customer'], 12)
        self.assertEqual(mapping['reference_plant'], 13)
        job.mapping = mapping
        job.save(update_fields=['mapping'])
        rows = preview(job)
        self.assertEqual(len(rows), 302)
        self.assertEqual(Counter(row['status'] for row in rows), {'new': 302}, [(row['row'], row['raw'], row['reason']) for row in rows if row['status'] != 'new'][:20])
        self.assertEqual(Part.objects.count(), 0)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Destination.objects.count(), 0)
        self.assertEqual(Box.objects.count(), 0)
        self.assertEqual(SheetColor.objects.count(), 0)
        self.client.force_login(self.editor)
        preview_page = self.client.get(reverse('catalog:import_preview', args=[job.pk]))
        self.assertContains(preview_page, 'CLIENTE (2)')
        self.assertContains(preview_page, 'PLANTA')
        self.assertNotContains(preview_page, 'CLIENTE no existe')
        confirm(job.pk, self.editor)
        self.assertEqual(Part.objects.count(), 302)
        self.assertEqual(Part.objects.filter(wall_note='NO').count(), 4)
        self.assertTrue(Part.objects.exclude(reference_customer='').exists())
        imported = Part.objects.get(part_number='82-105077-15')
        self.assertIsNone(imported.wall)
        self.assertEqual(imported.wall_note, 'NO')
        excel_page = self.client.get(reverse('catalog:list'), {'view': 'excel', 'q': imported.part_number})
        self.assertContains(excel_page, 'NO')
        self.assertContains(excel_page, imported.reference_customer)
        confirm(job.pk, self.editor)
        self.assertEqual(Part.objects.count(), 302)
        other = ImportJob.objects.create(actor=self.editor, filename=path.name, file=SimpleUploadedFile(path.name, path.read_bytes()), sheet='Sheet1 (2)')
        _, other_names = headers(other, other.sheet)
        other.mapping = auto_mapping(other_names)
        other.save(update_fields=['mapping'])
        other_rows = preview(other)
        self.assertGreaterEqual(Counter(row['status'] for row in other_rows)['duplicate'], 4)
        with self.assertRaises(ValidationError):
            confirm(other.pk, self.editor)

    def test_main_pages_render_and_actions_exist(self):
        self.client.force_login(self.editor)
        part = create_part({'customer': self.customer, 'part_number': 'VIS-1'}, self.editor)
        for url in [reverse('catalog:list'), reverse('catalog:detail', args=[part.pk]), reverse('catalog:create'), reverse('catalog:edit', args=[part.pk]), reverse('catalog:import_upload'), reverse('catalog:imports'), reverse('catalog:related', args=['clientes'])]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
        self.assertContains(self.client.get(reverse('catalog:list')), 'Nuevo número de parte')
        excel_response = self.client.get(reverse('catalog:list'), {'view': 'excel'})
        self.assertContains(excel_response, 'CLIENTE (2)')
        self.assertContains(excel_response, 'PLANTA')
        job = self.make_job([['LENNOX 1', 'VIS-2', 1]])
        self.assertEqual(self.client.get(reverse('catalog:import_map', args=[job.pk])).status_code, 200)
        preview(job)
        self.assertEqual(self.client.get(reverse('catalog:import_preview', args=[job.pk])).status_code, 200)
        self.editor.groups.add(Group.objects.get(name='Administrador'))
        for url in [reverse('catalog:history'), reverse('catalog:users'), reverse('catalog:user_create'), reverse('catalog:integrations')]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertIn(b'VIS-1', self.client.get(reverse('catalog:export')).content)
        self.assertTrue(self.client.get(reverse('catalog:import_template')).content.startswith(b'PK'))

    def test_bootstrap_admin_once(self):
        with patch.dict('os.environ', {'BOOTSTRAP_ADMIN_HASH': make_password('test-only-password')}):
            call_command('bootstrap_admin', verbosity=0)
            admin = User.objects.get(username='administrator')
            self.assertTrue(admin.is_superuser)
            self.assertTrue(admin.check_password('test-only-password'))
            with self.assertRaises(CommandError):
                call_command('bootstrap_admin', verbosity=0)

    def test_api_auth_and_paged_changes(self):
        integration, token = Integration.create_key('MESA')
        self.assertEqual(self.client.get('/api/v1/parts/').status_code, 401)
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        part = create_part({'customer': self.customer, 'part_number': 'A-1'}, self.editor)
        update_part(part.pk, {'active': False}, 1, self.editor)
        first = self.client.get('/api/v1/changes/?limit=1', **headers).json()
        self.assertEqual(first['results'][0]['operation'], 'create')
        self.assertTrue(first['has_more'])
        second = self.client.get('/api/v1/changes/', {'limit': 1, 'cursor': first['next_cursor']}, **headers).json()
        self.assertEqual(second['results'][0]['operation'], 'deactivate')
        self.assertFalse(second['results'][0]['part']['active'])
        repeated = self.client.get('/api/v1/changes/?limit=1', **headers).json()
        self.assertEqual(repeated['results'][0]['sequence'], first['results'][0]['sequence'])
        self.assertEqual(self.client.get('/api/v1/parts/?page_size=1', **headers).json()['count'], 1)
        integration.active = False
        integration.save()
        self.assertEqual(self.client.get('/api/v1/parts/', **headers).status_code, 401)
