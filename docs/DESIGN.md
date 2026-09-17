# spotter-eld: Design

The design record for spotter-eld, a Django and React trip planner that produces FMCSA hours-of-service logs. It was written before the build as the single source of truth and amended as live testing turned up problems; the amendments are left in place, so the notes read as decisions with their reasons rather than as a clean-room spec.

Sections 1 and 2 of the working copy (the assignment text and a table of private reference files) are omitted. The remaining sections keep their numbers, so references such as "spec §28" in code comments still resolve here.

---

## 3. Regulatory scope (49 CFR Part 395, property-carrying, 70hr/8day)

### In scope, must be implemented

**11-hour driving limit (§395.3(a)(3)).** Maximum 11 hours of driving after 10 consecutive hours off duty.

**14-hour driving window (§395.3(a)(2)).** Driving is prohibited after the 14th consecutive hour from the moment any work starts. The window does not pause for breaks or meals. Only 10 consecutive hours off duty or sleeper berth resets both the 11 and the 14.

**30-minute break (§395.3(a)(3)(ii)).** Required after 8 cumulative, not consecutive, hours of driving. Must be 30 consecutive minutes of non-driving. May be logged off duty, on duty not driving, or sleeper berth. Does not extend the 14-hour window. Pickup, dropoff, and fueling stops satisfy it when they are consecutive and at least 30 minutes.

**70 hours / 8 days (§395.3(b)).** Rolling window over total on-duty time, meaning driving plus on-duty not driving. Oldest day drops off. Once at 70, driving stops. Other on-duty work is still permitted.

**34-hour restart (§395.3(c)).** Optional. If the cycle blocks the trip, insert 34 consecutive off-duty hours, reset the cycle to zero, and annotate it in remarks.

**On-duty work after hour 14 is legal.** Only driving is prohibited. Model the 14-hour rule as a constraint on driving, never as something that force-ends the day.

**Fueling is on-duty time (§395.2).** "All time inspecting, servicing, or conditioning any truck, including fueling it." It burns the 14-hour window and the 70-hour cycle, not driving time.

**RODS content (§395.8).** Every log page needs date, total miles driving today, truck and trailer numbers, carrier name, main office address, driver signature, co-driver name, home terminal time zone, remarks with city and state at every duty status change, per-status total hours summing to 24, and shipping document number or shipper and commodity.

### Out of scope, hooks only

Named placeholder classes with a CFR citation and `NotImplementedError`. Not registered in the active rule tuple.

- `AdverseDrivingRule` (§395.1(b)(1)) — out of scope: the assignment assumes no adverse driving conditions
- `SplitSleeperBerthRule` (§395.1(g))
- `ShortHaulRule` (§395.1(e))
- `SixtyHourCycleRule` (§395.3(b), 60/7 variant)

---

## 4. Assumptions we are making

The assignment does not specify these. Each one goes in the README with its reasoning so the reviewer sees deliberate choices rather than guesses.

| Assumption | Value | Basis |
|---|---|---|
| Average speed | 55 mph | Standard trucking planning figure. Brief gives no speed |
| Fuel stop duration | 30 minutes, on duty not driving | Brief gives frequency only |
| Pickup duration | 1 hour, on duty not driving | Given |
| Dropoff duration | 1 hour, on duty not driving | Given |
| Driver starting condition | Fresh off 10 consecutive hours off duty | Only a cycle-hours aggregate is supplied, no duty history |
| Rest status | 10-hour rests logged as sleeper berth, 30-minute breaks as off duty | Either is legal. Consistency matters more than the choice |
| Prior cycle hours | Seeded as one lump that never rolls off | Input is a single aggregate, not a per-day history |
| Time zone | Single home terminal zone, supplied in the request | §395.8 requires terminal time even across zones |

---

## 5. Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Django 5 + DRF, Python 3.12 | Required by the assignment |
| Frontend | React 18 + Vite + TypeScript | Payload has real shape, TS earns its keep |
| Map display | Leaflet + OpenStreetMap tiles | No key, no card on file |
| Routing | OpenRouteService `/v2/directions/driving-hgv` | Free key, 2000 req/day, truck profile |
| Geocoding | OpenRouteService `/geocode/search` (Pelias) | Same key, avoids Nominatim rate limits |
| DB | SQLite local, Postgres on Render | Trip persistence is cheap to add |
| Backend host | Render free web service | Django on Vercel serverless is awkward |
| Frontend host | Vercel | Suggested by the assignment |
| Tests | pytest + pytest-django, vitest on the frontend | |

API keys live in backend env vars only. The browser never calls ORS directly.

---

## 6. File tree

Generated from the repository at the deploy step (§29): a snapshot, not a plan. `node_modules`, `venv`, `__pycache__`, `.git`, `dist` and `.pytest_cache` are omitted, and migrations are named by folder only.

