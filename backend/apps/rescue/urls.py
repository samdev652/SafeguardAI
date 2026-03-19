from django.urls import path
from .views import (
    NearestRescueUnitsView,
    RescueResponderHeartbeatView,
    RescueDispatchAcceptView,
    RescueDispatchQueueView,
    RescueUnitListView,
    SOSDispatchView,
)

urlpatterns = [
    path('units/', RescueUnitListView.as_view(), name='rescue-units'),
    path('units/nearest/', NearestRescueUnitsView.as_view(), name='rescue-units-nearest'),
    path('responders/heartbeat/', RescueResponderHeartbeatView.as_view(), name='rescue-responder-heartbeat'),
    path('sos/dispatch/', SOSDispatchView.as_view(), name='sos-dispatch'),
    path('dispatch-queue/', RescueDispatchQueueView.as_view(), name='rescue-dispatch-queue'),
    path('dispatch-queue/<int:request_id>/accept/', RescueDispatchAcceptView.as_view(), name='rescue-dispatch-accept'),
]
