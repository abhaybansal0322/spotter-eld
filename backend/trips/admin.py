"""Django admin registrations for trip models."""
from django.contrib import admin

from .models import LogDay, Stop, Trip


class StopInline(admin.TabularInline):
    model = Stop
    fields = ("index", "kind", "label")
    readonly_fields = fields
    extra = 0


class LogDayInline(admin.TabularInline):
    model = LogDay
    fields = ("index", "date")
    readonly_fields = fields
    extra = 0


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("id", "current_location", "pickup_location", "dropoff_location", "total_miles", "created_at")
    readonly_fields = ("id", "created_at")
    inlines = (StopInline, LogDayInline)
