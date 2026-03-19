from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('citizens', '0003_citizenprofile_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='citizenprofile',
            name='is_available_for_dispatch',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='citizenprofile',
            name='last_location_update',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='citizenprofile',
            name='responder_unit_type',
            field=models.CharField(
                choices=[
                    ('rescue_team', 'Rescue Team'),
                    ('fire_station', 'Fire Station'),
                    ('hospital', 'Hospital'),
                    ('police_post', 'Police Post'),
                    ('red_cross', 'Red Cross'),
                ],
                default='rescue_team',
                max_length=30,
            ),
        ),
    ]
