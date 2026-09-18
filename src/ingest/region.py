"""Region definitions — the other half of making this pipeline portable.

`configs/config.yaml` hardcodes `EPSG:2230` (NAD83 / California State Plane Zone VI)
as the analysis CRS. That is correct for San Diego and wrong everywhere else:
project Chicago into Zone VI and distances are off by kilometres, which silently
destroys a 76.2 m intersection buffer.

A region carries the three things that vary by place:
  - which crash source and which slice of it
  - a projected CRS whose units are metres and whose distortion is small locally
  - the OSM place query used to build the road network

Choosing the CRS
----------------
`utm_epsg_for()` derives the UTM zone from longitude. UTM is defined worldwide,
its units are metres, and within a zone the scale error is under ~1 part in 1000 --
about 8 cm over 76.2 m, far below crash geocoding precision. That makes it a safe
default for any city on Earth without a lookup table of national grids.

San Diego deliberately keeps EPSG:2230 rather than its UTM zone, so every existing
result stays byte-for-byte reproducible.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

REGIONS_DIR = Path(__file__).resolve().parents[2] / "configs" / "regions"


def utm_epsg_for(lon: float, lat: float) -> str:
    """EPSG code for the WGS84 UTM zone containing this point.

    326xx is northern hemisphere, 327xx southern. Valid for |lat| < 84; polar
    regions need UPS instead, which no city in this dataset requires.
    """
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise ValueError(f"lon/lat out of range: {lon}, {lat}")
    zone = int((lon + 180) // 6) + 1
    return f"EPSG:{(326 if lat >= 0 else 327)}{zone:02d}"


@dataclass(frozen=True)
class Region:
    """One city/area to build a model for."""

    name: str                       # slug, used in paths
    display_name: str
    adapter: str                    # key into src.ingest.adapters.ADAPTERS
    osm_place: str                  # OSMnx geocodable place, e.g. "San Diego, California, USA"
    center: tuple[float, float]     # (lon, lat), used to derive the CRS
    crs_analysis: str | None = None  # explicit override; otherwise UTM from center
    source_filters: dict = field(default_factory=dict)  # kwargs passed to adapter.load()
    notes: str = ""

    @property
    def crs(self) -> str:
        return self.crs_analysis or utm_epsg_for(*self.center)

    @classmethod
    def load(cls, name: str) -> "Region":
        path = REGIONS_DIR / f"{name}.yaml"
        if not path.exists():
            available = sorted(p.stem for p in REGIONS_DIR.glob("*.yaml") if p.stem != "_template")
            raise FileNotFoundError(
                f"No region config at {path}. Available: {available}\n"
                f"Copy {REGIONS_DIR / '_template.yaml'} to add one."
            )
        raw = yaml.safe_load(path.read_text())
        raw["center"] = tuple(raw["center"])
        return cls(**raw)

    @classmethod
    def available(cls) -> list[str]:
        return sorted(p.stem for p in REGIONS_DIR.glob("*.yaml") if not p.stem.startswith("_"))
