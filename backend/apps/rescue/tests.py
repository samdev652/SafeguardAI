from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.citizens.models import CitizenProfile


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

        self._create_responder(
            email='fire@example.com',
            full_name='Westlands Fire',
            phone='+254700000001',
            ward='Westlands',
            point=Point(36.80, -1.268, srid=4326),
            unit_type=CitizenProfile.RESPONDER_TYPE_FIRE,
        )
        self._create_responder(
            email='hospital@example.com',
            full_name='Nearby Hospital',
            phone='+254700000002',
            ward='Parklands',
            point=Point(36.82, -1.266, srid=4326),
            unit_type=CitizenProfile.RESPONDER_TYPE_HOSPITAL,
        )
        self._create_responder(
            email='police@example.com',
            full_name='Police Post',
            phone='+254700000003',
            ward='Parklands',
            point=Point(36.825, -1.268, srid=4326),
            unit_type=CitizenProfile.RESPONDER_TYPE_POLICE,
        )

    def _create_responder(self, email: str, full_name: str, phone: str, ward: str, point: Point, unit_type: str):
        user = User.objects.create_user(username=email, password='StrongPass123')
        return CitizenProfile.objects.create(
            user=user,
            full_name=full_name,
            phone_number=phone,
            ward_name=ward,
            village_name='',
            preferred_language='en',
            role=CitizenProfile.ROLE_RESCUE_TEAM,
            responder_unit_type=unit_type,
            is_available_for_dispatch=True,
            last_location_update=timezone.now(),
            location=point,
            channels=['sms'],
        )

    def test_nearest_units_returns_three(self):
        url = reverse('rescue-units-nearest')
        response = self.client.get(url, {'latitude': -1.27, 'longitude': 36.81})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

    def test_nearest_units_excludes_unavailable_responders(self):
        responder = CitizenProfile.objects.filter(role=CitizenProfile.ROLE_RESCUE_TEAM).first()
        responder.is_available_for_dispatch = False
        responder.save(update_fields=['is_available_for_dispatch'])

        url = reverse('rescue-units-nearest')
        response = self.client.get(url, {'latitude': -1.27, 'longitude': 36.81})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_nearest_units_excludes_stale_locations(self):
        responder = CitizenProfile.objects.filter(role=CitizenProfile.ROLE_RESCUE_TEAM).first()
        responder.last_location_update = timezone.now() - timedelta(minutes=30)
        responder.save(update_fields=['last_location_update'])

        url = reverse('rescue-units-nearest')
        response = self.client.get(url, {'latitude': -1.27, 'longitude': 36.81})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_responder_heartbeat_updates_location(self):
        responder_user = User.objects.create_user(username='team@example.com', password='StrongPass123')
        CitizenProfile.objects.create(
            user=responder_user,
            full_name='Responder One',
            phone_number='+254700999999',
            ward_name='Westlands',
            village_name='Kangemi',
            preferred_language='en',
            role=CitizenProfile.ROLE_RESCUE_TEAM,
            location=Point(36.9, -1.3, srid=4326),
            channels=['sms'],
        )

        self.client.force_authenticate(user=responder_user)
        url = reverse('rescue-responder-heartbeat')
        response = self.client.post(
            url,
            {
                'latitude': -1.271,
                'longitude': 36.812,
                'is_available_for_dispatch': True,
                'unit_type': CitizenProfile.RESPONDER_TYPE_FIRE,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        updated = CitizenProfile.objects.get(user=responder_user)
        self.assertAlmostEqual(updated.location.y, -1.271, places=3)
        self.assertAlmostEqual(updated.location.x, 36.812, places=3)
        self.assertEqual(updated.responder_unit_type, CitizenProfile.RESPONDER_TYPE_FIRE)
        self.assertIsNotNone(updated.last_location_update)

    def test_sos_dispatch_requires_auth_and_returns_units(self):
        url = reverse('sos-dispatch')
        unauthorized = self.client.post(url, {'description': 'Flood rescue needed'}, format='json')
        self.assertEqual(unauthorized.status_code, 401)

        self.client.force_authenticate(user=self.user)
        authorized = self.client.post(url, {'description': 'Flood rescue needed'}, format='json')
        self.assertEqual(authorized.status_code, 201)
        self.assertEqual(authorized.data['status'], 'pending')
        self.assertEqual(len(authorized.data['dispatched_units']), 3)
