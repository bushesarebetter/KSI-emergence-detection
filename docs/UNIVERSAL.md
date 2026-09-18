# Going universal: porting the model beyond San Diego

Status: **crash-source layer built and audited on real data. Downstream stages not
yet ported.**

The headline finding is that universality and accuracy are not in tension here —
they are the same problem. The project's binding constraint has always been 21
positive examples. FARS supplies **70,900 intersection-related fatal crashes on
surface streets across 2016–2023**, in 288 cities with enough volume to model. The
reason to go multi-city is not distribution; it is that the sample-size ceiling
capping every result in this repo disappears.

---

## The two-tier label problem

There is no national US database of serious-injury crashes. NHTSA states that
serious-injury data is maintained by individual states with widely varying
quality; the national non-fatal product (CRSS) is a *sample* producing national
estimates, which cannot rank individual intersections.

So there are exactly two tiers, and the architecture keeps them apart:

| | Source | Coverage | Label | Positives |
|---|---|---|---|---|
| **Universal spine** | [FARS](https://www.nhtsa.gov/crash-data-systems/fatality-analysis-reporting-system) | All 50 states + DC + PR | **Fatal only** | 70,900 (2016–2023) |
| **KSI where available** | SWITRS, state DOTs | Per-jurisdiction | Killed **or** seriously injured | 21 (San Diego verified run) |

`CrashSource.supports_ksi` is the guard. A `fatal_only` source reports
`label_name() == "fatal"`, and **a model trained on it predicts fatal crashes, not
KSI.** Mixing the two definitions in one results table is the single worst failure
mode available here — the numbers would look like the San Diego results while
meaning something different. `tests/test_adapters.py` pins this.

---

## FARS audit — the check that gated the plan

Run: `python scripts/audit_crash_source.py --adapter fars --intersection-only`

**Verdict: USABLE.**

| Check | Result | Why it matters |
|---|---|---|
| Coordinate coverage | **100.00%** | SWITRS's obvious geocode field is only ~44% populated |
| ≥4 decimal places | **99.56%** | 3 decimals ≈ 111 m, coarser than the 76.2 m buffer |
| Duplicate coordinates | **0.67%** (max 5 at one point) | The real risk — centroid snapping would destroy intersection assignment |
| Cities ≥25 crashes | **288** of 7,350 | Below ~25, nothing is measurable |

That third row was the one I was worried about, since this project has already
been burned by crash geocoding once. FARS is materially cleaner than SWITRS on
every axis.

**Volume, top cities (intersection-related, surface streets, 2016–2023):**

| City | Crashes | | City | Crashes |
|---|---:|---|---|---:|
| Los Angeles, CA | 912 | | Detroit, MI | 383 |
| Phoenix, AZ | 699 | | Tucson, AZ | 358 |
| Houston, TX | 528 | | Jacksonville, FL | 338 |
| Chicago, IL | 495 | | Albuquerque, NM | 333 |
| Philadelphia, PA | 394 | | **San Diego, CA** | **152** |

San Diego's 152 fatal-crash records against the verified run's 21 KSI positives is
the comparison worth sitting with.

---

## What ports, and what doesn't

| Stage | Portable | Notes |
|---|---|---|
| Crash ingestion | ✅ **done** | `src/ingest/adapters/` — canonical schema + FARS + SWITRS |
| Projection / CRS | ✅ **done** | `src/ingest/region.py` derives the UTM zone from longitude |
| Road network | ✅ Global | OSMnx geocodes any place on Earth |
| Node spine, buffering, panel | ✅ Global | Pure geometry, no source coupling |
| 13 of 20 crash features | ✅ Global | Need only date + severity + coordinates |
| 7 of 20 crash features | ⚠️ Partial | See below |
| Terrain (`dem_loader.py`) | 🇺🇸 US only | USGS 3DEP; needs SRTM/Copernicus elsewhere |
| Transit (`gtfs_loader.py`) | ✅ Global | GTFS is a worldwide standard |
| Council-district rollups | ❌ SD-specific | Dashboard-only; needs a per-region boundary file |

### The 7 source-coupled features

| Feature | SWITRS | FARS | Status |
|---|---|---|---|
| `ped_crashes_72mo` | `PEDESTRIAN_ACCIDENT` | `PBTYPE` / `PEDS` | ✅ both |
| `bike_crashes_72mo` | `BICYCLE_ACCIDENT` | `PBTYPE` | ✅ both |
| `broadside_72mo` | `TYPE_OF_COLLISION` | `MAN_COLL` ("Angle") | ✅ both |
| `night_72mo` | `LIGHTING` | `LGT_COND` | ✅ both |
| `dui_72mo` | `ALCOHOL_INVOLVED` | needs `person`/`drugs` tables | ⚠️ NA in FARS |
| `left_turn_72mo` | `Parties.MOVE_PRE_ACC` | needs `vehicle` table | ⚠️ NA in FARS |
| `ped_row_violation_72mo` | `PCF_VIOL_CATEGORY` | no direct equivalent | ❌ NA in FARS |

The three unavailable ones are reported as `NA`, never `False` — a fabricated
`False` would make the feature builder count "unknown" as "did not happen" and
bias every one of those features toward zero. Two of the three are recoverable by
joining FARS's `vehicle.csv` and `person.csv`; that work is not done.

**FARS also adds something SWITRS lacks:** `RELJCT2` marks whether a crash was at
or related to an intersection, which is a direct check on the geometric buffer
attribution this project currently relies on entirely.

---

## Adding a city

```bash
# 1. Get the data (public, no account — unlike TIMS)
mkdir -p data/raw/fars && cd data/raw/fars
for y in 2016 2017 2018 2019 2020 2021 2022 2023; do
  curl -sLO "https://static.nhtsa.gov/nhtsa/downloads/FARS/${y}/National/FARS${y}NationalCSV.zip"
done

# 2. Define the region
cp configs/regions/_template.yaml configs/regions/austin.yaml
$EDITOR configs/regions/austin.yaml     # set osm_place, center [lon, lat], filters

# 3. Audit before trusting it
python scripts/audit_crash_source.py --region austin
```

The region's analysis CRS is derived from its `center` longitude via UTM, so no
projection lookup is needed. San Diego pins `EPSG:2230` explicitly to keep every
published result byte-for-byte reproducible.

---

## Honest limits

- **Not yet ported:** everything downstream of ingestion still reads SWITRS
  column names directly. `build_panel.py`, `build_crash_emergence.py`, and the
  model scripts need to consume the canonical frame before a second city can
  actually be trained.
- **FARS coordinate *accuracy* is unmeasured.** Precision and snapping were
  audited; whether a point sits within 76.2 m of the true location was not. That
  needs ground-truthing against a city with an independent crash dataset.
- **Fatal-only changes what "emergence" means.** Fatal crashes are rarer than KSI,
  so per-intersection counts are thinner even though the national corpus is vastly
  larger. The gain comes from pooling cities, not from any single city.
- **San Diego still cannot be reproduced locally.** SWITRS requires a manual TIMS
  account and download; I cannot do that step for you. `configs/regions/san_diego_fars.yaml`
  exists as a calibration region so you can measure what is lost between the two
  label definitions on the same city.

## Next

1. Port `build_panel.py` and `build_crash_emergence.py` to the canonical frame.
   This is the remaining blocker on training any second city.
2. Recover `is_dui` and `is_left_turn` from FARS `person.csv` / `vehicle.csv`.
3. Build a multi-city panel and run `scripts/improvement_bakeoff.py` on it — the
   first evaluation in this project's history that is not sample-size limited.
