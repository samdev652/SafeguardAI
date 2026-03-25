import json
import logging
import re
import requests
from datetime import datetime
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class GeminiRiskAnalyzer:
    _ALLOWED_LEVELS = {'safe', 'medium', 'high', 'critical'}
    _DOWNGRADE_MAP = {'critical': 'high', 'high': 'medium', 'medium': 'safe', 'safe': 'safe'}

    _HAZARD_THRESHOLDS = {
        'flood': (
            'Flood risk thresholds:\n'
            '  - Medium: precipitation 10–18 mm/24h OR soil moisture 0.30–0.38 m³/m³\n'
            '  - High: precipitation 18–35 mm/24h OR soil moisture > 0.38 m³/m³\n'
            '  - Critical: precipitation > 35 mm/24h AND soil moisture > 0.42 m³/m³'
        ),
        'landslide': (
            'Landslide risk thresholds:\n'
            '  - Medium: precipitation 8–12 mm/24h and soil moisture 0.28–0.32 m³/m³ on slopes\n'
            '  - High: precipitation 12–20 mm/24h and soil moisture > 0.32 m³/m³ on slopes\n'
            '  - Critical: precipitation > 20 mm/24h and soil moisture > 0.36 m³/m³ on steep terrain'
        ),
        'drought': (
            'Drought risk thresholds:\n'
            '  - Medium: soil moisture 0.15–0.18 m³/m³ and rainfall < 5 mm in 7 days\n'
            '  - High: soil moisture < 0.15 m³/m³ and rainfall < 2 mm in 7 days\n'
            '  - Critical: soil moisture < 0.10 m³/m³ and rainfall 0 mm in 14 days'
        ),
        'earthquake': (
            'Earthquake risk thresholds:\n'
            '  - ONLY seismic zones (Rift Valley counties, Nairobi, Mombasa, Kwale, Kilifi, '
            'Tana River, Lamu) may exceed medium.\n'
            '  - All other Kenyan counties: NEVER above medium regardless of data.'
        ),
        'storm': (
            'Storm risk thresholds:\n'
            '  - Medium: wind speed 40–55 km/h\n'
            '  - High: wind speed 55–80 km/h with gusts\n'
            '  - Critical: wind speed > 80 km/h or confirmed tornado/cyclone conditions'
        ),
    }

    _SEISMIC_ZONES = {
        'nakuru', 'narok', 'kajiado', 'baringo', 'elgeyo marakwet', 'turkana',
        'west pokot', 'samburu', 'laikipia', 'nyandarua', 'kericho', 'bomet',
        'nairobi', 'mombasa', 'kwale', 'kilifi', 'tana river', 'lamu',
    }

    # ------------------------------------------------------------------ #
    #  Rate limiting — one Gemini call per ward+hazard within N minutes   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _rate_limit_key(ward_name: str, hazard_type: str) -> str:
        ward = (ward_name or 'unknown').strip().lower().replace(' ', '_')
        hazard = (hazard_type or 'unknown').strip().lower()
        return f'gemini_rl:{ward}:{hazard}'

    def _is_rate_limited(self, observation: dict) -> bool:
        key = self._rate_limit_key(
            observation.get('ward_name', ''),
            observation.get('hazard_type', ''),
        )
        return cache.get(key) is not None

    def _set_rate_limit(self, observation: dict) -> None:
        key = self._rate_limit_key(
            observation.get('ward_name', ''),
            observation.get('hazard_type', ''),
        )
        timeout = getattr(settings, 'GEMINI_RATE_LIMIT_MINUTES', 60) * 60
        cache.set(key, True, timeout=timeout)

    # ------------------------------------------------------------------ #
    #  Gemini HTTP helper                                                 #
    # ------------------------------------------------------------------ #

    def _gemini_call(self, prompt: str, response_mime: str = 'application/json', timeout: int = 20) -> str:
        url = (
            f'https://generativelanguage.googleapis.com/v1beta/models/'
            f'{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}'
        )
        payload = {
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'responseMimeType': response_mime},
        }
        try:
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            logger.info('AI prediction handled by: Gemini')
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                logger.warning('Gemini 429 Quota Exceeded. Falling back to Groq.')
                return self._groq_call(prompt, response_mime, timeout)
            raise

    def _groq_call(self, prompt: str, response_mime: str = 'application/json', timeout: int = 20) -> str:
        url = 'https://api.groq.com/openai/v1/chat/completions'
        headers = {
            'Authorization': f'Bearer {settings.GROQ_API_KEY}',
            'Content-Type': 'application/json',
        }
        response_format = {"type": "json_object"} if response_mime == 'application/json' else {"type": "text"}
        payload = {
            'model': settings.GROQ_MODEL,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.1,
            'response_format': response_format,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        logger.info('AI prediction handled by: Groq (Fallback)')
        return response.json()['choices'][0]['message']['content']

    # ------------------------------------------------------------------ #
    #  Second-pass verification for high/critical assessments             #
    # ------------------------------------------------------------------ #

    def _verify_assessment(self, observation: dict, first_result: dict) -> dict:
        """Make a second independent Gemini call to verify a high/critical assessment.

        If the verification disagrees (returns a lower risk level), downgrade
        by one step.  Returns the potentially-adjusted result dict.
        """
        risk_level = first_result.get('risk_level', '').lower()
        if risk_level not in ('high', 'critical'):
            return first_result

        verification_prompt = (
            'You are an independent disaster risk reviewer for Kenya.\n'
            'A previous analysis produced the assessment below. Your job is to '
            'verify whether the risk level is justified by the raw weather data.\n\n'
            f'Weather observation: {json.dumps(observation)}\n'
            f'Previous assessment: {json.dumps(first_result)}\n\n'
            'Return JSON only with keys: verified (boolean), recommended_risk_level '
            '(safe|medium|high|critical), reason (string).\n'
            'If the data does NOT support the claimed risk level, set verified=false '
            'and lower recommended_risk_level accordingly.'
        )

        try:
            text = self._gemini_call(verification_prompt)
            verification = self._parse_structured_response(text)

            verified = verification.get('verified')
            if isinstance(verified, str):
                verified = verified.lower() in ('true', '1', 'yes')

            recommended = str(verification.get('recommended_risk_level', '')).strip().lower()
            reason = str(verification.get('reason', '')).strip()

            if not verified and recommended in self._ALLOWED_LEVELS:
                # Only downgrade (never upgrade from verification)
                level_order = ['safe', 'medium', 'high', 'critical']
                if level_order.index(recommended) < level_order.index(risk_level):
                    downgraded = self._DOWNGRADE_MAP.get(risk_level, risk_level)
                    logger.warning(
                        'Gemini verification DISAGREED: %s → %s (recommended=%s, reason=%s) '
                        'for ward=%s hazard=%s',
                        risk_level, downgraded, recommended, reason,
                        observation.get('ward_name'), observation.get('hazard_type'),
                    )
                    first_result['risk_level'] = downgraded
                    return first_result

            logger.info(
                'Gemini verification AGREED with %s for ward=%s hazard=%s',
                risk_level, observation.get('ward_name'), observation.get('hazard_type'),
            )
        except Exception as exc:
            logger.error('Gemini verification call failed: %s', exc)
            # On verification failure, conservatively downgrade
            downgraded = self._DOWNGRADE_MAP.get(risk_level, risk_level)
            logger.warning(
                'Verification unavailable — conservatively downgrading %s → %s '
                'for ward=%s hazard=%s',
                risk_level, downgraded,
                observation.get('ward_name'), observation.get('hazard_type'),
            )
            first_result['risk_level'] = downgraded

        return first_result

    # ------------------------------------------------------------------ #
    #  Main analysis entry point                                          #
    # ------------------------------------------------------------------ #

    def analyze(self, observation: dict, bypass_rate_limit: bool = False) -> dict:
        if not settings.GEMINI_API_KEY:
            return self._fallback(observation)

        # --- Rate limiting ---
        if not bypass_rate_limit and self._is_rate_limited(observation):
            logger.info(
                'Gemini rate-limited for ward=%s hazard=%s — returning fallback',
                observation.get('ward_name'), observation.get('hazard_type'),
            )
            return self._fallback(observation)

        # --- Build prompt with scientific thresholds + seasonal context ---
        hazard_type = observation.get('hazard_type', '').lower()
        threshold_text = self._HAZARD_THRESHOLDS.get(hazard_type, '')

        month = datetime.now().strftime('%B')
        kenya_seasons = (
            'Kenya rainfall context: March-May (long rains, heaviest nationwide), '
            'Oct-Dec (short rains), Jan-Feb/Jun-Sep (dry seasons). '
            f'Current month is {month}. Compare observed values to seasonal norms '
            'for this specific area before assigning risk.'
        )

        seismic_note = ''
        if hazard_type == 'earthquake':
            ward = observation.get('ward_name', '').lower()
            if not any(zone in ward for zone in self._SEISMIC_ZONES):
                seismic_note = (
                    '\nIMPORTANT: This location is NOT in a known Kenyan seismic zone. '
                    'You MUST NOT return risk above medium.'
                )

        hard_rules = (
            '\n\nHARD RULES (you MUST follow these):\n'
            '1. NEVER return high or critical risk without citing a specific number '
            '   from the input weather data that exceeds the threshold above.\n'
            '2. NEVER invent or assume data values not present in the input.\n'
            '3. NEVER predict earthquake risk above medium for counties outside '
            '   the Rift Valley, Nairobi, and coastal seismic zones '
            '   (Mombasa, Kwale, Kilifi, Tana River, Lamu).\n'
            '4. If weather data is missing or incomplete, return risk_level "safe" '
            '   and note the missing data in the summary. Do NOT guess.\n'
            '5. The confidence field must be a float between 0.0 and 1.0 reflecting '
            '   how certain you are given the available data.'
        )

        prompt = (
            f'You are a disaster risk analyst for Kenya. It is {month}.\n'
            f'{kenya_seasons}\n\n'
            f'SCIENTIFIC THRESHOLDS FOR {hazard_type.upper()}:\n{threshold_text}\n'
            f'{seismic_note}\n\n'
            'Return JSON only with keys: risk_level (safe|medium|high|critical), '
            'risk_score (0-100), guidance_en, guidance_sw, summary, confidence (0.0-1.0).\n\n'
            f'Input weather data: {json.dumps(observation)}'
            f'{hard_rules}'
        )

        try:
            text = self._gemini_call(prompt)
            parsed = self._parse_structured_response(text)

            # --- Confidence threshold check ---
            confidence = parsed.get('confidence')
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 0.0

            orig_level = parsed.get('risk_level', '').lower()

            if confidence < 0.65:
                logger.warning(
                    'Gemini assessment DISCARDED (confidence=%.2f) for ward=%s hazard=%s: %s',
                    confidence, observation.get('ward_name'),
                    observation.get('hazard_type'), parsed,
                )
                return self._fallback(observation)

            if confidence < 0.75:
                downgraded = self._DOWNGRADE_MAP.get(orig_level, 'safe')
                if downgraded != orig_level:
                    logger.info(
                        'Gemini assessment DOWNGRADED %s → %s (confidence=%.2f) '
                        'for ward=%s hazard=%s',
                        orig_level, downgraded, confidence,
                        observation.get('ward_name'), observation.get('hazard_type'),
                    )
                    parsed['risk_level'] = downgraded

            result = self._normalize_analysis(parsed, observation)

            # --- Second verification call for high/critical ---
            result = self._verify_assessment(observation, result)

            # --- Record rate limit after successful call ---
            self._set_rate_limit(observation)

            return result

        except Exception as e:
            logger.error('Gemini analysis error: %s', e)
            return None

    # ------------------------------------------------------------------ #
    #  Response parsing & normalization                                    #
    # ------------------------------------------------------------------ #

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
    # Nairobi
    ('Westlands', -1.2648, 36.8172),
    ('Kibra', -1.3107, 36.7878),
    ('Langata', -1.3667, 36.7333),
    # Mombasa
    ('Mvita', -4.0435, 39.6682),
    ('Nyali', -4.0226, 39.7127),
    # Kisumu
    ('Kisumu Central', -0.0917, 34.768),
    ('Kondele', -0.08, 34.75),
    # Nakuru
    ('Nakuru Town East', -0.2833, 36.0833),
    ('Njoro', -0.331, 35.946),
    ('Naivasha', -0.7167, 36.4333),
    # Murang'a
    ('Kangema', -0.685, 36.965),
    ('Kiharu', -0.718, 37.053),
    # Turkana
    ('Turkana Central', 3.1166, 35.5966),
    # Kilifi
    ('Kilifi North', -3.6333, 39.85),
    ('Malindi Town', -3.2138, 40.1169),
    # Busia
    ('Teso North', 0.4605, 34.1296),
    ('Budalangi', 0.1133, 34.0833),
    # Tana River
    ('Garsen', -2.2833, 40.1167),
    ('Bura', -1.1, 39.95),
    # Mandera
    ('Mandera East', 3.9373, 41.8569),
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
