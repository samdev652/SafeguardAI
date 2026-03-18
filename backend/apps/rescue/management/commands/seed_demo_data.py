from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.rescue.models import RescueUnit
from apps.hazards.models import RiskAssessment


class Command(BaseCommand):
    help = 'Seed sample rescue units and risk assessments for local testing'

    def handle(self, *args, **options):
        RescueUnit.objects.get_or_create(
            name='Nairobi Fire Station',
            defaults={
                'unit_type': RescueUnit.TYPE_FIRE,
                'phone_number': '+254700000001',
                'county': 'Nairobi',
                'ward_name': 'Westlands',
                'location': Point(36.8172, -1.2648, srid=4326),
            },
        )
        RescueUnit.objects.get_or_create(
            name='Aga Khan Hospital',
            defaults={
                'unit_type': RescueUnit.TYPE_HOSPITAL,
                'phone_number': '+254700000002',
                'county': 'Nairobi',
                'ward_name': 'Parklands',
                'location': Point(36.8197, -1.2606, srid=4326),
            },
        )
        RescueUnit.objects.get_or_create(
            name='Parklands Police Post',
            defaults={
                'unit_type': RescueUnit.TYPE_POLICE,
                'phone_number': '+254700000003',
                'county': 'Nairobi',
                'ward_name': 'Parklands',
                'location': Point(36.8105, -1.2662, srid=4326),
            },
        )
        RescueUnit.objects.get_or_create(
            name='Kenya Red Cross Nairobi',
            defaults={
                'unit_type': RescueUnit.TYPE_REDCROSS,
                'phone_number': '+254700000004',
                'county': 'Nairobi',
                'ward_name': 'Starehe',
                'location': Point(36.8254, -1.2862, srid=4326),
            },
        )

        RiskAssessment.objects.create(
            ward_name='Westlands',
            village_name='Kangemi',
            hazard_type='flood',
            risk_level='medium',
            risk_score=58.0,
            guidance_en='Avoid river crossings and prepare emergency supplies.',
            guidance_sw='Epuka kuvuka mito na andaa vifaa vya dharura.',
            summary='Moderate flood risk expected in low-lying areas.',
            location=Point(36.744, -1.267, srid=4326),
        )
        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully.'))
