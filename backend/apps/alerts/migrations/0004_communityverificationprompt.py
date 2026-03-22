from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('citizens', '0004_citizenprofile_rescue_presence'),
        ('hazards', '0004_riskassessment_community_fields'),
        ('alerts', '0003_incidentreport'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommunityVerificationPrompt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_number', models.CharField(max_length=20)),
                ('prompt_message', models.TextField()),
                ('vote', models.CharField(blank=True, choices=[('yes', 'Yes'), ('no', 'No')], max_length=8)),
                ('raw_reply', models.TextField(blank=True)),
                ('prompted_at', models.DateTimeField(auto_now_add=True)),
                ('replied_at', models.DateTimeField(blank=True, null=True)),
                ('citizen', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_prompts', to='citizens.citizenprofile')),
                ('risk_assessment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='community_prompts', to='hazards.riskassessment')),
            ],
        ),
        migrations.AddIndex(
            model_name='communityverificationprompt',
            index=models.Index(fields=['phone_number', 'prompted_at'], name='alerts_comm_phone_n_3f4380_idx'),
        ),
        migrations.AddConstraint(
            model_name='communityverificationprompt',
            constraint=models.UniqueConstraint(fields=('risk_assessment', 'citizen'), name='unique_prompt_per_risk_and_citizen'),
        ),
    ]
