"""API contract tests. ORS is faked at http.request_json; the database is the pytest-django test database."""
import uuid

import pytest
from django.core.cache import cache
from django.db import DatabaseError

from tests.conftest import BASE_LAT, BASE_LNG, north_of_base, pelias_place, straight_trip
from trips.models import LogDay, Stop, Trip
from trips.services import http, planner
from trips.services.errors import InputError, UpstreamError

STATUSES = {"OFF_DUTY", "SLEEPER_BERTH", "DRIVING", "ON_DUTY_NOT_DRIVING"}

PLAN_URL = "/api/trips/plan/"
VALID = {
    "current_location": "Origin, AA",
    "pickup_location": "Pickup, BB",
    "dropoff_location": "Dropoff, CC",
    "current_cycle_used": 10,
    "start_time": "2026-09-16T06:00:00-04:00",
    "timezone": "America/New_York",
}


@pytest.fixture(autouse=True)
def clear_throttle_history():
    """Throttle counters live in the cache; clear it so one test's requests never throttle the next."""
    cache.clear()
    yield
    cache.clear()


def test_health(api_client):
    response = api_client.get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _post(api_client, **overrides):
    return api_client.post(PLAN_URL, {**VALID, **overrides}, format="json")


@pytest.mark.django_db
def test_valid_request_returns_201_and_full_contract(api_client, fake_ors):
    fake_ors(straight_trip(50, 700))

    response = _post(api_client)

    assert response.status_code == 201
    body = response.json()
    assert list(body) == ["id", "timezone", "limits", "summary", "route", "stops", "days", "violations", "stored"]
    assert body["stored"] is True
    uuid.UUID(body["id"])
    assert body["timezone"] == "America/New_York"
    assert list(body["summary"]) == [
        "total_miles", "driving_hours", "elapsed_hours", "days",
        "cycle_used_at_start_hours", "on_duty_added_hours", "cycle_used_at_end", "restart_required",
    ]
    assert set(body["route"]) == {"geometry", "bbox"}
    assert all(len(point) == 2 for point in body["route"]["geometry"])
    assert len(body["route"]["bbox"]) == 2
    for stop in body["stops"]:
        assert set(stop) == {"kind", "at_mile", "lat", "lng", "label", "arrive", "depart", "duration_hours"}
    for day in body["days"]:
        assert set(day) == {"date", "date_index", "header", "segments", "totals", "total_miles_driving", "remarks", "recap"}
        assert set(day["totals"]) == STATUSES
        assert {segment["status"] for segment in day["segments"]} <= STATUSES
        assert set(day["recap"]) == {
            "on_duty_today_hours", "a_on_duty_last_7_days_hours", "b_available_tomorrow_hours", "c_on_duty_last_5_days_hours",
        }
        assert {"from", "to", "carrier_name", "vehicle_numbers", "shipping_document", "home_terminal_timezone"} <= set(day["header"])
    assert [stop["kind"] for stop in body["stops"]][0] == "START"
    assert body["stops"][-1]["kind"] == "DROPOFF"


@pytest.mark.django_db
def test_days_match_sheets_and_total_24_hours(api_client, fake_ors):
    fake_ors(straight_trip(100, 2000))

    body = _post(api_client).json()

    assert body["summary"]["days"] == len(body["days"]) == 4
    assert [day["date"] for day in body["days"]] == ["2026-09-16", "2026-09-17", "2026-09-18", "2026-09-19"]
    for day in body["days"]:
        assert sum(day["totals"].values()) == 24
        assert day["segments"][0]["start_min"] == 0 and day["segments"][-1]["end_min"] == 1440


@pytest.mark.parametrize(
    ("overrides", "field", "fragment"),
    [
        ({"pickup_location": "   "}, "pickup_location", "may not be blank"),
        ({"current_cycle_used": 70.25}, "current_cycle_used", "less than or equal to 70"),
        ({"current_cycle_used": -1}, "current_cycle_used", "greater than or equal to 0"),
        ({"dropoff_location": "  pickup,   BB "}, "dropoff_location", "must be different"),
        ({"timezone": "Mars/Olympus_Mons"}, "timezone", "Unknown timezone"),
        ({"start_time": "next tuesday"}, "start_time", "ISO 8601"),
        ({"start_time": "2026-02-30T06:00:00"}, "start_time", "ISO 8601"),
    ],
    ids=["blank-address", "cycle-above-70", "cycle-negative", "same-pickup-dropoff", "unknown-timezone",
         "malformed-start-time", "impossible-date"],
)
@pytest.mark.django_db
def test_validation_errors_return_400_with_readable_message(api_client, fake_ors, overrides, field, fragment):
    fake = fake_ors(straight_trip(50, 700))

    response = _post(api_client, **overrides)

    assert response.status_code == 400
    body = response.json()
    assert fragment in body["detail"]
    assert field in body["errors"]
    assert fake.calls == []
    assert Trip.objects.count() == 0


