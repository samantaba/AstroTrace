"""Event bundle writer: packages logs, IQ, and SigMF metadata."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

import numpy as np

from . import sigmf


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_event_bundle(
    event: Dict[str, Any],
    iq: Optional[np.ndarray],
    sample_rate: float,
    center_freq: float,
    mode: str,
    bundle_root: str | Path = "runs",
    save_sigmf: bool = True,
) -> Path:
    """Create a self-contained bundle for an event.

    Contents:
      - event.json (metadata from EventLogger)
      - manifest.json (paths + hashes)
      - SigMF data/meta if IQ provided
    """
    ts = event.get("time") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    freq_mhz = center_freq / 1e6
    bundle_name = f"{ts.replace(':','').replace(' ','_')}_{freq_mhz:.3f}MHz"
    bundle_dir = Path(bundle_root) / bundle_name
    bundle_dir.mkdir(parents=True, exist_ok=True)

    event_path = bundle_dir / "event.json"
    with event_path.open("w", encoding="utf-8") as f:
        json.dump(event, f, indent=2)

    manifest = {
        "event": {"path": str(event_path), "sha256": _sha256_file(event_path)},
        "meta": {
            "sample_rate_hz": sample_rate,
            "center_freq_hz": center_freq,
            "mode": mode,
        },
        "artifacts": [],
    }

    if save_sigmf and iq is not None and iq.size > 0:
        sig_paths = sigmf.write_sigmf(
            iq=iq,
            sample_rate=sample_rate,
            center_freq=center_freq,
            base_path=bundle_dir / "capture",
            extra={"core:mode": mode},
        )
        manifest["artifacts"].append(sig_paths["sigmf_data"])
        manifest["artifacts"].append(sig_paths["sigmf_meta"])

    manifest_path = bundle_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return bundle_dir

