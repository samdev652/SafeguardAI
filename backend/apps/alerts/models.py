from django.db import models


class Alert(models.Model):
    CHANNEL_SMS = 'sms'
    CHANNEL_WHATSAPP = 'whatsapp'
    CHANNEL_PUSH = 'push'
    CHANNEL_CHOICES = [
        (CHANNEL_SMS, 'SMS'),
        (CHANNEL_WHATSAPP, 'WhatsApp'),
        (CHANNEL_PUSH, 'Push Notification'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'

    risk_assessment = models.ForeignKey('hazards.RiskAssessment', on_delete=models.CASCADE, related_name='alerts')
    citizen = models.ForeignKey('citizens.CitizenProfile', on_delete=models.CASCADE, related_name='alerts')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    message = models.TextField()
    status = models.CharField(max_length=20, default=STATUS_PENDING)
    provider_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['status', 'channel'])]


class RescueRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_DISPATCHED = 'dispatched'
    STATUS_RESOLVED = 'resolved'

    citizen = models.ForeignKey('citizens.CitizenProfile', on_delete=models.CASCADE, related_name='rescue_requests')
    risk_assessment = models.ForeignKey('hazards.RiskAssessment', on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)


class IncidentReport(models.Model):
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    county_name = models.CharField(max_length=120)
    ward_name = models.CharField(max_length=120)
    location_name = models.CharField(max_length=160, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    photo_url = models.URLField(blank=True)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['county_name', 'status', 'created_at'])]
