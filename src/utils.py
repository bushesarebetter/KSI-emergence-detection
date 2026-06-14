"""Shared utilities: config loading, paths, constants."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    if path is None:
        path = ROOT / "configs" / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def project_root() -> Path:
    return ROOT


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(directory: Path, entries: list[dict]) -> None:
    """Write a manifest.json into directory."""
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"files": entries}
    with open(directory / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)


def buffer_feet(cfg: dict) -> float:
    """Convert buffer_m to US survey feet (EPSG:2230 linear unit)."""
    # 1 US survey foot = 1200/3937 metres exactly
    m_per_us_ft = 1200.0 / 3937.0
    return cfg["geometry"]["buffer_m"] / m_per_us_ft


def intersection_id(x_2230: float, y_2230: float, decimals: int = 1) -> str:
    """Stable hex hash of rounded EPSG:2230 coordinates."""
    key = f"{round(x_2230, decimals)},{round(y_2230, decimals)}"
    return hashlib.md5(key.encode()).hexdigest()
