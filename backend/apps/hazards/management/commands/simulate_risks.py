
import json
import random
from datetime import datetime
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.hazards.models import RiskAssessment, WardBoundary
from apps.hazards.services import GeminiRiskAnalyzer



class Command(BaseCommand):
    help = 'Simulate real-time risk events for all wards.'

    def handle(self, *args, **options):
        now = datetime.now()
        wards = WardBoundary.objects.all()
        count = 0
        gemini = GeminiRiskAnalyzer()
        for ward in wards:
            # Simulate weather data for the ward
            observation = {
                'ward_name': ward.ward_name,
                'county_name': ward.county_name,
                'hazard_type': random.choice(['flood', 'landslide', 'drought', 'earthquake']),
                'severity_index': random.uniform(0, 100),
                'temperature_2m': random.uniform(18, 38),
                'precipitation': random.uniform(0, 30),
                'wind_speed_10m': random.uniform(0, 80),
            }
            # First Gemini call
            result = gemini.analyze(observation)
            risk_level = result['risk_level']
            # Only verify if high or critical
            if risk_level in ('high', 'critical'):
                verification_prompt = (
                    "You are an independent disaster risk reviewer. Review the following weather data and the first risk assessment. "
                    "Respond ONLY with 'agree' or 'disagree' and a one sentence reason.\n"
                    f"Weather data: {json.dumps(observation)}\n"
                    f"First assessment: {json.dumps(result)}"
                )
                # Make a second Gemini call for verification
                verification = self._gemini_verify(verification_prompt)
                if verification:
                    verdict = verification.get('verdict', '').strip().lower()
                    reason = verification.get('reason', '')
                    if verdict == 'disagree':
                        # Downgrade risk level by one step
                        if risk_level == 'critical':
                            result['risk_level'] = 'high'
                        elif risk_level == 'high':
                            result['risk_level'] = 'medium'
                        # Optionally, append reason to summary
                        result['summary'] += f" (Gemini disagreed: {reason})"
            # Save only after verification
            centroid = ward.geometry.centroid
            RiskAssessment.objects.create(
                ward_name=ward.ward_name,
                village_name='',
                hazard_type=observation['hazard_type'],
                risk_level=result['risk_level'],
                risk_score=result['risk_score'],
                guidance_en=result['guidance_en'],
                guidance_sw=result['guidance_sw'],
                summary=result['summary'],
                location=centroid,
            )
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Simulated risk events for {count} wards.'))

    def _gemini_verify(self, prompt: str) -> dict:
        # Use Gemini API directly for verification, expecting a simple agree/disagree JSON
        from django.conf import settings
        import requests
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
            # Try to parse as JSON: {"verdict": "agree", "reason": "..."}
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return None
