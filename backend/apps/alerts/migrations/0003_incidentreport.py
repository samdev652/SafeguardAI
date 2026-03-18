from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alerts', '0002_alert_alerts_aler_status_4599b1_idx'),
    ]

    operations = [
        migrations.CreateModel(
            name='IncidentReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('county_name', models.CharField(max_length=120)),
                ('ward_name', models.CharField(max_length=120)),
                ('location_name', models.CharField(blank=True, max_length=160)),
                ('latitude', models.FloatField()),
                ('longitude', models.FloatField()),
                ('photo_url', models.URLField(blank=True)),
                ('description', models.TextField()),
                ('status', models.CharField(choices=[('open', 'Open'), ('in_progress', 'In Progress'), ('resolved', 'Resolved')], default='open', max_length=20)),
                ('internal_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddIndex(
            model_name='incidentreport',
            index=models.Index(fields=['county_name', 'status', 'created_at'], name='alerts_inci_county__4a2a29_idx'),
        ),
    ]
