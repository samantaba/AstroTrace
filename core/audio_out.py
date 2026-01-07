"""Lightweight audio output helper for demodulated audio."""

from __future__ import annotations

import numpy as np
from queue import Queue, Empty
from threading import Thread, Event
import time


class AudioOutput:
    """Queue-based audio player using sounddevice if available, else PyAudio."""

    def __init__(self, sample_rate: int = 16_000, blocksize: int = 1024):
        self.sample_rate = sample_rate
        self.blocksize = blocksize
        self._queue: Queue[np.ndarray] = Queue(maxsize=100)
        self._stop = Event()
        self._thread: Thread | None = None
        self._backend = None
        self._stream = None
        self.available = False
        self._init_backend()

    def _init_backend(self):
        try:
            import sounddevice as sd  # type: ignore

            self._backend = ("sounddevice", sd)
            self.available = True
        except Exception:
            try:
                import pyaudio  # type: ignore

                self._backend = ("pyaudio", pyaudio.PyAudio())
                self.available = True
            except Exception:
                self.available = False

    def start(self):
        if not self.available or self._thread is not None:
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._thread = None
        if self._backend and self._backend[0] == "pyaudio" and self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
        self._stream = None

    def push(self, audio: np.ndarray):
        if not self.available:
            return
        if audio is None or audio.size == 0:
            return
        # Ensure float32 and clamp
        audio = np.asarray(audio, dtype=np.float32)
        audio = np.clip(audio, -1.0, 1.0)
        try:
            self._queue.put_nowait(audio.copy())
        except Exception:
            # Drop if queue is full
            pass

    def _run(self):
        if not self.available:
            return
        if self._backend[0] == "sounddevice":
            sd = self._backend[1]

            def callback(outdata, frames, time_info, status):  # type: ignore
                try:
                    chunk = self._queue.get_nowait()
                except Empty:
                    chunk = np.zeros(frames, dtype=np.float32)
                if chunk.size < frames:
                    pad = np.zeros(frames - chunk.size, dtype=np.float32)
                    chunk = np.concatenate([chunk, pad])
                outdata[:] = chunk.reshape(-1, 1)[:frames]

            with sd.OutputStream(
                samplerate=self.sample_rate,
                channels=1,
                blocksize=self.blocksize,
                dtype="float32",
                callback=callback,
            ):
                while not self._stop.is_set():
                    time.sleep(0.05)
            return

        if self._backend[0] == "pyaudio":
            pa = self._backend[1]
            self._stream = pa.open(
                format=pa.get_format_from_width(2),
                channels=1,
                rate=int(self.sample_rate),
                output=True,
                frames_per_buffer=self.blocksize,
            )
            while not self._stop.is_set():
                try:
                    chunk = self._queue.get(timeout=0.1)
                except Empty:
                    continue
                self._stream.write(chunk.tobytes())

    def __del__(self):
        self.stop()