```
spotter-eld/
├── backend/
│   ├── config/
│   │   ├── settings/
│   │   │   ├── __init__.py                                  empty; manage.py, wsgi.py and asgi.py pick dev or prod
│   │   │   ├── base.py                                      shared settings, secrets and hosts from env
│   │   │   ├── dev.py                                       DEBUG on, SQLite fallback, localhost CORS
│   │   │   └── prod.py                                      DEBUG off, Postgres, database cache, HTTPS, one trusted proxy
│   │   ├── __init__.py
│   │   ├── asgi.py                                          DJANGO_ENV defaults to prod
│   │   ├── urls.py                                          includes trips.urls only
│   │   └── wsgi.py                                          gunicorn entry, DJANGO_ENV defaults to prod
│   ├── tests/
│   │   ├── hos/
│   │   │   ├── __init__.py
│   │   │   ├── test_engine.py
│   │   │   ├── test_primitives.py
│   │   │   ├── test_purity.py                               AST: no django, requests or datetime in hos/
│   │   │   ├── test_rules.py
│   │   │   ├── test_segments.py
│   │   │   ├── test_sheets.py
│   │   │   └── test_state.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── test_geocode.py                              includes the persistent cache tests
│   │   │   ├── test_network_boundary.py                     AST: only http, geocode and routing import an HTTP client
│   │   │   ├── test_planner.py                              includes naming tiers and prewarm
│   │   │   ├── test_route_index.py
│   │   │   └── test_routing.py
│   │   ├── __init__.py
│   │   ├── conftest.py                                      fixtures, canned ORS payloads, FakeOrs
│   │   └── test_api.py
│   ├── trips/
│   │   ├── management/
│   │   │   ├── commands/
│   │   │   │   ├── __init__.py
│   │   │   │   └── prewarm.py                               plans a route to fill the geocode cache, reports hits (§28)
│   │   │   └── __init__.py
│   │   ├── migrations/                                      0001 trips, 0002 geocode cache
│   │   ├── services/
│   │   │   ├── hos/
│   │   │   │   ├── __init__.py                              public surface: plan_duty, DutyEvent, DutyStatus
│   │   │   │   ├── constants.py                             every limit, single source of truth
│   │   │   │   ├── engine.py                                the loop
│   │   │   │   ├── enums.py                                 DutyStatus, StopKind
│   │   │   │   ├── events.py                                DutyEvent, Waypoint, RestRequirement
│   │   │   │   ├── rules.py                                 rule classes and the active tuple
│   │   │   │   ├── segments.py                              midnight splitting
│   │   │   │   ├── sheets.py                                DaySheet assembly
│   │   │   │   └── state.py                                 DriverState, apply_event, replay
│   │   │   ├── __init__.py
│   │   │   ├── errors.py                                    NotFoundError, RouteTooLongError, UpstreamError, InputError
│   │   │   ├── geocode.py                                   network: forward and reverse Pelias, lru then database cache
│   │   │   ├── geocode_cache.py                             persistent GeocodeCache reads and writes; may import Django (§28)
│   │   │   ├── http.py                                      shared session, timeouts, retry policy; the mock seam
│   │   │   ├── planner.py                                   orchestration, the only module aware of both geo and HOS
│   │   │   ├── route_index.py                               pure, bisect over cumulative distance
│   │   │   └── routing.py                                   network: driving-hgv directions
│   │   ├── __init__.py
│   │   ├── admin.py                                         Trip admin with stop and day inlines
│   │   ├── apps.py
│   │   ├── exceptions.py                                    service errors to HTTP statuses, JSON 404 and 500
│   │   ├── models.py                                        Trip, Stop, LogDay, GeocodeCache
│   │   ├── serializers.py                                   TripPlanRequest, TripPlanResponse
│   │   ├── urls.py                                          health/, limits/, trips/plan/, trips/<uuid>/
│   │   └── views.py                                         HealthView, LimitsView, PlanTripView, TripDetailView
│   ├── .env.example                                         every env var the backend reads
│   ├── manage.py                                            DJANGO_ENV defaults to dev
│   ├── pytest.ini                                           pins config.settings.dev
│   ├── requirements-dev.txt                                 pytest, pytest-django, pytest-cov, responses
│   └── requirements.txt                                     pinned runtime dependencies
├── docs/
│   └── DESIGN.md                                            design decisions, API contract and the amendment history behind them
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── __tests__/
│   │   │   │   └── client.test.ts
│   │   │   └── client.ts                                    one axios instance, baseURL from VITE_API_URL
│   │   ├── components/
│   │   │   ├── __tests__/
│   │   │   │   ├── CycleMeter.test.tsx
│   │   │   │   ├── DayTabs.test.tsx
│   │   │   │   ├── johnDoeDay.json                          page 18 of the FMCSA guide, serialized
│   │   │   │   ├── leafletMock.tsx                          react-leaflet stand-ins and the shared mock map
│   │   │   │   ├── LogGrid.test.tsx
│   │   │   │   ├── LogSheet.test.tsx
│   │   │   │   ├── PlanPage.test.tsx
│   │   │   │   ├── RouteMap.test.tsx
│   │   │   │   ├── ScrollX.test.tsx
│   │   │   │   ├── StopTimeline.test.tsx
│   │   │   │   └── TripForm.test.tsx
│   │   │   ├── states/
│   │   │   │   ├── EmptyState.tsx
│   │   │   │   ├── ErrorState.tsx
│   │   │   │   ├── LoadingState.tsx
│   │   │   │   ├── ResultsSkeleton.tsx                      placeholder blocks behind idle, loading and error
│   │   │   │   └── states.css
│   │   │   ├── CycleMeter.css
│   │   │   ├── CycleMeter.tsx                               cycle bar from the summary
│   │   │   ├── DayTabs.css
│   │   │   ├── DayTabs.tsx                                  one tab per sheet, print all
│   │   │   ├── LogGrid.css
│   │   │   ├── LogGrid.tsx                                  24x4 SVG only
│   │   │   ├── LogSheet.css
│   │   │   ├── LogSheet.tsx                                 full paper form
│   │   │   ├── PlanPage.tsx                                 layout and the state switch (lives here, not in pages/)
│   │   │   ├── RouteMap.css
│   │   │   ├── RouteMap.tsx                                 Leaflet map, markers, fly-to on select
│   │   │   ├── ScrollX.css
│   │   │   ├── ScrollX.tsx                                  sideways-scroll wrapper with edge fades
│   │   │   ├── StopTimeline.css
│   │   │   ├── StopTimeline.tsx                             stop table, bidirectional hover
│   │   │   ├── TripForm.css
│   │   │   ├── TripForm.tsx                                 the four inputs, Advanced start time and zone
│   │   │   ├── TripSummary.css
│   │   │   └── TripSummary.tsx                              summary figures, share link
│   │   ├── hooks/
│   │   │   ├── __tests__/
│   │   │   │   └── useTripPlan.test.tsx
│   │   │   ├── useLimits.ts                                 fetches /api/limits/ on mount
│   │   │   ├── useTripPlan.ts                               idle | loading | error | success, plan or open by id
│   │   │   └── useTripUrl.ts                                /trip/:id via the history API, no router library
│   │   ├── lib/
│   │   │   ├── __tests__/
│   │   │   │   ├── format.test.ts
│   │   │   │   ├── limits.test.ts
│   │   │   │   ├── logGrid.test.ts
│   │   │   │   └── stops.test.ts
│   │   │   ├── cycle.ts                                     cycle meter model
│   │   │   ├── format.ts                                    hours, miles, terminal-time formatting
│   │   │   ├── limits.ts                                    parseLimits narrows the limits object once (§26)
│   │   │   ├── logGrid.ts                                   pure coordinate math
│   │   │   ├── stops.ts                                     stop kind labels, glyphs, colours; pin spreading
│   │   │   └── tripForm.ts                                  form values, client-side validation, request shape
│   │   ├── test/
│   │   │   ├── fixtures.ts                                  API limits, John Doe day, trip plan
│   │   │   ├── setup.ts                                     Testing Library cleanup
│   │   │   └── tripPlan.json                                real planner output, Chicago to Denver
│   │   ├── index.css                                        chrome tokens, light and dark
│   │   ├── main.tsx                                         mounts PlanPage
│   │   ├── types.ts                                         mirrors the API contract
│   │   └── vite-env.d.ts
│   ├── .env.example                                         VITE_API_URL
│   ├── index.html                                           Vite entry, fonts
│   ├── package-lock.json
│   ├── package.json
│   ├── tsconfig.json
│   ├── vercel.json                                          Vite build, /trip/* rewrite to index.html
│   └── vite.config.ts
├── .gitignore
└── render.yaml                                              Render Blueprint: API web service and free Postgres
```

---

## 7. Layering rules

```
views  ->  serializers  ->  services/planner
                                  |
                    +-------------+-------------+
                    |                           |
            geocode / routing            services/hos/*
            (network, mockable)          (pure, stdlib only)
                    |
              route_index (pure)
```

Imports flow one direction, downward. Hard constraints:

- `services/hos/` imports no Django, no `requests`, no `datetime`. `math`, `bisect`, `enum`, `dataclasses` and `typing` are fine. `import trips.services.hos.engine` must work with Django unconfigured. `tests/hos/test_purity.py` walks the AST and fails the build if any of those appear.
- `geocode.py` and `routing.py` are the only modules that touch the network. Explicit timeouts. Geocode results cached by normalized address string. Both mockable at the `services/http.py` seam.
- `views.py` is thin. Serializer validates, service is called, serialized result is returned. No business logic.
- Routes live in `trips/urls.py`. `config/urls.py` only includes it.

