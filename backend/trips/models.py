"""Persistence models: Trip, Stop, LogDay.

A stored trip is the serialized API payload, split so each stop and each day is its own row. Retrieval
reassembles that payload exactly; nothing is recomputed, so a plan reads back the same even after the
HOS rules or ORS data change.
"""
import uuid
from datetime import date

from django.db import models, transaction


class TripQuerySet(models.QuerySet):
    def with_children(self):
        return self.prefetch_related("stops", "days")

    @transaction.atomic
    def create_from_payload(self, inputs, payload):
        """Store a response payload built by TripPlanResponseSerializer, keyed by its id."""
        trip = self.create(
            id=uuid.UUID(payload["id"]),
            current_location=inputs["current_location"],
            pickup_location=inputs["pickup_location"],
            dropoff_location=inputs["dropoff_location"],
            current_cycle_used=inputs["current_cycle_used"],
            start_time=inputs["start_time"],
            timezone=inputs["timezone"],
            total_miles=payload["summary"]["total_miles"],
            route_geometry=payload["route"]["geometry"],
            route_bbox=payload["route"]["bbox"],
            summary=payload["summary"],
            limits=payload["limits"],
        )
        Stop.objects.bulk_create(
            Stop(trip=trip, index=index, kind=stop["kind"], label=stop["label"], payload=stop)
            for index, stop in enumerate(payload["stops"])
        )
        LogDay.objects.bulk_create(
            LogDay(trip=trip, index=index, date=date.fromisoformat(day["date"]), payload=day)
            for index, day in enumerate(payload["days"])
        )
        return trip


class Trip(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    current_location = models.CharField(max_length=255)
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    current_cycle_used = models.FloatField(help_text="Hours already used in the 70hr/8day cycle, as submitted")
    start_time = models.DateTimeField(help_text="Rounded down to the 15-minute grid")
    timezone = models.CharField(max_length=64, help_text="Home terminal IANA zone")
    total_miles = models.FloatField()
    route_geometry = models.JSONField(help_text="[[lat, lng], ...]")
    route_bbox = models.JSONField(help_text="[[south, west], [north, east]]")
    summary = models.JSONField()
    limits = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TripQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.pickup_location} to {self.dropoff_location} ({self.id})"

    def to_payload(self):
        """The API payload as it was returned when the trip was planned. Use with TripQuerySet.with_children."""
        return {
            "id": str(self.id),
            "timezone": self.timezone,
            "limits": self.limits,
            "summary": self._summary_with_defaults(),
            "route": {"geometry": self.route_geometry, "bbox": self.route_bbox},
            "stops": [stop.payload for stop in self.stops.all()],
            "days": [day.payload for day in self.days.all()],
            "violations": [],
        }


    def _summary_with_defaults(self):
        """Rows written before the summary carried the cycle start and added hours read back with estimates rather than
        raising: the submitted hours stand in for the engine's seed, and the trip added what the end figure gained.
        A restart zeroed the cycle, so then everything at the end was added. Estimates, not the exact figures."""
        summary = dict(self.summary)
        start = summary.setdefault("cycle_used_at_start_hours", self.current_cycle_used)
        end = summary["cycle_used_at_end"]
        summary.setdefault("on_duty_added_hours", end if summary["restart_required"] else max(0.0, end - start))
        return summary


class Stop(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="stops")
    index = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=16)
    label = models.CharField(max_length=255)
    payload = models.JSONField()

    class Meta:
        ordering = ["index"]
        constraints = [models.UniqueConstraint(fields=["trip", "index"], name="unique_stop_index_per_trip")]

    def __str__(self):
        return f"{self.kind} at {self.label}"


class LogDay(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="days")
    index = models.PositiveSmallIntegerField()
    date = models.DateField()
    payload = models.JSONField()

    class Meta:
        ordering = ["index"]
        constraints = [models.UniqueConstraint(fields=["trip", "index"], name="unique_log_day_index_per_trip")]

    def __str__(self):
        return f"Log for {self.date}"
