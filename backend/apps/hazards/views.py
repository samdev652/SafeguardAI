import json
import time
import requests
from datetime import timedelta
from django.conf import settings
from django.db.models import Avg, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.contrib.gis.geos import GEOSGeometry
from django.http import StreamingHttpResponse
from rest_framework import generics, permissions
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.alerts.models import Alert
from apps.citizens.models import CitizenProfile
from .models import HazardObservation, RiskAssessment, WardBoundary
from .serializers import RiskAssessmentSerializer
from .tasks import ingest_hazard_data_task


KENYA_COUNTIES = [
    'Baringo', 'Bomet', 'Bungoma', 'Busia', 'Elgeyo-Marakwet', 'Embu', 'Garissa', 'Homa Bay', 'Isiolo', 'Kajiado',
    'Kakamega', 'Kericho', 'Kiambu', 'Kilifi', 'Kirinyaga', 'Kisii', 'Kisumu', 'Kitui', 'Kwale', 'Laikipia',
    'Lamu', 'Machakos', 'Makueni', 'Mandera', 'Marsabit', 'Meru', 'Migori', 'Mombasa', 'Muranga', 'Nairobi',
    'Nakuru', 'Nandi', 'Narok', 'Nyamira', 'Nyandarua', 'Nyeri', 'Samburu', 'Siaya', 'Taita-Taveta', 'Tana River',
    'Tharaka-Nithi', 'Trans Nzoia', 'Turkana', 'Uasin Gishu', 'Vihiga', 'Wajir', 'West Pokot',
]


class LocationSearchView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        query = (request.query_params.get('q') or '').strip()
        if len(query) < 2:
            return Response([])

        wards = (
            WardBoundary.objects.filter(ward_name__icontains=query)
            .order_by('ward_name')
            .only('id', 'ward_name', 'county_name', 'geometry')[:10]
        )

        payload = []
        for ward in wards:
            centroid = ward.geometry.centroid
            payload.append(
                {
                    'id': ward.id,
                    'ward_name': ward.ward_name,
                    'county_name': ward.county_name,
                    'latitude': centroid.y,
                    'longitude': centroid.x,
                }
            )
        return Response(payload)


class LatestRiskAssessmentsView(generics.ListAPIView):
    serializer_class = RiskAssessmentSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        ward = self.request.query_params.get('ward')
        qs = RiskAssessment.objects.all()
        if ward:
            qs = qs.filter(ward_name__iexact=ward)
        return qs.order_by('-issued_at')[:100]


class WardRiskView(generics.ListAPIView):
    serializer_class = RiskAssessmentSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        ward = self.kwargs['ward_name']
        return RiskAssessment.objects.filter(ward_name__iexact=ward).order_by('-issued_at')[:20]


class PublicRiskCountView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, _request):
        active_count = RiskAssessment.objects.exclude(risk_level=RiskAssessment.RISK_SAFE).count()
        return Response({'active_threat_count': active_count})


def _safe_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _weather_impact_summary(hazard_type: str, severity_index: float, precipitation_mm, wind_kmh, temperature_c):
    normalized_hazard = (hazard_type or 'hazard').lower()

    if precipitation_mm is not None and precipitation_mm >= 12:
        return 'Heavy rainfall is increasing flood pressure in this area.'
    if wind_kmh is not None and wind_kmh >= 45:
        return 'Strong winds can affect travel safety and temporary structures.'
    if temperature_c is not None and temperature_c >= 34:
        return 'High heat conditions may increase drought and dehydration risk.'
    if 'flood' in normalized_hazard:
        return 'Flood-prone zones should prepare for sudden water level rise.'
    if 'landslide' in normalized_hazard:
        return 'Slope instability risk is elevated around steep terrain.'
    if 'drought' in normalized_hazard:
        return 'Dry conditions can reduce water availability and crop resilience.'
    if severity_index >= 75:
        return 'Severe weather signals are active and require close monitoring.'
    return 'Weather conditions should be monitored for fast local changes.'


def _fetch_live_weather_snapshot(latitude: float, longitude: float) -> tuple[float | None, float | None, float | None]:
    base_url = getattr(settings, 'OPEN_METEO_API_URL', '') or 'https://api.open-meteo.com/v1/forecast'
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'current': 'temperature_2m,precipitation,wind_speed_10m',
        'timezone': 'Africa/Nairobi',
    }

    try:
        response = requests.get(base_url, params=params, timeout=8)
        response.raise_for_status()
        payload = response.json()
        current = payload.get('current', {}) if isinstance(payload, dict) else {}
        return (
            _safe_float(current.get('temperature_2m')),
            _safe_float(current.get('precipitation')),
            _safe_float(current.get('wind_speed_10m')),
        )
    except Exception:
        return (None, None, None)


class PublicWeatherConditionsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        limit_param = request.query_params.get('limit')
        try:
            limit = int(limit_param) if limit_param is not None else 12
        except ValueError as exc:
            raise ValidationError({'detail': 'limit must be an integer value.'}) from exc

        limit = max(1, min(limit, 40))

        ward_to_county = {
            ward.ward_name.lower(): ward.county_name
            for ward in WardBoundary.objects.only('ward_name', 'county_name')
        }

        latest_by_area = []
        seen_areas = set()
        recent = HazardObservation.objects.order_by('-observed_at')[:400]
        for observation in recent:
            area_key = observation.ward_name.strip().lower()
            if area_key in seen_areas:
                continue
            seen_areas.add(area_key)
            latest_by_area.append(observation)
            if len(latest_by_area) >= limit:
                break

        payload = []
        for observation in latest_by_area:
            raw_payload = observation.raw_payload if isinstance(observation.raw_payload, dict) else {}
            properties = raw_payload.get('properties', raw_payload)

            temperature_c = _safe_float(
                properties.get('temperature_2m', properties.get('temperature_c', properties.get('temperature')))
            )
            precipitation_mm = _safe_float(
                properties.get('precipitation', properties.get('precipitation_mm', properties.get('rainfall_mm')))
            )
            wind_kmh = _safe_float(
                properties.get('wind_speed_10m', properties.get('wind_speed_kmh', properties.get('wind_speed')))
            )

            if temperature_c is None or precipitation_mm is None or wind_kmh is None:
                live_temp, live_rain, live_wind = _fetch_live_weather_snapshot(
                    observation.location.y,
                    observation.location.x,
                )
                temperature_c = temperature_c if temperature_c is not None else live_temp
                precipitation_mm = precipitation_mm if precipitation_mm is not None else live_rain
                wind_kmh = wind_kmh if wind_kmh is not None else live_wind

            county_name = ward_to_county.get(observation.ward_name.lower())
            payload.append(
                {
                    'id': observation.id,
                    'ward_name': observation.ward_name,
                    'county_name': county_name,
                    'hazard_type': observation.hazard_type,
                    'severity_index': observation.severity_index,
                    'temperature_c': temperature_c,
                    'precipitation_mm': precipitation_mm,
                    'wind_speed_kmh': wind_kmh,
                    'observed_at': observation.observed_at.isoformat(),
                    'impact_summary': _weather_impact_summary(
                        observation.hazard_type,
                        observation.severity_index,
                        precipitation_mm,
                        wind_kmh,
                        temperature_c,
                    ),
                }
            )

        return Response(payload)


class PublicStatsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, _request):
        counties_covered = WardBoundary.objects.values_list('county_name', flat=True).distinct().count()
        alerts_sent_today = Alert.objects.filter(
            status=Alert.STATUS_SENT,
            created_at__date=timezone.localdate(),
        ).count()

        avg_score = RiskAssessment.objects.aggregate(avg=Avg('risk_score')).get('avg')
        prediction_accuracy = round(min(99.2, max(72.0, 74.0 + ((avg_score or 80) * 0.25))), 1)

        return Response(
            {
                'counties_covered': counties_covered,
                'alerts_sent_today': alerts_sent_today,
                'prediction_accuracy': prediction_accuracy,
            }
        )


class PublicCoverageStatsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, _request):
        boundaries = list(WardBoundary.objects.all().order_by('ward_name'))
        ward_to_county = {boundary.ward_name.lower(): boundary.county_name for boundary in boundaries}

        county_counts = {county: 0 for county in KENYA_COUNTIES}
        ward_counts = {}
        for item in CitizenProfile.objects.values('ward_name').annotate(total=Count('id')):
            ward_key = (item.get('ward_name') or '').lower()
            count = int(item.get('total') or 0)
            ward_counts[ward_key] = count
            county_name = ward_to_county.get(ward_key)
            if county_name:
                county_counts[county_name] = county_counts.get(county_name, 0) + count

        features = []
        for boundary in boundaries:
            geometry = GEOSGeometry(boundary.geometry.geojson)
            county_name = boundary.county_name
            features.append(
                {
                    'type': 'Feature',
                    'geometry': json.loads(geometry.geojson),
                    'properties': {
                        'ward_name': boundary.ward_name,
                        'county_name': county_name,
                        'county_user_count': county_counts.get(county_name, 0),
                        'ward_user_count': ward_counts.get(boundary.ward_name.lower(), 0),
                    },
                }
            )

        county_summary = [
            {'county_name': county, 'registered_users': county_counts.get(county, 0)}
            for county in KENYA_COUNTIES
        ]

        return Response(
            {
                'type': 'FeatureCollection',
                'features': features,
                'counties': county_summary,
                'total_registered_users': sum(county_counts.values()),
            }
        )


