"""Trip API routes, mounted under api/ by config.urls."""
from django.urls import path

from .views import HealthView, PlanTripView, TripDetailView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("trips/plan/", PlanTripView.as_view(), name="trip-plan"),
    path("trips/<uuid:trip_id>/", TripDetailView.as_view(), name="trip-detail"),
]
