"""Seed 20+ real Kenyan ward locations across 10 counties for demo coverage."""
import logging
from django.contrib.gis.geos import MultiPolygon, Polygon, Point
from django.core.management.base import BaseCommand
from apps.hazards.models import WardBoundary

logger = logging.getLogger(__name__)

# Real ward centroids — each gets a tiny bounding-box polygon so the
# geometry__intersects lookup used by the ingestion pipeline works.
WARDS = [
    # County           Ward               Lat        Lon
    ('Nairobi',        'Westlands',       -1.2648,   36.8172),
    ('Nairobi',        'Kibra',           -1.3107,   36.7878),
    ('Mombasa',        'Mvita',           -4.0435,   39.6682),
    ('Mombasa',        'Nyali',           -4.0226,   39.7127),
    ('Kisumu',         'Kisumu Central',  -0.0917,   34.7680),
    ('Kisumu',         'Kondele',         -0.0800,   34.7500),
    ('Nakuru',         'Nakuru Town East',-0.2833,   36.0833),
    ('Nakuru',         'Njoro',           -0.3310,   35.9460),
    ("Murang'a",       'Kangema',         -0.6850,   36.9650),
    ("Murang'a",       'Kiharu',          -0.7180,   37.0530),
    ('Turkana',        'Turkana Central', 3.1166,    35.5966),
    ('Turkana',        'Lodwar Township', 3.1191,    35.5979),
    ('Kilifi',         'Kilifi North',    -3.6333,   39.8500),
    ('Kilifi',         'Malindi Town',    -3.2138,   40.1169),
    ('Busia',          'Teso North',      0.4605,    34.1296),
    ('Busia',          'Budalangi',       0.1133,    34.0833),
    ('Tana River',     'Garsen',          -2.2833,   40.1167),
    ('Tana River',     'Bura',            -1.1000,   39.9500),
    ('Mandera',        'Mandera East',    3.9373,    41.8569),
    ('Mandera',        'Mandera West',    3.9200,    41.2000),
    # Extra wards for richer coverage
    ('Nairobi',        'Starehe',         -1.2864,   36.8254),
    ('Nairobi',        'Langata',         -1.3667,   36.7333),
    ('Nakuru',         'Naivasha',        -0.7167,   36.4333),
]


def _tiny_polygon(lat: float, lon: float) -> MultiPolygon:
    """Create a small ~200m square polygon around the centroid."""
    d = 0.001  # ~111m at the equator
    ring = [
        (lon - d, lat - d),
        (lon + d, lat - d),
        (lon + d, lat + d),
        (lon - d, lat + d),
        (lon - d, lat - d),
    ]
    return MultiPolygon(Polygon(ring, srid=4326), srid=4326)


class Command(BaseCommand):
    help = 'Seed 20+ real Kenyan ward boundaries for demo/investor coverage.'

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        for county, ward_name, lat, lon in WARDS:
            _, was_created = WardBoundary.objects.get_or_create(
                ward_name=ward_name,
                defaults={
                    'county_name': county,
                    'geometry': _tiny_polygon(lat, lon),
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Ward seeding complete: {created} created, {skipped} already existed. '
                f'Total wards: {WardBoundary.objects.count()}'
            )
        )
