# Route data

`route_infos.csv` is the raw source file retained from the upstream fork by
[Abir Rahman Sakin](https://github.com/abirrahman26/ByteTrip-A-Travel-Route-Finder).
The values are placeholder data for this portfolio prototype, not live fares,
distances, or travel times.

Run `python clean_routes.py` after changing the raw file. The cleaner applies
these deterministic rules:

- normalize the known district spelling variants;
- divide a fare by 10 when its raw value is at least 500 Tk;
- collapse reverse and duplicate undirected pairs by taking the maximum value
  independently for cost, distance, and time;
- reject missing values, self-loops, negative numbers, and non-integer numeric
  fields.

The generated `route_infos_clean.csv` is the file consumed by the Flask app.
Any remaining fare above 500 Tk is printed for manual review and is not changed
by the cleaner.