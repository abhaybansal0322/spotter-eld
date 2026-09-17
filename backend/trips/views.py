"""Thin API views: validate, call a service, serialize. No business logic.

Service errors are mapped to HTTP statuses by trips.exceptions.api_exception_handler, not here.
"""
import uuid

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import Trip
from .serializers import TripPlanRequestSerializer, TripPlanResponseSerializer
from .services.planner import limits, plan_trip


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})


class LimitsView(APIView):
    throttle_classes = ()  # static constants: nothing to protect, and the form needs them on every page load

    def get(self, request):
        return Response({"limits": limits()}, headers={"Cache-Control": "public, max-age=3600"})


class TripPlanBurstThrottle(AnonRateThrottle):
    scope = "trip_plan_burst"


class TripPlanDailyThrottle(AnonRateThrottle):
    scope = "trip_plan_daily"


class PlanTripView(APIView):
    throttle_classes = (TripPlanBurstThrottle, TripPlanDailyThrottle)

    def post(self, request):
        request_serializer = TripPlanRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        plan = plan_trip(**request_serializer.planner_arguments())
        payload = TripPlanResponseSerializer(
            plan, context={"trip_id": uuid.uuid4(), "timezone": request_serializer.validated_data["timezone"]}
        ).data
        Trip.objects.create_from_payload(request_serializer.validated_data, payload)
        return Response(payload, status=status.HTTP_201_CREATED)


class TripDetailView(APIView):
    def get(self, request, trip_id):
        trip = get_object_or_404(Trip.objects.with_children(), pk=trip_id)
        return Response(trip.to_payload())