No abstractions beyond what is in this document. No plugin registries, no repository pattern, no DI framework.

---

## 8. Domain model

**Time.** One internal unit everywhere on the backend: integer minutes since trip start. Conversion to wall clock happens in exactly one place, the response serializer, using the home terminal time zone from the request. `sheets.py` never sees a `datetime`. It receives `minutes_to_first_midnight` as a plain integer.

**DutyStatus.** Enum, four members, declared in form order so `status.row_index` falls out of the ordering:

```
OFF_DUTY, SLEEPER_BERTH, DRIVING, ON_DUTY_NOT_DRIVING
```

**DutyEvent.** Frozen dataclass:

```
status: DutyStatus
start_min: int
duration_min: int
at_mile: float
kind: StopKind | None = None    # FUEL and RESTART drive resets in apply_event
location: str | None = None     # "Richmond, VA"
remark: str | None = None
```

`at_mile` exists because the engine knows the mile position when it inserts a rest but must not geocode. It records the mile and leaves `location=None`. The planner fills location afterward with `dataclasses.replace` using the RouteIndex. Without this, engine-inserted rests cannot get the remarks §395.8 requires.

**Waypoint.** Frozen dataclass: `at_mile, kind, label, duration_min`. Built by the planner, consumed by the engine.

**StopKind.** Enum: `START, PICKUP, DROPOFF, FUEL, BREAK, REST, RESTART`. One enum drives both the map marker and the timeline row.

**DriverState.** Frozen dataclass of accumulators only, no decision-making methods:

```
driving_min, window_min, since_break_min, non_driving_run_min,
miles_since_fuel, window_open: bool, day_on_duty: tuple[int, ...]
```

There is no scalar `cycle_min` field. `day_on_duty` is the single source of truth for the cycle, holding per-day on-duty minutes and appended as the trip crosses midnights. `cycle_min` is a computed property:

```
cycle_min = sum(day_on_duty[-CYCLE_DAYS:])
```

Prior cycle hours from the request are seeded as one synthetic entry at index 0, representing the collapsed previous eight days. It rolls off naturally once eight new days accumulate. Two counters that can disagree is a bug waiting to happen, so there is only one.

**Window accumulation.** `window_min` increases on every event once work has started, including off-duty breaks, meals and short sleeper periods, because the 14 hours are consecutive clock hours. The only thing that resets it is a qualifying rest of 10 hours or more. This lives in `apply_event` and nowhere else.

`apply_event(state, event) -> DriverState` is a module-level pure function in `state.py`.

**Constants.** `constants.py` holds every limit as a named integer in minutes. Nothing anywhere else contains a magic number. The API response carries a `limits` object built from that module, and the frontend reads limits from the payload. TypeScript never hardcodes a limit.

---

## 9. Rules

Each rule is a small class:

```
driving_allowance(state) -> int          minutes of driving permitted before this rule binds
rest_requirement() -> RestRequirement    what must happen when it binds
```

`RestRequirement` is declarative: `status, duration_min, kind`. It carries **no** reset list. `apply_event` in `state.py` is the single authority on what any event does to state, keyed off status, duration and `kind`. No rule mutates state, no if/elif chain decides what a rest does, and nothing anywhere resets a field by reflecting on its name.

| Rule | Allowance | Rest when it binds | `kind` |
|---|---|---|---|
| `SeventyHourCycleRule` | `CYCLE_LIMIT_MIN - cycle_min` | `RESTART_MIN` OFF_DUTY | `RESTART` |
| `FourteenHourWindowRule` | `WINDOW_LIMIT_MIN - window_min` | `QUALIFYING_REST_MIN` SLEEPER_BERTH | `REST` |
| `ElevenHourRule` | `DRIVE_LIMIT_MIN - driving_min` | `QUALIFYING_REST_MIN` SLEEPER_BERTH | `REST` |
| `ThirtyMinuteBreakRule` | `BREAK_AFTER_DRIVE_MIN - since_break_min` | `BREAK_DURATION_MIN` OFF_DUTY | `BREAK` |
| `FuelStopRule` | `int((FUEL_INTERVAL_MI - miles_since_fuel) / AVG_SPEED_MPH * MINUTES_PER_HOUR)` | `FUEL_DURATION_MIN` ON_DUTY_NOT_DRIVING | `FUEL` |

A 34-hour restart trivially contains 10 consecutive hours off duty, so `apply_event` resets driving, window and break from its duration alone, and flattens the cycle from its `kind`. Every allowance returns integer minutes, including the fuel rule. All constant names are the §23 names; no aliases.

**Tuple order is the tie-break order.** When two rules report zero, the first wins. A 10-hour rest does not restore an exhausted cycle, and a 30-minute break does not restore the 14-hour window. This tuple in `rules.py` is the only place rule priority is encoded.

`FuelStopRule` is operational rather than 49 CFR, but it has the identical shape. Keeping it as a rule is what lets `miles_since_fuel` stay in DriverState instead of being special-cased in the loop. Say so in its docstring.

---

## 10. Engine

```
plan_duty(waypoints, initial_state, minutes_to_first_midnight) -> list[DutyEvent]
```

`minutes_to_first_midnight` is strictly in the range 1 to 1440. A trip starting at exactly 00:00 sends 1440, never 0. `plan_duty` raises `ValueError` outside that range, and also when waypoint miles are not non-decreasing or the first is below zero.

Loop:

1. `allowance = min(rule.driving_allowance(state) for rule in RULES)`
2. if `allowance <= 0`: find the first rule reporting zero, emit its rest event, apply the reset, continue
3. `chunk = min(allowance, ceil_to_grid(minutes_to_next_waypoint), minutes_to_next_midnight)`
4. emit a DRIVING event of `chunk`, advance state and mile
5. on reaching a waypoint, emit its ON_DUTY_NOT_DRIVING event of `waypoint.duration_min`

No long if/elif chain. Events append to one list, once per event. No list concatenation or string `+=` inside loops.

Two behaviors that must be exactly right:

**Non-driving work continues past hour 14.** The 14-hour rule returns a driving allowance of zero. It forbids driving, it does not end the day. If the driver reaches hour 14 already parked at the dropoff, the dropoff hour is emitted as on-duty work, added to window and cycle, and only then is the rest inserted.

**Breaks are satisfied by work.** `apply_event` accrues `non_driving_run_min` across a consecutive run of non-driving events and clears `since_break_min` when the run reaches `BREAK_QUALIFY_MIN`. Pickup, dropoff and fuel stops clear the requirement for free, so the engine never inserts a redundant break right after an hour of loading, and a stop cut in half at midnight still earns its credit. This lives in `apply_event` only, so it applies identically to every non-driving status. See §24 rule 4.

**15-minute alignment by construction, never by snapping.** Nothing is rounded after the fact. Instead:

- Allowances round **down** to a multiple of 15: `floor_to_grid(allowance)`
- Distance-derived minutes round **up**: `ceil_to_grid(miles / AVG_SPEED_MPH * MINUTES_PER_HOUR)`
- Every limit in `constants.py` (660, 840, 480, 4200, 2040) and every waypoint duration (60, 60, 30) is already a multiple of 15

