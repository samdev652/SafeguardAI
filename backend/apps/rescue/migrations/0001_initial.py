from django.db import migrations, models
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='RescueUnit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=180)),
                ('unit_type', models.CharField(choices=[('fire_station', 'Fire Station'), ('hospital', 'Hospital'), ('police_post', 'Police Post'), ('red_cross', 'Red Cross')], max_length=30)),
                ('phone_number', models.CharField(max_length=20)),
                ('county', models.CharField(max_length=120)),
                ('ward_name', models.CharField(max_length=120)),
                ('location', django.contrib.gis.db.models.fields.PointField(geography=True, srid=4326)),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.AddIndex(
            model_name='rescueunit',
            index=models.Index(fields=['unit_type', 'ward_name'], name='rescue_resc_unit_ty_b23fc6_idx'),
        ),
    ]