@pytest.mark.django_db
def test_missing_field_is_named_in_the_message(api_client, fake_ors):
    fake_ors(straight_trip(50, 700))
    payload = {key: value for key, value in VALID.items() if key != "current_location"}

    response = api_client.post(PLAN_URL, payload, format="json")

    assert response.status_code == 400
    assert response.json()["detail"] == "Current location: This field is required."


@pytest.mark.django_db
def test_start_time_is_rounded_down_to_the_grid(api_client, fake_ors):
    fake_ors(straight_trip(50, 700))

    body = _post(api_client, start_time="2026-09-16T06:07:59-04:00").json()

    assert body["stops"][0]["arrive"] == "2026-09-16T06:00:00-04:00"
    assert Trip.objects.get().start_time.isoformat() == "2026-09-16T10:00:00+00:00"


@pytest.mark.django_db
def test_optional_start_time_and_timezone_default(api_client, fake_ors):
    fake_ors(straight_trip(50, 700))
    payload = {key: value for key, value in VALID.items() if key not in ("start_time", "timezone")}

    response = api_client.post(PLAN_URL, payload, format="json")

    assert response.status_code == 201
    assert response.json()["timezone"] == "America/New_York"
    arrive = response.json()["stops"][0]["arrive"]
    assert arrive[-6:] in ("-04:00", "-05:00")  # New York
    assert int(arrive[14:16]) % 15 == 0 and arrive[17:19] == "00"


def _unroutable(index):
    message = f"Could not find routable point within a radius of 350.0 meters of specified coordinate {index}: -101.0 37.0."
    return UpstreamError("HTTP 404", status=404, body={"error": {"code": 2010, "message": message}})


@pytest.mark.django_db
def test_unroutable_address_returns_422_naming_the_input(api_client, fake_ors):
    fake_ors(_unroutable(2))

    response = _post(api_client)

    assert response.status_code == 422
    assert response.json() == {"detail": "No truck-accessible road was found near the dropoff location (Dropoff, CC)."}
    assert Trip.objects.count() == 0


@pytest.mark.django_db
def test_unroutable_index_maps_through_the_two_point_route(api_client, fake_ors):
    fake = fake_ors(_unroutable(1))
    fake.addresses["origin, aa"] = pelias_place(BASE_LNG, BASE_LAT + 1, "Origin", "AA")  # at the pickup: routes [current, dropoff]

    response = _post(api_client)

    assert response.status_code == 422
    assert response.json()["detail"] == "No truck-accessible road was found near the dropoff location (Dropoff, CC)."


@pytest.mark.django_db
def test_route_over_the_distance_limit_returns_422_saying_so(api_client, fake_ors):
    body = {"error": {"code": 2004, "message": "The approximated route distance must not be greater than 6000000.0 meters."}}
    fake_ors(UpstreamError("HTTP 400", status=400, body=body))

    response = _post(api_client)

    assert response.status_code == 422
    assert response.json() == {"detail": "This trip is longer than the routing service can plan in one route. Try a shorter trip."}


@pytest.mark.django_db
def test_unparseable_route_error_falls_back_to_a_generic_sentence(api_client, fake_ors):
    fake_ors(UpstreamError("HTTP 400", status=400, body={"error": {"code": 2009, "message": "Route could not be found."}}))

    response = _post(api_client)

    assert response.status_code == 422
    assert response.json() == {"detail": "No drivable truck route connects these locations."}


@pytest.mark.django_db
def test_pickup_and_dropoff_at_the_same_coordinates_returns_422(api_client, fake_ors):
    fake = fake_ors(straight_trip(50, 700))
    fake.addresses["dropoff, cc"] = pelias_place(BASE_LNG, north_of_base(0)[0] + 1, "Pickup Annex", "CC")

    response = _post(api_client)

    assert response.status_code == 422
    assert response.json()["detail"] == "The pickup location (Pickup, BB) and dropoff location (Pickup Annex, CC) are the same place."
    assert fake.urls(planner.routing.DIRECTIONS_URL) == []


