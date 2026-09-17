"""Request and response serializers: TripPlanRequest, TripPlanResponse. The only place minutes become wall-clock time."""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from .services.hos.constants import CYCLE_LIMIT_MIN, GRID_RESOLUTION_MIN, MINUTES_PER_HOUR
from .services.route_index import simplify

DEFAULT_TIMEZONE = "America/New_York"
CYCLE_LIMIT_HOURS = CYCLE_LIMIT_MIN / MINUTES_PER_HOUR
GEOMETRY_SIMPLIFY_EPSILON_DEG = 0.0001  # wire format only; RouteIndex keeps the full polyline for mile lookups
COORDINATE_DECIMALS = 5  # about 1 m


def _normalize(address):
    return " ".join(address.lower().split())


def _hours(minutes):
    return minutes / MINUTES_PER_HOUR


def _rounded(point):
    return [round(point[0], COORDINATE_DECIMALS), round(point[1], COORDINATE_DECIMALS)]


class TripPlanRequestSerializer(serializers.Serializer):
    current_location = serializers.CharField(max_length=255)
    pickup_location = serializers.CharField(max_length=255)
    dropoff_location = serializers.CharField(max_length=255)
    current_cycle_used = serializers.FloatField(min_value=0, max_value=CYCLE_LIMIT_HOURS)
    start_time = serializers.CharField(required=False)
    timezone = serializers.CharField(required=False, default=DEFAULT_TIMEZONE)

    def validate_timezone(self, value):
        try:
            return ZoneInfo(value).key
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError(f"Unknown timezone {value!r}. Use an IANA name such as America/Chicago.")

    def validate(self, data):
        if _normalize(data["pickup_location"]) == _normalize(data["dropoff_location"]):
            raise serializers.ValidationError({"dropoff_location": "Pickup and dropoff must be different locations."})

        zone = ZoneInfo(data["timezone"])
        raw = data.get("start_time")
        if raw is None:
            start = timezone.now().astimezone(zone)
        else:
            try:
                parsed = parse_datetime(raw.strip())
            except ValueError:
                parsed = None
            if parsed is None:
                raise serializers.ValidationError({"start_time": "Use an ISO 8601 date and time, such as 2026-09-16T06:00:00-04:00."})
            start = parsed.astimezone(zone) if parsed.tzinfo else parsed.replace(tzinfo=zone)
        # Round down to the log grid before anything downstream sees it, so every derived boundary is on the grid.
        data["start_time"] = start.replace(minute=start.minute - start.minute % GRID_RESOLUTION_MIN, second=0, microsecond=0)
        return data

    def planner_arguments(self):
        data = self.validated_data
        return {
            "current": data["current_location"],
            "pickup": data["pickup_location"],
            "dropoff": data["dropoff_location"],
            "cycle_used_min": data["current_cycle_used"] * MINUTES_PER_HOUR,
            "start_time": data["start_time"],
            "tz_name": data["timezone"],
        }


class ZonedDateTimeField(serializers.Field):
    """ISO 8601 in the datetime's own zone. DRF's DateTimeField would convert to the server zone."""

    def to_representation(self, value):
        return value.isoformat()


class CoordinateField(serializers.FloatField):
    def to_representation(self, value):
        return round(float(value), COORDINATE_DECIMALS)


class StopSerializer(serializers.Serializer):
    kind = serializers.CharField()
    at_mile = serializers.FloatField()
    lat = CoordinateField()
    lng = CoordinateField()
    label = serializers.CharField()
    arrive = ZonedDateTimeField()
    depart = ZonedDateTimeField()
    duration_hours = serializers.FloatField()


class SummarySerializer(serializers.Serializer):
    total_miles = serializers.FloatField()
    driving_hours = serializers.FloatField()
    elapsed_hours = serializers.FloatField()
    days = serializers.IntegerField()
    cycle_used_at_start_hours = serializers.FloatField()
    on_duty_added_hours = serializers.FloatField()
    cycle_used_at_end = serializers.FloatField()
    restart_required = serializers.BooleanField()


class RouteSerializer(serializers.Serializer):
    geometry = serializers.SerializerMethodField()
    bbox = serializers.SerializerMethodField()

    def get_geometry(self, route):
        return [_rounded(point) for point in simplify(route.geometry, GEOMETRY_SIMPLIFY_EPSILON_DEG)]

    def get_bbox(self, route):
        return [_rounded(corner) for corner in route.bbox]


class DaySerializer(serializers.Serializer):
    """One paper log page. Segments and remark times stay in minutes from midnight for the grid; totals and recap are hours."""

    date = serializers.DateField()
    date_index = serializers.IntegerField(source="sheet.date_index")
    header = serializers.SerializerMethodField()
    segments = serializers.SerializerMethodField()
    totals = serializers.SerializerMethodField()
    total_miles_driving = serializers.FloatField(source="sheet.total_miles_driving")
    remarks = serializers.SerializerMethodField()
    recap = serializers.SerializerMethodField()

    def get_header(self, dated):
        remarks = dated.sheet.remarks
        return {
            "from": remarks[0][1] if remarks else None,
            "to": remarks[-1][1] if remarks else None,
            "total_mileage_today": dated.sheet.total_miles_driving,
            "home_terminal_timezone": self.context["timezone"],
            # The request carries no carrier, vehicle or shipment details; the form shows these lines blank.
            "carrier_name": None,
            "main_office_address": None,
            "home_terminal_address": None,
            "vehicle_numbers": None,
            "driver_name": None,
            "co_driver": None,
            "shipping_document": None,
        }

    def get_segments(self, dated):
        return [
            {"status": status.name, "start_min": start, "end_min": end}
            for status, start, end in dated.sheet.segments
        ]

    def get_totals(self, dated):
        return {status.name: _hours(minutes) for status, minutes in dated.sheet.totals.items()}

    def get_remarks(self, dated):
        return [{"at_min": at_min, "location": location} for at_min, location in dated.sheet.remarks]

    def get_recap(self, dated):
        recap = dated.sheet.recap
        return {
            "on_duty_today_hours": _hours(recap.on_duty_today),
            "a_on_duty_last_7_days_hours": _hours(recap.a_on_duty_last_7_days),
            "b_available_tomorrow_hours": _hours(recap.b_available_tomorrow),
            "c_on_duty_last_5_days_hours": _hours(recap.c_on_duty_last_5_days),
        }


class TripPlanResponseSerializer(serializers.Serializer):
    """The §25 response. Needs context trip_id and timezone."""

    id = serializers.SerializerMethodField()
    timezone = serializers.SerializerMethodField()
    limits = serializers.DictField(child=serializers.IntegerField())
    summary = SummarySerializer()
    route = RouteSerializer()
    stops = StopSerializer(many=True)
    days = DaySerializer(source="sheets", many=True)
    violations = serializers.SerializerMethodField()

    def get_id(self, plan):
        return str(self.context["trip_id"])

    def get_timezone(self, plan):
        return self.context["timezone"]

    def get_violations(self, plan):
        return []  # violation-free by construction; present for parity with ELD output
