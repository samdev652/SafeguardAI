import os

from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.cache import cache
from django.test import TestCase
from unittest.mock import patch
from django.contrib.auth.models import User

from apps.alerts.models import Alert, CommunityVerificationPrompt
from apps.alerts.tasks import dispatch_risk_alerts_task
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

    @patch('apps.alerts.services.AlertDispatcher.send_sms')
    def test_otp_flow_verifies_and_subscribes(self, mock_send_sms):
        mock_send_sms.return_value = {'sent': True, 'provider': 'africas_talking', 'response': {}}

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

    @patch('apps.alerts.views.find_nearest_rescue_units')
    @patch('apps.alerts.services.AlertDispatcher.send_sms')
    def test_subscribe_sends_sms_briefing_with_risk_and_rescue_contacts(self, mock_send_sms, mock_nearest_units):
        mock_send_sms.return_value = {'sent': True, 'provider': 'africas_talking', 'response': {}}
        mock_nearest_units.return_value = [
            type(
                'Responder',
                (),
                {
                    'full_name': 'Rescue Team Alpha',
                    'responder_unit_type': 'rescue_team',
                    'phone_number': '+254711000111',
                },
            )(),
        ]

        send_response = self.client.post(
            '/api/alerts/otp/send/',
            {'phone': '+254700123456'},
            content_type='application/json',
        )
        self.assertEqual(send_response.status_code, 200)

        cached_otp = cache.get('otp:+254700123456')
        verify_response = self.client.post(
            '/api/alerts/otp/verify/',
            {'phone': '+254700123456', 'otp': cached_otp},
            content_type='application/json',
        )
        self.assertEqual(verify_response.status_code, 200)

        subscribe_response = self.client.post(
            '/api/alerts/subscribe/',
            {
                'ward_id': self.ward.id,
                'phone': '+254700123456',
                'channels': ['sms'],
            },
            content_type='application/json',
        )
        self.assertEqual(subscribe_response.status_code, 201)

        sent_messages = [call.args[1] for call in mock_send_sms.call_args_list]
        self.assertTrue(any('Current risk:' in message for message in sent_messages))
        self.assertTrue(any('What to do:' in message for message in sent_messages))
        self.assertTrue(any('Nearest rescue contacts:' in message for message in sent_messages))

    @patch('apps.alerts.services.AlertDispatcher.send_sms')
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

    @patch('apps.alerts.services.AlertDispatcher.send_sms')
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

    @patch('apps.alerts.services.AlertDispatcher.send_whatsapp')
    def test_otp_send_whatsapp_channel(self, mock_send_whatsapp):
        os.environ['OTP_ALLOW_DEV_FALLBACK'] = 'False'
        mock_send_whatsapp.return_value = {'sent': True, 'provider': 'meta_whatsapp', 'response': {}}

        send_response = self.client.post(
            '/api/alerts/otp/send/',
            {'phone': '+254700123456', 'channel': 'whatsapp'},
            content_type='application/json',
        )

        self.assertEqual(send_response.status_code, 200)
        payload = send_response.json()
        self.assertEqual(payload['channel'], 'whatsapp')


class DispatchRiskAlertsTaskTests(TestCase):
    def setUp(self):
        polygon = Polygon(
            ((36.77, -1.24), (36.83, -1.24), (36.83, -1.29), (36.77, -1.29), (36.77, -1.24)),
            srid=4326,
        )
        WardBoundary.objects.create(
            ward_name='Westlands',
            county_name='Nairobi',
            geometry=MultiPolygon(polygon),
        )
        self.risk = RiskAssessment.objects.create(
            ward_name='Westlands',
            village_name='Kangemi',
            hazard_type='flood',
            risk_level='high',
            risk_score=82.0,
            guidance_en='Move to higher ground immediately.',
            guidance_sw='Nenda sehemu ya juu mara moja.',
            summary='High flood risk.',
            location=Point(36.80, -1.26, srid=4326),
        )

        citizen_user = User.objects.create(username='citizen_test')
        self.citizen = CitizenProfile.objects.create(
            user=citizen_user,
            full_name='Citizen One',
            phone_number='+254700111222',
            ward_name='Westlands',
            village_name='Kangemi',
            preferred_language='en',
            location=Point(36.81, -1.25, srid=4326),
            channels=['sms', 'whatsapp'],
        )

        rescue_user = User.objects.create(username='rescue_test', is_active=True)
        CitizenProfile.objects.create(
            user=rescue_user,
            full_name='Rescue Team Alpha',
            phone_number='+254711000111',
            ward_name='Westlands',
            village_name='CBD',
            role=CitizenProfile.ROLE_RESCUE_TEAM,
            preferred_language='en',
            location=Point(36.801, -1.261, srid=4326),
            channels=['sms'],
            is_available_for_dispatch=True,
            last_location_update=self.risk.issued_at,
        )

    @patch('apps.alerts.services.AlertDispatcher.send_whatsapp')
    @patch('apps.alerts.services.AlertDispatcher.send_sms')
    def test_dispatch_includes_nearest_contacts_and_marks_sent(self, mock_send_sms, mock_send_whatsapp):
        mock_send_sms.return_value = {'sent': True, 'channel': 'sms'}
        mock_send_whatsapp.return_value = {'sent': True, 'channel': 'whatsapp'}

        result = dispatch_risk_alerts_task(self.risk.id)

        self.assertEqual(result['sent_alerts'], 2)
        alerts = Alert.objects.filter(citizen=self.citizen).order_by('channel')
        self.assertEqual(alerts.count(), 2)
        self.assertIn('Nearest rescue contacts:', alerts[0].message)
        self.assertIn('Rescue Team Alpha', alerts[0].message)
        self.assertTrue(all(alert.status == Alert.STATUS_SENT for alert in alerts))

    @patch('apps.alerts.services.AlertDispatcher.send_whatsapp')
    @patch('apps.alerts.services.AlertDispatcher.send_sms')
    def test_dispatch_marks_failed_when_provider_rejects(self, mock_send_sms, mock_send_whatsapp):
        mock_send_sms.return_value = {'sent': False, 'channel': 'sms', 'reason': 'auth failed'}
        mock_send_whatsapp.return_value = {'sent': True, 'channel': 'whatsapp'}

        result = dispatch_risk_alerts_task(self.risk.id)

        self.assertEqual(result['sent_alerts'], 1)
        sms_alert = Alert.objects.get(citizen=self.citizen, channel='sms')
        whatsapp_alert = Alert.objects.get(citizen=self.citizen, channel='whatsapp')
        self.assertEqual(sms_alert.status, Alert.STATUS_FAILED)
        self.assertEqual(whatsapp_alert.status, Alert.STATUS_SENT)


