from django.contrib.gis.db import models


class RescueUnit(models.Model):
    TYPE_FIRE = 'fire_station'
    TYPE_HOSPITAL = 'hospital'
    TYPE_POLICE = 'police_post'
    TYPE_REDCROSS = 'red_cross'
    UNIT_TYPES = [
        (TYPE_FIRE, 'Fire Station'),
        (TYPE_HOSPITAL, 'Hospital'),
        (TYPE_POLICE, 'Police Post'),
        (TYPE_REDCROSS, 'Red Cross'),
    ]

    name = models.CharField(max_length=180)
    unit_type = models.CharField(max_length=30, choices=UNIT_TYPES)
    phone_number = models.CharField(max_length=20)
    county = models.CharField(max_length=120)
    ward_name = models.CharField(max_length=120)
    location = models.PointField(geography=True, srid=4326)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=['unit_type', 'ward_name'])]

    def __str__(self) -> str:
        return f'{self.name} ({self.unit_type})'
