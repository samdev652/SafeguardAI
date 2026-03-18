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