class CommunityVerificationWebhookTests(TestCase):
    def setUp(self):
        polygon = Polygon(
            ((36.77, -1.24), (36.83, -1.24), (36.83, -1.29), (36.77, -1.29), (36.77, -1.24)),
            srid=4326,
        )
        WardBoundary.objects.create(
            ward_name='Westlands',
            county_name='Nairobi',
            geometry=MultiPolygon(polygon),
        )
        self.risk = RiskAssessment.objects.create(
            ward_name='Westlands',
            village_name='Kangemi',
            hazard_type='flood',
            risk_level='high',
            risk_score=86.0,
            guidance_en='Move to higher ground immediately.',
            guidance_sw='Nenda sehemu ya juu mara moja.',
            summary='High flood risk.',
            location=Point(36.80, -1.26, srid=4326),
        )

    @patch('apps.alerts.views.AlertDispatcher.send_sms')
    def test_yes_threshold_marks_risk_verified_and_broadcasts(self, mock_send_sms):
        mock_send_sms.return_value = {'sent': True, 'provider': 'africas_talking', 'response': {}}
        for idx in range(3):
            user = User.objects.create(username=f'yes-user-{idx}')
            citizen = CitizenProfile.objects.create(
                user=user,
                full_name=f'Yes Citizen {idx}',
                phone_number=f'+2547000001{idx}',
                ward_name='Westlands',
                village_name='Kangemi',
                preferred_language='en',
                location=Point(36.80, -1.26, srid=4326),
                channels=['sms'],
            )
            CommunityVerificationPrompt.objects.create(
                risk_assessment=self.risk,
                citizen=citizen,
                phone_number=citizen.phone_number,
                prompt_message='Reply YES if conditions are dangerous, NO if all clear.',
            )

        for idx in range(3):
            response = self.client.post(
                '/api/alerts/sms/reply/webhook/',
                {'from': f'+2547000001{idx}', 'text': 'YES'},
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)

        self.risk.refresh_from_db()
        self.assertEqual(self.risk.community_status, RiskAssessment.COMMUNITY_VERIFIED)
        self.assertIsNotNone(self.risk.community_verified_at)
        self.assertTrue(any('CONFIRMED' in call.args[1] for call in mock_send_sms.call_args_list))

    @patch('apps.alerts.views.AlertDispatcher.send_sms')
    def test_no_threshold_marks_all_clear_and_downgrades_risk(self, mock_send_sms):
        mock_send_sms.return_value = {'sent': True, 'provider': 'africas_talking', 'response': {}}
        for idx in range(5):
            user = User.objects.create(username=f'no-user-{idx}')
            citizen = CitizenProfile.objects.create(
                user=user,
                full_name=f'No Citizen {idx}',
                phone_number=f'+2547111001{idx}',
                ward_name='Westlands',
                village_name='Kangemi',
                preferred_language='en',
                location=Point(36.80, -1.26, srid=4326),
                channels=['sms'],
            )
            CommunityVerificationPrompt.objects.create(
                risk_assessment=self.risk,
                citizen=citizen,
                phone_number=citizen.phone_number,
                prompt_message='Reply YES if conditions are dangerous, NO if all clear.',
            )

        for idx in range(5):
            response = self.client.post(
                '/api/alerts/sms/reply/webhook/',
                {'from': f'+2547111001{idx}', 'text': 'NO'},
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)

        self.risk.refresh_from_db()
        self.assertEqual(self.risk.community_status, RiskAssessment.COMMUNITY_ALL_CLEAR)
        self.assertEqual(self.risk.risk_level, RiskAssessment.RISK_SAFE)
        self.assertIsNotNone(self.risk.community_all_clear_at)
        self.assertTrue(any('ALL-CLEAR' in call.args[1] for call in mock_send_sms.call_args_list))