So every emitted duration is a multiple of 15 and the totals are exact. An allowance of 1 to 14 minutes floors to zero and triggers its rest slightly early, which is legal and conservative. This cannot loop forever, because the inserted rest resets the accumulator that bound. Snapping after emission would let a chunk round up past its allowance, which is a violation, or round down to a zero-length chunk, which hangs the loop. Do not do it.

**No rest after the final waypoint.** The loop terminates when the last waypoint is consumed. The end-of-trip dropoff never gets a trailing 10-hour rest appended.

**No work event crosses midnight.** Minutes-to-next-midnight is one of the terms in the chunk `min()`, and **every** DRIVING or ON_DUTY_NOT_DRIVING event straddling a boundary is emitted as two events, whether a waypoint or a rule produced it. A fuel stop is on-duty time, so it splits like any other work. This keeps `day_on_duty` exact without the engine reasoning about calendars. OFF_DUTY and SLEEPER_BERTH rests stay whole and are split later by `split_at_midnight`, which is harmless because they contribute nothing to the cycle, and keeping them whole is what preserves their qualifying length.

Splitting a stop produces two events at the same mile with the same `kind`. The planner merges adjacent events sharing both when it builds the stops list, so the map and timeline show one stop.

---

## 11. Midnight splitting and day sheets

Two pure functions, deliberately separate:

```
split_at_midnight(events, minutes_to_first_midnight) -> list[list[DutyEvent]]
build_sheets(day_buckets, minutes_to_first_midnight, prior_cycle_min, restart_day_indices) -> list[DaySheet]
```

`restart_day_indices` is a `frozenset[int]` of the day indices on which a 34-hour restart completes. The planner derives it from the engine's events, which carry `kind`. Sheets do not detect restarts themselves.

`split_at_midnight` walks the event list once, maintaining the index of the current day bucket. Events straddling a boundary are cut in two, with the second half keeping status, kind, location and mile. Single pass, no per-day filter.

Day boundary is midnight in the home terminal time zone. All logged times use that zone even when the route crosses zones.

`DaySheet`:

```
date_index, segments[], totals{off, sb, drive, on},
total_miles_driving, remarks[{at_min, location}], recap{...}
```

Adjacent events sharing a status merge into one segment, so every segment boundary is a status change.

**Remarks.** One at every status change **whose location differs from the previous remark**. The driver writes a city once per place, not once per status change: page 18 of the guide shows six labels for twelve changes, because each stop is both entered and left at the same place. Every sheet after day 0 also gets a remark at minute 0 carrying the location of the event in progress at midnight, which is the form's "place you reported". Day 0 gets one too when its first event starts at minute 0, since a trip beginning at midnight has no leading padding and therefore no early status change to carry the location.

`segments` use minutes from midnight, 0 to 1440, snapped to 15.

**Padding.** `build_sheets` fills the time before the first event on the first day and after the last event on the final day as OFF_DUTY. This is a presentation concern of "this sheet covers a full 24 hours", so it belongs here and not in the engine.

**Invariant, asserted in tests for every sheet:** `off + sb + drive + on == 1440`.

`recap` carries on-duty minutes today (one box on the form, holding the total of lines 3 and 4) and the 70hr/8day A, B and C boxes, computed **from the sheets' own per-day segment totals**, plus the prior-cycle seed for days before the trip. Per the printed form, **A covers the last 7 days including today** and C the last 5. B is `CYCLE_LIMIT_MIN - A`, floored at zero, and is truthfully "hours available tomorrow", because tomorrow's rolling 8-day window spans tomorrow plus those 7 days. `state.cycle_min` stays on 8 days: it is the live cycle driving the rule, a different number from the recap's tomorrow-facing projection. Say so in a comment, or it reads as a bug. Sums reach back only as far as the most recent entry in `restart_day_indices`. `day_on_duty` is engine-internal cycle bookkeeping and is never read by `sheets.py`. Do not leave the recap blank.

---

## 12. API contract

`POST /api/trips/plan/`

```json
{
  "current_location": "Richmond, VA",
  "pickup_location": "Baltimore, MD",
  "dropoff_location": "Newark, NJ",
  "current_cycle_used": 12.5,
  "start_time": "2026-09-16T06:00:00-04:00",
  "timezone": "America/New_York"
}
```

Response:

```json
{
  "id": "uuid",
  "limits": { "drive_limit_min": 660, "window_limit_min": 840, "...": 0 },
  "summary": {
    "total_miles": 412,
    "driving_hours": 7.5,
    "elapsed_hours": 13.0,
    "days": 2,
    "cycle_used_at_end": 33.0,
    "restart_required": false
  },
  "route": { "geometry": [[lat, lng]], "bbox": [] },
  "stops": [
    {
      "kind": "PICKUP", "at_mile": 108, "lat": 0, "lng": 0,
      "label": "Baltimore, MD", "arrive": "ISO", "depart": "ISO",
      "duration_hours": 1.0
    }
  ],
  "days": [],
  "violations": []
}
```

The serializer rounds `start_time` **down** to the nearest 15 minutes before anything downstream sees it, so every derived boundary lands on the grid. `start_time` defaults to now in the supplied zone, `timezone` defaults to `America/New_York`. Both sit behind an Advanced toggle in the UI so the visible form is exactly the four required inputs: current location, pickup, dropoff and current cycle used.

`violations` is a typed array that is always empty in this version. The planner is violation-free by construction, and the field exists for parity with real ELD output. Do not invent entries for it.

Validation failures return 400 with a flat readable message. Unroutable addresses return 422.

---

## 13. Log sheet rendering

Must visually reproduce the blank paper Driver's Daily Log, the standard FMCSA record-of-duty-status form.

**Grid.** 24 hourly columns, midnight to midnight, each subdivided into four 15-minute ticks. Four rows, top to bottom: Off Duty, Sleeper Berth, Driving, On Duty (Not Driving).

**Layout math** (in `lib/logGrid.ts`, not in the component):

```
GRID_X = 60, GRID_W = 960      → 40 px per hour, 10 px per 15 min
GRID_Y = <header height actually used>, ROW_H = 30   → GRID_H = 120
minutesToX(m) = GRID_X + m * (GRID_W / 1440)
statusToY(s)  = GRID_Y + s.row_index * ROW_H + ROW_H / 2
```

**The duty line.** One continuous `<polyline>` per day. Horizontal run along the status row, vertical connector at each transition, next horizontal run. `buildPolylinePoints(segments)` emits the horizontal and vertical points as consecutive entries. This mirrors how a driver's pen never leaves the paper, and it is simpler than stitching separate elements.

**Ticks.** Three heights, as printed: hour tallest and labelled, half-hour medium, quarter-hour short. `tickMarks` returns `{ x, size: 'hour' | 'half' | 'quarter', label? }`. Across a 24-hour day that is 97 positions, 25 of them on the hour and 72 between. Never emit both a major and a minor at the same x.

**Totals.** Per-status total at the right edge of each row.

