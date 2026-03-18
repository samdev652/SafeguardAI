from django.urls import path
from .views import LatestRiskAssessmentsView, PublicRiskCountView, RiskAcknowledgeView

urlpatterns = [
    path('current/', LatestRiskAssessmentsView.as_view(), name='risk-current'),
    path('count/', PublicRiskCountView.as_view(), name='risk-count'),
    path('<int:risk_id>/acknowledge/', RiskAcknowledgeView.as_view(), name='risk-acknowledge'),
]
