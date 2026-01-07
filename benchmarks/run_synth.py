"""Headless synthetic benchmark runner for AstroTrace."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from benchmarks.synthetic import generate_case
from SDR.signal_processing import compute_power, demodulate
from core.logger import EventLogger
from core import bundles


def run_once(kind: str, threshold: float, bundle_root: str) -> bool:
    case = generate_case(kind)
    iq = case["iq"]
    sample_rate = case["sample_rate"]
    center_freq = 100e6

    power = compute_power(iq)
    if power < threshold:
        print(f"[{kind}] below threshold: {power:.4f}")
        return False

    audio = demodulate(iq, mode="FM", sample_rate=sample_rate, audio_rate=16_000)
    logger = EventLogger()
    event = logger.log_event(center_freq, f"synthetic:{kind}")
    bundles.write_event_bundle(
        event=event,
        iq=iq,
        sample_rate=sample_rate,
        center_freq=center_freq,
        mode="FM",
        bundle_root=bundle_root,
        save_sigmf=True,
    )
    logger.close()
    print(f"[{kind}] logged and bundled. power={power:.4f}, audio_len={len(audio)}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Run synthetic IQ benchmarks.")
    parser.add_argument("--bundle-root", default="runs_synth", help="Where to place bundles.")
    parser.add_argument("--threshold", type=float, default=0.05, help="Power threshold for detection.")
    parser.add_argument("--kinds", nargs="+", default=["tone", "fm", "noise"], help="Synthetic kinds to run.")
    args = parser.parse_args()

    Path(args.bundle_root).mkdir(parents=True, exist_ok=True)
    results = []
    for kind in args.kinds:
        results.append(run_once(kind, args.threshold, args.bundle_root))
    ok = all(results)
    print("All synthetic cases passed." if ok else "Some synthetic cases fell below threshold.")


if __name__ == "__main__":
    main()

