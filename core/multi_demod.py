from __future__ import annotations

"""
Lightweight multi-channel demodulation helpers.

We keep per-channel state (frequency, mode, squelch, audio buffer) and
demodulate multiple narrow channels out of a single wideband IQ stream.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
import numpy as np

from SDR.signal_processing import DemodulatorFactory, compute_power


@dataclass
class ChannelConfig:
    freq_hz: float
    mode: str = "FM"
    squelch_linear: float = 10 ** (-60.0 / 20.0)  # linear from dBFS
    enabled: bool = True
    name: str = ""


@dataclass
class ChannelState:
    config: ChannelConfig
    demod: Any
    audio_rms: float = 0.0
    last_audio: Optional[np.ndarray] = None
    last_power_db: float = -120.0


class MultiChannelDemod:
    """
    Manage multiple narrow-band demodulators on one wideband IQ stream.
    """

    def __init__(self, sample_rate: float, channel_added_cb: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.sample_rate = sample_rate
        self.channels: List[ChannelState] = []
        self.channel_added_cb = channel_added_cb

    def add_channel(self, cfg: ChannelConfig):
        state = ChannelState(
            config=cfg,
            demod=DemodulatorFactory.get(cfg.mode, audio_rate=16_000),
        )
        self.channels.append(state)
        if self.channel_added_cb:
            try:
                self.channel_added_cb({"freq": cfg.freq_hz, "mode": cfg.mode})
            except Exception:
                pass

    def remove_channel(self, freq_hz: float):
        self.channels = [c for c in self.channels if c.config.freq_hz != freq_hz]

    def set_channels(self, cfgs: List[ChannelConfig]):
        self.channels = []
        for cfg in cfgs:
            self.add_channel(cfg)

    def process(self, center_freq: float, samples: np.ndarray) -> List[Dict[str, Any]]:
        """Demod all enabled channels. Returns a list of audio/info dicts."""
        if samples.size == 0 or not self.channels:
            return []
        results = []
        t = np.arange(samples.size, dtype=np.float32) / self.sample_rate
        for ch in self.channels:
            if not ch.config.enabled:
                continue
            # Mix to baseband
            offset = ch.config.freq_hz - center_freq
            lo = np.exp(-1j * 2.0 * np.pi * offset * t)
            bb = samples * lo
            power_lin = compute_power(bb)
            power_db = 20 * np.log10(power_lin + 1e-6)
            ch.last_power_db = power_db
            if power_lin < ch.config.squelch_linear:
                ch.last_audio = None
                ch.audio_rms = 0.0
                continue
            audio = ch.demod.demod(bb, self.sample_rate)
            if audio.size > 0:
                ch.last_audio = audio
                ch.audio_rms = float(np.sqrt(np.mean(audio ** 2)))
                results.append(
                    {
                        "freq_hz": ch.config.freq_hz,
                        "mode": ch.config.mode,
                        "audio": audio,
                        "audio_rms": ch.audio_rms,
                        "power_db": power_db,
                    }
                )
        return results