@pytest.mark.django_db
def test_unknown_address_returns_422_naming_the_input(api_client, fake_ors):
    fake_ors(straight_trip(50, 700))

    response = _post(api_client, pickup_location="Atlantis, ZZ")

    assert response.status_code == 422
    assert "pickup location" in response.json()["detail"]


@pytest.mark.django_db
def test_ors_server_error_returns_502(api_client, fake_ors):
    fake_ors(http.UpstreamError("POST directions returned HTTP 500", status=500))

    response = _post(api_client)

    assert response.status_code == 502
    assert "unavailable" in response.json()["detail"]
    assert "HTTP 500" not in response.json()["detail"]


@pytest.mark.django_db
def test_exhausted_ors_quota_says_so_rather_than_unavailable(api_client, fake_ors):
    fake_ors(http.UpstreamError("GET search returned HTTP 403", status=403, body={"error": "Quota exceeded"}))

    response = _post(api_client)

    assert response.status_code == 502
    assert "usage limit" in response.json()["detail"]


@pytest.mark.django_db
def test_input_error_from_the_service_returns_400(api_client, monkeypatch):
    def reject(**kwargs):
        raise InputError("start_time must fall on a 15-minute boundary")

    monkeypatch.setattr("trips.views.plan_trip", reject)

    response = _post(api_client)

    assert response.status_code == 400
    assert response.json() == {"detail": "start_time must fall on a 15-minute boundary"}


@pytest.mark.django_db
def test_unexpected_value_error_is_a_500_in_json(api_client, monkeypatch):
    def broken(**kwargs):
        raise ValueError("duration_min must be positive, got 0")

    monkeypatch.setattr("trips.views.plan_trip", broken)
    api_client.raise_request_exception = False

    response = api_client.post(PLAN_URL, VALID, format="json")

    assert response.status_code == 500
    assert response["Content-Type"] == "application/json"
    assert response.json() == {"detail": "Something went wrong on our side. Please try again."}
    assert "duration_min" not in response.content.decode()


def test_malformed_trip_id_returns_json_404(api_client):
    response = api_client.get("/api/trips/abc/")

    assert response.status_code == 404
    assert response["Content-Type"] == "application/json"
    assert response.json() == {"detail": "Not found."}


@pytest.mark.django_db
def test_twenty_first_plan_request_in_a_minute_is_throttled(api_client, fake_ors):
    fake_ors(straight_trip(50, 700))

    statuses = [_post(api_client).status_code for _ in range(21)]

    assert statuses == [201] * 20 + [429]
    assert "throttled" in _post(api_client).json()["detail"]


@pytest.mark.django_db
def test_geometry_is_simplified_and_rounded(api_client, fake_ors):
    fake_ors(straight_trip(50, 700))  # 71 collinear vertices

    body = _post(api_client).json()

    geometry = body["route"]["geometry"]
    assert len(geometry) == 2  # a straight road needs only its ends
    assert geometry[0] == [35.0, -101.0]
    assert all(value == round(value, 5) for point in geometry + body["route"]["bbox"] for value in point)
    assert all(stop["lat"] == round(stop["lat"], 5) and stop["lng"] == round(stop["lng"], 5) for stop in body["stops"])


@pytest.mark.django_db
def test_trip_persists_and_detail_returns_the_same_payload(api_client, fake_ors, django_assert_num_queries):
    fake_ors(straight_trip(100, 2000))
    created = _post(api_client).json()

    trip = Trip.objects.get(pk=created["id"])
    assert Stop.objects.filter(trip=trip).count() == len(created["stops"])
    assert LogDay.objects.filter(trip=trip).count() == len(created["days"])

    with django_assert_num_queries(3):  # the trip, its stops, its days: constant however many rows each has
        response = api_client.get(f"/api/trips/{created['id']}/")

    assert response.status_code == 200
    assert response.json() == created


@pytest.mark.parametrize(
    ("restart_required", "end", "added"), [(False, 41.0, 31.0), (True, 21.0, 21.0)], ids=["no-restart", "restart"],
)
@pytest.mark.django_db
def test_trip_stored_before_the_cycle_fields_existed_reads_back_with_estimates(
    api_client, fake_ors, restart_required, end, added,
):
    fake_ors(straight_trip(50, 700))
    created = _post(api_client).json()  # current_cycle_used is 10
    trip = Trip.objects.get(pk=created["id"])
    legacy = {key: value for key, value in trip.summary.items() if key not in ("cycle_used_at_start_hours", "on_duty_added_hours")}
    trip.summary = {**legacy, "cycle_used_at_end": end, "restart_required": restart_required}
    trip.save()

    response = api_client.get(f"/api/trips/{created['id']}/")

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["cycle_used_at_start_hours"] == 10
    assert summary["on_duty_added_hours"] == added


