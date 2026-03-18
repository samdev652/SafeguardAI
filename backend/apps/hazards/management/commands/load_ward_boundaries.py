import json
from pathlib import Path
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.core.management.base import BaseCommand, CommandError
from apps.hazards.models import WardBoundary


class Command(BaseCommand):
    help = 'Load ward boundaries GeoJSON into WardBoundary model'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, required=True, help='Path to GeoJSON file')

    def handle(self, *args, **options):
        file_path = Path(options['file'])
        if not file_path.exists():
            raise CommandError(f'GeoJSON file not found: {file_path}')

        with file_path.open('r', encoding='utf-8') as fh:
            payload = json.load(fh)

        features = payload.get('features', [])
        if not features:
            raise CommandError('No features found in GeoJSON payload')

        created = 0
        updated = 0

        for feature in features:
            properties = feature.get('properties', {})
            ward_name = (properties.get('ward_name') or properties.get('ward') or '').strip()
            county_name = (properties.get('county_name') or properties.get('county') or 'Unknown').strip()
            if not ward_name:
                continue

            geometry = GEOSGeometry(json.dumps(feature.get('geometry')))
            if isinstance(geometry, Polygon):
                geometry = MultiPolygon(geometry)

            obj, was_created = WardBoundary.objects.update_or_create(
                ward_name=ward_name,
                defaults={
                    'county_name': county_name,
                    'geometry': geometry,
                    'metadata': {k: v for k, v in properties.items() if k not in ['ward_name', 'ward', 'county_name', 'county']},
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'Ward boundaries load complete. created={created}, updated={updated}'))
