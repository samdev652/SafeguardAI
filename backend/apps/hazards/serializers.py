from rest_framework import serializers
from .models import HazardObservation, RiskAssessment, WardBoundary


class RiskAssessmentSerializer(serializers.ModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    county_name = serializers.SerializerMethodField()

    class Meta:
        model = RiskAssessment
        fields = [
            'id', 'ward_name', 'county_name', 'village_name', 'hazard_type', 'risk_level',
            'risk_score', 'guidance_en', 'guidance_sw', 'summary', 'issued_at',
            'latitude', 'longitude'
        ]

    def get_latitude(self, obj):
        return obj.location.y

    def get_longitude(self, obj):
        return obj.location.x

    def get_county_name(self, obj):
        ward = WardBoundary.objects.filter(ward_name__iexact=obj.ward_name).only('county_name').first()
        return ward.county_name if ward else None


class HazardObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = HazardObservation
        fields = '__all__'


class WardBoundarySerializer(serializers.ModelSerializer):
    class Meta:
        model = WardBoundary
        fields = ['id', 'ward_name', 'county_name', 'geometry', 'metadata', 'created_at']
