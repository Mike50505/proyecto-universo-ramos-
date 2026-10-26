from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0007_integration_sample_policy")]

    operations = [
        migrations.AddField(
            model_name="part",
            name="weight_unit",
            field=models.CharField(
                blank=True,
                choices=[("kg", "Kilogramos (kg)"), ("g", "Gramos (g)")],
                default="",
                max_length=2,
            ),
        ),
    ]
