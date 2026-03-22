import logging
import os
import random
import csv
from datetime import datetime
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from apps.citizens.models import CitizenProfile
from apps.hazards.models import RiskAssessment, WardBoundary
from apps.rescue.services import find_nearest_rescue_units
from .models import Alert, CommunityVerificationPrompt, IncidentReport, RescueRequest
from .services import AlertDispatcher
from .serializers import AlertSerializer, CountyAlertHistorySerializer, IncidentReportSerializer


logger = logging.getLogger(__name__)

OTP_TTL_SECONDS = 300
OTP_VERIFIED_TTL_SECONDS = 600
OTP_CHANNEL_SMS = 'sms'
OTP_CHANNEL_WHATSAPP = 'whatsapp'
COMMUNITY_YES_THRESHOLD = 3
COMMUNITY_NO_THRESHOLD = 5


def normalize_kenya_phone(phone: str) -> str:
    normalized = ''.join(ch for ch in phone if ch.isdigit() or ch == '+').strip()
    if normalized.startswith('0'):
        normalized = f'+254{normalized[1:]}'
    elif normalized.startswith('254'):
        normalized = f'+{normalized}'

    digits = ''.join(ch for ch in normalized if ch.isdigit())
    has_valid_length = len(digits) == 12
    has_valid_prefix = digits.startswith('2547') or digits.startswith('2541')
    if not normalized.startswith('+254') or not has_valid_length or not has_valid_prefix:
        raise ValidationError({'phone': 'Use a valid Kenya mobile number in +2547XXXXXXXX or +2541XXXXXXXX format.'})
    return normalized


def cleaned_env_value(name: str, default: str = '') -> str:
    value = os.getenv(name, default)
    if value is None:
        return default
    cleaned = str(value).strip()
    # Allow copy-pasted quoted secrets in .env without breaking auth headers.
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def is_truthy(value: str) -> bool:
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


class SendOtpView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw_phone = str(request.data.get('phone', '')).strip()
        channel = str(request.data.get('channel', OTP_CHANNEL_SMS)).strip().lower()
        if channel not in {OTP_CHANNEL_SMS, OTP_CHANNEL_WHATSAPP}:
            raise ValidationError({'channel': 'Choose sms or whatsapp.'})

        phone = normalize_kenya_phone(raw_phone)
        otp = f'{random.randint(1000, 9999)}'
        cache.set(f'otp:{phone}', otp, timeout=OTP_TTL_SECONDS)
        cache.delete(f'otp:verified:{phone}')

        message = f'[Safeguard OTP] Verification code: {otp}. Expires in 5 minutes. Do not share this code.'
        provider = {'sent': False, 'provider': 'unknown', 'reason': 'unattempted'}
        dispatcher = AlertDispatcher()
        try:
            if channel == OTP_CHANNEL_WHATSAPP:
                provider = dispatcher.send_whatsapp(phone, message)
            else:
                provider = dispatcher.send_sms(phone, message, purpose='otp')
        except Exception as exc:  # pragma: no cover - provider/network failure should not crash UX.
            logger.exception('Failed sending OTP via provider')
            provider = {'sent': False, 'provider': channel, 'reason': str(exc)}

        if not provider.get('sent'):
            detail = provider.get('reason') or 'OTP provider could not deliver the message.'

            fallback_enabled = is_truthy(cleaned_env_value('OTP_ALLOW_DEV_FALLBACK', 'False')) or settings.DEBUG
            if fallback_enabled:
                logger.warning('OTP provider failed; using fallback mode. reason=%s', detail)
                return Response(
                    {
                        'detail': 'OTP generated using fallback mode.',
                        'phone': phone,
                        'channel': channel,
                        'provider': {
                            'sent': True,
                            'provider': 'debug_fallback',
                            'reason': detail,
                        },
                        'dev_otp': otp,
                    }
                )

            return Response(
                {'detail': f'OTP dispatch failed: {detail}', 'phone': phone, 'channel': channel, 'provider': provider},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({'detail': 'OTP sent.', 'phone': phone, 'channel': channel, 'provider': provider})


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


class OtpPhoneLoginView(APIView):
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

        profile = CitizenProfile.objects.filter(phone_number=phone).select_related('user').first()
        if not profile:
            return Response({'detail': 'No subscription found for this phone number.'}, status=status.HTTP_404_NOT_FOUND)

        refresh = RefreshToken.for_user(profile.user)
        cache.delete(f'otp:{phone}')
        cache.delete(f'otp:verified:{phone}')
        return Response(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'role': profile.role,
                'ward_name': profile.ward_name,
            }
        )


class SmsReplyWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        import logging
        logger = logging.getLogger(__name__)

        raw_phone = str(request.data.get('from') or request.data.get('phoneNumber') or '').strip()
        raw_text = str(request.data.get('text') or '').strip()
        logger.info('Webhook received: data=%r', request.data)
        if not raw_phone or not raw_text:
            logger.warning('Webhook rejected: missing phone or text. data=%r', request.data)
            return Response({'detail': 'ignored'}, status=status.HTTP_200_OK)


        try:
            phone = normalize_kenya_phone(raw_phone)
        except ValidationError as e:
            logger.warning('Webhook rejected: invalid phone format (%r). data=%r', raw_phone, request.data)
            return Response({'detail': 'ignored'}, status=status.HTTP_200_OK)


        vote = raw_text.split()[0].strip().lower()
        if vote not in {CommunityVerificationPrompt.VOTE_YES, CommunityVerificationPrompt.VOTE_NO}:
            logger.warning('Webhook rejected: invalid vote (%r). data=%r', vote, request.data)
            return Response({'detail': 'ignored'}, status=status.HTTP_200_OK)


        outbound_message = ''
        with transaction.atomic():
            prompt = (
                CommunityVerificationPrompt.objects.select_related('risk_assessment')
                .select_for_update()
                .filter(phone_number=phone, vote='')
                .order_by('-prompted_at')
                .first()
            )
            if not prompt:
                logger.warning('Webhook rejected: no pending prompt for phone=%r. data=%r', phone, request.data)
                return Response({'detail': 'ignored'}, status=status.HTTP_200_OK)

            prompt.vote = vote
            prompt.raw_reply = raw_text
            prompt.replied_at = timezone.now()
            prompt.save(update_fields=['vote', 'raw_reply', 'replied_at'])

            risk = RiskAssessment.objects.select_for_update().get(id=prompt.risk_assessment_id)
            prompts = CommunityVerificationPrompt.objects.filter(risk_assessment=risk)
            yes_count = prompts.filter(vote=CommunityVerificationPrompt.VOTE_YES).count()
            no_count = prompts.filter(vote=CommunityVerificationPrompt.VOTE_NO).count()

            if yes_count >= COMMUNITY_YES_THRESHOLD and risk.community_status == RiskAssessment.COMMUNITY_PENDING:
                risk.community_status = RiskAssessment.COMMUNITY_VERIFIED
                risk.community_verified_at = timezone.now()
                risk.save(update_fields=['community_status', 'community_verified_at'])
                outbound_message = (
                    f'[Safeguard CONFIRMED] {risk.hazard_type.title()} risk in {risk.ward_name} '
                    'has been community verified. Follow official guidance and stay safe.'
                )
            elif no_count >= COMMUNITY_NO_THRESHOLD and risk.community_status == RiskAssessment.COMMUNITY_PENDING:
                risk.risk_level = RiskAssessment.RISK_SAFE
                risk.community_status = RiskAssessment.COMMUNITY_ALL_CLEAR
                risk.community_all_clear_at = timezone.now()
                risk.summary = f'Community all-clear reported for {risk.hazard_type} in {risk.ward_name}.'
                risk.save(
                    update_fields=['risk_level', 'community_status', 'community_all_clear_at', 'summary']
                )
                outbound_message = (
                    f'[Safeguard ALL-CLEAR] Community reports indicate normal conditions in {risk.ward_name}. '
                    'Risk has been downgraded. Continue normal activity and monitor updates.'
                )

        if outbound_message:
            self._broadcast_ward_sms(risk, outbound_message)

        return Response({'detail': 'ok'}, status=status.HTTP_200_OK)

    def _broadcast_ward_sms(self, risk: RiskAssessment, message: str) -> None:
        dispatcher = AlertDispatcher()
        citizens = CitizenProfile.objects.filter(ward_name__iexact=risk.ward_name).only('phone_number')
        for citizen in citizens:
            try:
                dispatcher.send_sms(citizen.phone_number, message, purpose='alert')
            except Exception:
                logger.exception('Failed broadcasting community status SMS')


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

        if CitizenProfile.CHANNEL_SMS in profile.channels:
            contacts = []
            try:
                nearest_units = list(find_nearest_rescue_units(centroid.x, centroid.y))
                for unit in nearest_units[:3]:
                    unit_type = str(unit.responder_unit_type or 'rescue_team').replace('_', ' ')
                    contacts.append(f'{unit.full_name} ({unit_type}) {unit.phone_number}')
            except Exception:
                contacts = []

            contacts_line = (
                'Nearest rescue contacts: ' + '; '.join(contacts)
                if contacts
                else 'Nearest rescue contacts: call county emergency center.'
            )

            if latest_risk:
                guidance = latest_risk.guidance_sw if profile.preferred_language == 'sw' else latest_risk.guidance_en
                sms_message = (
                    f'[Safeguard ALERT] Subscription active for {ward.ward_name}.\n'
                    f'Current risk: {latest_risk.hazard_type} ({latest_risk.risk_level.upper()}).\n'
                    f'What to do: {guidance}\n'
                    f'{contacts_line}'
                )
            else:
                sms_message = (
                    f'[Safeguard ALERT] Subscription active for {ward.ward_name}.\n'
                    'Current risk: SAFE.\n'
                    'What to do: Keep your phone reachable for urgent alerts.\n'
                    f'{contacts_line}'
                )

            try:
                AlertDispatcher().send_sms(phone, sms_message, purpose='alert')
            except Exception:
                logger.exception('Failed sending subscription briefing SMS')

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
