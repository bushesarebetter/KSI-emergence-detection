# Adding a city

The pipeline is adapter-based and the dashboard reads one configuration object, so a new
city is data plus configuration, not new code. This is the checklist, in the order it has
worked for San Diego.

## 1. Crash records

Any source that yields one row per crash with a date, coordinates and a severity the
`src/ingest/adapters` canonical schema can carry (`ksi` or `fatal_only`). In California
that is SWITRS via TIMS for every city. Elsewhere, the city's own open crash data, or FARS
for a fatal-only version. Write an adapter if the source is new; add a region file under
`configs/regions/` with the city boundary, the projected CRS and the windows.

## 2. The city's own review rule

Find the threshold the city already uses to review an intersection (San Diego: five injury
crashes in a year) and how many corners that produces a year. It sets the candidate
universe in the pipeline (D18) and the "distance to the City's review" the site shows.

## 3. Political geography

A GeoJSON of council districts (or wards) and the public contact page for each office. The
site links residents to them.

## 4. Run the pipeline and export

`scripts/build_export_panel_verified.py` writes `intersections.geojson`, `districts.json`
and `meta.json` into `dashboard/public/data/`.

## 5. Join the local context (after every export)

```bash
python scripts/join_traffic_counts.py        # daily traffic counts, if the city publishes them
python scripts/join_recent_collisions.py     # police reports since the model's cutoff, if published
python scripts/fetch_intersection_control.py # signals or stop signs, from OpenStreetMap
python scripts/fetch_school_proximity.py     # schools within 300 m, from OpenStreetMap
python scripts/refine_intersection_names.py  # cross-street names, from OpenStreetMap
```

Each of the first two needs a small adapter for the city's file layout; the three
OpenStreetMap scripts work anywhere. All are optional: the interface omits a line when its
file is absent.

## 6. The dashboard configuration

Edit `dashboard/src/city.js`: names, map centre and bounds, the review rule, districts and
council URLs, attributions, authors. Update `public/sitemap.xml`, `robots.txt` and the
Open Graph tags in `index.html` for the new domain. Set the Google Maps key and, for the
route check, the Geocoding and Directions APIs.

## 7. What still names San Diego

The countermeasure costs are national figures. The funding sources on `/funding` are
California's (HSIP via Caltrans, ATP, Safe Routes to School); another state swaps that
list. The About page's methodology text describes this model and names the City's own
traffic-count and police-report files; keep the model text if the pipeline is the same and
rewrite the two data-source sentences for the new city's files.

## 8. Before launch

Run the node checks used during development (advice, chips and countermeasures over every
exported site; see `docs/DECISIONS.md` D24) and the browser pass in `docs/HOSTING_RENDER.md`.
Then read the terms on the privacy page once more with the new city's name in them.
