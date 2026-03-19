from django.contrib.gis.geos import Point
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from apps.alerts.models import RescueRequest
from apps.citizens.models import CitizenProfile
from .models import RescueUnit
from .serializers import RescueDispatchQueueSerializer, RescueUnitSerializer
from .services import find_nearest_rescue_units


def ensure_rescue_team_access(user):
    profile = CitizenProfile.objects.filter(user=user).first()
    if not profile:
        raise PermissionDenied('Citizen profile required.')
    if profile.role != CitizenProfile.ROLE_RESCUE_TEAM:
        raise PermissionDenied('Only rescue team accounts can access dispatch queue.')
    return profile


class RescueUnitListView(generics.ListAPIView):
    serializer_class = RescueUnitSerializer
    permission_classes = [permissions.AllowAny]
    queryset = RescueUnit.objects.filter(is_active=True)


class NearestRescueUnitsView(generics.ListAPIView):
    serializer_class = RescueUnitSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        lat_param = self.request.query_params.get('latitude')
        lon_param = self.request.query_params.get('longitude')
        if lat_param is None or lon_param is None:
            raise ValidationError({'detail': 'latitude and longitude are required query params.'})
        try:
            latitude = float(lat_param)
            longitude = float(lon_param)
        except ValueError as exc:
            raise ValidationError({'detail': 'latitude and longitude must be numeric values.'}) from exc
        unit_type = self.request.query_params.get('unit_type')
        return find_nearest_rescue_units(longitude, latitude, unit_type)


class SOSDispatchView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        profile = CitizenProfile.objects.get(user=request.user)
        nearest = find_nearest_rescue_units(profile.location.x, profile.location.y)
        rescue_request = RescueRequest.objects.create(
            citizen=profile,
            description=request.data.get('description', ''),
            status=RescueRequest.STATUS_PENDING,
        )
        payload = {
            'rescue_request_id': rescue_request.id,
            'status': rescue_request.status,
            'dispatched_units': RescueUnitSerializer(nearest, many=True).data,
        }
        return Response(payload, status=status.HTTP_201_CREATED)


class RescueResponderHeartbeatView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        profile = ensure_rescue_team_access(request.user)

        lat_param = request.data.get('latitude')
        lon_param = request.data.get('longitude')
        if lat_param is None or lon_param is None:
            raise ValidationError({'detail': 'latitude and longitude are required.'})

        try:
            latitude = float(lat_param)
            longitude = float(lon_param)
        except (TypeError, ValueError) as exc:
            raise ValidationError({'detail': 'latitude and longitude must be numeric values.'}) from exc

        is_available = request.data.get('is_available_for_dispatch')
        unit_type = request.data.get('unit_type')
        update_fields = ['location', 'last_location_update']

        profile.location = Point(longitude, latitude, srid=4326)
        profile.last_location_update = timezone.now()

        if is_available is not None:
            if isinstance(is_available, bool):
                parsed_is_available = is_available
            elif isinstance(is_available, str):
                normalized = is_available.strip().lower()
                if normalized in {'true', '1', 'yes', 'on'}:
                    parsed_is_available = True
                elif normalized in {'false', '0', 'no', 'off'}:
                    parsed_is_available = False
                else:
                    raise ValidationError({'detail': 'is_available_for_dispatch must be a boolean value.'})
            else:
                raise ValidationError({'detail': 'is_available_for_dispatch must be a boolean value.'})

            profile.is_available_for_dispatch = parsed_is_available
            update_fields.append('is_available_for_dispatch')

        if unit_type is not None:
            allowed_types = {choice[0] for choice in CitizenProfile.RESPONDER_TYPE_CHOICES}
            if unit_type not in allowed_types:
                raise ValidationError({'detail': 'unit_type is invalid.'})
            profile.responder_unit_type = unit_type
            update_fields.append('responder_unit_type')

        profile.save(update_fields=update_fields)
        return Response(RescueUnitSerializer(profile).data, status=status.HTTP_200_OK)


class RescueDispatchQueueView(generics.ListAPIView):
    serializer_class = RescueDispatchQueueSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        ensure_rescue_team_access(self.request.user)
        return RescueRequest.objects.select_related('citizen').filter(
            status__in=[RescueRequest.STATUS_PENDING, RescueRequest.STATUS_DISPATCHED]
        ).order_by('-created_at')[:100]


class RescueDispatchAcceptView(generics.GenericAPIView):
    serializer_class = RescueDispatchQueueSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, request_id: int, *args, **kwargs):
        ensure_rescue_team_access(request.user)
        rescue_request = get_object_or_404(RescueRequest.objects.select_related('citizen'), pk=request_id)
        if rescue_request.status != RescueRequest.STATUS_RESOLVED:
            rescue_request.status = RescueRequest.STATUS_DISPATCHED
            rescue_request.dispatched_at = timezone.now()
            rescue_request.save(update_fields=['status', 'dispatched_at'])
        return Response(self.serializer_class(rescue_request).data, status=status.HTTP_200_OK)
