# spotter-eld

**Live app: https://spotter-eld-eight.vercel.app** · API: https://spotter-eld-api-p2rq.onrender.com · Source: https://github.com/abhaybansal0322/spotter-eld

The API is on Render's free tier. If nobody has used it for 15 minutes it goes to sleep, and the first request then takes up to 45 seconds; the loading screen tells you that's what is happening. Once it's awake, a plan comes back in 1 to 8 seconds.

![A filled Driver's Daily Log produced by the app for a Los Angeles to Boston trip](docs/images/log-sheet.png)

## What it does

You give it four things: where a property-carrying truck is now, the pickup, the dropoff, and how many hours the driver has already used in the 70-hour/8-day cycle. It routes the trip on a truck profile and schedules it under the FMCSA hours-of-service rules, inserting 30-minute breaks, 10-hour rests, fuel stops and, if the cycle runs out, a 34-hour restart. The result is a map and a stop timeline, plus one filled-in Driver's Daily Log per calendar day, drawn as the paper form a driver fills in by hand. Every plan gets a link you can share.

## Assumptions

The assignment fixes the ruleset (property-carrying, 70 hours/8 days, no adverse conditions), a fuel stop at least every 1,000 miles, and one hour each for pickup and dropoff. The rest of this table is my call, written down so you can check it.

| Assumption | Value | Basis |
|---|---|---|
| Average speed | 55 mph | Common planning figure for a loaded truck; the assignment gives no speed. Driving time is road miles at this speed |
| Pickup and dropoff | 1 hour each, on duty not driving | Given. Logged on line 4 as on-duty time (§395.2) |
| Fuel stop | 30 minutes, on duty not driving, at least every 1,000 miles | The frequency is given and I picked the duration. §395.2 counts fueling as on-duty time ("servicing... including fueling"), so a stop uses up the 14-hour window and the cycle but not driving time |
| Starting condition | Fresh off 10 consecutive hours off duty | The input is a cycle-hours total with no duty history, so the 11-hour and 14-hour clocks start at zero (§395.3(a)(1)) |
| Rest status | 10-hour rests logged as sleeper berth, 30-minute breaks as off duty | Either status is legal for either (§395.3(a)(1), §395.3(a)(3)(ii)). I picked one convention so every log reads the same way |
| Prior cycle hours | Treated as one lump that stays in the 8-day window | The input is a single number with no per-day breakdown. Treating it this way can overstate the cycle and can never understate it (§395.3(b)(2)) |
| Time zone | Every time on every sheet is in one home terminal zone, America/New_York by default | §395.8 requires the home terminal's time standard even when the route crosses zones. Start time and zone are under Advanced on the form |
| Start time | Now, rounded down to 15 minutes, unless you set one | Every boundary then falls on the log's 15-minute grid, so nothing needs rounding later |

## Hours-of-service rules

Each rule is a small class that reports how many more minutes of driving it allows. The engine drives for the smallest of those numbers, then inserts whatever rest the binding rule needs.

- 11-hour driving limit, §395.3(a)(3). At most 11 hours behind the wheel after 10 consecutive hours off.
- 14-hour window, §395.3(a)(2). No driving after the 14th hour since work began, and breaks don't pause the clock. It only stops driving, so on-duty work such as unloading at the dropoff can still finish after hour 14.
- 30-minute break, §395.3(a)(3)(ii). Required after 8 cumulative hours of driving. Any 30 consecutive minutes off the wheel count, so an hour-long pickup or a fuel stop clears it and the planner doesn't add a redundant break.
- 70 hours in 8 days, §395.3(b)(2). A rolling window over driving plus other on-duty time. At 70, driving stops.
- 34-hour restart, §395.3(c). Inserted when the cycle would block the trip, and it resets the cycle to zero.
- Record of duty status, §395.8. Date, miles, per-status totals that add up to 24, a city and state at every duty change, and the recap boxes.

Deliberately left out. Each exists as a named class that raises `NotImplementedError`:

- Adverse driving conditions, §395.1(b)(1). The assignment assumes none.
- Split sleeper berth, §395.1(g). The planner always takes a full 10-hour rest, so it never needs to pair shorter ones.
- Short-haul exception, §395.1(e). That's for drivers who return to their reporting location within 14 hours, which isn't this use case.
- 60 hours in 7 days, §395.3(b)(1). The assignment specifies 70/8. The sheet keeps the form's 60/7 recap column and marks it unused.

## Accepted simplifications

All of these are legal, and each errs on the conservative side.

- "Total mileage today" and "total miles driving today" always show the same number. The first is the truck's miles and the second the driver's, and they only differ with a co-driver or someone else driving the same truck. Every plan here is solo. Both come from route positions, so a trip's sheets add up to its route distance.
- A trip across a daylight-saving changeover is off by an hour, because every day is treated as 1,440 wall-clock minutes.
- When the cycle blocks the trip, the planner takes a full 34-hour restart. Waiting for the oldest day to roll off instead would mean simulating idle days, for very little gain.
- A 30-minute break can land shortly before a forced 10-hour rest, where it does little. Real paper logs look like this too.
- The rolling 8-day drop-off never fires on a generated trip. The engine plans right up to the limits, so the cycle hits 70 and takes a restart before eight days pass. The drop-off code is there and tested, for a driver who shows up with a partly used cycle.

## OpenRouteService quota

Routing and geocoding go through OpenRouteService's free tier. I measured its limits from the response headers on a free key, and they're far below the published figures: **200 directions, 100 geocode searches and roughly 100 reverse geocodes per day**. When a quota runs out, ORS returns HTTP 403 with `{"error": "Quota exceeded"}` and no rate-limit headers.

One long plan uses 3 searches, 1 route and about 11 reverse lookups (one for each inserted stop), so without a cache the key stops naming stops after about nine long trips. Naming is best effort. If a reverse lookup fails, the stop gets a road and the nearest town already resolved on that trip, like `"I 80 near Ottawa, IL"`, with the distance added when that town is more than 50 miles away. The plan itself still succeeds. **If you see a label like that, the quota ran out; the schedule is still correct.**

To stay inside the quota, geocode results are stored in Postgres (`GeocodeCache`), with an in-process cache in front. Stored answers never expire. Genuine no-matches are cached too, but quota errors and server errors aren't, since those are temporary. `python manage.py prewarm FROM PICKUP TO --cycle-hours 0,20,50` plans a route once for each cycle-hours value, fills the cache, and reports how many lookups hit the cache against how many called ORS. A warmed long plan makes exactly one ORS call, for the route. Rest and fuel stops land at the same miles whatever the start time, so they stay cached. The remark written at each midnight moves when the start time changes, though, so a plan at a new start time usually costs one or two extra reverse lookups.

The two demo presets on the form (Amarillo to Denver, and Los Angeles to Boston) are prewarmed, so they use almost no geocode quota. The short one plans in about a second and the long one in about seven, nearly all of which is the route call, which isn't cached. I left out address autocomplete on purpose: it would spend a geocode search on every keystroke, out of the same 100-a-day budget that planning needs.

## Implementation notes

- Reverse geocoding asks for `layers=address`. With admin-only layers, Pelias does a point-in-polygon lookup that silently ignores the search radius and returns the county whenever a stop is outside town limits. Nearby addresses carry the name of their town, and the radius (15 km, then 150 km) actually gets used.
- Routes avoid border crossings. The unconstrained truck route from Los Angeles to Boston goes through Ontario, and a Part 395 log shouldn't.
- An address ending in a state code has to resolve inside that state. Pelias almost never reports no match: "Atlantis, ZZ" comes back as Atlantis, FL with full confidence. Without this check, a typo would get routed to some other city with nothing flagged.
- ORS rejects routes longer than about 6,000 km. The API turns that into a 422 that says the trip is too long, so it doesn't read as "no route found".
- Reverse lookups use the route point at the nearest 5-mile mark. A town doesn't change within 5 miles, and sharing the point lets cached answers cover nearby stops. The stops themselves keep their exact miles.
- Saving a plan is best effort. If the database write fails, you still get the plan back, marked `stored: false`, and the share link is hidden.

## Architecture

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

The hours-of-service engine in `backend/trips/services/hos/` is pure: it works in integer minutes since trip start and imports no Django, no HTTP client and no `datetime`. Two tests parse the source to enforce the boundaries. One fails if anything in `hos/` imports Django, `requests` or `datetime`; the other fails if anything besides `http.py`, `geocode.py` and `routing.py` imports an HTTP client. Every limit is defined once, in `hos/constants.py`, and reaches the frontend through the API's `limits` object, so no regulatory number is hardcoded in TypeScript. The planner is the only module that deals with both geography and hours of service.

On the frontend, all the log-grid maths (minutes to x, status to y, the continuous duty line, the three tick heights, where remarks go) lives as pure functions in `frontend/src/lib/logGrid.ts`. `LogGrid.tsx` just places what it's given.

The full design record, with the API contract and the reasoning behind each decision, is in [docs/DESIGN.md](docs/DESIGN.md).

## Testing

278 backend tests (pytest) and 138 frontend tests (vitest), and both suites run offline. On the backend, ORS is faked at one seam, `services/http.py`, with canned payloads; the frontend mocks its API client. The worked example on page 18 of the FMCSA *Interstate Truck Driver's Guide to Hours of Service* (John Doe, Richmond VA to Newark NJ) is a test fixture, and it has to reproduce the guide's totals: 10 hours off duty, 1.75 sleeper berth, 7.75 driving and 4.5 on duty. Every sheet generated in any test is checked to cover exactly 24 hours.

## Local setup

You need Python 3.12 and Node 20.19 or later.

Backend, from `backend/`:

```bash
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # set ORS_API_KEY; the rest has working local defaults
python manage.py migrate
python manage.py runserver
```

With no `DATABASE_URL` set it uses SQLite, and `manage.py` defaults to the dev settings.

Frontend, from `frontend/`:

```bash
npm install
cp .env.example .env   # VITE_API_URL=http://localhost:8000
npm run dev
```

Tests:

```bash
cd backend && pytest
cd frontend && npm test && npm run typecheck
```

The two `.env.example` files list every environment variable. The backend reads `ORS_API_KEY`, `SECRET_KEY`, `DATABASE_URL`, `DJANGO_ENV`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` and `NUM_PROXIES`; the frontend reads `VITE_API_URL`.

## Deploying

- The backend deploys to Render from `render.yaml`: a free web service plus a free Postgres database. Free services can't run a pre-deploy command, so `migrate` and `createcachetable` run in the build command. Gunicorn runs two workers with a 60-second timeout.
- `NUM_PROXIES=3`. On Render, `X-Forwarded-For` arrives as client, then Cloudflare edge, then Render's internal proxy, so the throttle reads the third entry from the end. That's the real client IP, and a forged header can't change it. The number depends on the host, so if the hosting changes, check it again against the throttle's cache keys.
- `.github/workflows/keep-warm.yml` pings `/api/health/` every 5 minutes so the free instance never goes to sleep. It's every 5 rather than every 10 because GitHub's scheduler can run late and the instance sleeps at 15.
- The frontend deploys to Vercel with `frontend` as the root directory and `VITE_API_URL` pointing at the Render URL. `frontend/vercel.json` rewrites `/trip/*` to `index.html`; without it, every shared link would 404.
- The free Postgres database expires 30 days after it was created, around 17 October 2026, and is deleted 14 days after that. Stored trips, share links and the geocode cache go with it.
