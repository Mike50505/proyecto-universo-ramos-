from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('catalog', '0003_box_box_name_ci_unique_and_more')]
    operations = [
        migrations.AddField(model_name='part', name='reference_customer', field=models.CharField(blank=True, default='', max_length=150), preserve_default=False),
        migrations.AddField(model_name='part', name='reference_plant', field=models.CharField(blank=True, default='', max_length=150), preserve_default=False),
        migrations.AddField(model_name='part', name='wall_note', field=models.CharField(blank=True, default='', max_length=120), preserve_default=False),
    ]
