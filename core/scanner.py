from __future__ import annotations

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
import time

from SDR.sdr_ingest import create_sdr_source
from SDR.signal_processing import compute_power, DemodulatorFactory
from core.transcriber import Transcriber
from core.logger import EventLogger
from core.vector_store import TranscriptIndex
from core import bundles
from core.multi_demod import MultiChannelDemod, ChannelConfig


class ScannerThread(QThread):
    """
    Thread that handles scanning frequencies (or staying on one frequency in manual mode),
    detecting signals, recording audio, and invoking transcription.
    """

    signal_update = pyqtSignal(object)  # spectrum data
    signal_event = pyqtSignal(object)  # log event or status
    audio_level = pyqtSignal(float)  # post-demod audio RMS for UI meter
    audio_frame = pyqtSignal(object)  # float32 audio chunk for playback
    device_info = pyqtSignal(object)  # emitted once after SDR creation
    now_playing = pyqtSignal(float, str)  # freq_hz, mode

    def __init__(
        self,
        freq_range=(100e6, 101e6, 0.2e6),
        mode="FM",
        gain=None,
        squelch_db=-60.0,
        scan_mode=True,
        sample_rate=2.5e5,
        source_type="rtl",
        source_args=None,
        dwell_seconds=0.25,
        hold_seconds=0.5,
        audio_rate=16_000,
        enable_transcription: bool = False,
        transcription_model: str = "base.en",
        ui_max_fps: float = 20.0,
        max_event_seconds: float = 6.0,
        min_event_seconds: float = 1.0,
        hunt_mode: bool = False,
        multi_channels: list[dict] | None = None,
        transcript_index: TranscriptIndex | None = None,
        save_bundles: bool = True,
        bundle_root: str = "runs",
        parent=None,
    ):
        super().__init__(parent)
        self.start_freq = freq_range[0]
        self.stop_freq = freq_range[1]
        self.step_freq = freq_range[2] if len(freq_range) > 2 else 0
        if self.step_freq is None:
            self.step_freq = 0
        self.mode = mode
        self.gain = gain
        self.squelch_db = squelch_db
        self.squelch_linear = 10 ** (squelch_db / 20.0)
        self.scan_mode = scan_mode
        self.sample_rate = sample_rate
        self.source_type = source_type
        self.source_args = source_args or {}
        self.dwell_seconds = dwell_seconds
        self.hold_seconds = hold_seconds
        self.audio_rate = audio_rate
        self.save_bundles = save_bundles
        self.bundle_root = bundle_root
        self.enable_transcription = bool(enable_transcription)
        self.transcription_model = str(transcription_model or "base.en")
        self.ui_max_fps = float(ui_max_fps) if ui_max_fps else 20.0
        self.max_event_seconds = float(max_event_seconds) if max_event_seconds else 6.0
        self.min_event_seconds = float(min_event_seconds) if min_event_seconds else 0.0
        self.hunt_mode = bool(hunt_mode)
        self.multi_cfg = multi_channels or []

        self.logger = EventLogger(transcript_index=transcript_index)
        self.transcript_index = transcript_index
        self.transcriber = None
        self.sdr = None
        self.block_size = 4096
        self.demodulator = DemodulatorFactory.get(mode=self.mode, audio_rate=self.audio_rate)
        self._announced_active = False
        self.multi_demod = None
        try:
            self.now_playing.emit(self.start_freq, self.mode)
        except Exception:
            pass

    def _build_frequency_list(self):
        if self.scan_mode:
            if self.step_freq <= 0:
                return [self.start_freq]
            return list(np.arange(self.start_freq, self.stop_freq + (self.step_freq * 0.5), self.step_freq))
        return [self.start_freq]

    def run(self):
        """Main thread loop: set up SDR and perform scanning or receiving."""
        try:
            self.sdr = create_sdr_source(
                kind=self.source_type,
                sample_rate=self.sample_rate,
                center_freq=self.start_freq,
                gain=self.gain,
                filename=self.source_args.get("filename"),
            )
        except Exception as e:
            self.signal_event.emit(f"SDR init failed: {e}")
            return
        try:
            self.device_info.emit(self.sdr.get_info())
        except Exception:
            self.device_info.emit({"name": self.source_type, "error": "info unavailable"})

        # Transcription is optional; never block scanning/plots on model downloads.
        if self.enable_transcription and self.source_type != "synthetic":
            try:
                self.transcriber = Transcriber(model_size=self.transcription_model)
            except Exception as e:
                msg = f"Transcriber init failed: {e}"
                if "CERTIFICATE_VERIFY_FAILED" in str(e) or "certificate verify failed" in str(e).lower():
                    msg += (
                        " (SSL certificate verification failed while fetching model. "
                        "On macOS, try running the Python 'Install Certificates' script, "
                        "or disable transcription for now.)"
                    )
                self.signal_event.emit(msg)
                self.transcriber = None
        else:
            self.transcriber = None

        freq_list = self._build_frequency_list()
        current_index = 0
        num_freqs = len(freq_list)

        if self.multi_cfg:
            ch_cfgs = []
            for c in self.multi_cfg:
                try:
                    ch_cfgs.append(
                        ChannelConfig(
                            freq_hz=float(c.get("freq_hz")),
                            mode=str(c.get("mode", "FM")),
                            squelch_linear=10 ** (float(c.get("squelch_db", -60.0)) / 20.0),
                            enabled=bool(c.get("enabled", True)),
                            name=str(c.get("name", "")),
                        )
                    )
                except Exception:
                    continue
            self.multi_demod = MultiChannelDemod(sample_rate=self.sample_rate)
            self.multi_demod.set_channels(ch_cfgs)

        audio_buffer = []
        iq_buffer = []
        recording_freq = None
        quiet_count = 0
        quiet_threshold_blocks = 5
        active_signal = False
        active_started_at = None

        # Avoid overwhelming the UI thread. pyqtgraph redraws are expensive; cap update rate.
        last_ui_update = 0.0
        ui_period = 1.0 / max(self.ui_max_fps, 1.0)

        while not self.isInterruptionRequested():
            freq = freq_list[current_index]
            if self.scan_mode and not active_signal:
                self.sdr.tune(freq)
                time.sleep(self.dwell_seconds)

            samples = self.sdr.read_samples(self.block_size)
            if samples.size == 0:
                break

            now = time.monotonic()
            if self.hunt_mode and not active_signal and self.scan_mode:
                # Faster sweeps: shorten dwell pacing if hunt is on
                self.dwell_seconds = min(self.dwell_seconds, 0.12)
            if (now - last_ui_update) >= ui_period:
                # Spectrum for UI (rate-limited)
                fft_vals = 20 * np.log10(np.abs(np.fft.fftshift(np.fft.fft(samples, n=512))) + 1e-6)
                fft_vals = fft_vals - np.max(fft_vals)
                freqs = np.linspace(-0.5, 0.5, len(fft_vals)) * self.sdr.sample_rate + freq
                self.signal_update.emit((freqs / 1e6, fft_vals))
                last_ui_update = now

            power_linear = compute_power(samples)
            power_db = 20 * np.log10(power_linear + 1e-6)

            # Multi-channel demod (optional)
            if self.multi_demod:
                try:
                    multi_audio = self.multi_demod.process(freq, samples)
                    for ma in multi_audio:
                        if "audio" in ma and ma["audio"] is not None:
                            try:
                                self.audio_frame.emit(ma["audio"])
                            except Exception:
                                pass
                        self.audio_level.emit(ma.get("audio_rms", 0.0))
                except Exception:
                    pass

            if not active_signal and power_linear > self.squelch_linear:
                active_signal = True
                recording_freq = freq
                audio_buffer = []
                iq_buffer = []
                quiet_count = 0
                active_started_at = time.monotonic()
                self._announced_active = True
                try:
                    self.now_playing.emit(recording_freq, self.mode)
                except Exception:
                    pass

            if active_signal and freq == recording_freq:
                iq_buffer.append(np.copy(samples))
                audio_chunk = self.demodulator.demod(samples, self.sdr.sample_rate)
                if audio_chunk.size > 0:
                    audio_buffer.append(audio_chunk)
                    try:
                        rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
                        self.audio_level.emit(rms)
                        self.audio_frame.emit(audio_chunk)
                    except Exception:
                        pass
                if power_linear < self.squelch_linear:
                    quiet_count += 1
                else:
                    quiet_count = 0
                # If signal quiets or we exceed max duration, finalize the event.
                too_long = False
                if active_started_at is not None:
                    elapsed = time.monotonic() - active_started_at
                    if elapsed >= self.max_event_seconds:
                        too_long = True

                if quiet_count >= quiet_threshold_blocks or too_long:
                    active_signal = False
                    quiet_count = 0
                    recording_freq = freq
                    audio_data = np.concatenate(audio_buffer) if audio_buffer else np.array([], dtype=np.float32)
                    event_elapsed = 0.0
                    if active_started_at is not None:
                        event_elapsed = time.monotonic() - active_started_at
                    transcribed_text = ""
                    if audio_data.size > 0 and self.transcriber:
                        try:
                            transcribed_text = self.transcriber.transcribe_audio(audio_data, sample_rate=self.audio_rate)
                        except Exception:
                            transcribed_text = "[Transcription Error]"
                    event = self.logger.log_event(
                        recording_freq,
                        transcribed_text,
                        metadata={
                            "power_db": power_db,
                            "duration_s": event_elapsed,
                        },
                    )
                    self.signal_event.emit(event)
                    if self.save_bundles and event_elapsed >= self.min_event_seconds:
                        try:
                            iq_data = np.concatenate(iq_buffer) if iq_buffer else np.array([], dtype=np.complex64)
                            bundles.write_event_bundle(
                                event=event,
                                iq=iq_data,
                                sample_rate=self.sdr.sample_rate,
                                center_freq=recording_freq,
                                mode=self.mode,
                                bundle_root=self.bundle_root,
                                save_sigmf=True,
                            )
                        except Exception:
                            # Avoid crashing scanner on bundle write issues.
                            pass
                    elif self.save_bundles and event_elapsed < self.min_event_seconds:
                        # Avoid directory spam on very short keys; inform UI once.
                        self.signal_event.emit(
                            f"Skipped saving bundle (duration {event_elapsed:.2f}s below min {self.min_event_seconds:.2f}s)."
                        )
                    if self.scan_mode:
                        time.sleep(self.hold_seconds)
                    recording_freq = None
                    audio_buffer = []
                    iq_buffer = []
                    active_started_at = None
                    self._announced_active = False
                    try:
                        self.audio_level.emit(0.0)
                    except Exception:
                        pass

            if self.scan_mode and not active_signal:
                current_index = (current_index + 1) % num_freqs

            # Yield a tiny bit to keep CPU reasonable (especially for synthetic/non-scan).
            if self.source_type == "synthetic" and not self.scan_mode:
                time.sleep(0.002)

        if self.sdr:
            self.sdr.close()
        self.logger.close()