**Remarks row.** Beneath the grid, city and state abbreviation at every duty status change, rotated vertical text. The anchor sits at the **end of the leader line** with `text-anchor="end"`, so the label hangs downward into the remarks band. Anchoring below the grid and rotating from there, as an earlier draft had it, runs the text upward into the grid itself.

```jsx
<text transform={`rotate(-90 ${x} ${y})`} x={x} y={y} textAnchor="end">Richmond, VA</text>
```

Two remarks 15 minutes apart are only 10px apart, so labels closer than a minimum x gap alternate between two depths in the band. Labels cap at 22 characters with an ellipsis and an SVG `<title>` carrying the full text, since a fallback like `"US-287 N near Dropoff, CC"` would otherwise clip at the viewBox edge.

**Tick direction.** Rows 1 and 2 hang their half- and quarter-hour ticks from the row's top edge; rows 3 and 4 rise from the bottom. Hour lines are full-height rules. This is what the printed form does.

**Header fields.** Date, total miles driving today, total mileage today, carrier name, main office address, home terminal address, vehicle numbers, driver signature line, co-driver, shipping document number.

**Recap block.** On-duty hours today, total of lines 3 and 4, and the 70hr/8day A, B, C boxes.

One sheet per calendar day. Longer trips produce multiple sheets.

**Component split.** `LogGrid.tsx` renders only the 24x4 SVG and contains zero arithmetic. `LogSheet.tsx` renders the full paper form and embeds `LogGrid`.

---

## 14. Frontend structure

`useTripPlan()` owns a discriminated union:

```ts
{ status: 'idle' }
| { status: 'loading' }
| { status: 'error', message: string }
| { status: 'success', data: TripPlan }
```

Every view switches on it, which makes a missing loading or error state structurally impossible. `PlanPage.tsx` is layout plus that switch, nothing else.

`lib/logGrid.ts` exports pure functions with no React import, each unit tested:

```
minutesToX(min): number
statusToY(status): number
buildPolylinePoints(segments): string
tickMarks(): {x, major}[]
remarkAnchor(atMin): {x, y, transform}
```

`api/client.ts` exports one configured axios instance with baseURL, timeout, and an error interceptor normalizing DRF validation errors into a flat message. Components import the hook, never the client. No `fetch` in components.

Loading, error and empty states on every data view.

---

## 15. Performance

- Build a `RouteIndex` once from the polyline with a cumulative-distance array, then `bisect` for mile-to-coordinate lookups. No repeated linear scans per stop.
- Bucket events into days in a single pass, not a nested filter per day.
- `prefetch_related` on any query walking related objects.
- No list concatenation or string `+=` inside loops.

**Stop naming.** A rest at mile 487 has coordinates but no name, and §395.8 requires a city or town plus a state abbreviation at every duty status change. ORS step names are roads (`"I-95 N"`), so they cannot satisfy that on their own. The chain, in order:

1. Interpolate the coordinate via `RouteIndex`, then `/geocode/reverse` it with `layers=address`, `size=10` and `boundary.circle.radius=15` (km), taking the nearest result carrying a locality, then localadmin, then county. **`layers=address` is required**: with admin-only layers Pelias runs a coarse reverse, ignores the radius entirely, and answers with whichever area contains the point, which returns a county wherever the point falls outside town limits
2. On a miss, retry once at radius 150. The nearest address can be 12 km or more out on a rural interstate, and Pelias defaults the reverse radius to 1 km
3. On a second miss, `"<road> near <city>"`, where the city is the nearest **by road mile** of the three geocoded input locations **plus every stop already resolved in this plan**. Stops resolve in mile order, so a fallback late in a long route borrows a real nearby city rather than a terminus hundreds of miles away. With no road, `"Near <city>"`. Never the bare city name, which would claim the driver is somewhere they may be 100 miles from.

When the nearest anchor is more than 50 road miles away, the label carries the distance instead of implying proximity: `"I 80, approx 1,197 mi from Boston, MA"`. This only happens when reverse geocoding is unavailable for every stop, which the §28 cache makes rare, and it is honest rather than wrong

The label is built from `locality`, then `localadmin`, then `county`. `region` is not in the chain: it yields `"Wyoming, WY"`, which is not a city or town. There is no mile-only fallback either, since three geocoded input cities are always available, so every label carries a place and a state.

Only inserted rests and stops are named, never every vertex, so the call volume is a handful per trip. Results cache by coordinate rounded to three decimals, roughly 110 metres, and **misses cache too**: the private helper returns `None` rather than raising, so a rural point is not re-queried on every request.

**`Route` shape.** `geometry` as `(lat, lng)`, `total_miles`, `named_points` as `(mile, label)` sorted by mile, `bbox` in Leaflet bounds order, and `leg_miles`, the per-segment road distances. Without `leg_miles` the planner cannot place the pickup waypoint, since only ORS knows where on the polyline the intermediate point falls.

`road_at(mile, named_points)` is a **containment** lookup, not a nearest-neighbour one: the last step start at or before the mile, via `bisect_right - 1`, returning `None` only when the mile precedes the first named point. There is no distance threshold, because a legitimate interstate step can run 350 miles and any threshold would leave a rest mid-step unnamed or, worse, attributed to a side street 250 miles back.

**Naming is best effort.** The chain catches `UpstreamError` as well as `NotFoundError` and falls through to the final tier. A flaky or rate-limited reverse lookup degrades a label; it does not fail a plan whose route is already in hand. This is the one deliberate exception to the error mapping below.

**Upstream error mapping.** HTTP 404, and HTTP 400 carrying ORS error code 2004, 2009 or 2010, become `NotFoundError` and surface as a 422. Everything else is `UpstreamError` and surfaces as a 5xx. A route past the ORS distance limit is a bad request, not a server fault.

**Timeout budget.** Geocoding uses an 8-second read timeout. **Routing gets 30 seconds**: a long route with border avoidance takes around 7 seconds every time, and a cold short route was measured at 5.4. Read timeouts are **not** retried, because a slow answer is slow computation rather than a failure; connection errors and 5xx still are. A plan makes 4 to 15 sequential ORS calls and measured 2 to 15 seconds end to end, so `render.yaml` runs gunicorn with `--timeout 60`.

**Routing options.** `avoid_borders: "controlled"`. A US log under Part 395 should not route through Ontario, which the unconstrained truck route from Los Angeles to Boston does. `avoid_countries` is silently ignored by ORS and is not an alternative.

**Forward geocoding validates the state.** Pelias almost never reports no match: `"Atlantis, ZZ"` resolves to Atlantis, FL at confidence 1. So when an address ends in a two-letter state code, the match must fall in that state or it is a `NotFoundError`. Without this the 422 path is dead code on real input.

**Coordinate order.** ORS GeoJSON is `[lng, lat]`. `routing.py` and `geocode.py` swap at the network boundary; everything inland, including the API response, is `(lat, lng)`, which is what Leaflet expects. An unswapped implementation produces plausible-looking wrong answers with no error, so its fixture must use asymmetric coordinates.

---

## 16. Config

