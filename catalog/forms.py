from django import forms
from django.contrib.auth.models import User
from .models import Box, Customer, Destination, Part, SheetColor

class PartForm(forms.ModelForm):
    version = forms.IntegerField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Part
        fields = ["customer", "destination", "part_number", "diameter", "wall", "wall_note", "weight", "box", "std", "sheet_color", "reference_customer", "reference_plant"]
        labels = {"customer": "Cliente", "destination": "Destino", "part_number": "Número de parte", "diameter": "Diámetro", "wall": "Pared", "weight": "Peso", "box": "Caja", "std": "STD.", "sheet_color": "Hoja color"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reference_customer'].label = 'Cliente (segunda columna)'
        self.fields['reference_plant'].label = 'Planta (columna adicional)'
        self.fields['wall_note'].label = 'Pared (texto original, si no es decimal)'
        for name in ("customer", "destination", "box", "sheet_color"):
            self.fields[name].queryset = self.fields[name].queryset.filter(active=True)
        if self.instance and self.instance.pk:
            self.fields["version"].initial = self.instance.version

class NamedForm(forms.Form):
    name = forms.CharField(max_length=150, label="Nombre")

class UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False, help_text="Solo para cuentas nuevas o cambio de contraseña.")
    role = forms.ChoiceField(choices=[("Administrador", "Administrador"), ("Editor", "Editor"), ("Consulta", "Consulta")])

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active"]

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            user.groups.clear()
            from django.contrib.auth.models import Group
            user.groups.add(Group.objects.get(name=self.cleaned_data["role"]))
        return user
