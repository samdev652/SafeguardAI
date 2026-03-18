from django.db import migrations, models
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='HazardObservation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(choices=[('kmd', 'KMD'), ('noaa', 'NOAA')], max_length=20)),
                ('ward_name', models.CharField(max_length=120)),
                ('village_name', models.CharField(blank=True, max_length=120)),
                ('hazard_type', models.CharField(max_length=40)),
                ('severity_index', models.FloatField()),
                ('raw_payload', models.JSONField(default=dict)),
                ('location', django.contrib.gis.db.models.fields.PointField(geography=True, srid=4326)),
                ('observed_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-observed_at']},
        ),
        migrations.CreateModel(
            name='RiskAssessment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ward_name', models.CharField(max_length=120)),
                ('village_name', models.CharField(blank=True, max_length=120)),
                ('hazard_type', models.CharField(max_length=40)),
                ('risk_level', models.CharField(choices=[('safe', 'Safe'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')], max_length=20)),
                ('risk_score', models.FloatField()),
                ('guidance_en', models.TextField()),
                ('guidance_sw', models.TextField()),
                ('summary', models.TextField()),
                ('location', django.contrib.gis.db.models.fields.PointField(geography=True, srid=4326)),
                ('issued_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-issued_at']},
        ),
        migrations.AddIndex(
            model_name='hazardobservation',
            index=models.Index(fields=['ward_name', 'hazard_type'], name='hazards_haz_ward_na_9a9f20_idx'),
        ),
        migrations.AddIndex(
            model_name='riskassessment',
            index=models.Index(fields=['ward_name', 'risk_level', 'hazard_type'], name='hazards_ris_ward_na_44efff_idx'),
        ),
    ]
