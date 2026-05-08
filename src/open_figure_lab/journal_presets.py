"""Built-in journal presets for figure validation and rendering defaults."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


PRESETS: dict[str, dict[str, Any]] = {
    "nature": {
        "name": "Nature",
        "figure_width_mm": {
            "single_column": 89,
            "double_column": 183,
        },
        "font": {
            "family": "Arial",
            "min_size_pt": 5,
            "normal_size_pt": 6.5,
            "max_size_pt": 7,
        },
        "export": {
            "vector": ["pdf", "svg", "eps"],
            "raster": ["png", "tiff"],
            "default_dpi": 600,
        },
        "line_width_pt": {
            "axis": 0.5,
            "data": 0.7,
            "border": 0.5,
        },
        "matplotlib": {
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        },
    },
    "nature_comm": {
        "name": "Nature Communications",
        "figure_width_mm": {
            "single_column": 89,
            "double_column": 183,
        },
        "font": {
            "family": "Arial",
            "min_size_pt": 5,
            "normal_size_pt": 6.5,
            "max_size_pt": 7,
        },
        "export": {
            "vector": ["pdf", "svg", "eps"],
            "raster": ["png", "tiff"],
            "default_dpi": 600,
        },
        "line_width_pt": {
            "axis": 0.5,
            "data": 0.7,
            "border": 0.5,
        },
        "matplotlib": {
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        },
    },
}


def list_presets() -> list[str]:
    """Return stable preset identifiers."""

    return sorted(PRESETS)


def get_preset(name: str) -> dict[str, Any]:
    """Return a defensive copy of a preset."""

    try:
        return deepcopy(PRESETS[name])
    except KeyError as exc:
        available = ", ".join(list_presets())
        raise ValueError(f"Unknown journal preset '{name}'. Available: {available}") from exc

