from datetime import timedelta

from rest_framework import serializers
from django.utils import timezone

from apps.alerts.models import RescueRequest


class RescueUnitSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.SerializerMethodField()
    unit_type = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    county = serializers.SerializerMethodField()
    ward_name = serializers.SerializerMethodField()
    distance_m = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    is_live = serializers.SerializerMethodField()
    last_location_update = serializers.SerializerMethodField()

    def get_name(self, obj):
        return getattr(obj, 'name', getattr(obj, 'full_name', 'Unknown responder'))

    def get_unit_type(self, obj):
        return getattr(obj, 'unit_type', getattr(obj, 'responder_unit_type', 'rescue_team'))

    def get_phone_number(self, obj):
        return getattr(obj, 'phone_number', '')

    def get_county(self, obj):
        return getattr(obj, 'county', '')

    def get_ward_name(self, obj):
        return getattr(obj, 'ward_name', '')

    def get_distance_m(self, obj):
        distance = getattr(obj, 'distance_m', None)
        if distance is None:
            return None
        return float(getattr(distance, 'm', distance))

    def get_latitude(self, obj):
        return obj.location.y

    def get_longitude(self, obj):
        return obj.location.x

    def get_is_live(self, obj):
        if hasattr(obj, 'is_available_for_dispatch'):
            last_update = getattr(obj, 'last_location_update', None)
            if not last_update:
                return False
            return bool(obj.is_available_for_dispatch and last_update >= timezone.now() - timedelta(minutes=10))
        return bool(getattr(obj, 'is_active', False))

    def get_last_location_update(self, obj):
        last_update = getattr(obj, 'last_location_update', None)
        return last_update.isoformat() if last_update else None


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
