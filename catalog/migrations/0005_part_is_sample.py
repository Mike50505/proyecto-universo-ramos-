from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0004_part_reference_columns")]

    operations = [
        migrations.AddField(
            model_name="part",
            name="is_sample",
            field=models.BooleanField(
                default=False,
                verbose_name="Pieza de muestra",
                help_text="Marque si esta pieza es una muestra pendiente de autorización.",
            ),
        ),
    ]
