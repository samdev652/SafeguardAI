from rest_framework import generics, permissions
from rest_framework.exceptions import NotFound
from .models import CitizenProfile
from .serializers import CitizenProfileSerializer, CitizenRegistrationSerializer
from apps.hazards.models import WardBoundary


class CitizenRegisterView(generics.CreateAPIView):
    serializer_class = CitizenRegistrationSerializer
    permission_classes = [permissions.AllowAny]


class CitizenProfileView(generics.RetrieveAPIView):
    serializer_class = CitizenProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile = CitizenProfile.objects.filter(user=self.request.user).first()
        if not profile:
            raise NotFound('Citizen profile not found for this account.')
        return profile


class CountyUsersView(generics.ListAPIView):
    serializer_class = CitizenProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        profile = CitizenProfile.objects.filter(user=self.request.user).first()
        if not profile:
            raise NotFound('Citizen profile not found for this account.')
        if profile.role != CitizenProfile.ROLE_COUNTY_OFFICIAL:
            raise NotFound('County official role required.')

        ward = WardBoundary.objects.filter(ward_name__iexact=profile.ward_name).only('county_name').first()
        county = ward.county_name if ward else profile.ward_name
        ward_names = list(WardBoundary.objects.filter(county_name__iexact=county).values_list('ward_name', flat=True))
        if not ward_names:
            ward_names = [profile.ward_name]
        return CitizenProfile.objects.filter(ward_name__in=ward_names).order_by('-created_at')[:500]
