from django.contrib import admin
from .models import RescueUnit


@admin.register(RescueUnit)
class RescueUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit_type', 'county', 'ward_name', 'is_active')
    list_filter = ('unit_type', 'county', 'is_active')
    search_fields = ('name', 'ward_name', 'county')