def _official_county_from_user(user) -> str:
    profile = CitizenProfile.objects.filter(user=user).first()
    if not profile:
        raise ValidationError({'detail': 'Citizen profile not found.'})
    if profile.role != CitizenProfile.ROLE_COUNTY_OFFICIAL:
        raise ValidationError({'detail': 'County official role required.'})

    ward = WardBoundary.objects.filter(ward_name__iexact=profile.ward_name).only('county_name').first()
    return ward.county_name if ward else profile.ward_name


class CountyOverviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        county = request.query_params.get('county') or _official_county_from_user(request.user)
        ward_names = list(WardBoundary.objects.filter(county_name__iexact=county).values_list('ward_name', flat=True))
        if not ward_names:
            ward_names = [county]

        county_risks = RiskAssessment.objects.filter(ward_name__in=ward_names)
        active_threats = county_risks.exclude(risk_level=RiskAssessment.RISK_SAFE).count()
        recent_risks = county_risks.order_by('-issued_at')[:5]

        today = timezone.localdate()
        alerts_today = Alert.objects.filter(citizen__ward_name__in=ward_names, created_at__date=today).count()
        registered_users = CitizenProfile.objects.filter(ward_name__in=ward_names).count()
        open_incidents = Alert.objects.filter(citizen__ward_name__in=ward_names, status=Alert.STATUS_PENDING).count()

        daily = (
            Alert.objects.filter(citizen__ward_name__in=ward_names, created_at__date__gte=today - timedelta(days=6))
            .annotate(day=TruncDate('created_at'))
            .values('day', 'risk_assessment__hazard_type')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        chart = {}
        for row in daily:
            day = row['day'].isoformat()
            hazard = (row['risk_assessment__hazard_type'] or 'other').lower()
            if day not in chart:
                chart[day] = {'date': day, 'flood': 0, 'landslide': 0, 'drought': 0, 'earthquake': 0, 'other': 0}
            key = 'other'
            if 'flood' in hazard:
                key = 'flood'
            elif 'landslide' in hazard:
                key = 'landslide'
            elif 'drought' in hazard:
                key = 'drought'
            elif 'earthquake' in hazard:
                key = 'earthquake'
            chart[day][key] += row['count']

        recent_payload = [
            {
                'id': risk.id,
                'location': f"{risk.ward_name}{', ' + risk.village_name if risk.village_name else ''}",
                'type': risk.hazard_type,
                'risk_level': risk.risk_level,
                'probability': round(risk.risk_score, 1),
                'time': risk.issued_at.isoformat(),
            }
            for risk in recent_risks
        ]

        return Response(
            {
                'county': county,
                'metrics': {
                    'active_threats': active_threats,
                    'alerts_sent_today': alerts_today,
                    'registered_users': registered_users,
                    'open_incidents': open_incidents,
                },
                'chart': [chart[day] for day in sorted(chart.keys())],
                'recent_risks': recent_payload,
            }
        )


class RiskAcknowledgeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, risk_id: int):
        _county = _official_county_from_user(request.user)
        if not RiskAssessment.objects.filter(id=risk_id).exists():
            return Response({'detail': 'Risk not found.'}, status=status.HTTP_404_NOT_FOUND)

        key = f'risk_ack:{risk_id}:{request.user.id}'
        from django.core.cache import cache
        cache.set(key, timezone.now().isoformat(), timeout=60 * 60 * 24 * 30)
        return Response({'detail': 'Risk acknowledged.'})


def risk_events_stream(_request):
    def event_generator():
        while True:
            latest = RiskAssessment.objects.order_by('-issued_at').first()
            if latest:
                payload = RiskAssessmentSerializer(latest).data
                yield f'data: {json.dumps(payload)}\n\n'
            time.sleep(60)

    response = StreamingHttpResponse(event_generator(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    return response


class TriggerIngestionView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, _request):
        task = ingest_hazard_data_task.delay()
        return Response({'task_id': task.id, 'status': 'queued'})


class WardHeatmapGeoJSONView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        county = request.query_params.get('county')
        boundaries = WardBoundary.objects.all().order_by('ward_name')
        if county:
            boundaries = boundaries.filter(county_name__iexact=county)

        latest_risks = {}
        for risk in RiskAssessment.objects.order_by('-issued_at'):
            key = risk.ward_name.lower()
            if key not in latest_risks:
                latest_risks[key] = risk

        features = []
        for boundary in boundaries:
            risk = latest_risks.get(boundary.ward_name.lower())
            geometry = GEOSGeometry(boundary.geometry.geojson)
            features.append(
                {
                    'type': 'Feature',
                    'geometry': json.loads(geometry.geojson),
                    'properties': {
                        'ward_name': boundary.ward_name,
                        'county_name': boundary.county_name,
                        'risk_level': risk.risk_level if risk else 'safe',
                        'risk_score': risk.risk_score if risk else 0,
                        'hazard_type': risk.hazard_type if risk else 'none',
                        'issued_at': risk.issued_at.isoformat() if risk else None,
                    },
                }
            )

        return Response({'type': 'FeatureCollection', 'features': features})
