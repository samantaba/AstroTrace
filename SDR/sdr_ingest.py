from __future__ import annotations

import numpy as np
from abc import ABC, abstractmethod

try:
    from rtlsdr import RtlSdr
    _rtl_import_error = None
except Exception as e:
    RtlSdr = None
    _rtl_import_error = e
try:
    import SoapySDR
    from SoapySDR import SOAPY_SDR_RX, SOAPY_SDR_CS16
    _soapy_import_error = None
except Exception as e:
    SoapySDR = None
    _soapy_import_error = e


class BaseSDRSource(ABC):
    """Common interface for SDR sources."""

    def __init__(self, sample_rate: float, center_freq: float, gain: float | None):
        self.sample_rate = sample_rate
        self.center_freq = center_freq
        self.gain = gain

    @abstractmethod
    def read_samples(self, num_samples: int) -> np.ndarray:
        ...

    @abstractmethod
    def tune(self, freq_hz: float) -> None:
        ...

    @abstractmethod
    def close(self) -> None:
        ...

    @abstractmethod
    def get_info(self) -> dict:
        """Return a user-friendly description of the source (for UI status)."""
        ...


class RTLSDRSource(BaseSDRSource):
    def __init__(self, sample_rate: float, center_freq: float, gain: float | None):
        if RtlSdr is None:
            detail = f"{_rtl_import_error}" if _rtl_import_error else "unknown import error"
            raise RuntimeError(
                "RTL-SDR backend unavailable. "
                f"Python module 'rtlsdr' failed to import ({detail}). "
                "Install 'pyrtlsdr' and ensure the system 'librtlsdr' is installed "
                "(macOS: `brew install rtl-sdr`)."
            )
        super().__init__(sample_rate, center_freq, gain)
        try:
            self.device = RtlSdr()
        except Exception as e:
            raise RuntimeError(
                "RTL-SDR init failed. "
                f"{e} "
                "If this is a missing library/driver issue, install 'librtlsdr' "
                "(macOS: `brew install rtl-sdr`)."
            ) from e
        self.device.sample_rate = sample_rate
        self.device.center_freq = center_freq
        self.device.gain = "auto" if gain is None else gain

    def read_samples(self, num_samples: int) -> np.ndarray:
        samples = self.device.read_samples(num_samples)
        return np.array(samples, dtype=np.complex64)

    def tune(self, freq_hz: float) -> None:
        self.center_freq = freq_hz
        self.device.center_freq = freq_hz

    def close(self) -> None:
        self.device.close()

    def get_info(self) -> dict:
        info = {
            "name": "RTL-SDR",
            "sample_rate": self.sample_rate,
            "center_freq": self.center_freq,
            "gain": self.gain,
        }
        try:
            info["manufacturer"] = getattr(self.device, "manufacturer", None)
            info["product"] = getattr(self.device, "product", None)
            info["serial"] = getattr(self.device, "serial", None)
        except Exception:
            pass
        return info


class SoapySDRSource(BaseSDRSource):
    def __init__(self, sample_rate: float, center_freq: float, gain: float | None):
        if SoapySDR is None:
            detail = f"{_soapy_import_error}" if _soapy_import_error else "not installed"
            raise RuntimeError(
                "SoapySDR backend unavailable. "
                f"{detail}. "
                "On macOS, install via Homebrew: `brew install soapysdr`."
            )
        super().__init__(sample_rate, center_freq, gain)
        self.device = SoapySDR.Device(dict())
        self.device.setSampleRate(SOAPY_SDR_RX, 0, sample_rate)
        self.device.setFrequency(SOAPY_SDR_RX, 0, center_freq)
        if gain is not None:
            try:
                self.device.setGain(SOAPY_SDR_RX, 0, gain)
            except Exception:
                pass
        self.rx_stream = self.device.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CS16, [0])
        self.device.activateStream(self.rx_stream)

    def read_samples(self, num_samples: int) -> np.ndarray:
        buff = np.empty(2 * num_samples, dtype=np.int16)
        sr = self.device.readStream(self.rx_stream, [buff], num_samples)
        if getattr(sr, "ret", 0) > 0:
            iq = buff.astype(np.float32).view(np.complex64)
            return iq[: sr.ret]
        return np.array([], dtype=np.complex64)

    def tune(self, freq_hz: float) -> None:
        self.center_freq = freq_hz
        self.device.setFrequency(SOAPY_SDR_RX, 0, freq_hz)

    def close(self) -> None:
        try:
            self.device.deactivateStream(self.rx_stream)
            self.device.closeStream(self.rx_stream)
        except Exception:
            pass

    def get_info(self) -> dict:
        info = {
            "name": "SoapySDR",
            "sample_rate": self.sample_rate,
            "center_freq": self.center_freq,
            "gain": self.gain,
        }
        try:
            info["driver"] = self.device.getDriverKey()
            info["hardware"] = self.device.getHardwareKey()
            info.update(self.device.getHardwareInfo() or {})
        except Exception:
            pass
        return info


