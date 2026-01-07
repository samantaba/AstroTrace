"""Minimal SigMF export utilities for AstroTrace."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import numpy as np


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_sigmf(iq: np.ndarray, sample_rate: float, center_freq: float, base_path: Path, extra: dict | None = None) -> dict:
    """Write IQ data and SigMF metadata sidecar.

    Args:
        iq: complex64 IQ samples.
        sample_rate: sample rate in Hz.
        center_freq: center frequency in Hz.
        base_path: base path without extension (e.g., /runs/case1/recording).
        extra: optional extra metadata to include under global namespace.

    Returns:
        A dict with paths and hashes for manifest inclusion.
    """
    base_path.parent.mkdir(parents=True, exist_ok=True)
    data_path = base_path.with_suffix(".sigmf-data")
    meta_path = base_path.with_suffix(".sigmf-meta")

    # Ensure correct dtype
    iq = np.asarray(iq, dtype=np.complex64)
    iq.tofile(data_path)

    now = datetime.now(timezone.utc).isoformat()
    meta = {
        "global": {
            "version": "0.0.1",
            "core:datatype": "cf32_le",
            "core:sample_rate": sample_rate,
            "core:frequency": center_freq,
            "core:description": "AstroTrace event capture",
            "core:author": "AstroTrace",
            "core:datetime": now,
        },
        "captures": [
            {
                "core:sample_start": 0,
                "core:frequency": center_freq,
                "core:datetime": now,
            }
        ],
        "annotations": [],
    }
    if extra:
        meta["global"].update(extra)

    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return {
        "sigmf_data": {"path": str(data_path), "sha256": _sha256_file(data_path)},
        "sigmf_meta": {"path": str(meta_path), "sha256": _sha256_file(meta_path)},
    }

