import json
import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.hazards.models import RiskAssessment

# Example hazards and guidance
HAZARD_TYPES = [
    ('flood', 'Avoid flooded areas.'),
    ('landslide', 'Stay away from slopes.'),
    ('drought', 'Conserve water.'),
    ('earthquake', 'Drop, cover, and hold.'),
]

WARD_DATA = [
    {
        "ward_name": "Westlands",
        "county_name": "Nairobi",
        "center": (36.8075, -1.2675),
    },
    {
        "ward_name": "Parklands/Highridge",
        "county_name": "Nairobi",
        "center": (36.825, -1.269),
    },
    {
        "ward_name": "Starehe",
        "county_name": "Nairobi",
        "center": (36.835, -1.2905),
    },
]

class Command(BaseCommand):
    help = 'Simulate real-time risk events for all wards.'

    def handle(self, *args, **options):
        now = datetime.now()
        for ward in WARD_DATA:
            hazard, guidance = random.choice(HAZARD_TYPES)
            risk_level = random.choices(
                ['safe', 'medium', 'high', 'critical'],
                weights=[0.5, 0.2, 0.2, 0.1],
                k=1
            )[0]
            risk_score = random.uniform(10, 99) if risk_level != 'safe' else random.uniform(0, 20)
            summary = f"AI detected {hazard} risk in {ward['ward_name']} ({risk_level})"
            location = Point(ward['center'][0], ward['center'][1])
            RiskAssessment.objects.create(
                ward_name=ward['ward_name'],
                village_name='',
                hazard_type=hazard,
                risk_level=risk_level,
                risk_score=risk_score,
                guidance_en=guidance,
                guidance_sw=guidance,  # For demo
                summary=summary,
                location=location,
            )
        self.stdout.write(self.style.SUCCESS('Simulated risk events for all wards.'))
