from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('citizens', '0001_initial'),
        ('hazards', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel', models.CharField(choices=[('sms', 'SMS'), ('whatsapp', 'WhatsApp'), ('push', 'Push Notification')], max_length=20)),
                ('message', models.TextField()),
                ('status', models.CharField(default='pending', max_length=20)),
                ('provider_response', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('citizen', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alerts', to='citizens.citizenprofile')),
                ('risk_assessment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alerts', to='hazards.riskassessment')),
            ],
        ),
        migrations.CreateModel(
            name='RescueRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('dispatched_at', models.DateTimeField(blank=True, null=True)),
                ('citizen', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rescue_requests', to='citizens.citizenprofile')),
                ('risk_assessment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='hazards.riskassessment')),
            ],
        ),
    ]
