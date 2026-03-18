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


class IngestionTaskTests(TestCase):
    @patch('apps.hazards.tasks.dispatch_risk_alerts_task.delay')
    @patch('apps.hazards.tasks.GeminiRiskAnalyzer.analyze')
    @patch('apps.hazards.tasks.fetch_noaa_data')
    @patch('apps.hazards.tasks.fetch_kmd_data')
    def test_ingestion_creates_observations_and_risks(
        self,
        mock_kmd,
        mock_noaa,
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
