from django.urls import path
from .views import (
    AlertSubscribeView,
    CountyAlertExportView,
    CountyAlertHistoryView,
    CountyDispatchLogView,
    IncidentReportListView,
    IncidentReportUpdateView,
    MyAlertsView,
    SendOtpView,
    VerifyOtpView,
)

urlpatterns = [
    path('my/', MyAlertsView.as_view(), name='my-alerts'),
    path('otp/send/', SendOtpView.as_view(), name='alerts-otp-send'),
    path('otp/verify/', VerifyOtpView.as_view(), name='alerts-otp-verify'),
    path('subscribe/', AlertSubscribeView.as_view(), name='alerts-subscribe'),
    path('history/', CountyAlertHistoryView.as_view(), name='county-alert-history'),
    path('export/', CountyAlertExportView.as_view(), name='county-alert-export'),
    path('incidents/', IncidentReportListView.as_view(), name='incident-report-list'),
    path('incidents/<int:pk>/', IncidentReportUpdateView.as_view(), name='incident-report-update'),
    path('dispatch-log/', CountyDispatchLogView.as_view(), name='county-dispatch-log'),
]
