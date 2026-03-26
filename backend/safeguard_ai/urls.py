from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.hazards.views import (
    CountyOverviewView, LocationSearchView, PublicCoverageStatsView,
    PublicStatsView, ChatView, DataStatusView, WardResolutionView
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/citizens/', include('apps.citizens.urls')),
    path('api/risk/', include('apps.hazards.risk_urls')),
    path('api/locations/search/', LocationSearchView.as_view(), name='location-search'),
    path('api/stats/public/', PublicStatsView.as_view(), name='public-stats'),
    path('api/stats/coverage/', PublicCoverageStatsView.as_view(), name='public-coverage-stats'),
    path('api/county/overview/', CountyOverviewView.as_view(), name='county-overview'),
    path('api/hazards/', include('apps.hazards.urls')),
    path('api/alerts/', include('apps.alerts.urls')),
    path('api/rescue/', include('apps.rescue.urls')),
    path('api/chat/', ChatView.as_view(), name='chat-endpoint'),
    path('api/hazards/resolve-ward/', WardResolutionView.as_view(), name='resolve-ward'),
    path('api/data/status/', DataStatusView.as_view(), name='data-status'),
]
