"""Minimal SigMF import utilities for AstroTrace."""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np


def read_sigmf(base_path: str | Path) -> tuple[np.ndarray, dict]:
    """Read SigMF data/meta given base path (without extension or with .sigmf-meta)."""
    base = Path(base_path)
    if base.suffix == ".sigmf-meta":
        base = base.with_suffix("")
    data_path = base.with_suffix(".sigmf-data")
    meta_path = base.with_suffix(".sigmf-meta")

    if not data_path.exists() or not meta_path.exists():
        raise FileNotFoundError("SigMF data/meta not found")

    with meta_path.open("r", encoding="utf-8") as f:
        meta = json.load(f)
    raw = np.fromfile(data_path, dtype=np.complex64)
    return raw, meta

