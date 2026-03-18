from django.contrib import admin
from .models import HazardObservation, RiskAssessment, WardBoundary


@admin.register(HazardObservation)
class HazardObservationAdmin(admin.ModelAdmin):
    list_display = ('source', 'hazard_type', 'ward_name', 'severity_index', 'observed_at')
    search_fields = ('ward_name', 'village_name', 'hazard_type')


@admin.register(RiskAssessment)
class RiskAssessmentAdmin(admin.ModelAdmin):
    list_display = ('hazard_type', 'ward_name', 'risk_level', 'risk_score', 'issued_at')
    search_fields = ('ward_name', 'village_name', 'hazard_type', 'risk_level')


@admin.register(WardBoundary)
class WardBoundaryAdmin(admin.ModelAdmin):
    list_display = ('ward_name', 'county_name', 'created_at')
    search_fields = ('ward_name', 'county_name')