@pytest.mark.django_db
def test_a_failed_save_still_returns_the_full_plan_marked_unstored(api_client, fake_ors, monkeypatch):
    fake_ors(straight_trip(100, 2000))
    stored_body = _post(api_client).json()
    cache.clear()  # the second plan must not be throttled or served differently

    def fail(*args, **kwargs):
        raise DatabaseError("database is locked")

    monkeypatch.setattr(Trip.objects, "create_from_payload", fail)
    response = _post(api_client)

    assert response.status_code == 201
    body = response.json()
    assert body["stored"] is False
    unstored = {key: value for key, value in body.items() if key not in ("id", "stored")}
    assert unstored == {key: value for key, value in stored_body.items() if key not in ("id", "stored")}
    assert api_client.get(f"/api/trips/{body['id']}/").status_code == 404


@pytest.mark.django_db
def test_unknown_trip_id_returns_404(api_client):
    response = api_client.get(f"/api/trips/{uuid.uuid4()}/")

    assert response.status_code == 404
    assert response.json() == {"detail": "No saved trip has this link. It may have been mistyped."}


@pytest.mark.django_db
def test_limits_match_constants(api_client, fake_ors):
    fake_ors(straight_trip(50, 700))

    body = _post(api_client).json()

    assert body["limits"] == planner.limits()
    assert body["limits"]["cycle_limit_min"] == 4200


def test_limits_endpoint_serves_the_plan_limits_unthrottled_and_cacheable(api_client):
    responses = [api_client.get("/api/limits/") for _ in range(10)]  # well past the plan endpoint's 5/min

    assert [response.status_code for response in responses] == [200] * 10
    assert responses[0].json() == {"limits": planner.limits()}
    assert "max-age" in responses[0]["Cache-Control"]


@pytest.mark.django_db
def test_on_duty_added_is_exact_where_end_minus_start_is_not(api_client, fake_ors):
    fake_ors(straight_trip(50, 5000))

    body = _post(api_client, current_cycle_used=10).json()
    summary = body["summary"]

    assert summary["days"] > 8
    on_duty_from_sheets = sum(day["totals"]["DRIVING"] + day["totals"]["ON_DUTY_NOT_DRIVING"] for day in body["days"])
    assert summary["cycle_used_at_start_hours"] == 10
    assert summary["on_duty_added_hours"] == on_duty_from_sheets
    # Over eight days the live cycle has shed hours (here through the restart), so end minus start understates the trip.
    assert summary["cycle_used_at_end"] - summary["cycle_used_at_start_hours"] < summary["on_duty_added_hours"]


@pytest.mark.django_db
def test_violations_present_and_empty(api_client, fake_ors):
    fake_ors(straight_trip(50, 700))

    assert _post(api_client).json()["violations"] == []


@pytest.mark.django_db
def test_timezone_is_top_level_and_survives_storage(api_client, fake_ors):
    fake_ors(straight_trip(50, 700))

    created = _post(api_client, timezone="America/Chicago", start_time="2026-09-16T06:00:00-05:00").json()
    stored = api_client.get(f"/api/trips/{created['id']}/").json()

    assert created["timezone"] == stored["timezone"] == "America/Chicago"
    assert created["stops"][0]["arrive"].endswith("-05:00")


def test_prod_trusts_exactly_one_proxy_hop_and_shares_throttle_counts_across_workers():
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    # Settings read the environment at import, so load prod in a fresh interpreter rather than this configured one.
    env = {**os.environ, "SECRET_KEY": "x" * 50, "DATABASE_URL": "sqlite://:memory:", "ALLOWED_HOSTS": "example.com",
           "RENDER_EXTERNAL_HOSTNAME": "spotter-eld-api.onrender.com"}
    env.pop("DJANGO_SETTINGS_MODULE", None)
    script = ("import json, config.settings.prod as prod; "
              "print(json.dumps([prod.REST_FRAMEWORK, prod.CACHES, prod.ALLOWED_HOSTS]))")
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, check=True,
    )

    rest_framework, caches, allowed_hosts = json.loads(result.stdout)
    assert rest_framework["NUM_PROXIES"] == 1
    assert caches["default"]["BACKEND"] == "django.core.cache.backends.db.DatabaseCache"
    assert allowed_hosts == ["example.com", "spotter-eld-api.onrender.com"]
    assert rest_framework["EXCEPTION_HANDLER"] == "trips.exceptions.api_exception_handler"
