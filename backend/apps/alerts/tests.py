from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.cache import cache
from django.test import TestCase

from apps.citizens.models import CitizenProfile
from apps.hazards.models import RiskAssessment, WardBoundary


class PublicAlertRegistrationFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        polygon = Polygon(
            ((36.77, -1.24), (36.83, -1.24), (36.83, -1.29), (36.77, -1.29), (36.77, -1.24)),
            srid=4326,
        )
        self.ward = WardBoundary.objects.create(
            ward_name='Westlands',
            county_name='Nairobi',
            geometry=MultiPolygon(polygon),
        )
        RiskAssessment.objects.create(
            ward_name='Westlands',
            village_name='Kangemi',
            hazard_type='flood',
            risk_level='high',
            risk_score=83.5,
            guidance_en='Move to safer ground.',
            guidance_sw='Nenda eneo salama.',
            summary='High flood risk.',
            location=Point(36.80, -1.26, srid=4326),
        )

    def test_location_search_returns_matching_ward(self):
        response = self.client.get('/api/locations/search/?q=west')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        payload = response.json()[0]
        self.assertEqual(payload['ward_name'], 'Westlands')
        self.assertEqual(payload['county_name'], 'Nairobi')
        self.assertIn('latitude', payload)
        self.assertIn('longitude', payload)

    def test_subscribe_requires_verified_otp(self):
        response = self.client.post(
            '/api/alerts/subscribe/',
            {
                'ward_id': self.ward.id,
                'phone': '+254700123456',
                'channels': ['sms', 'whatsapp'],
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Phone must be OTP verified first', response.json()['detail'])

    def test_otp_flow_verifies_and_subscribes(self):
        send_response = self.client.post(
            '/api/alerts/otp/send/',
            {'phone': '+254700123456'},
            content_type='application/json',
        )
        self.assertEqual(send_response.status_code, 200)

        cached_otp = cache.get('otp:+254700123456')
        self.assertIsNotNone(cached_otp)

        verify_response = self.client.post(
            '/api/alerts/otp/verify/',
            {'phone': '+254700123456', 'otp': cached_otp},
            content_type='application/json',
        )
        self.assertEqual(verify_response.status_code, 200)
        self.assertEqual(verify_response.json()['verified'], True)

        subscribe_response = self.client.post(
            '/api/alerts/subscribe/',
            {
                'ward_id': self.ward.id,
                'phone': '+254700123456',
                'channels': ['whatsapp'],
            },
            content_type='application/json',
        )
        self.assertEqual(subscribe_response.status_code, 201)
        payload = subscribe_response.json()
        self.assertEqual(payload['ward_name'], 'Westlands')
        self.assertEqual(payload['risk_level'], 'high')
        self.assertEqual(payload['channels'], ['sms', 'whatsapp'])

        profile = CitizenProfile.objects.get(phone_number='+254700123456')
        self.assertEqual(profile.ward_name, 'Westlands')
        self.assertEqual(profile.channels, ['sms', 'whatsapp'])
