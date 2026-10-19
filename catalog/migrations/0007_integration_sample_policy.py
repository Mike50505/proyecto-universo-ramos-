from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0006_importjob_sample_overrides")]

    operations = [
        migrations.AddField(model_name="integration", name="include_samples", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="integration", name="policy_version", field=models.PositiveIntegerField(default=1)),
    ]
