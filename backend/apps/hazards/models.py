from django.contrib.gis.db import models


class HazardObservation(models.Model):
    SOURCE_KMD = 'kmd'
    SOURCE_NOAA = 'noaa'
    SOURCE_OPEN_METEO = 'open_meteo'
    SOURCE_CHOICES = [
        (SOURCE_KMD, 'KMD'),
        (SOURCE_NOAA, 'NOAA'),
        (SOURCE_OPEN_METEO, 'Open-Meteo'),
    ]

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    ward_name = models.CharField(max_length=120)
    village_name = models.CharField(max_length=120, blank=True)
    hazard_type = models.CharField(max_length=40)
    severity_index = models.FloatField()
    raw_payload = models.JSONField(default=dict)
    location = models.PointField(geography=True, srid=4326)
    observed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-observed_at']
        indexes = [models.Index(fields=['ward_name', 'hazard_type'])]


class RiskAssessment(models.Model):
    RISK_SAFE = 'safe'
    RISK_MEDIUM = 'medium'
    RISK_HIGH = 'high'
    RISK_CRITICAL = 'critical'
    RISK_CHOICES = [
        (RISK_SAFE, 'Safe'),
        (RISK_MEDIUM, 'Medium'),
        (RISK_HIGH, 'High'),
        (RISK_CRITICAL, 'Critical'),
    ]

    ward_name = models.CharField(max_length=120)
    village_name = models.CharField(max_length=120, blank=True)
    hazard_type = models.CharField(max_length=40)
    risk_level = models.CharField(max_length=20, choices=RISK_CHOICES)
    risk_score = models.FloatField()
    guidance_en = models.TextField()
    guidance_sw = models.TextField()
    summary = models.TextField()
    location = models.PointField(geography=True, srid=4326)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issued_at']
        indexes = [models.Index(fields=['ward_name', 'risk_level', 'hazard_type'])]


class WardBoundary(models.Model):
    ward_name = models.CharField(max_length=120, unique=True)
    county_name = models.CharField(max_length=120)
    geometry = models.MultiPolygonField(geography=True, srid=4326)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['county_name', 'ward_name'])]

    def __str__(self) -> str:
        return f'{self.ward_name}, {self.county_name}'
