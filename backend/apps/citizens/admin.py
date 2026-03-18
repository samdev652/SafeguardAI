from django.contrib import admin
from .models import CitizenProfile


@admin.register(CitizenProfile)
class CitizenProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone_number', 'role', 'ward_name', 'preferred_language', 'created_at')
    list_filter = ('role', 'preferred_language', 'ward_name')
    search_fields = ('full_name', 'phone_number', 'ward_name')
