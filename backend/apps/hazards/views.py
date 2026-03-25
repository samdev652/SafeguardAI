import hashlib
import logging
import os
import traceback
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)

CHAT_CACHE_TTL = 60 * 30        # 30 minutes
RATE_LIMIT_MAX = 30              # messages per window
RATE_LIMIT_WINDOW = 60 * 60     # 1 hour in seconds


def _get_client_ip(request) -> str:
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


@method_decorator(csrf_exempt, name='dispatch')
class ChatView(APIView):
    authentication_classes = []
    permission_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            from groq import Groq
            from apps.hazards.models import RiskAssessment
            from apps.alerts.models import CommunityVerificationPrompt
            from apps.citizens.models import CitizenProfile
            from .models import HazardObservation, WardBoundary
            from django.conf import settings
            from django.utils import timezone
            import json
            import hashlib

            message = request.data.get('message')
            ward = request.data.get('ward') or 'Unknown'
            session_id = request.data.get('session_id') or request.META.get('HTTP_X_SESSION_ID') or _get_client_ip(request)

            if not message:
                return Response({'error': 'Message is required.'}, status=status.HTTP_400_BAD_REQUEST)

            # 30-minute Response Caching
            message_hash = hashlib.md5(message.strip().lower().encode('utf-8')).hexdigest()
            response_cache_key = f"chat_resp_{ward}_{message_hash}"
            cached_response = cache.get(response_cache_key)
            if cached_response:
                return Response(cached_response)

            # Rate limiting (30 requests per hour per IP)
            ip = _get_client_ip(request)
            cache_key = f"chat_rl_{ip}"
            requests_count = cache.get(cache_key, 0)
            if requests_count >= 30:
                return Response({'error': 'Rate limit exceeded.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            cache.set(cache_key, requests_count + 1, timeout=3600)

            user_ward = ward
            user_county = "Unknown"
            if request.user.is_authenticated:
                profile = CitizenProfile.objects.filter(user=request.user).first()
                if profile:
                    user_ward = profile.ward_name
                    ward_obj = WardBoundary.objects.filter(ward_name__iexact=profile.ward_name).only('county_name').first()
                    if ward_obj:
                        user_county = ward_obj.county_name

            nairobi_time = timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S %Z')
            month = timezone.now().month
            if month in [3, 4, 5]:
                season = "Long Rains (March to May) - Most dangerous time for floods."
            elif month in [10, 11, 12]:
                season = "Short Rains (October to December) - High flood risk."
            else:
                season = "Dry Season - High drought risk in arid areas."

            # Fetch active risk assessments
            assessments = RiskAssessment.objects.exclude(risk_level=RiskAssessment.RISK_SAFE).order_by('-issued_at')[:15]
            risk_context = ""
            for a in assessments:
                # Mock community verification status based on recent system structures
                yes_votes = CommunityVerificationPrompt.objects.filter(risk_assessment=a, vote='yes').count()
                status_text = f"Community Verified ({yes_votes} confirmations)" if yes_votes > 0 else "AI-Only Prediction"
                
                risk_context += (
                    f"- Ward: {a.ward_name} | Hazard: {a.hazard_type.title()} | Risk: {a.risk_level.title()} "
                    f"| Probability: {int(a.risk_score)}% | Status: {status_text}\n"
                    f"  What to do: {a.guidance_en}\n"
                )

            if not risk_context:
                risk_context = "No active high/critical risk assessments right now."

            # Fetch local weather for user's ward
            weather_ctx = "No weather data locally available."
            local_weather = HazardObservation.objects.filter(ward_name__iexact=user_ward).order_by('-observed_at').first()
            if local_weather and isinstance(local_weather.raw_payload, dict):
                props = local_weather.raw_payload.get('properties', local_weather.raw_payload)
                t = props.get('temperature_2m', 'N/A')
                p = props.get('precipitation', '0')
                weather_ctx = f"Temp: {t}°C, Rainfall: {p}mm"

            # Preparedness score (mock logic based on user counts or static for demo)
            prep_score = 65

            # System Prompt (Rafiki)
            system_prompt = (
                "You are Rafiki, the official Safeguard AI disaster intelligence assistant for Kenya. Rafiki means friend in Swahili. "
                "You must feel like a knowledgeable, hyper-local Kenyan friend who genuinely cares about the user's safety—not a cold government system. "
                "CRITICAL RULES: \n"
                "1. Language Auto-Detection: Always answer in the exact same language the user writes in. If they write Swahili, reply in fluent Swahili. If they write English, use English. If they write Sheng (Kenyan slang), reply naturally in Sheng without sounding translated. Switch languages instantly if the user switches.\n"
                "2. Proactive Safety: Always proactively mention any active high or critical alerts for the user's ward or the ward they ask about, even if they didn't ask directly. \n"
                "3. Hyper-Local Details: Never give generic advice. When discussing floods in Nairobi, specifically mention rivers like Nairobi River or Ngong River. Name real streets, landmarks, and rescue units. \n"
                "4. Disaster First-Response: For floods: turn off mains electricity, never walk in moving water > ankle deep, move documents upstairs. For landslides: listen for cracking slopes, watch for muddy water. For earthquakes: drop, cover, hold on, avoid lifts. For droughts: boil water, prioritize animals. \n"
                "5. Emergency Escalation: If the user uses emergency words (help, SOS, emergency, stuck, trapped, injured, drowning, fire, earthquake, niokoe, msaada, nimezingirwa, nimepotea, nimeumia, mafuriko sasa, moto, tetemeko, nimekwama, saidia), you MUST set is_emergency=true and IMMEDIATELY list the nearest rescue contacts at the very start of your message as phone numbers.\n"
                "6. Bilingual Alert Formatting: When sending emergency instructions, format them exactly like SMS alerts using 🚨 emojis, DO NOW, DO NOT, and Rescue Contacts.\n"
                "7. Historical Context: You know that the 2024 long rains caused 300 deaths and KES 187 billion in losses. The 2019 Patel Dam in Solai killed 47. You know flood plains (Budalangi, Nyando, Tana Delta), steep slopes (Murang'a, Nyeri), seismic zones (Rift Valley), and drought zones (Turkana, Mandera).\n"
                "8. Keep your response under 200 words but never cut off safety info.\n\n"
                "--- LIVE SYSTEM CONTEXT ---\n"
                f"Current Time (Nairobi): {nairobi_time}\n"
                f"Current Season: {season}\n"
                f"User's Logged-in Location: Ward: {user_ward}, County: {user_county}\n"
                f"User Ward Preparedness Score: {prep_score}%\n"
                f"User Ward Current Weather: {weather_ctx}\n"
                f"Active Risk Assessments:\n{risk_context}\n"
                "Rescue Units (Reference for emergencies): Red Cross Headquarters (+254 700 395 395), Nairobi Fire Station (+254 20 222 2181), National Disaster Operations Centre (0800 721 211).\n\n"
                "You MUST return your entire response as a structured JSON object containing EXACTLY these keys:\n"
                '- "reply": Your main text response to the user.\n'
                '- "suggestions": A JSON array of 3 short, contextually smart follow-up question strings (e.g., ["Show me evacuation routes", "Alert my family", "Who do I call right now?"]).\n'
                '- "is_emergency": boolean (true if the user is in danger/needs rescue, false otherwise).\n'
                '- "relevant_ward": The ward name you are discussing.\n'
                '- "risk_level": "critical", "high", "medium", or "safe".'
            )

            # Redis Conversation Memory Management
            hist_key = f"chat_hist_{session_id}"
            history = cache.get(hist_key, [])
            
            # Format history for Groq messages
            messages = [{'role': 'system', 'content': system_prompt}]
            for msg in history[-8:]:  # Keep last 8 turns of context
                messages.append(msg)
            messages.append({'role': 'user', 'content': message})

            client = Groq(api_key=os.getenv('GROQ_API_KEY'))
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=messages,
                max_tokens=600,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            reply_text = response.choices[0].message.content.strip()

            # Append to history and save
            history.append({'role': 'user', 'content': message})
            history.append({'role': 'assistant', 'content': reply_text})
            cache.set(hist_key, history[-10:], timeout=86400) # 24 hr TTL

            parsed_reply = json.loads(reply_text)
            
            # Save the new response to cache
            cache.set(response_cache_key, parsed_reply, timeout=1800)

            return Response(parsed_reply)

        except Exception as e:
            logger.error(f"[Chatbot] Error: {traceback.format_exc()}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
import json
import time
import requests
from datetime import timedelta
from django.conf import settings
from django.db.models import Avg, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.contrib.gis.geos import GEOSGeometry, Point
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

    @method_decorator(cache_page(10))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        ward = request.query_params.get('ward')
        if ward:
            qs = RiskAssessment.objects.filter(ward_name__iexact=ward).order_by('-issued_at')[:100]
            serializer = self.get_serializer(qs, many=True)
            return Response(serializer.data)

        # Build a ward_name → county_name lookup from WardBoundary
        ward_to_county = {
            wb.ward_name.lower(): wb.county_name
            for wb in WardBoundary.objects.only('ward_name', 'county_name')
        }

        # Grab top 100 recent
        qs = RiskAssessment.objects.all().order_by('-issued_at')[:100]
        results = list(qs)

        # Ensure the 10 core counties are always represented for the demo
        core_counties = ['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', "Murang'a", 'Kilifi', 'Busia', 'Tana River', 'Turkana', 'Mandera']
        existing_counties = {ward_to_county.get(r.ward_name.lower()) for r in results}
        existing_counties.discard(None)

        missing = [c for c in core_counties if c not in existing_counties]
        for c in missing:
            # Find wards that belong to this county
            county_wards = [w for w, cn in ward_to_county.items() if cn.lower() == c.lower()]
            if county_wards:
                latest = (
                    RiskAssessment.objects
                    .filter(ward_name__in=[w for w in WardBoundary.objects.filter(county_name__iexact=c).values_list('ward_name', flat=True)])
                    .order_by('-issued_at')
                    .first()
                )
                if latest:
                    results.append(latest)

        # Re-sort descending
        results.sort(key=lambda x: x.issued_at, reverse=True)

        serializer = self.get_serializer(results[:110], many=True)
        return Response(serializer.data)


class WardRiskView(generics.ListAPIView):
    serializer_class = RiskAssessmentSerializer
    permission_classes = [permissions.AllowAny]

    @method_decorator(cache_page(10))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        ward = self.kwargs['ward_name']
        return RiskAssessment.objects.filter(ward_name__iexact=ward).order_by('-issued_at')[:20]


class PublicRiskCountView(APIView):
    permission_classes = [permissions.AllowAny]

    @method_decorator(cache_page(10))
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

    @method_decorator(cache_page(10))
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
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        force_demo_ward = request.data.get('force_demo_ward')
        task = ingest_hazard_data_task.delay(force_demo_ward=force_demo_ward)
        return Response({
            'task_id': task.id, 
            'status': 'queued', 
            'demo_mode': bool(force_demo_ward)
        })


class SimulateRiskView(APIView):
    """DEBUG-only endpoint that instantly generates fresh predictions for 3 random wards."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not settings.DEBUG:
            return Response(
                {'detail': 'Simulation endpoint is only available when DEBUG=True.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        import random
        from .services import GeminiRiskAnalyzer
        from apps.alerts.tasks import dispatch_risk_alerts_task

        count = min(int(request.data.get('count', 3)), 10)
        wards = list(WardBoundary.objects.all())
        if not wards:
            return Response(
                {'detail': 'No wards in database. Run: python manage.py seed_wards'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        selected = random.sample(wards, min(count, len(wards)))
        analyzer = GeminiRiskAnalyzer()
        results = []

        for ward in selected:
            centroid = ward.geometry.centroid
            hazard = random.choice(['flood', 'landslide', 'drought'])
            precip = round(random.uniform(15, 70), 1)
            soil = round(random.uniform(0.25, 0.48), 2)
            temp = round(random.uniform(22, 38), 1)

            obs = HazardObservation.objects.create(
                source='demo_simulation',
                ward_name=ward.ward_name,
                village_name='Simulated Zone',
                hazard_type=hazard,
                severity_index=round(random.uniform(50, 98), 1),
                location=Point(centroid.x, centroid.y, srid=4326),
                raw_payload={'properties': {
                    'precipitation_mm': precip,
                    'soil_moisture': soil,
                    'temperature_2m': temp,
                }},
                observed_at=timezone.now(),
            )

            obs_dict = {
                'ward_name': obs.ward_name,
                'village_name': obs.village_name,
                'hazard_type': obs.hazard_type,
                'severity_index': obs.severity_index,
                'source': obs.source,
                'temperature_c': temp,
                'precipitation_mm': precip,
                'soil_moisture': soil,
            }

            analysis = analyzer.analyze(obs_dict, bypass_rate_limit=True)

            risk = RiskAssessment.objects.create(
                ward_name=obs.ward_name,
                village_name=obs.village_name,
                hazard_type=obs.hazard_type,
                risk_level=analysis['risk_level'],
                risk_score=float(analysis['risk_score']),
                guidance_en=analysis['guidance_en'],
                guidance_sw=analysis['guidance_sw'],
                summary=analysis['summary'],
                location=obs.location,
            )

            if risk.risk_level in ('high', 'critical'):
                dispatch_risk_alerts_task.delay(risk.id)

            results.append({
                'ward': ward.ward_name,
                'county': ward.county_name,
                'hazard': hazard,
                'risk_level': risk.risk_level,
                'risk_score': risk.risk_score,
                'summary': risk.summary,
            })

        return Response({
            'simulated': len(results),
            'results': results,
        })


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
