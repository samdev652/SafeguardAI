
import json
import random
from datetime import datetime
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.hazards.models import RiskAssessment, WardBoundary
from apps.hazards.services import GeminiRiskAnalyzer


class Command(BaseCommand):
    help = 'Simulate real-time risk events for all wards via GeminiRiskAnalyzer.'

    def handle(self, *args, **options):
        wards = WardBoundary.objects.all()
        count = 0
        gemini = GeminiRiskAnalyzer()
        for ward in wards:
            observation = {
                'ward_name': ward.ward_name,
                'county_name': ward.county_name,
                'hazard_type': random.choice(['flood', 'landslide', 'drought', 'earthquake']),
                'severity_index': random.uniform(0, 100),
                'temperature_2m': random.uniform(18, 38),
                'precipitation': random.uniform(0, 30),
                'wind_speed_10m': random.uniform(0, 80),
            }
            # All Gemini calls routed through the central analyzer
            result = gemini.analyze(observation)
            if not result:
                continue

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
