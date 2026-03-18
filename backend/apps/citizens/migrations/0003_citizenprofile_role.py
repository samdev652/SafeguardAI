from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('citizens', '0002_rename_citizens_ci_ward_na_d42d2e_idx_citizens_ci_ward_na_b46ec7_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='citizenprofile',
            name='role',
            field=models.CharField(
                choices=[
                    ('citizen', 'Citizen'),
                    ('county_official', 'County Official'),
                    ('rescue_team', 'Rescue Team'),
                ],
                default='citizen',
                max_length=30,
            ),
        ),
    ]
