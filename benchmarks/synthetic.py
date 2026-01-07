"""Synthetic IQ generator and benchmark harness."""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Callable, Dict, Any


@dataclass
class SynthSignal:
    name: str
    generator: Callable[[int, float], np.ndarray]


def _tone(num_samples: int, sample_rate: float, freq_hz: float = 1_000.0) -> np.ndarray:
    t = np.arange(num_samples) / sample_rate
    return np.exp(1j * 2 * np.pi * freq_hz * t).astype(np.complex64)


def _fm_voice_like(num_samples: int, sample_rate: float, deviation: float = 5_000.0, tone: float = 440.0) -> np.ndarray:
    t = np.arange(num_samples) / sample_rate
    phase = 2 * np.pi * deviation * np.sin(2 * np.pi * tone * t) / sample_rate
    carrier = np.exp(1j * np.cumsum(phase))
    return carrier.astype(np.complex64)


def _noise(num_samples: int, snr_db: float = -5.0) -> np.ndarray:
    noise = (np.random.randn(num_samples) + 1j * np.random.randn(num_samples)).astype(np.complex64)
    if snr_db is None:
        return noise
    tone = _tone(num_samples, 1.0, 0.0)  # dummy tone power 1
    noise_power = np.mean(np.abs(noise) ** 2)
    tone_power = np.mean(np.abs(tone) ** 2)
    scale = np.sqrt(tone_power / noise_power * 10 ** (-snr_db / 10))
    return noise * scale


def generate_case(kind: str, num_samples: int = 8192, sample_rate: float = 250_000.0) -> Dict[str, Any]:
    """Return synthetic IQ and label for quick tests."""
    generators = {
        "tone": lambda: _tone(num_samples, sample_rate, freq_hz=5_000.0),
        "fm": lambda: _fm_voice_like(num_samples, sample_rate, deviation=7_000.0, tone=440.0),
        "noise": lambda: _noise(num_samples, snr_db=-3.0),
    }
    if kind not in generators:
        raise ValueError(f"Unknown synthetic kind: {kind}")
    iq = generators[kind]()
    return {
        "iq": iq,
        "label": kind,
        "sample_rate": sample_rate,
    }

