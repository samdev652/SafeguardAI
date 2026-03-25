from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib.gis.geos import Point
from django.utils import timezone
from .models import HazardObservation, RiskAssessment, WardBoundary
from .services import GeminiRiskAnalyzer, fetch_kmd_data, fetch_noaa_data, fetch_open_meteo_data
from apps.alerts.tasks import dispatch_risk_alerts_task


def _ward_from_coordinates(location: Point) -> WardBoundary | None:
    return WardBoundary.objects.filter(geometry__intersects=location).only('ward_name').first()


def _normalize_ward_name(properties: dict, location: Point) -> str:
    direct_ward = str(properties.get('ward', '')).strip()
    if direct_ward:
        return direct_ward

    area = str(properties.get('area', '')).strip()
    if area:
        exact = WardBoundary.objects.filter(ward_name__iexact=area).only('ward_name').first()
        if exact:
            return exact.ward_name

    by_geometry = _ward_from_coordinates(location)
    if by_geometry:
        return by_geometry.ward_name

    return area or 'Unknown Ward'


def _normalize_severity(properties: dict) -> float:
    value = properties.get('severity_index', properties.get('severity', 50))
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value or '').strip().lower()
    if not text:
        return 50.0

    try:
        return float(text)
    except ValueError:
        pass

    mapping = {
        'extreme': 95.0,
        'severe': 85.0,
        'high': 75.0,
        'moderate': 60.0,
        'low': 35.0,
        'minor': 25.0,
    }
    return mapping.get(text, 50.0)


def _normalize_items(items: list[dict], source: str) -> list[dict]:
    normalized = []
    for item in items:
        properties = item.get('properties', item)
        geometry = item.get('geometry') if isinstance(item, dict) else None
        coordinates = geometry.get('coordinates') if isinstance(geometry, dict) else None
        if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
            coordinates = [36.8219, -1.2921]
        lon, lat = coordinates[0], coordinates[1]
        location = Point(lon, lat, srid=4326)
        ward_name = _normalize_ward_name(properties, location)
        normalized.append({
            'source': source,
            'ward_name': ward_name,
            'village_name': properties.get('village', ''),
            'hazard_type': properties.get('hazard_type', properties.get('event', 'flood')).lower(),
            'severity_index': _normalize_severity(properties),
            'location': location,
            'raw_payload': item,
            'observed_at': timezone.now(),
        })
    return normalized


def _safe_fetch(fetcher) -> list[dict]:
    try:
        return fetcher() or []
    except Exception:
        return []


def _max_items_per_run() -> int:
    raw = getattr(settings, 'HAZARD_MAX_ITEMS_PER_RUN', 80)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 80
    return max(1, min(value, 500))


def _alert_dedup_minutes() -> int:
    raw = getattr(settings, 'HAZARD_ALERT_DEDUP_MINUTES', 30)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 30
    return max(0, min(value, 240))


def _is_duplicate_alert_window(risk: RiskAssessment) -> bool:
    dedup_minutes = _alert_dedup_minutes()
    if dedup_minutes == 0:
        return False

    window_start = timezone.now() - timedelta(minutes=dedup_minutes)
    return RiskAssessment.objects.filter(
        ward_name__iexact=risk.ward_name,
        hazard_type__iexact=risk.hazard_type,
        risk_level=risk.risk_level,
        issued_at__gte=window_start,
    ).exclude(id=risk.id).exists()


@shared_task
def ingest_hazard_data_task(force_demo_ward: str = None) -> dict:
    analyzer = GeminiRiskAnalyzer()

    kmd_items = _normalize_items(_safe_fetch(fetch_kmd_data), 'kmd')
    noaa_items = _normalize_items(_safe_fetch(fetch_noaa_data), 'noaa')
    open_meteo_items = _normalize_items(_safe_fetch(fetch_open_meteo_data), 'open_meteo')
    all_items = (kmd_items + noaa_items + open_meteo_items)[:_max_items_per_run()]

    if force_demo_ward:
        # Inject synthetic high-risk anomaly to ensure investors see 
        # the AI react critically and trigger SMS instantly.
        demo_item = {
            'source': 'demo_simulation',
            'ward_name': force_demo_ward,
            'village_name': 'Demo Simulation Area',
            'hazard_type': 'flood',
            'severity_index': 98.0,
            'location': Point(36.8219, -1.2921, srid=4326),
            'raw_payload': {
                'properties': {
                    'precipitation_mm': 65.4,
                    'soil_moisture': 0.45,
                    'wind_speed_10m': 20.0,
                }
            },
            'observed_at': timezone.now(),
        }
        all_items.insert(0, demo_item)

    created = 0
    dispatched = 0
    dedup_skipped = 0
    rate_limited = 0
    for item in all_items:
        observation = HazardObservation.objects.create(**item)
        obs_dict = {
            'ward_name': observation.ward_name,
            'village_name': observation.village_name,
            'hazard_type': observation.hazard_type,
            'severity_index': observation.severity_index,
            'source': observation.source,
            'temperature_c': 28.5,
            'precipitation_mm': item.get('raw_payload', {}).get('properties', {}).get('precipitation_mm', 0),
            'soil_moisture': item.get('raw_payload', {}).get('properties', {}).get('soil_moisture', 0),
        }

        is_demo = bool(force_demo_ward and observation.ward_name.lower() == force_demo_ward.lower())

        if is_demo:
            was_rate_limited = False
            analysis = analyzer.analyze(obs_dict, bypass_rate_limit=True)
        else:
            was_rate_limited = analyzer._is_rate_limited(obs_dict)
            analysis = analyzer.analyze(obs_dict)

        if analysis is None:
            continue
        
        if was_rate_limited:
            rate_limited += 1

        risk = RiskAssessment.objects.create(
            ward_name=observation.ward_name,
            village_name=observation.village_name,
            hazard_type=observation.hazard_type,
            risk_level=analysis['risk_level'],
            risk_score=float(analysis['risk_score']),
            guidance_en=analysis['guidance_en'],
            guidance_sw=analysis['guidance_sw'],
            summary=analysis['summary'],
            location=observation.location,
        )

        if risk.risk_level in {RiskAssessment.RISK_HIGH, RiskAssessment.RISK_CRITICAL}:
            if not is_demo and _is_duplicate_alert_window(risk):
                dedup_skipped += 1
            else:
                dispatch_risk_alerts_task.delay(risk.id)
                dispatched += 1
        created += 1

    return {
        'created_observations': created,
        'dispatched_alert_jobs': dispatched,
        'dedup_skipped_alert_jobs': dedup_skipped,
        'gemini_rate_limited': rate_limited,
        'processed_items': len(all_items),
        'demo_mode': bool(force_demo_ward),
    }