- Settings split into `base.py`, `dev.py`, `prod.py`. `settings/__init__.py` is empty.
- `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `DATABASE_URL`, `ORS_API_KEY` from env. `DEBUG` is **not** from env: it is hardcoded `True` in `dev.py` and `False` in `prod.py`, because one typo in an env var should never ship a debug build. `prod.py` refuses to boot without `SECRET_KEY` or `DATABASE_URL`.
- `manage.py`, `wsgi.py` and `asgi.py` load `.env` via `python-dotenv` behind `try/except ImportError`, read `DJANGO_ENV`, and set `DJANGO_SETTINGS_MODULE` to `config.settings.dev` or `config.settings.prod` directly. **`manage.py` defaults to dev; `wsgi.py` and `asgi.py` default to prod**, matching how each is invoked, so a Render service missing the variable cannot boot with DEBUG on. `render.yaml` sets it explicitly regardless. An unrecognised value raises rather than falling through. Switching inside the package `__init__` lets a stray `.env` hijack pytest, which pins the settings module in `pytest.ini`.
- `psycopg[binary]` is in `requirements.txt`. Without it a `postgres://` URL fails at startup.
- `.env.example` for backend and frontend.
- Pinned `requirements.txt`, separate `requirements-dev.txt`, `.gitignore`.

---

## 17. Test plan

**Rules in isolation.** Construct a `DriverState` directly, assert the allowance. Cycle at 4199 returns 1, at 4200 returns 0. Window at 839 returns 1. `since_break` at 480 returns 0.

**Engine scenarios**, handmade waypoint lists, no network:
1. Hits the 11-hour limit before the 14-hour window
2. Hits the 14-hour window before 11 driving hours, because of a long pickup
3. 30-minute break satisfied by the one-hour pickup, asserting no extra break event exists
4. 70-hour cycle blocks driving at `cycle_used=70`, asserting the first DRIVING event is preceded by a 34-hour OFF_DUTY event. The START waypoint has duration 0, since the assignment requires no pre-trip inspection
5. Multi-day run producing four sheets with correct cycle accumulation

**FMCSA reference case.** The John Doe log from page 18 of the guide, encoded as a fixture:

> Reports 6:00 a.m. Richmond VA, on duty to 7:30. Drives 1.5h, fuels 0.5h in Fredericksburg VA. Drives 2.5h to Baltimore MD, lunch off duty. Drives 2h, 0.5h delivery in Philadelphia PA. Drives 0.5h, sleeper berth 4:00 p.m. to 5:45 p.m. in Cherry Hill NJ. Drives to Newark NJ by 7:00 p.m., on duty to 9:00 p.m., off duty after.
>
> Expected totals: off duty 10, sleeper berth 1.75, driving 7.75, on duty not driving 4.5. Sum 24.

This is the single test that says the interpretation of the regulation is correct.

It belongs to the **sheets and segments** step, not the engine step. The day contains a one-hour off-duty lunch, a 1.75-hour sleeper period, a two-hour post-trip and a fuel stop at roughly mile 80. None of those are producible by an engine rule or a waypoint. It is a hand-written `DutyEvent` list fed to `split_at_midnight` and `build_sheets`.

**Segments and sheets.** Handcrafted event lists including one event straddling midnight and one trip starting at 22:00. `off + sb + drive + on == 1440` asserted on every sheet in every test via a shared helper.

**Route index.** Known polyline, assert mile-to-coordinate against hand-computed values, plus boundaries at mile 0 and total length.

**API.** Contract shape, plus validation failures: cycle above 70, cycle negative, blank address, identical pickup and dropoff, unroutable address.

**Purity.** AST walk over `services/hos/` asserting no import of django, requests, or datetime.

All network mocked at the `services/http.py` seam with canned ORS payloads in `conftest.py`. The suite runs offline.

---

## 18. Execution order

This is a **from-scratch build**. No prior code exists. Steps 3 and 4 decide the grade; everything after is presentation.

1. Repo audit (done)
2. Scaffold: git init, Django project, settings split, urls split, `.env.example`, `.gitignore`, pinned requirements, pytest harness, health endpoint
3. `hos/` primitives and rules: constants, enums, events, state, rules, engine, purity test, rule tests, engine scenario tests
4. `segments.py` and `sheets.py` with their tests, including the John Doe fixture
5. `route_index.py` with its test
6. `geocode.py`, `routing.py`, `http.py` behind mockable seams
7. `planner.py`, orchestrating waypoints, engine, location backfill and sheets
8. Models, migration, serializers carrying the `limits` block, thin views, `test_api.py`
9. Frontend scaffold: Vite, React 18, TypeScript, vitest, `.env.example`
10. Frontend data layer: client, hook, types, then `lib/logGrid.ts` with tests
11. Components, states directory, `LogSheet` and `LogGrid` split cleanly, `PlanPage`
12. Deploy, README, Loom

---

## 19. Risks

**Render cold start.** Free tier sleeps after 15 minutes and takes 30 to 60 seconds to wake. If the reviewer opens a cold link and it hangs, it reads as broken. Mitigate with a loading state that says what is happening, plus a cron-job.org ping every 10 minutes.

**ORS rate limits.** Measured on a real free key, far below the published figures: directions 200/day, geocode search 100/day, reverse around 100/day. A long plan spends 3 searches, 1 route and about 11 reverse calls, so an uncached key dies after roughly 9 long trips. Beyond the quota, reverse returns HTTP 403 `{"error": "Quota exceeded"}` with no headers, labels silently degrade to the fallback tier, and planning eventually fails outright. This is why §28 exists. The endpoint's own 100/day throttle is never the binding constraint.

**Key leakage.** Routing and geocoding go through Django. The key is a backend env var only.

**Time zones.** Store UTC, render in the single home terminal zone. Required by §395.8 and worth showing off.

---

## 20. Deliverable polish

**README:** live URL first, one screenshot of a filled log sheet, the assumptions table from section 4 with a CFR citation per rule, then local setup.

**Loom, 4 minutes:** 60s live multi-day trip end to end, 90s on the engine loop and constraint ordering, 60s on the SVG grid math, 30s on structure and tests.

---

## 21. Working agreement for the agent

- One step at a time. Do the step named in the prompt and nothing else.
- Report back with what changed, what the tests say, and anything that contradicted this spec.
- Do not invent abstractions. If something seems to need one, raise it instead of adding it.
- Do not modify files outside the step's stated scope.
- If a decision is genuinely undetermined by this document, stop and ask. Do not guess and move on.

---

## 22. Environment notes

