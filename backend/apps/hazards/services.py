import json
import requests
from django.conf import settings


class GeminiRiskAnalyzer:
    def analyze(self, observation: dict) -> dict:
        if not settings.GEMINI_API_KEY:
            return self._fallback(observation)

        prompt = (
            'You are a disaster risk analyst for Kenya. Return JSON only with keys '
            'risk_level, risk_score, guidance_en, guidance_sw, summary. '
            f'Input data: {json.dumps(observation)}'
        )
        url = (
            f'https://generativelanguage.googleapis.com/v1beta/models/'
            f'{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}'
        )
        payload = {'contents': [{'parts': [{'text': prompt}]}]}

        try:
            response = requests.post(url, json=payload, timeout=20)
            response.raise_for_status()
            text = response.json()['candidates'][0]['content']['parts'][0]['text']
            return json.loads(text)
        except Exception:
            return self._fallback(observation)

    def _fallback(self, observation: dict) -> dict:
        severity = float(observation.get('severity_index', 0))
        if severity >= 85:
            risk_level = 'critical'
        elif severity >= 65:
            risk_level = 'high'
        elif severity >= 40:
            risk_level = 'medium'
        else:
            risk_level = 'safe'

        return {
            'risk_level': risk_level,
            'risk_score': severity,
            'guidance_en': 'Move to higher ground and keep emergency contacts ready.',
            'guidance_sw': 'Nenda sehemu ya juu na uwe na nambari za dharura tayari.',
            'summary': f'{observation.get("hazard_type", "hazard").title()} risk is {risk_level}.',
        }


def fetch_kmd_data() -> list[dict]:
    if not settings.KMD_API_URL:
        return []
    headers = {'Authorization': f'Bearer {settings.KMD_API_KEY}'} if settings.KMD_API_KEY else {}
    response = requests.get(settings.KMD_API_URL, headers=headers, timeout=20)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else data.get('items', [])


def fetch_noaa_data() -> list[dict]:
    if not settings.NOAA_API_URL:
        return []
    headers = {'token': settings.NOAA_API_KEY} if settings.NOAA_API_KEY else {}
    response = requests.get(settings.NOAA_API_URL, headers=headers, timeout=20)
    response.raise_for_status()
    data = response.json()
    return data.get('features', []) if isinstance(data, dict) else []


DEFAULT_OPEN_METEO_POINTS = [
    ('Nairobi', -1.286389, 36.817223),
    ('Mombasa', -4.0435, 39.6682),
    ('Kisumu', -0.0917, 34.768),
    ('Nakuru', -0.3031, 36.08),
    ('Eldoret', 0.5143, 35.2698),
]


def _parse_open_meteo_points() -> list[tuple[str, float, float]]:
    """
    Parse OPEN_METEO_POINTS as: "Name:lat,lon;Name2:lat,lon".
    Falls back to a small default Kenya coverage list when omitted/invalid.
    """
    raw_points = (getattr(settings, 'OPEN_METEO_POINTS', '') or '').strip()
    if not raw_points:
        return DEFAULT_OPEN_METEO_POINTS

    parsed_points: list[tuple[str, float, float]] = []
    for segment in raw_points.split(';'):
        piece = segment.strip()
        if not piece or ':' not in piece:
            continue
        name, coords = piece.split(':', 1)
        if ',' not in coords:
            continue
        lat_text, lon_text = coords.split(',', 1)
        try:
            parsed_points.append((name.strip() or 'Unknown Area', float(lat_text), float(lon_text)))
        except ValueError:
            continue

    return parsed_points or DEFAULT_OPEN_METEO_POINTS


def _open_meteo_hazard_profile(temperature: float, precipitation: float, wind_speed: float) -> tuple[str, float]:
    # Convert basic weather signals into a hazard type and a normalized severity score.
    if precipitation >= 18:
        return 'flood', min(100.0, 45.0 + precipitation * 2.2 + wind_speed * 0.2)
    if precipitation >= 8:
        return 'flood', min(100.0, 35.0 + precipitation * 2.5 + wind_speed * 0.15)
    if wind_speed >= 55:
        return 'storm', min(100.0, 35.0 + wind_speed * 1.1)
    if temperature >= 34 and precipitation <= 0.5:
        return 'drought', min(100.0, 30.0 + (temperature - 30.0) * 7.0)
    return 'general', 0.0


def fetch_open_meteo_data() -> list[dict]:
    base_url = getattr(settings, 'OPEN_METEO_API_URL', '') or ''
    if not base_url:
        return []

    observations: list[dict] = []
    for location_name, latitude, longitude in _parse_open_meteo_points():
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'current': 'temperature_2m,precipitation,wind_speed_10m',
            'timezone': 'Africa/Nairobi',
        }
        response = requests.get(base_url, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        current = payload.get('current', {}) if isinstance(payload, dict) else {}

        temperature = float(current.get('temperature_2m', 0) or 0)
        precipitation = float(current.get('precipitation', 0) or 0)
        wind_speed = float(current.get('wind_speed_10m', 0) or 0)

        hazard_type, severity = _open_meteo_hazard_profile(temperature, precipitation, wind_speed)
        if severity < 45:
            continue

        observations.append(
            {
                'geometry': {'coordinates': [longitude, latitude]},
                'properties': {
                    'area': location_name,
                    'hazard_type': hazard_type,
                    'severity_index': round(severity, 2),
                    'temperature_2m': temperature,
                    'precipitation': precipitation,
                    'wind_speed_10m': wind_speed,
                },
                'source_payload': payload,
            }
        )

    return observations
