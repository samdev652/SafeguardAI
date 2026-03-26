from django.db import IntegrityError, transaction
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from rest_framework import serializers
from .models import CitizenProfile


class CitizenRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, min_length=8)
    latitude = serializers.FloatField(write_only=True)
    longitude = serializers.FloatField(write_only=True)
    role = serializers.ChoiceField(choices=CitizenProfile.ROLE_CHOICES, required=False)

    class Meta:
        model = CitizenProfile
        fields = [
            'full_name', 'phone_number', 'ward_name', 'village_name', 'preferred_language',
            'channels', 'email', 'password', 'latitude', 'longitude', 'role'
        ]

    def validate_email(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate_channels(self, value):
        if not value:
            raise serializers.ValidationError('Select at least one alert channel.')
        return value

    def validate_phone_number(self, value):
        if CitizenProfile.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError('An account with this phone number already exists.')
        return value

    def create(self, validated_data):
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        latitude = validated_data.pop('latitude')
        longitude = validated_data.pop('longitude')

        try:
            with transaction.atomic():
                user = User.objects.create_user(username=email, email=email, password=password)
                profile = CitizenProfile.objects.create(
                    user=user,
                    location=Point(longitude, latitude, srid=4326),
                    **validated_data,
                )
                return profile
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {'detail': 'Account could not be created. Email or phone number may already exist.'}
            ) from exc


class CitizenProfileSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(required=False)
    longitude = serializers.FloatField(required=False)

    class Meta:
        model = CitizenProfile
        fields = [
            'id', 'full_name', 'phone_number', 'ward_name', 'village_name',
            'preferred_language', 'channels', 'role', 'latitude', 'longitude', 'created_at'
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['latitude'] = instance.location.y
        ret['longitude'] = instance.location.x
        return ret

    def update(self, instance, validated_data):
        lat = validated_data.pop('latitude', None)
        lon = validated_data.pop('longitude', None)
        if lat is not None and lon is not None:
            instance.location = Point(lon, lat, srid=4326)
        return super().update(instance, validated_data)
