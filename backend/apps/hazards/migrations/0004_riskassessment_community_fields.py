from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hazards', '0003_rename_hazards_haz_ward_na_9a9f20_idx_hazards_haz_ward_na_f40593_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='riskassessment',
            name='community_all_clear_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='riskassessment',
            name='community_status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('verified', 'Verified'), ('all_clear', 'All Clear')],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='riskassessment',
            name='community_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