- Local Python may be 3.13. That is fine. Render pins 3.12 via `render.yaml`. Do not pin micro versions in `requirements.txt`.
- Confirm ORS quotas on the dashboard before step 6. Geocoding may have a lower daily cap than directions. Cache geocode results by normalized address string regardless.
- `.gitignore` must cover `.DS_Store`, `.claude/`, `venv/`, `node_modules/`, `.env`, `__pycache__/`, `*.sqlite3`, `dist/`.
- `cycle_used_at_start_hours` is the engine's seed, not the submitted figure. The seed rounds up to the whole minute, so it can exceed the input by under a minute.
- The rolling 8-day drop-off never fires on a real plan. The engine plans at the limits, so the cycle reaches 70 hours and takes a 34-hour restart before eight days elapse. The drop-off path is still implemented and tested synthetically, because a driver arriving with a partial cycle can reach it; no generated trip does.
- Trips spanning a daylight-saving changeover drift by an hour. The HOS layer treats every day as 1440 minutes and `minutes_to_first_midnight` is wall-clock, which keeps it inside 1 to 1440; measuring elapsed time instead would hand `plan_duty` a 1500-minute day on the fall-back date.
- When the current location and the pickup geocode to within an epsilon, the planner routes two points instead of three and places the pickup at mile 0, rather than depending on ORS accepting a zero-length leg.
- The API's `limits` object carries every public integer constant, not only regulatory ones. The frontend needs `GRID_RESOLUTION_MIN` and `MINUTES_PER_DAY` for the grid exactly as it needs `CYCLE_LIMIT_MIN` for the cycle meter, and the point of the object is that no number is hardcoded in TypeScript.
- Response geometry is rounded to 5 decimals and Douglas-Peucker simplified at 0.0001 degrees. `RouteIndex` keeps the full polyline server-side, so mile lookups lose no accuracy; only the wire format and the stored row are reduced.
- `prior_cycle_min` is one lump, so it stays in recap A while the 7-day window still reaches before the trip, and in C while the 5-day window does. This can overstate A and C, never understate them, and B is floored at zero.
- `total_miles_driving` is driving minutes at `AVG_SPEED_MPH`, so it can differ slightly from route distance by the grid ceiling. On a hand-written fixture from a real log it differs by more, which is expected and not a defect.
- Two accepted simplifications for the README, both legal and both erring conservative: a 30-minute break can land shortly before a forced 10-hour rest and do little useful work, which is exactly how real paper logs look; and a blocked cycle always inserts a full 34-hour restart rather than waiting for the oldest day to roll off, which would require simulating idle days for a marginal gain.
- The 10-hour qualifying rest is recognised only as a single event, not as consecutive off-duty and sleeper periods combining. The engine never emits adjacent rests, so the case cannot arise.

---

## 23. Constants (canonical values, all in minutes unless named otherwise)

```
AVG_SPEED_MPH          = 55
DRIVE_LIMIT_MIN        = 660     # 11h
WINDOW_LIMIT_MIN       = 840     # 14h
QUALIFYING_REST_MIN    = 600     # 10h, resets driving + window + since_break
BREAK_AFTER_DRIVE_MIN  = 480     # 8h cumulative driving
BREAK_QUALIFY_MIN      = 30      # a non-driving block of this length clears the break
CYCLE_LIMIT_MIN        = 4200    # 70h
CYCLE_DAYS             = 8
RESTART_MIN            = 2040    # 34h
FUEL_INTERVAL_MI       = 1000
FUEL_DURATION_MIN      = 30
PICKUP_DURATION_MIN    = 60
DROPOFF_DURATION_MIN   = 60
BREAK_DURATION_MIN     = 30      # length of the break the engine inserts
GRID_RESOLUTION_MIN    = 15
MINUTES_PER_DAY        = 1440
MINUTES_PER_HOUR       = 60
RECAP_A_DAYS           = 7       # recap box A, as printed on the form
RECAP_C_DAYS           = 5       # recap box C, as printed on the form
```

`floor_to_grid()` and `ceil_to_grid()` live in `constants.py` next to `GRID_RESOLUTION_MIN`, since that is the only place the number appears.

## 24. State transition semantics (`apply_event`)

`DriverState` fields: `driving_min`, `window_min`, `since_break_min`, `non_driving_run_min`, `miles_since_fuel`, `window_open: bool`, `day_on_duty: tuple[int, ...]`. `cycle_min` is a computed property, `sum(day_on_duty[-CYCLE_DAYS:])`.

Rules applied in this order for every event:

1. **Window opening.** DRIVING or ON_DUTY_NOT_DRIVING sets `window_open = True`. Off-duty or sleeper time before the first work of the day does not open it.
2. **Window accumulation.** If `window_open`, every event adds its duration to `window_min`, including breaks and meals.
3. **Qualifying rest.** An OFF_DUTY or SLEEPER_BERTH event of `QUALIFYING_REST_MIN` or longer sets `driving_min`, `window_min` and `since_break_min` to zero and `window_open` to False. Rule 2 runs first and rule 3 overwrites it; the end state is identical either way, so there is nothing to observe or test about the ordering.
4. **Break satisfaction.** Every non-driving event adds its duration to `non_driving_run_min`; every DRIVING event resets it to zero. When `non_driving_run_min` reaches `BREAK_QUALIFY_MIN`, `since_break_min` is set to zero. Credit accrues across a *consecutive run* rather than per event, which is what 49 CFR §395.3(a)(3)(ii) actually allows (15 minutes on duty plus 15 off duty combine). It also means a fuel stop cut in half at midnight still earns its credit.
5. **Driving.** DRIVING adds duration to `driving_min` and `since_break_min`, and adds `duration / MINUTES_PER_HOUR * AVG_SPEED_MPH` to `miles_since_fuel`.
6. **Cycle.** DRIVING and ON_DUTY_NOT_DRIVING add duration to the last element of `day_on_duty`. Off duty and sleeper add nothing.
7. **Fuel.** An event with `kind is StopKind.FUEL` sets `miles_since_fuel` to zero.
8. **Restart.** An event with `kind is StopKind.RESTART` replaces `day_on_duty` with `(0,)`. Rule 3 has already zeroed driving, window and break from its duration.

`replay(events, initial_state, minutes_to_first_midnight) -> DriverState` folds a finished event list back through `apply_event` and `advance_day`, giving the end-of-trip cycle. It lives here rather than in the planner so the midnight loop is written once and tested once, and `plan_duty` keeps its signature.

`advance_day(state)` appends a new zero to `day_on_duty`. The engine calls it when elapsed time crosses a day boundary, using an integer offset. No `datetime` is involved.

`DriverState.initial(prior_cycle_min)` seeds `day_on_duty` as `(prior_cycle_min, 0)`. A one-tuple would fold day one's work into the prior-hours entry, which corrupts the day-one figures and drops the seed a day late.

`day_on_duty` exists solely to serve `SeventyHourCycleRule` during simulation. Nothing downstream reads it, so a restart flattening it to `(0,)` loses nothing.

Mileage is derived from driving duration rather than carried on the event. Since durations are ceiled to the grid, derived mileage is never less than actual, so fuel stops trigger slightly early. Conservative and intentional.

---

## 25. API contract, as built

Frozen. The frontend builds against exactly this. One vocabulary for duty status throughout: `OFF_DUTY`, `SLEEPER_BERTH`, `DRIVING`, `ON_DUTY_NOT_DRIVING`, in that row order.

### `POST /api/trips/plan/` → 201

```
id            uuid string
timezone      IANA zone of the home terminal, e.g. "America/Chicago"
limits        { <constant_name_lowercased>: int }   every public int in constants.py
summary       { total_miles, driving_hours, elapsed_hours, days,
                cycle_used_at_start_hours, on_duty_added_hours,
                cycle_used_at_end, restart_required }
route         { geometry: [[lat, lng], ...], bbox: [[s, w], [n, e]] }
stops         [ { kind, at_mile, lat, lng, label, arrive, depart, duration_hours } ]
days          [ DaySheet ]
violations    []          always empty, typed, present for ELD parity
```

