import os

from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.cache import cache
from django.test import TestCase
from unittest.mock import patch

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

    @patch('apps.alerts.views.send_sms_via_africas_talking')
    def test_otp_flow_verifies_and_subscribes(self, mock_send_sms):
        mock_send_sms.return_value = {'sent': True, 'provider': 'africas_talking', 'response': '{}'}

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

    @patch('apps.alerts.views.send_sms_via_africas_talking')
    def test_otp_send_returns_502_when_provider_rejects(self, mock_send_sms):
        os.environ['OTP_ALLOW_DEV_FALLBACK'] = 'False'
        mock_send_sms.return_value = {
            'sent': False,
            'provider': 'africas_talking',
            'reason': 'InvalidSenderId',
            'response': '{}',
        }

        send_response = self.client.post(
            '/api/alerts/otp/send/',
            {'phone': '+254700123456'},
            content_type='application/json',
        )

        self.assertEqual(send_response.status_code, 502)
        self.assertIn('OTP dispatch failed', send_response.json()['detail'])

    @patch('apps.alerts.views.send_sms_via_africas_talking')
    def test_otp_send_fallback_mode_returns_dev_otp(self, mock_send_sms):
        os.environ['OTP_ALLOW_DEV_FALLBACK'] = 'True'
        mock_send_sms.return_value = {
            'sent': False,
            'provider': 'africas_talking',
            'reason': 'InvalidSenderId',
            'response': '{}',
        }

        send_response = self.client.post(
            '/api/alerts/otp/send/',
            {'phone': '+254700123456'},
            content_type='application/json',
        )

        self.assertEqual(send_response.status_code, 200)
        payload = send_response.json()
        self.assertEqual(payload['provider']['provider'], 'debug_fallback')
        self.assertTrue(payload['provider']['sent'])
        self.assertRegex(payload['dev_otp'], r'^\d{4}$')
