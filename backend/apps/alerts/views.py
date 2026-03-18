import logging
import os
import random
import csv
import urllib.parse
import urllib.request
from datetime import datetime
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.http import HttpResponse
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.citizens.models import CitizenProfile
from apps.hazards.models import RiskAssessment, WardBoundary
from .models import Alert, IncidentReport, RescueRequest
from .serializers import AlertSerializer, CountyAlertHistorySerializer, IncidentReportSerializer


logger = logging.getLogger(__name__)

OTP_TTL_SECONDS = 300
OTP_VERIFIED_TTL_SECONDS = 600


def normalize_kenya_phone(phone: str) -> str:
    normalized = ''.join(ch for ch in phone if ch.isdigit() or ch == '+').strip()
    if normalized.startswith('0'):
        normalized = f'+254{normalized[1:]}'
    elif normalized.startswith('254'):
        normalized = f'+{normalized}'
    if not normalized.startswith('+254') or len(''.join(ch for ch in normalized if ch.isdigit())) != 12:
        raise ValidationError({'phone': 'Use a valid Kenya phone number in +2547XXXXXXXX format.'})
    return normalized


def send_sms_via_africas_talking(phone: str, message: str) -> dict:
    username = os.getenv('AFRICASTALKING_USERNAME', 'sandbox')
    api_key = os.getenv('AFRICASTALKING_API_KEY')
    sender = os.getenv('AFRICASTALKING_SENDER_ID', '')
    if not api_key:
        logger.warning('AFRICASTALKING_API_KEY missing; OTP is generated but SMS was not dispatched to provider.')
        return {'sent': False, 'provider': 'africas_talking', 'reason': 'missing_api_key'}

    payload = {
        'username': username,
        'to': phone,
        'message': message,
    }
    if sender:
        payload['from'] = sender

    data = urllib.parse.urlencode(payload).encode('utf-8')
    request = urllib.request.Request(
        url='https://api.africastalking.com/version1/messaging',
        data=data,
        method='POST',
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'apiKey': api_key,
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read().decode('utf-8')
    return {'sent': True, 'provider': 'africas_talking', 'response': body}


class SendOtpView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw_phone = str(request.data.get('phone', '')).strip()
        phone = normalize_kenya_phone(raw_phone)
        otp = f'{random.randint(1000, 9999)}'
        cache.set(f'otp:{phone}', otp, timeout=OTP_TTL_SECONDS)
        cache.delete(f'otp:verified:{phone}')

        message = f'Safeguard AI code: {otp}. Expires in 5 minutes.'
        provider = {'sent': False, 'provider': 'africas_talking', 'reason': 'unattempted'}
        try:
            provider = send_sms_via_africas_talking(phone, message)
        except Exception as exc:  # pragma: no cover - provider/network failure should not crash UX.
            logger.exception('Failed sending OTP via Africa\'s Talking')
            provider = {'sent': False, 'provider': 'africas_talking', 'reason': str(exc)}

        return Response({'detail': 'OTP sent.', 'phone': phone, 'provider': provider})


class VerifyOtpView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw_phone = str(request.data.get('phone', '')).strip()
        phone = normalize_kenya_phone(raw_phone)
        otp = str(request.data.get('otp', '')).strip()
        if len(otp) != 4 or not otp.isdigit():
            raise ValidationError({'otp': 'Enter the 4-digit OTP.'})

        cached_otp = cache.get(f'otp:{phone}')
        if cached_otp != otp:
            return Response({'detail': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        cache.set(f'otp:verified:{phone}', True, timeout=OTP_VERIFIED_TTL_SECONDS)
        cache.delete(f'otp:{phone}')
        return Response({'verified': True})


class AlertSubscribeView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ward_id = request.data.get('ward_id')
        raw_phone = str(request.data.get('phone', '')).strip()
        channels = request.data.get('channels') or []
        if not isinstance(channels, list):
            raise ValidationError({'channels': 'Channels must be a list.'})

        phone = normalize_kenya_phone(raw_phone)
        if not cache.get(f'otp:verified:{phone}'):
            return Response({'detail': 'Phone must be OTP verified first.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ward = WardBoundary.objects.get(id=ward_id)
        except (TypeError, ValueError, WardBoundary.DoesNotExist):
            raise ValidationError({'ward_id': 'Selected ward was not found.'})

        allowed = {CitizenProfile.CHANNEL_SMS, CitizenProfile.CHANNEL_WHATSAPP, CitizenProfile.CHANNEL_PUSH}
        normalized_channels = [str(channel).lower().strip() for channel in channels if str(channel).strip()]
        normalized_channels = [channel for channel in normalized_channels if channel in allowed]
        if CitizenProfile.CHANNEL_SMS not in normalized_channels:
            normalized_channels.insert(0, CitizenProfile.CHANNEL_SMS)
        normalized_channels = sorted(set(normalized_channels), key=['sms', 'whatsapp', 'push'].index)

        existing_profile = CitizenProfile.objects.filter(phone_number=phone).select_related('user').first()
        if existing_profile:
            user = existing_profile.user
        else:
            username_base = f'phone_{"".join(ch for ch in phone if ch.isdigit())}'
            username = username_base
            suffix = 1
            while User.objects.filter(username=username).exists():
                username = f'{username_base}_{suffix}'
                suffix += 1

            user = User.objects.create(username=username, is_active=True)
            user.set_unusable_password()
            user.save(update_fields=['password'])

        centroid = ward.geometry.centroid
        profile_defaults = {
            'user': user,
            'full_name': f'Subscriber {phone[-4:]}',
            'ward_name': ward.ward_name,
            'village_name': '',
            'preferred_language': 'en',
            'location': Point(centroid.x, centroid.y, srid=4326),
            'channels': normalized_channels,
        }
        profile, _ = CitizenProfile.objects.update_or_create(
            phone_number=phone,
            defaults=profile_defaults,
        )

        latest_risk = RiskAssessment.objects.filter(ward_name__iexact=ward.ward_name).order_by('-issued_at').first()
        risk_level = latest_risk.risk_level if latest_risk else 'safe'
        cache.delete(f'otp:verified:{phone}')

        return Response(
            {
                'detail': 'Subscription successful.',
                'ward_name': ward.ward_name,
                'risk_level': risk_level,
                'channels': profile.channels,
            },
            status=status.HTTP_201_CREATED,
        )


class MyAlertsView(generics.ListAPIView):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Alert.objects.filter(citizen__user=self.request.user).order_by('-created_at')[:100]


def _county_from_user(user) -> str:
    profile = CitizenProfile.objects.filter(user=user).first()
    if not profile:
        raise ValidationError({'detail': 'Citizen profile not found.'})
    if profile.role != CitizenProfile.ROLE_COUNTY_OFFICIAL:
        raise ValidationError({'detail': 'County official role required.'})
    ward = WardBoundary.objects.filter(ward_name__iexact=profile.ward_name).only('county_name').first()
    if ward:
        return ward.county_name
    return profile.ward_name


def _filtered_county_alerts(request):
    county = request.query_params.get('county') or _county_from_user(request.user)
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    hazard_type = request.query_params.get('hazard_type')
    channel = request.query_params.get('channel')
    risk_level = request.query_params.get('risk_level')

    ward_names = list(WardBoundary.objects.filter(county_name__iexact=county).values_list('ward_name', flat=True))
    if not ward_names:
        ward_names = [county]

    queryset = Alert.objects.select_related('citizen', 'risk_assessment').filter(citizen__ward_name__in=ward_names)
    if hazard_type:
        queryset = queryset.filter(risk_assessment__hazard_type__icontains=hazard_type)
    if channel:
        queryset = queryset.filter(channel__iexact=channel)
    if risk_level:
        queryset = queryset.filter(risk_assessment__risk_level__iexact=risk_level)
    if start_date:
        queryset = queryset.filter(created_at__date__gte=start_date)
    if end_date:
        queryset = queryset.filter(created_at__date__lte=end_date)
    return queryset.order_by('-created_at'), county


class CountyAlertHistoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class CountyAlertHistoryView(generics.ListAPIView):
    serializer_class = CountyAlertHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CountyAlertHistoryPagination

    def get_queryset(self):
        queryset, _county = _filtered_county_alerts(self.request)
        return queryset


class CountyAlertExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset, county = _filtered_county_alerts(request)
        if (request.query_params.get('format') or '').lower() != 'csv':
            return Response({'detail': 'Only CSV export is supported.'}, status=status.HTTP_400_BAD_REQUEST)

        response = HttpResponse(content_type='text/csv')
        filename = county.lower().replace(' ', '_')
        response['Content-Disposition'] = f'attachment; filename="alerts_{filename}.csv"'
        writer = csv.writer(response)
        writer.writerow(['id', 'county', 'ward', 'hazard_type', 'risk_level', 'channel', 'status', 'created_at'])

        for alert in queryset[:5000]:
            writer.writerow([
                alert.id,
                county,
                alert.citizen.ward_name,
                alert.risk_assessment.hazard_type,
                alert.risk_assessment.risk_level,
                alert.channel,
                alert.status,
                alert.created_at.isoformat(),
            ])
        return response


class IncidentReportListView(generics.ListCreateAPIView):
    serializer_class = IncidentReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        county = self.request.query_params.get('county') or _county_from_user(self.request.user)
        return IncidentReport.objects.filter(county_name__iexact=county).order_by('-created_at')


class IncidentReportUpdateView(generics.UpdateAPIView):
    serializer_class = IncidentReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = IncidentReport.objects.all()
    lookup_field = 'pk'

    def patch(self, request, *args, **kwargs):
        report = self.get_object()
        _county = _county_from_user(request.user)
        if report.county_name.lower() != _county.lower():
            return Response({'detail': 'Cannot update reports outside your county.'}, status=status.HTTP_403_FORBIDDEN)
        return super().patch(request, *args, **kwargs)


class CountyDispatchLogView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        county = request.query_params.get('county') or _county_from_user(request.user)
        ward_names = list(WardBoundary.objects.filter(county_name__iexact=county).values_list('ward_name', flat=True))
        if not ward_names:
            ward_names = [county]

        logs = (
            RescueRequest.objects.select_related('citizen', 'risk_assessment')
            .filter(citizen__ward_name__in=ward_names)
            .order_by('-created_at')[:200]
        )
        payload = [
            {
                'id': log.id,
                'ward_name': log.citizen.ward_name,
                'status': log.status,
                'description': log.description,
                'hazard_type': log.risk_assessment.hazard_type if log.risk_assessment else None,
                'created_at': log.created_at.isoformat(),
                'dispatched_at': log.dispatched_at.isoformat() if log.dispatched_at else None,
            }
            for log in logs
        ]
        return Response(payload)
