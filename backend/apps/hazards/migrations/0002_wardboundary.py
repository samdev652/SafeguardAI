from django.db import migrations, models
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):
    dependencies = [
        ('hazards', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WardBoundary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ward_name', models.CharField(max_length=120, unique=True)),
                ('county_name', models.CharField(max_length=120)),
                ('geometry', django.contrib.gis.db.models.fields.MultiPolygonField(geography=True, srid=4326)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddIndex(
            model_name='wardboundary',
            index=models.Index(fields=['county_name', 'ward_name'], name='hazards_wa_county__f9d958_idx'),
        ),
    ]
