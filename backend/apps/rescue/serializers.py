from rest_framework import serializers
from apps.alerts.models import RescueRequest
from .models import RescueUnit


class RescueUnitSerializer(serializers.ModelSerializer):
    distance_m = serializers.FloatField(read_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = RescueUnit
        fields = [
            'id', 'name', 'unit_type', 'phone_number', 'county', 'ward_name',
            'distance_m', 'latitude', 'longitude'
        ]

    def get_latitude(self, obj):
        return obj.location.y

    def get_longitude(self, obj):
        return obj.location.x


class RescueDispatchQueueSerializer(serializers.ModelSerializer):
    citizen_name = serializers.CharField(source='citizen.full_name', read_only=True)
    citizen_phone_number = serializers.CharField(source='citizen.phone_number', read_only=True)
    ward_name = serializers.CharField(source='citizen.ward_name', read_only=True)
    village_name = serializers.CharField(source='citizen.village_name', read_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = RescueRequest
        fields = [
            'id',
            'status',
            'description',
            'created_at',
            'dispatched_at',
            'citizen_name',
            'citizen_phone_number',
            'ward_name',
            'village_name',
            'latitude',
            'longitude',
        ]

    def get_latitude(self, obj):
        return obj.citizen.location.y

    def get_longitude(self, obj):
        return obj.citizen.location.x
