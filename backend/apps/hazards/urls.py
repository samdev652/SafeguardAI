from django.urls import path
from .views import (
    LatestRiskAssessmentsView,
    TriggerIngestionView,
    WardHeatmapGeoJSONView,
    WardRiskView,
    risk_events_stream,
)
from .api_forecast import SevenDayRiskForecastView
from .views_chatbot import ChatbotMessageView

urlpatterns = [
    path('risks/', LatestRiskAssessmentsView.as_view(), name='risk-list'),
    path('risks/ward/<str:ward_name>/', WardRiskView.as_view(), name='ward-risk-list'),
    path('risks/ward-heatmap/', WardHeatmapGeoJSONView.as_view(), name='ward-heatmap-geojson'),
    path('risks/events/', risk_events_stream, name='risk-events-stream'),
    path('ingest/trigger/', TriggerIngestionView.as_view(), name='ingest-trigger'),
    path('forecast/', SevenDayRiskForecastView.as_view(), name='seven-day-forecast'),
    path('chatbot/message/', ChatbotMessageView.as_view(), name='chatbot-message'),
]
