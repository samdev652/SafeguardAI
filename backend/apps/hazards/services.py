import json
import re
import requests
from django.conf import settings


class GeminiRiskAnalyzer:
    _ALLOWED_LEVELS = {'safe', 'medium', 'high', 'critical'}


    def analyze(self, observation: dict) -> dict:
        import logging
        if not settings.GEMINI_API_KEY:
            return self._fallback(observation)

        # --- 1. Scientific rainfall and soil moisture thresholds ---
        hazard_thresholds = {
            'flood': 'Flood risk: precipitation > 18mm in 24h or soil moisture > 0.38 m3/m3',
            'landslide': 'Landslide risk: precipitation > 12mm in 24h and soil moisture > 0.32 m3/m3 on slopes',
            'drought': 'Drought risk: soil moisture < 0.18 m3/m3 and rainfall < 2mm in 7 days',
            'earthquake': 'Earthquake risk: only above medium in seismic counties (e.g. Rift Valley); never high/critical elsewhere',
        }
        hazard_type = observation.get('hazard_type', '').lower()
        threshold_text = hazard_thresholds.get(hazard_type, '')

        # --- 2. Add current month and Kenya's seasonal rainfall context ---
        from datetime import datetime
        month = datetime.now().strftime('%B')
        kenya_seasons = (
            'Kenya rainfall context: March-May (long rains), Oct-Dec (short rains), Jan-Feb/Jun-Sep (dry). '
            'Compare current month to normal rainfall for this area.'
        )

        # --- 3. Hard rules section ---
        hard_rules = (
            '\nHARD RULES:\n'
            '- Never return high or critical risk without citing a specific number from the weather data.\n'
            '- Never invent data values.\n'
            '- Never predict earthquake risk above medium for non-seismic Kenyan counties.\n'
            '- If weather data is missing, return low risk and note missing data, do not guess.'
        )

        prompt = (
            f'You are a disaster risk analyst for Kenya. It is {month}. {kenya_seasons}\n'
            f'{threshold_text}\n'
            'Return JSON only with keys risk_level, risk_score, guidance_en, guidance_sw, summary, confidence.\n'
            f'Input data: {json.dumps(observation)}\n'
            f'{hard_rules}'
        )

        url = (
            f'https://generativelanguage.googleapis.com/v1beta/models/'
            f'{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}'
        )
        payload = {
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'responseMimeType': 'application/json'},
        }

        try:
            response = requests.post(url, json=payload, timeout=20)
            response.raise_for_status()
            text = response.json()['candidates'][0]['content']['parts'][0]['text']
            parsed = self._parse_structured_response(text)
            # --- 4. Confidence threshold check ---
            confidence = parsed.get('confidence')
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 0.0
            orig_level = parsed.get('risk_level', '').lower()
            downgrade_map = {'critical': 'high', 'high': 'medium', 'medium': 'safe', 'safe': 'safe'}
            if confidence < 0.65:
                logging.warning(f"Gemini assessment discarded (confidence={confidence:.2f}): {parsed}")
                return self._fallback(observation)
            elif confidence < 0.75:
                downgraded = downgrade_map.get(orig_level, 'safe')
                if downgraded != orig_level:
                    logging.info(f"Gemini assessment downgraded from {orig_level} to {downgraded} (confidence={confidence:.2f}): {parsed}")
                    parsed['risk_level'] = downgraded
            return self._normalize_analysis(parsed, observation)
        except Exception as e:
            logging.error(f"Gemini analysis error: {e}")
            return self._fallback(observation)

    def _parse_structured_response(self, text: str) -> dict:
        raw = str(text or '').strip()
        if not raw:
            raise ValueError('Empty model response')

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # Handle model responses that include fenced JSON.
        match = re.search(r'\{[\s\S]*\}', raw)
        if not match:
            raise ValueError('No JSON object found in model response')
        parsed = json.loads(match.group(0))
        if not isinstance(parsed, dict):
            raise ValueError('Model response JSON is not an object')
        return parsed

    def _normalize_analysis(self, parsed: dict, observation: dict) -> dict:
        severity = float(observation.get('severity_index', 0) or 0)

        risk_level = str(parsed.get('risk_level', '')).strip().lower()
        if risk_level not in self._ALLOWED_LEVELS:
            risk_level = self._fallback(observation)['risk_level']

        risk_score = parsed.get('risk_score', severity)
        try:
            risk_score = max(0.0, min(100.0, float(risk_score)))
        except (TypeError, ValueError):
            risk_score = severity

        guidance_en = str(parsed.get('guidance_en') or '').strip()
        guidance_sw = str(parsed.get('guidance_sw') or '').strip()
        summary = str(parsed.get('summary') or '').strip()

        fallback = self._fallback(observation)
        return {
            'risk_level': risk_level,
            'risk_score': risk_score,
            'guidance_en': guidance_en or fallback['guidance_en'],
            'guidance_sw': guidance_sw or fallback['guidance_sw'],
            'summary': summary or fallback['summary'],
        }

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


    def chat(self, messages, language='en'):
        """
        messages: list of {role: 'system'|'user'|'assistant', content: str}
        language: 'en' or 'sw'
        """
        import requests
        import json
        from django.conf import settings
        prompt_parts = []
        for m in messages:
            if m['role'] == 'system':
                prompt_parts.append(f"[SYSTEM]\n{m['content']}")
            elif m['role'] == 'user':
                prompt_parts.append(f"[USER]\n{m['content']}")
            elif m['role'] == 'assistant':
                prompt_parts.append(f"[ASSISTANT]\n{m['content']}")
        prompt = '\n'.join(prompt_parts)
        url = (
            f'https://generativelanguage.googleapis.com/v1beta/models/'
            f'{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}'
        )
        payload = {
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'responseMimeType': 'text/plain'},
        }
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            text = response.json()['candidates'][0]['content']['parts'][0]['text']
            return text.strip()
        except Exception as e:
            return 'Sorry, I could not process your request at this time.'


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
