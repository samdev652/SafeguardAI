from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.citizens.models import CitizenProfile
from apps.rescue.models import RescueUnit


class RescueRoutingTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='citizen@example.com', password='StrongPass123')
        self.profile = CitizenProfile.objects.create(
            user=self.user,
            full_name='Test Citizen',
            phone_number='+254700123456',
            ward_name='Westlands',
            village_name='Kangemi',
            preferred_language='en',
            location=Point(36.81, -1.27, srid=4326),
            channels=['sms'],
        )

        RescueUnit.objects.create(
            name='Westlands Fire',
            unit_type='fire_station',
            phone_number='+254700000001',
            county='Nairobi',
            ward_name='Westlands',
            location=Point(36.80, -1.268, srid=4326),
        )
        RescueUnit.objects.create(
            name='Nearby Hospital',
            unit_type='hospital',
            phone_number='+254700000002',
            county='Nairobi',
            ward_name='Parklands',
            location=Point(36.82, -1.266, srid=4326),
        )
        RescueUnit.objects.create(
            name='Police Post',
            unit_type='police_post',
            phone_number='+254700000003',
            county='Nairobi',
            ward_name='Parklands',
            location=Point(36.825, -1.268, srid=4326),
        )

    def test_nearest_units_returns_three(self):
        url = reverse('rescue-units-nearest')
        response = self.client.get(url, {'latitude': -1.27, 'longitude': 36.81})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

    def test_sos_dispatch_requires_auth_and_returns_units(self):
        url = reverse('sos-dispatch')
        unauthorized = self.client.post(url, {'description': 'Flood rescue needed'}, format='json')
        self.assertEqual(unauthorized.status_code, 401)

        self.client.force_authenticate(user=self.user)
        authorized = self.client.post(url, {'description': 'Flood rescue needed'}, format='json')
        self.assertEqual(authorized.status_code, 201)
        self.assertEqual(authorized.data['status'], 'dispatched')
        self.assertEqual(len(authorized.data['dispatched_units']), 3)
