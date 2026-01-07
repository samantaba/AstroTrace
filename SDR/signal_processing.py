"""Signal processing utilities used by AstroTrace.

These DSP functions are intentionally lightweight but functional for the
prototype. They can be swapped with higher-quality DSP blocks later (e.g.,
dedicated demodulators with proper filtering, de-emphasis, and AGC).
"""

import numpy as np
from typing import Optional


def compute_power(samples: np.ndarray) -> float:
    """Compute RMS magnitude."""
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.abs(samples) ** 2)))


def _resample(audio: np.ndarray, src_rate: float, target_rate: float) -> np.ndarray:
    if src_rate == target_rate or audio.size == 0:
        return audio.astype(np.float32)
    ratio = target_rate / float(src_rate)
    new_length = int(np.ceil(audio.size * ratio))
    return np.interp(
        np.linspace(0, audio.size, new_length, endpoint=False),
        np.arange(audio.size),
        audio,
    ).astype(np.float32)


def _single_pole_iir(signal: np.ndarray, alpha: float) -> np.ndarray:
    if signal.size == 0:
        return signal
    out = np.empty_like(signal, dtype=np.float32)
    acc = 0.0
    for i, s in enumerate(signal):
        acc = alpha * acc + (1 - alpha) * s
        out[i] = acc
    return out


def _deemphasis(audio: np.ndarray, sample_rate: float, tau: float = 75e-6) -> np.ndarray:
    # Simple RC de-emphasis for FM broadcast
    if audio.size == 0:
        return audio
    dt = 1.0 / sample_rate
    alpha = np.exp(-dt / tau)
    return _single_pole_iir(audio, alpha)


def _simple_agc(audio: np.ndarray, target_rms: float = 0.1, eps: float = 1e-6) -> np.ndarray:
    if audio.size == 0:
        return audio
    rms = np.sqrt(np.mean(audio**2)) + eps
    return (audio * (target_rms / rms)).astype(np.float32)


class BaseDemodulator:
    def __init__(self, audio_rate: float = 16_000):
        self.audio_rate = audio_rate

    def demod(self, samples: np.ndarray, sample_rate: float) -> np.ndarray:
        raise NotImplementedError


class FMDemodulator(BaseDemodulator):
    def demod(self, samples: np.ndarray, sample_rate: float) -> np.ndarray:
        if samples.size == 0:
            return np.array([], dtype=np.float32)
        phase = np.unwrap(np.angle(samples))
        inst_freq = np.diff(phase) * sample_rate / (2 * np.pi)
        inst_freq = inst_freq - np.mean(inst_freq)
        deemph = _deemphasis(inst_freq, sample_rate)
        audio = _resample(deemph, sample_rate, self.audio_rate)
        return _simple_agc(audio)


class AMDemodulator(BaseDemodulator):
    def demod(self, samples: np.ndarray, sample_rate: float) -> np.ndarray:
        if samples.size == 0:
            return np.array([], dtype=np.float32)
        envelope = np.abs(samples)
        audio = envelope - np.mean(envelope)
        audio = _resample(audio, sample_rate, self.audio_rate)
        return _simple_agc(audio)


class PassthroughDemodulator(BaseDemodulator):
    def demod(self, samples: np.ndarray, sample_rate: float) -> np.ndarray:
        return _resample(np.real(samples), sample_rate, self.audio_rate)


class DemodulatorFactory:
    @staticmethod
    def get(mode: str, audio_rate: float = 16_000) -> BaseDemodulator:
        mode = (mode or "FM").upper()
        if mode == "FM":
            return FMDemodulator(audio_rate)
        if mode == "AM":
            return AMDemodulator(audio_rate)
        return PassthroughDemodulator(audio_rate)


def demodulate(samples: np.ndarray, mode: str, sample_rate: float, audio_rate: Optional[float] = 16_000) -> np.ndarray:
    """Compatibility function: delegate to the appropriate demodulator."""
    demod = DemodulatorFactory.get(mode, audio_rate=audio_rate or sample_rate)
    return demod.demod(samples, sample_rate)
