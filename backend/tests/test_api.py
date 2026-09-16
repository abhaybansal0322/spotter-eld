"""API contract tests. ORS is faked at http.request_json; the database is the pytest-django test database."""
import uuid

import pytest

from tests.conftest import straight_trip
from trips.models import LogDay, Stop, Trip
from trips.services import http, planner

PLAN_URL = "/api/trips/plan/"
VALID = {
    "current_location": "Origin, AA",
    "pickup_location": "Pickup, BB",
    "dropoff_location": "Dropoff, CC",
    "current_cycle_used": 10,
    "start_time": "2026-09-16T06:00:00-04:00",
    "timezone": "America/New_York",
}


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
    assert list(body) == ["id", "limits", "summary", "route", "stops", "days", "violations"]
    uuid.UUID(body["id"])
    assert set(body["summary"]) == {"total_miles", "driving_hours", "elapsed_hours", "days", "cycle_used_at_end", "restart_required"}
    assert set(body["route"]) == {"geometry", "bbox"}
    assert all(len(point) == 2 for point in body["route"]["geometry"])
    assert len(body["route"]["bbox"]) == 2
    for stop in body["stops"]:
        assert set(stop) == {"kind", "at_mile", "lat", "lng", "label", "arrive", "depart", "duration_hours"}
    for day in body["days"]:
        assert set(day) == {"date", "date_index", "header", "segments", "totals", "total_miles_driving", "remarks", "recap"}
        assert set(day["totals"]) == {"off", "sb", "drive", "on"}
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
    arrive = response.json()["stops"][0]["arrive"]
    assert arrive[-6:] in ("-04:00", "-05:00")  # New York
    assert int(arrive[14:16]) % 15 == 0 and arrive[17:19] == "00"


@pytest.mark.django_db
def test_unroutable_address_returns_422_with_upstream_message(api_client, fake_ors):
    message = "Could not find routable point within a radius of 350.0 meters of specified coordinate 2: -101.0 36.0."
    fake_ors(http.UpstreamError("HTTP 404", status=404, body={"error": {"code": 2010, "message": message}}))

    response = _post(api_client)

    assert response.status_code == 422
    assert response.json() == {"detail": message}
    assert Trip.objects.count() == 0


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
def test_value_error_from_the_service_returns_400(api_client, fake_ors, monkeypatch):
    fake_ors(straight_trip(50, 700))

    def reject(**kwargs):
        raise ValueError("start_time must fall on a 15-minute boundary")

    monkeypatch.setattr("trips.views.plan_trip", reject)

    response = _post(api_client)

    assert response.status_code == 400
    assert response.json() == {"detail": "start_time must fall on a 15-minute boundary"}


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


@pytest.mark.django_db
def test_unknown_trip_id_returns_404(api_client):
    response = api_client.get(f"/api/trips/{uuid.uuid4()}/")

    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.django_db
def test_limits_match_constants(api_client, fake_ors):
    fake_ors(straight_trip(50, 700))

    body = _post(api_client).json()

    assert body["limits"] == planner.limits()
    assert body["limits"]["cycle_limit_min"] == 4200


@pytest.mark.django_db
def test_violations_present_and_empty(api_client, fake_ors):
    fake_ors(straight_trip(50, 700))

    assert _post(api_client).json()["violations"] == []
