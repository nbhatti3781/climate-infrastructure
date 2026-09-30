"""Resumable county-processing entry point.

The spatial source adapters will be added one hazard at a time after the
Howard County validation run. This file defines the checkpoint contract so a
national run can resume without repeating completed counties.
"""
from __future__ import annotations

import json
from pathlib import Path

from config import PROCESSED


def checkpoint_path(geoid: str) -> Path:
    return PROCESSED / "counties" / f"{geoid}.json"


def is_complete(geoid: str) -> bool:
    return checkpoint_path(geoid).exists()


def save_checkpoint(geoid: str, result: dict) -> None:
    path = checkpoint_path(geoid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    print("Pipeline scaffold ready. Next validation target: Howard County, MD (24027).")
