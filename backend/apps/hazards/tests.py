from unittest.mock import patch
from django.contrib.auth.models import User
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.urls import reverse
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APITestCase

from apps.citizens.models import CitizenProfile
from apps.hazards.models import HazardObservation, RiskAssessment, WardBoundary
from apps.hazards.tasks import ingest_hazard_data_task


class WardHeatmapApiTests(APITestCase):
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
        RiskAssessment.objects.create(
            ward_name='Westlands',
            village_name='Kangemi',
            hazard_type='flood',
            risk_level='critical',
            risk_score=92.4,
            guidance_en='Move to high ground immediately.',
            guidance_sw='Nenda sehemu ya juu mara moja.',
            summary='Critical flood risk.',
            location=Point(36.80, -1.26, srid=4326),
        )

    def test_ward_heatmap_returns_geojson_feature_collection(self):
        url = reverse('ward-heatmap-geojson')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['type'], 'FeatureCollection')
        self.assertEqual(len(response.data['features']), 1)
        feature = response.data['features'][0]
        self.assertEqual(feature['properties']['ward_name'], 'Westlands')
        self.assertEqual(feature['properties']['risk_level'], 'critical')


class PublicWeatherConditionsApiTests(APITestCase):
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
        HazardObservation.objects.create(
            source='open_meteo',
            ward_name='Westlands',
            village_name='Kangemi',
            hazard_type='flood',
            severity_index=82,
            raw_payload={
                'properties': {
                    'temperature_2m': 27.4,
                    'precipitation': 15.2,
                    'wind_speed_10m': 21.6,
                }
            },
            location=Point(36.80, -1.26, srid=4326),
            observed_at=timezone.now(),
        )

    def test_weather_conditions_returns_area_weather_and_impact(self):
        response = self.client.get('/api/risk/weather-conditions/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        item = response.data[0]
        self.assertEqual(item['ward_name'], 'Westlands')
        self.assertEqual(item['county_name'], 'Nairobi')
        self.assertEqual(item['hazard_type'], 'flood')
        self.assertEqual(item['precipitation_mm'], 15.2)
        self.assertIn('flood', item['impact_summary'].lower())


class IngestionTaskTests(TestCase):
    @patch('apps.hazards.tasks.dispatch_risk_alerts_task.delay')
    @patch('apps.hazards.tasks.GeminiRiskAnalyzer.analyze')
    @patch('apps.hazards.tasks.fetch_open_meteo_data')
    @patch('apps.hazards.tasks.fetch_noaa_data')
    @patch('apps.hazards.tasks.fetch_kmd_data')
    def test_ingestion_creates_observations_and_risks(
        self,
        mock_kmd,
        mock_noaa,
        mock_open_meteo,
        mock_analyze,
        mock_dispatch,
    ):
        mock_kmd.return_value = [
            {
                'ward': 'Westlands',
                'village': 'Kangemi',
                'hazard_type': 'flood',
                'severity_index': 88,
                'geometry': {'coordinates': [36.81, -1.27]},
            }
        ]
        mock_noaa.return_value = []
        mock_open_meteo.return_value = []
        mock_analyze.return_value = {
            'risk_level': 'critical',
            'risk_score': 88,
            'guidance_en': 'Evacuate now.',
            'guidance_sw': 'Hameni sasa.',
            'summary': 'Critical flood risk',
        }

        result = ingest_hazard_data_task()

        self.assertEqual(result['created_observations'], 1)
        self.assertEqual(HazardObservation.objects.count(), 1)
        self.assertEqual(RiskAssessment.objects.count(), 1)
        mock_dispatch.assert_called_once()

    @patch('apps.hazards.tasks.dispatch_risk_alerts_task.delay')
    @patch('apps.hazards.tasks.GeminiRiskAnalyzer.analyze')
    @patch('apps.hazards.tasks.fetch_open_meteo_data')
    @patch('apps.hazards.tasks.fetch_noaa_data')
    @patch('apps.hazards.tasks.fetch_kmd_data')
    def test_ingestion_skips_alert_dispatch_for_medium_or_safe_risk(
        self,
        mock_kmd,
        mock_noaa,
        mock_open_meteo,
        mock_analyze,
        mock_dispatch,
    ):
        mock_kmd.return_value = [
            {
                'ward': 'Westlands',
                'village': 'Kangemi',
                'hazard_type': 'flood',
                'severity_index': 42,
                'geometry': {'coordinates': [36.81, -1.27]},
            }
        ]
        mock_noaa.return_value = []
        mock_open_meteo.return_value = []
        mock_analyze.return_value = {
            'risk_level': 'medium',
            'risk_score': 42,
            'guidance_en': 'Monitor updates.',
            'guidance_sw': 'Fuatilia taarifa.',
            'summary': 'Medium flood risk',
        }

        result = ingest_hazard_data_task()

        self.assertEqual(result['created_observations'], 1)
        self.assertEqual(result['dispatched_alert_jobs'], 0)
        mock_dispatch.assert_not_called()

    @patch('apps.hazards.tasks.dispatch_risk_alerts_task.delay')
    @patch('apps.hazards.tasks.GeminiRiskAnalyzer.analyze')
    @patch('apps.hazards.tasks.fetch_open_meteo_data')
    @patch('apps.hazards.tasks.fetch_noaa_data')
    @patch('apps.hazards.tasks.fetch_kmd_data')
    def test_ingestion_uses_open_meteo_fallback_when_primary_feeds_empty(
        self,
        mock_kmd,
        mock_noaa,
        mock_open_meteo,
        mock_analyze,
        mock_dispatch,
    ):
        mock_kmd.return_value = []
        mock_noaa.return_value = []
        mock_open_meteo.return_value = [
            {
                'properties': {
                    'area': 'Nairobi',
                    'hazard_type': 'flood',
                    'severity_index': 72,
                },
                'geometry': {'coordinates': [36.817223, -1.286389]},
            }
        ]
        mock_analyze.return_value = {
            'risk_level': 'high',
            'risk_score': 72,
            'guidance_en': 'Avoid flood-prone roads.',
            'guidance_sw': 'Epuka barabara zenye mafuriko.',
            'summary': 'High flood risk',
        }

        result = ingest_hazard_data_task()

        self.assertEqual(result['created_observations'], 1)
        self.assertEqual(result['dispatched_alert_jobs'], 1)
        observation = HazardObservation.objects.get()
        self.assertEqual(observation.source, 'open_meteo')
        self.assertEqual(observation.ward_name, 'Nairobi')
        mock_dispatch.assert_called_once()

    @patch('apps.hazards.tasks.dispatch_risk_alerts_task.delay')
    @patch('apps.hazards.tasks.GeminiRiskAnalyzer.analyze')
    @patch('apps.hazards.tasks.fetch_open_meteo_data')
    @patch('apps.hazards.tasks.fetch_noaa_data')
    @patch('apps.hazards.tasks.fetch_kmd_data')
    def test_ingestion_deduplicates_repeat_high_risk_alerts(
        self,
        mock_kmd,
        mock_noaa,
        mock_open_meteo,
        mock_analyze,
        mock_dispatch,
    ):
        RiskAssessment.objects.create(
            ward_name='Westlands',
            village_name='Kangemi',
            hazard_type='flood',
            risk_level='high',
            risk_score=78,
            guidance_en='Move to safe shelter.',
            guidance_sw='Nenda makazi salama.',
            summary='High flood risk already issued.',
            location=Point(36.81, -1.27, srid=4326),
        )

        mock_kmd.return_value = [
            {
                'ward': 'Westlands',
                'village': 'Kangemi',
                'hazard_type': 'flood',
                'severity_index': 81,
                'geometry': {'coordinates': [36.81, -1.27]},
            }
        ]
        mock_noaa.return_value = []
        mock_open_meteo.return_value = []
        mock_analyze.return_value = {
            'risk_level': 'high',
            'risk_score': 81,
            'guidance_en': 'Avoid flood-prone roads.',
            'guidance_sw': 'Epuka barabara zenye mafuriko.',
            'summary': 'High flood risk',
        }

        result = ingest_hazard_data_task()

        self.assertEqual(result['created_observations'], 1)
        self.assertEqual(result['dispatched_alert_jobs'], 0)
        self.assertEqual(result['dedup_skipped_alert_jobs'], 1)
        mock_dispatch.assert_not_called()


class PublicCoverageStatsApiTests(APITestCase):
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

        user = User.objects.create_user(username='coverage-user', password='StrongPass123')
        CitizenProfile.objects.create(
            user=user,
            full_name='Coverage User',
            phone_number='+254700777111',
            ward_name='Westlands',
            village_name='Kangemi',
            preferred_language='en',
            location=Point(36.80, -1.26, srid=4326),
            channels=['sms'],
        )

    def test_public_coverage_endpoint_returns_map_data_and_county_summary(self):
        response = self.client.get('/api/stats/coverage/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['type'], 'FeatureCollection')
        self.assertGreaterEqual(len(response.data['features']), 1)
        self.assertEqual(response.data['total_registered_users'], 1)

        nairobi = next((item for item in response.data['counties'] if item['county_name'] == 'Nairobi'), None)
        self.assertIsNotNone(nairobi)
        self.assertEqual(nairobi['registered_users'], 1)
