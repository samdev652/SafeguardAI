from django.contrib.auth.models import User
from django.contrib.gis.db import models


class CitizenProfile(models.Model):
    ROLE_CITIZEN = 'citizen'
    ROLE_COUNTY_OFFICIAL = 'county_official'
    ROLE_RESCUE_TEAM = 'rescue_team'
    ROLE_CHOICES = [
        (ROLE_CITIZEN, 'Citizen'),
        (ROLE_COUNTY_OFFICIAL, 'County Official'),
        (ROLE_RESCUE_TEAM, 'Rescue Team'),
    ]

    CHANNEL_SMS = 'sms'
    CHANNEL_WHATSAPP = 'whatsapp'
    CHANNEL_PUSH = 'push'
    CHANNEL_CHOICES = [
        (CHANNEL_SMS, 'SMS'),
        (CHANNEL_WHATSAPP, 'WhatsApp'),
        (CHANNEL_PUSH, 'Push Notification'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='citizen_profile')
    full_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=20, unique=True)
    ward_name = models.CharField(max_length=120)
    village_name = models.CharField(max_length=120, blank=True)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default=ROLE_CITIZEN)
    preferred_language = models.CharField(max_length=10, default='en')
    location = models.PointField(geography=True, srid=4326)
    channels = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['ward_name'])]

    def __str__(self) -> str:
        return f'{self.full_name} ({self.ward_name})'