`kind` is one of `START`, `PICKUP`, `DROPOFF`, `FUEL`, `BREAK`, `REST`, `RESTART`. `arrive` and `depart` are ISO 8601 in the home terminal zone.

### DaySheet

```
date                  "YYYY-MM-DD"
date_index            int, 0-based
header                { from, to, total_mileage_today, home_terminal_timezone,
                        carrier_name, main_office_address, home_terminal_address,
                        vehicle_numbers, driver_name, co_driver, shipping_document }
segments              [ { status, start_min, end_min } ]   minutes from midnight, 0 to 1440
totals                { OFF_DUTY, SLEEPER_BERTH, DRIVING, ON_DUTY_NOT_DRIVING }   hours
total_miles_driving   float
remarks               [ { at_min, location } ]
recap                 { on_duty_today_hours, a_on_duty_last_7_days_hours,
                        b_available_tomorrow_hours, c_on_duty_last_5_days_hours }
```

Minutes for anything the grid draws, hours for anything the form prints. The header's carrier, office, terminal, vehicle, driver, co-driver and shipping fields are `null`: the request carries no inputs for them, and the form shows those lines blank.

### `GET /api/limits/` → 200

`{ limits: { ... } }`, the same object the plan response carries. The frontend fetches it on mount so the form's cycle cap, the empty-state copy and the page header read from the backend instead of repeating its numbers. Not throttled, cacheable.

### `GET /api/trips/<uuid>/` → 200

The same payload, as stored. Nothing is recomputed, so a plan reads back identically even after the rules or ORS data change.

### Errors

| Status | When | Body |
|---|---|---|
| 400 | Request validation failed | `{detail, errors}` |
| 400 | `InputError` from a service | `{detail}` |
| 404 | Unknown or malformed trip id | `{detail}` |
| 422 | `NotFoundError`: unroutable, ungeocodable, pickup equals dropoff | `{detail}` |
| 502 | `UpstreamError`: ORS failed | `{detail}` |
| 429 | Throttled | `{detail}` |

The frontend reads `detail` always and treats `errors` as optional per-field highlighting. A bare `ValueError` is a bug and returns 500; only `InputError` maps to 400.

`NotFoundError`, `UpstreamError` and `InputError` live in `trips/services/errors.py`.

### Throttling

`AnonRateThrottle` on the plan endpoint at `5/min` and `100/day`, sized to stay under the ORS free quota.

---

## 26. Frontend limit handling

`Limits` stays `Record<string, number>` on the wire, because the backend reflects it from `constants.py` and new limits must arrive without a contract change. The frontend narrows it once at the boundary:

```ts
interface RequiredLimits {
  minutes_per_day: number;
  minutes_per_hour: number;
  grid_resolution_min: number;
  cycle_limit_min: number;
  drive_limit_min: number;
  window_limit_min: number;
  break_after_drive_min: number;
}

parseLimits(limits: Limits): RequiredLimits
```

`useTripPlan` calls `parseLimits` on success and fails the request with a readable message if a key is missing. Everything downstream takes `RequiredLimits`, so a typo is a compile error rather than a blank grid. No number in `logGrid.ts` or any component is hardcoded except pixel layout.

`format.ts` is the exception: its minutes-to-hours conversion is a unit fact, not a regulatory limit, and threading `limits` through every display helper would cost more than it buys.

---

## 27. Visual direction

UI and UX are evaluated alongside accuracy, so the app is not allowed to look like an untouched component-library default.

The design idea is a deliberate contrast between two surfaces:

**The app chrome** reads like fleet dispatch software: dense, tabular, utilitarian. Tight vertical rhythm, a monospace or tabular-figure face for every number, muted neutrals with one accent used sparingly for duty-status colour, hairline rules instead of card shadows. Numbers align on their decimal point. Nothing is rounded and pillowy.

**The log sheet** reads like paper: near-white stock, hairline black rules, condensed sans caps for the printed captions, no shadows, no colour except the duty line. It should look photographed rather than designed.

That contrast is the point. The chrome is software, the sheet is a document the software produced.

Concrete rules:
- Duty statuses get one consistent colour each, used in the timeline, the legend and the map markers, but the log sheet's duty line stays black, as a pen would be
- `font-variant-numeric: tabular-nums` on every figure
- The grid never shrinks below a legible width. On narrow screens the sheet scrolls horizontally inside its own container with `overflow-x: auto`, so the page body never scrolls sideways
- Loading copy says what is happening and how long it may take, because a cold Render instance takes 30 to 60 seconds and a bare spinner reads as broken
- Any container that scrolls sideways shows it: an edge fade and a one-time hint, so hidden columns are discoverable on a phone
- The log sheet stays light in every colour scheme. It is paper, and paper does not have a dark mode. Map tiles stay light for the same reason
- Selection is bidirectional: hovering a timeline row highlights its marker, hovering a marker highlights and scrolls to its row, and selecting a stop pans and zooms the map to it. Scrolling happens on hover only, never on select, so tapping a marker on a phone does not pull the page away from the map
- Loading and error states render skeleton placeholders where the results will go, rather than leaving half the screen blank

---

## 28. Geocode cache

A free ORS key allows roughly 100 reverse lookups a day. A long plan spends about 11. Without a cache the hosted demo stops naming stops correctly after nine trips and then stops working, which is worse than any bug in this codebase, because the reviewer opens the live URL cold.

So geocode results persist in the database, not only in `lru_cache`:

- One table, `GeocodeCache`, keyed by a `kind` (`forward` or `reverse`) plus a normalised key: the lowercased whitespace-collapsed address for forward, the coordinate rounded to 3 decimals plus the radius for reverse
- Stores the resolved label and, for forward, the coordinates. A **genuine no-match is cached**, so a rural point is never re-queried. A **quota or 5xx failure is not cached**, because it is transient and caching it would freeze a degraded label in place permanently
- Read before any network call, written after a successful one. `lru_cache` stays in front of it as the per-process layer
- Entries do not expire. A town does not move, and a stale label is better than a dead demo
- The cache lives in `trips/services/geocode_cache.py`, which may import Django. `geocode.py` calls it. `hos/` purity is unaffected

A management command pre-warms a route so the demo trips are cached before the link goes out:

```
python manage.py prewarm "Amarillo, TX" "Dumas, TX" "Denver, CO" --cycle-hours 0,20,50
```

Reverse keys are coordinates, and rests land at different miles as cycle hours and start time change, so warming one setting warms only that setting. The command loops over a comma-separated spread.

It runs the planner once and reports how many lookups hit the cache against the network.

### Deploy note

Vercel needs a rewrite sending `/trip/*` to `index.html`, or every shared link 404s.

---

## 29. §6 is regenerated, not maintained by hand

The file tree in §6 was written before the build and has drifted three times. It is now regenerated from the actual repository at the deploy step and should be treated as a snapshot, not as a plan. The layering rules in §7 are what actually constrain where a file may live; the tree only records where files ended up.