class FileSDRSource(BaseSDRSource):
    def __init__(self, sample_rate: float, center_freq: float, filename: str):
        self.filename = filename
        self.file_data = np.load(filename)
        self.file_ptr = 0
        self.sample_count = len(self.file_data)
        super().__init__(sample_rate, center_freq, gain=None)

    def read_samples(self, num_samples: int) -> np.ndarray:
        if self.file_data is None:
            return np.array([], dtype=np.complex64)
        end_idx = min(self.file_ptr + num_samples, self.sample_count)
        samples = self.file_data[self.file_ptr : end_idx]
        self.file_ptr = end_idx
        if self.file_ptr >= self.sample_count:
            self.file_ptr = 0
        return np.array(samples, dtype=np.complex64)

    def tune(self, freq_hz: float) -> None:
        self.center_freq = freq_hz

    def close(self) -> None:
        self.file_data = None

    def get_info(self) -> dict:
        return {
            "name": "File Source",
            "sample_rate": self.sample_rate,
            "center_freq": self.center_freq,
            "filename": self.filename,
            "total_samples": self.sample_count,
        }


class SyntheticSDRSource(BaseSDRSource):
    """Synthetic IQ source (no hardware) for UI demos and smoke tests."""

    def __init__(self, sample_rate: float, center_freq: float, gain: float | None = None):
        super().__init__(sample_rate=sample_rate, center_freq=center_freq, gain=gain)
        self._sample_index = 0

    def read_samples(self, num_samples: int) -> np.ndarray:
        sr = float(self.sample_rate)
        n0 = self._sample_index
        t = (np.arange(num_samples, dtype=np.float32) + n0) / sr

        # Baseband noise
        noise = 0.08 * (np.random.randn(num_samples) + 1j * np.random.randn(num_samples))

        # Burst a tone on/off so squelch/event logic can trigger and stop.
        # Less frequent to avoid spamming bundles.
        burst_period_s = 10.0
        burst_on_s = 3.0
        phase = (n0 / sr) % burst_period_s
        tone_on = phase < burst_on_s
        if tone_on:
            tone_hz = 25_000.0
            tone = 1.0 * np.exp(1j * 2.0 * np.pi * tone_hz * t)
        else:
            tone = 0.0

        self._sample_index += num_samples
        return (noise + tone).astype(np.complex64)

    def tune(self, freq_hz: float) -> None:
        self.center_freq = freq_hz

    def close(self) -> None:
        pass

    def get_info(self) -> dict:
        return {
            "name": "Synthetic Source",
            "sample_rate": self.sample_rate,
            "center_freq": self.center_freq,
            "gain": self.gain,
        }


def create_sdr_source(kind: str, sample_rate: float, center_freq: float, gain: float | None = None, filename: str | None = None) -> BaseSDRSource:
    kind = (kind or "rtl").lower()
    if kind == "synthetic":
        return SyntheticSDRSource(sample_rate=sample_rate, center_freq=center_freq, gain=gain)
    if kind == "rtl":
        return RTLSDRSource(sample_rate=sample_rate, center_freq=center_freq, gain=gain)
    if kind == "soapy":
        return SoapySDRSource(sample_rate=sample_rate, center_freq=center_freq, gain=gain)
    if kind == "file":
        if not filename:
            raise ValueError("filename must be provided for file source")
        return FileSDRSource(sample_rate=sample_rate, center_freq=center_freq, filename=filename)
    raise ValueError(f"Unknown source type: {kind}")


class SDRIngest(BaseSDRSource):
    """Deprecated compatibility wrapper (kept for older callers)."""

    def __init__(self, sample_rate=2.4e6, center_freq=100e6, gain=None, source="rtl", filename=None):
        self._delegate = create_sdr_source(kind=source, sample_rate=sample_rate, center_freq=center_freq, gain=gain, filename=filename)
        super().__init__(sample_rate, center_freq, gain)

    def read_samples(self, num_samples: int) -> np.ndarray:
        return self._delegate.read_samples(num_samples)

    def tune(self, freq_hz: float) -> None:
        self._delegate.tune(freq_hz)

    def close(self) -> None:
        self._delegate.close()

    def get_info(self) -> dict:
        return self._delegate.get_info()
