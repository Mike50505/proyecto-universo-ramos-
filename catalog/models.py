import hashlib
import secrets
import unicodedata
import uuid
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

def normalize_code(value):
    """Unicode NFKC, trim edges, uppercase. Internal spaces and punctuation remain meaningful."""
    return unicodedata.normalize("NFKC", value or "").strip().upper()

class NamedValue(models.Model):
    name = models.CharField(max_length=150, unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return self.name

class Customer(NamedValue):
    class Meta(NamedValue.Meta):
        constraints = [models.UniqueConstraint(Lower('name'), name='customer_name_ci_unique')]

class Destination(NamedValue):
    class Meta(NamedValue.Meta):
        constraints = [models.UniqueConstraint(Lower('name'), name='destination_name_ci_unique')]

class Box(NamedValue):
    class Meta(NamedValue.Meta):
        constraints = [models.UniqueConstraint(Lower('name'), name='box_name_ci_unique')]

class SheetColor(NamedValue):
    class Meta(NamedValue.Meta):
        constraints = [models.UniqueConstraint(Lower('name'), name='sheetcolor_name_ci_unique')]

class Part(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    destination = models.ForeignKey(Destination, on_delete=models.PROTECT, blank=True, null=True)
    part_number = models.CharField(max_length=120)
    normalized_number = models.CharField(max_length=120, unique=True, editable=False)
    diameter = models.CharField(max_length=120, blank=True)
    wall = models.DecimalField(max_digits=14, decimal_places=6, blank=True, null=True)
    wall_note = models.CharField(max_length=120, blank=True)
    weight = models.DecimalField(max_digits=14, decimal_places=6, blank=True, null=True)
    box = models.ForeignKey(Box, on_delete=models.PROTECT, blank=True, null=True)
    std = models.CharField(max_length=120, blank=True)
    sheet_color = models.ForeignKey(SheetColor, on_delete=models.PROTECT, blank=True, null=True)
    reference_customer = models.CharField(max_length=150, blank=True)
    reference_plant = models.CharField(max_length=150, blank=True)
    active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_parts")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="updated_parts")

    class Meta:
        ordering = ["part_number"]
        indexes = [models.Index(fields=["customer", "active"]), models.Index(fields=["diameter"]), models.Index(fields=["updated_at"])]

    def clean(self):
        self.normalized_number = normalize_code(self.part_number)
        if not self.normalized_number:
            raise ValidationError({"part_number": "El número de parte es obligatorio."})
        if len(self.normalized_number) > 120:
            raise ValidationError({"part_number": "El número de parte es demasiado largo."})
        if Part.objects.exclude(pk=self.pk).filter(normalized_number=self.normalized_number).exists():
            raise ValidationError({"part_number": "Ya existe un número de parte con este código."})
        for field in ("wall", "weight"):
            if getattr(self, field) is not None and getattr(self, field) < 0:
                raise ValidationError({field: "No puede ser negativo."})

    def save(self, *args, **kwargs):
        self.normalized_number = normalize_code(self.part_number)
        super().save(*args, **kwargs)

    def snapshot(self):
        data = {}
        for field in ("id", "customer_id", "destination_id", "part_number", "diameter", "wall", "wall_note", "weight", "box_id", "std", "sheet_color_id", "reference_customer", "reference_plant", "active", "version"):
            value = getattr(self, field)
            data[field] = str(value) if isinstance(value, (uuid.UUID, Decimal)) else value
        data["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        return data

    def __str__(self):
        return self.part_number

class Change(models.Model):
    part = models.ForeignKey(Part, on_delete=models.PROTECT, related_name="changes")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    at = models.DateTimeField(auto_now_add=True)
    operation = models.CharField(max_length=16, choices=[(x, x) for x in ("create", "update", "deactivate", "reactivate")])
    source = models.CharField(max_length=16, choices=[("form", "Formulario"), ("import", "Importación")])
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField()

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["part", "id"])]

class ImportJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to="imports/%Y/%m/")
    sheet = models.CharField(max_length=120, blank=True)
    mapping = models.JSONField(default=dict)
    mode = models.CharField(max_length=16, choices=[("add", "Solo agregar nuevas"), ("update", "Actualizar existentes"), ("both", "Agregar y actualizar")], default="both")
    clear_blanks = models.BooleanField(default=False)
    status = models.CharField(max_length=16, default="uploaded")
    result = models.JSONField(default=dict)

class Integration(models.Model):
    name = models.CharField(max_length=120, unique=True)
    key_prefix = models.CharField(max_length=16, unique=True)
    key_hash = models.CharField(max_length=64)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def create_key(cls, name):
        prefix = secrets.token_hex(6)
        secret = secrets.token_urlsafe(32)
        token = f"ur_{prefix}_{secret}"
        integration = cls.objects.create(name=name, key_prefix=prefix, key_hash=hashlib.sha256(token.encode()).hexdigest())
        return integration, token
