"""Crash-source adapters.

Register a new jurisdiction by writing a CrashAdapter subclass and adding it to
ADAPTERS below. Everything downstream of ingestion is source-agnostic once the
adapter returns the canonical frame defined in `base.py`.

    from src.ingest.adapters import get_adapter

    src = get_adapter("fars").load(Path("data/raw/fars"), place="SAN DIEGO")
    if not src.supports_ksi:
        print(f"label is {src.label_name()}, not KSI")
"""
from __future__ import annotations

from src.ingest.adapters.base import (
    KSI_SEVERITIES,
    OPTIONAL_ATTRS,
    OPTIONAL_FLAGS,
    REQUIRED_COLUMNS,
    SEVERITY_SCHEME_FATAL_ONLY,
    SEVERITY_SCHEME_KSI,
    CrashAdapter,
    CrashSource,
)
from src.ingest.adapters.fars import FarsAdapter
from src.ingest.adapters.switrs import SwitrsAdapter

ADAPTERS: dict[str, type[CrashAdapter]] = {
    FarsAdapter.name: FarsAdapter,
    SwitrsAdapter.name: SwitrsAdapter,
}


def get_adapter(name: str) -> CrashAdapter:
    try:
        return ADAPTERS[name.lower()]()
    except KeyError:
        raise KeyError(
            f"No adapter named {name!r}. Available: {sorted(ADAPTERS)}. "
            "Add one in src/ingest/adapters/ and register it in ADAPTERS."
        ) from None


__all__ = [
    "ADAPTERS", "get_adapter",
    "CrashAdapter", "CrashSource",
    "FarsAdapter", "SwitrsAdapter",
    "REQUIRED_COLUMNS", "OPTIONAL_FLAGS", "OPTIONAL_ATTRS",
    "KSI_SEVERITIES", "SEVERITY_SCHEME_KSI", "SEVERITY_SCHEME_FATAL_ONLY",
]
