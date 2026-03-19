from datetime import timedelta

from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.utils import timezone

from apps.citizens.models import CitizenProfile


def find_nearest_rescue_units(longitude: float, latitude: float, unit_type: str | None = None):
    point = Point(longitude, latitude, srid=4326)
    stale_threshold = timezone.now() - timedelta(minutes=10)
    queryset = CitizenProfile.objects.filter(
        role=CitizenProfile.ROLE_RESCUE_TEAM,
        user__is_active=True,
        is_available_for_dispatch=True,
        last_location_update__gte=stale_threshold,
    )
    if unit_type:
        queryset = queryset.filter(responder_unit_type=unit_type)

    # GeoDjango compiles this to ST_Distance on PostGIS.
    return queryset.annotate(distance_m=Distance('location', point)).order_by('distance_m')[:3]
