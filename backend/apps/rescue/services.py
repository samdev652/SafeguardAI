from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from .models import RescueUnit


def find_nearest_rescue_units(longitude: float, latitude: float, unit_type: str | None = None):
    point = Point(longitude, latitude, srid=4326)
    queryset = RescueUnit.objects.filter(is_active=True)
    if unit_type:
        queryset = queryset.filter(unit_type=unit_type)

    # GeoDjango compiles this to ST_Distance on PostGIS.
    return queryset.annotate(distance_m=Distance('location', point)).order_by('distance_m')[:3]
