from django.contrib import admin
from .models import Alert, RescueRequest


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('citizen', 'channel', 'status', 'created_at', 'sent_at')
    list_filter = ('channel', 'status')


@admin.register(RescueRequest)
class RescueRequestAdmin(admin.ModelAdmin):
    list_display = ('citizen', 'status', 'created_at', 'dispatched_at')
    list_filter = ('status',)
