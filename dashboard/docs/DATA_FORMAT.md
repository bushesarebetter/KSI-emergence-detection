# Data Format Reference

The dashboard reads two static files from `dashboard/public/data/`.

---

## intersections.geojson

A GeoJSON FeatureCollection. Each feature represents one ranked intersection.

### Minimal valid example

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-117.1611, 32.7157]
      },
      "properties": {
        "rank": 1,
        "intersection_name": "Market St & Harbor Dr",
        "council_district": 3,
        "percentile": 99.8,
        "is_known_emergent": true,
        "is_crash_active": true,
        "crashes_training": 18,
        "crash_history": [
          { "year": 2013, "ksi": 0, "injury": 1, "pdo": 2 },
          { "year": 2014, "ksi": 0, "injury": 0, "pdo": 1 }
        ],
        "shap_features": [
          {
            "feature_name": "years_since_last_crash",
            "display_label": "0.4 years since last crash",
            "shap_value": 0.412,
            "raw_value": 0.4
          }
        ]
      }
    }
  ]
}
```

### Field descriptions

| Field | Type | Description |
|---|---|---|
| `geometry.coordinates` | `[lon, lat]` | WGS-84 longitude then latitude |
| `rank` | integer | Model rank, 1 = highest risk |
| `intersection_name` | string | Human-readable name, e.g. "A & B" |
| `council_district` | integer | San Diego council district, 1–9 |
| `percentile` | float | Score percentile in the full candidate pool (0–100) |
| `is_known_emergent` | boolean | True if the site had a KSI crash in the holdout window |
| `is_crash_active` | boolean | True if the site had any crash in the training window |
| `crashes_training` | integer | Total crash count in the training window |
| `crash_history` | array | One object per year; must cover consecutive years |
| `crash_history[].year` | integer | Calendar year |
| `crash_history[].ksi` | integer | Killed or seriously injured crash count |
| `crash_history[].injury` | integer | Injury (non-KSI) crash count |
| `crash_history[].pdo` | integer | Property-damage-only crash count |
| `shap_features` | array | SHAP feature importances; **must be sorted descending by shap_value** |
| `shap_features[].feature_name` | string | Internal feature identifier |
| `shap_features[].display_label` | string | Human-readable label shown in the chart |
| `shap_features[].shap_value` | float | SHAP value (non-negative) |
| `shap_features[].raw_value` | float or integer | Raw feature value |

---

## districts.json

A JSON array with one object per council district.

### Minimal valid example

```json
[
  {
    "district": 1,
    "top_50_count": 4,
    "top_100_count": 9,
    "top_200_count": 21,
    "top_500_count": 55
  }
]
```

### Field descriptions

| Field | Type | Description |
|---|---|---|
| `district` | integer | Council district number, 1–9 |
| `top_50_count` | integer | Number of top-50 intersections in this district |
| `top_100_count` | integer | Number of top-100 intersections in this district |
| `top_200_count` | integer | Number of top-200 intersections in this district |
| `top_500_count` | integer | Number of top-500 intersections in this district |

---

## Notes

- `crash_history` must cover **consecutive years** with no gaps. The chart renders years in order.
- `shap_features` must be **sorted descending by `shap_value`**. The panel renders them in the order provided.
- `coordinates` follow GeoJSON convention: `[longitude, latitude]`, not `[latitude, longitude]`.
