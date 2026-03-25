import logging
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point, Polygon
from apps.hazards.models import WardBoundary

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Seeds 30 high-risk ward locations across 10 major Kenyan counties.'

    def handle(self, *args, **options):
        # 10 counties, 3 wards each
        locations = [
            # Nairobi County (Floods)
            {'ward': 'Mukuru', 'county': 'Nairobi', 'lat': -1.3167, 'lon': 36.8667},
            {'ward': 'Mathare', 'county': 'Nairobi', 'lat': -1.2592, 'lon': 36.8544},
            {'ward': 'Kibera', 'county': 'Nairobi', 'lat': -1.3127, 'lon': 36.7870},

            # Mombasa County (Coastal floods/storms)
            {'ward': 'Kisauni', 'county': 'Mombasa', 'lat': -3.9833, 'lon': 39.7167},
            {'ward': 'Changamwe', 'county': 'Mombasa', 'lat': -4.0500, 'lon': 39.6333},
            {'ward': 'Likoni', 'county': 'Mombasa', 'lat': -4.0833, 'lon': 39.6667},

            # Kisumu County (Lake Victoria floods)
            {'ward': 'Nyando', 'county': 'Kisumu', 'lat': -0.1167, 'lon': 35.0167},
            {'ward': 'Muhoroni', 'county': 'Kisumu', 'lat': -0.1500, 'lon': 35.2000},
            {'ward': 'Kisumu Central', 'county': 'Kisumu', 'lat': -0.0917, 'lon': 34.7680},

            # Nakuru County (Landslides/Seismic)
            {'ward': 'Nakuru East', 'county': 'Nakuru', 'lat': -0.2833, 'lon': 36.0833},
            {'ward': 'Naivasha', 'county': 'Nakuru', 'lat': -0.7167, 'lon': 36.4333},
            {'ward': 'Subukia', 'county': 'Nakuru', 'lat': -0.1833, 'lon': 36.2833},

            # Murang'a County (Landslides)
            {'ward': 'Mathioya', 'county': 'Murang\'a', 'lat': -0.7167, 'lon': 36.9167},
            {'ward': 'Kigumo', 'county': 'Murang\'a', 'lat': -0.7833, 'lon': 37.0167},
            {'ward': 'Kangema', 'county': 'Murang\'a', 'lat': -0.7500, 'lon': 36.9667},

            # Turkana County (Drought/Flash floods)
            {'ward': 'Turkana North', 'county': 'Turkana', 'lat': 4.2500, 'lon': 35.2917},
            {'ward': 'Loima', 'county': 'Turkana', 'lat': 3.3333, 'lon': 35.3833},
            {'ward': 'Turkana Central', 'county': 'Turkana', 'lat': 3.1167, 'lon': 35.5833},

            # Kilifi County (Coastal floods/drought)
            {'ward': 'Malindi', 'county': 'Kilifi', 'lat': -3.2138, 'lon': 40.1169},
            {'ward': 'Kaloleni', 'county': 'Kilifi', 'lat': -3.8833, 'lon': 39.8500},
            {'ward': 'Ganze', 'county': 'Kilifi', 'lat': -3.5000, 'lon': 39.7833},

            # Busia County (Floods)
            {'ward': 'Budalangi', 'county': 'Busia', 'lat': 0.1333, 'lon': 34.0500},
            {'ward': 'Butula', 'county': 'Busia', 'lat': 0.5833, 'lon': 34.1167},
            {'ward': 'Nambale', 'county': 'Busia', 'lat': 0.5000, 'lon': 34.2333},

            # Tana River County (River floods)
            {'ward': 'Tana Delta', 'county': 'Tana River', 'lat': -2.0000, 'lon': 40.2500},
            {'ward': 'Bura', 'county': 'Tana River', 'lat': -1.1000, 'lon': 39.9500},
            {'ward': 'Garsen', 'county': 'Tana River', 'lat': -2.2667, 'lon': 40.1167},

            # Mandera County (Drought/Flash floods)
            {'ward': 'Mandera Central', 'county': 'Mandera', 'lat': 3.9333, 'lon': 41.8667},
            {'ward': 'Lafey', 'county': 'Mandera', 'lat': 3.8167, 'lon': 41.2000},
            {'ward': 'Banissa', 'county': 'Mandera', 'lat': 3.4833, 'lon': 41.3167},
        ]

        created_count = 0
        updated_count = 0

        from django.contrib.gis.geos import MultiPolygon
        
        for loc in locations:
            # Create a 5km bounding box around the point
            point = Point(loc['lon'], loc['lat'], srid=4326)
            
            # Simple roughly 5km buffer approximation (0.045 degrees is ~5km at equator)
            buffer = point.buffer(0.045)
            # Ensure it's a MultiPolygon
            if buffer.geom_type == 'MultiPolygon':
                geom = buffer
            else:
                geom = MultiPolygon(buffer, srid=4326)
                
            ward, created = WardBoundary.objects.update_or_create(
                ward_name=loc['ward'],
                county_name=loc['county'],
                defaults={
                    'geometry': geom
                }
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created: {loc['ward']} ({loc['county']})"))
            else:
                updated_count += 1
                self.stdout.write(f"Updated: {loc['ward']} ({loc['county']})")

        self.stdout.write(self.style.SUCCESS(f"\nSuccessfully seeded {created_count} new and updated {updated_count} wards."))
