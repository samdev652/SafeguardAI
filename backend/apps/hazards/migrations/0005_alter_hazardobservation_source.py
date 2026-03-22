from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hazards', '0004_riskassessment_community_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hazardobservation',
            name='source',
            field=models.CharField(
                choices=[('kmd', 'KMD'), ('noaa', 'NOAA'), ('open_meteo', 'Open-Meteo')],
                max_length=20,
            ),
        ),
    ]
