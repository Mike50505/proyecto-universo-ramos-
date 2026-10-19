from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0005_part_is_sample")]

    operations = [
        migrations.AddField(
            model_name="importjob",
            name="sample_overrides",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
