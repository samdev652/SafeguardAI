from django.conf import settings
from django.db import migrations, models
import django.contrib.gis.db.models.fields
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CitizenProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=200)),
                ('phone_number', models.CharField(max_length=20, unique=True)),
                ('ward_name', models.CharField(max_length=120)),
                ('village_name', models.CharField(blank=True, max_length=120)),
                ('preferred_language', models.CharField(default='en', max_length=10)),
                ('location', django.contrib.gis.db.models.fields.PointField(geography=True, srid=4326)),
                ('channels', models.JSONField(default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='citizen_profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name='citizenprofile',
            index=models.Index(fields=['ward_name'], name='citizens_ci_ward_na_d42d2e_idx'),
        ),
    ]
