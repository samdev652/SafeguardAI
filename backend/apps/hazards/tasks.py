from celery import shared_task
from django.contrib.gis.geos import Point
from django.utils import timezone
from .models import HazardObservation, RiskAssessment
from .services import GeminiRiskAnalyzer, fetch_kmd_data, fetch_noaa_data
from apps.alerts.tasks import dispatch_risk_alerts_task


def _normalize_items(items: list[dict], source: str) -> list[dict]:
    normalized = []
    for item in items:
        properties = item.get('properties', item)
        coordinates = item.get('geometry', {}).get('coordinates', [36.8219, -1.2921])
        lon, lat = coordinates[0], coordinates[1]
        normalized.append({
            'source': source,
            'ward_name': properties.get('ward', properties.get('area', 'Unknown Ward')),
            'village_name': properties.get('village', ''),
            'hazard_type': properties.get('hazard_type', properties.get('event', 'flood')).lower(),
            'severity_index': float(properties.get('severity_index', properties.get('severity', 50))),
            'location': Point(lon, lat, srid=4326),
            'raw_payload': item,
            'observed_at': timezone.now(),
        })
    return normalized


@shared_task
def ingest_hazard_data_task() -> dict:
    analyzer = GeminiRiskAnalyzer()

    kmd_items = _normalize_items(fetch_kmd_data(), 'kmd')
    noaa_items = _normalize_items(fetch_noaa_data(), 'noaa')
    all_items = kmd_items + noaa_items

    created = 0
    for item in all_items:
        observation = HazardObservation.objects.create(**item)
        analysis = analyzer.analyze({
            'ward_name': observation.ward_name,
            'village_name': observation.village_name,
            'hazard_type': observation.hazard_type,
            'severity_index': observation.severity_index,
            'source': observation.source,
        })

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
        dispatch_risk_alerts_task.delay(risk.id)
        created += 1

    return {'created_observations': created}
