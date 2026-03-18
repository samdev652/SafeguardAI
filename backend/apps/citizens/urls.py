from django.urls import path
from .views import CitizenProfileView, CitizenRegisterView, CountyUsersView

urlpatterns = [
    path('register/', CitizenRegisterView.as_view(), name='citizen-register'),
    path('me/', CitizenProfileView.as_view(), name='citizen-profile'),
    path('county-users/', CountyUsersView.as_view(), name='county-users'),
]
