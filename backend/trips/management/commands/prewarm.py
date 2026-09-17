"""Plan a route once so its geocoding is in the persistent cache before the demo link goes out (spec §28)."""
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from trips.serializers import TripPlanRequestSerializer
from trips.services import geocode, geocode_cache, http, planner, routing
from trips.services.errors import NotFoundError, UpstreamError

ENDPOINTS = {geocode.SEARCH_URL: "search", geocode.REVERSE_URL: "reverse", routing.DIRECTIONS_URL: "directions"}


class Command(BaseCommand):
    help = "Plan a trip once, caching its geocoding, and report cache hits against ORS calls."

    def add_arguments(self, parser):
        parser.add_argument("current_location")
        parser.add_argument("pickup_location")
        parser.add_argument("dropoff_location")
        parser.add_argument("--cycle-hours", type=float, default=0.0, help="Hours already used in the cycle (default 0)")
        parser.add_argument("--start-time", help="ISO 8601, e.g. 2026-09-21T06:00:00-05:00 (default now)")
        parser.add_argument("--timezone", help="Home terminal IANA zone (default America/New_York)")

    def handle(self, *args, **options):
        fields = ("current_location", "pickup_location", "dropoff_location", "start_time", "timezone")
        data = {field: options[field] for field in fields if options[field] is not None}
        request = TripPlanRequestSerializer(data={**data, "current_cycle_used": options["cycle_hours"]})
        if not request.is_valid():
            raise CommandError(f"Invalid trip: {request.errors}")

        lookups = Counter()  # (kind, "cache" | "network")
        calls = Counter()  # endpoint
        failures = Counter()  # (endpoint, HTTP status)
        real_lookup, real_request = geocode_cache.lookup, http.request_json

        def counted_lookup(kind, key):
            row = real_lookup(kind, key)
            lookups[kind, "cache" if row is not None else "network"] += 1
            return row

        def counted_request(method, url, **kwargs):
            endpoint = ENDPOINTS.get(url, url)
            calls[endpoint] += 1
            try:
                return real_request(method, url, **kwargs)
            except UpstreamError as error:
                failures[endpoint, error.status] += 1
                raise

        # The command counts through the same seams the tests use, and puts them back however planning ends.
        geocode_cache.lookup, http.request_json = counted_lookup, counted_request
        try:
            plan = planner.plan_trip(**request.planner_arguments())
        except (NotFoundError, UpstreamError) as error:
            raise CommandError(str(error)) from error
        finally:
            geocode_cache.lookup, http.request_json = real_lookup, real_request

        write = self.stdout.write
        write(f"{' -> '.join(data[field] for field in fields[:3])}: {plan.summary.total_miles:,.0f} mi, "
              f"{plan.summary.days} log sheets, {len(plan.stops)} stops")
        for stop in plan.stops:
            write(f"  {stop.kind.name:<8} mile {stop.at_mile:>8.1f}  {stop.label}")
        for kind in (geocode_cache.FORWARD, geocode_cache.REVERSE):
            cached, fetched = lookups[kind, "cache"], lookups[kind, "network"]
            write(f"{kind:<8} lookups {cached + fetched:>3}: {cached:>3} from cache, {fetched:>3} from ORS")
        write(f"ORS calls {sum(calls.values()):>3}: " + ", ".join(f"{name} {calls[name]}" for name in ("search", "reverse", "directions")))
        for (endpoint, status), count in sorted(failures.items(), key=str):
            self.stderr.write(f"  {count} {endpoint} call(s) failed with HTTP {status}; those answers were not cached, so run again later")
