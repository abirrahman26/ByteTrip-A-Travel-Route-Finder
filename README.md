# ByteTrip: Travel Route Finder

ByteTrip is a small Flask portfolio prototype for comparing inter-district
routes in Bangladesh. Choose an origin and destination to see the cheapest,
shortest-distance, fastest, and fewest-leg options, including the individual
legs that make up each route.

## Important data note

The fares, distances, and travel times are placeholder values. They are not
live operator data, official schedules, or travel advice. The results only show
what the algorithms produce from the included CSV data.

The original `route_infos.csv` is kept as the raw source. Run
`clean_routes.py` to generate `route_infos_clean.csv`, which the app reads.
The cleaning rules normalize known district spelling variants, divide fares by
10 when the raw fare is at least 500 Tk, and resolve conflicting duplicate
undirected pairs by taking the maximum value independently for cost, distance,
and time. See [`data/README.md`](ByteTrip-Travel%20Route%20Finder/data/README.md)
for the full rules and data credit.

## Algorithms

**Dijkstra** finds a best route for one weighted measure at a time: fare,
distance, or travel time. A route that is best for one measure is not promised
to be best for the others.

**Breadth-first search (BFS)** finds the route with the fewest direct legs.
Its fare, distance, and time are then summed along that route, so those totals
are comparisons rather than weighted optima.

## Setup

From the project directory:

```powershell
cd "ByteTrip-Travel Route Finder"
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python clean_routes.py
python app.py
```

Open `http://127.0.0.1:5000` in a browser. Set `BYTETRIP_DEBUG=1` only when
debug output is needed; debug mode is off by default.

Run the tests with:

```powershell
python -m pytest -q
```

## What this fork changed

- Added deterministic raw-data cleaning and generated clean route data.
- Made data loading independent of the current working directory.
- Reworked route reconstruction and added focused algorithm and data tests.
- Added input validation, explicit unreachable-route handling, and correct
  fewest-leg terminology.
- Reworked the interface with accessible controls, route comparison tables,
  per-leg breakdowns, responsive styling, and a local data notice.

## Credit

The original project and raw source data come from Abir Rahman Sakin's
[ByteTrip-A-Travel-Route-Finder repository](https://github.com/abirrahman26/ByteTrip-A-Travel-Route-Finder).
This repository is a cleaned-up educational fork and remains a portfolio
prototype, not a production route service.