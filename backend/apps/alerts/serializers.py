from rest_framework import serializers
from .models import Alert, IncidentReport, RescueRequest
from apps.hazards.models import WardBoundary


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = '__all__'


class RescueRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RescueRequest
        fields = '__all__'
        read_only_fields = ['status', 'dispatched_at']


class CountyAlertHistorySerializer(serializers.ModelSerializer):
    county_name = serializers.SerializerMethodField()
    ward_name = serializers.CharField(source='risk_assessment.ward_name', read_only=True)
    hazard_type = serializers.CharField(source='risk_assessment.hazard_type', read_only=True)
    risk_level = serializers.CharField(source='risk_assessment.risk_level', read_only=True)

    class Meta:
        model = Alert
        fields = [
            'id',
            'county_name',
            'ward_name',
            'hazard_type',
            'risk_level',
            'channel',
            'status',
            'message',
            'created_at',
            'sent_at',
        ]

    def get_county_name(self, obj):
        ward = WardBoundary.objects.filter(ward_name__iexact=obj.citizen.ward_name).only('county_name').first()
        return ward.county_name if ward else obj.citizen.ward_name


class IncidentReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncidentReport
        fields = [
            'id',
            'county_name',
            'ward_name',
            'location_name',
            'latitude',
            'longitude',
            'photo_url',
            'description',
            'status',
            'internal_notes',
            'created_at',
            'updated_at',
        ]
