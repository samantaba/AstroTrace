import csv
import datetime
import json
import logging
import threading
from typing import List, Dict, Any, Optional

from .vector_store import TranscriptIndex


class EventLogger:
    """
    Logs events (signal detections, transcriptions, etc.) to disk and keeps a
    process-wide recent buffer. Optionally mirrors transcripts into a
    vector store for semantic search.
    """

    _global_events: List[Dict[str, Any]] = []
    _lock = threading.Lock()

    def __init__(self, log_file: str = "sdr_events.log", jsonl_file: str = "sdr_events.jsonl", transcript_index: Optional[TranscriptIndex] = None):
        self.log_file = log_file
        self.jsonl_file = jsonl_file
        self.transcript_index = transcript_index
        self.events: List[Dict[str, Any]] = []
        self._csv = None
        try:
            self._csv = open(self.log_file, "a", newline="")
            if self._csv.tell() == 0:
                writer = csv.writer(self._csv)
                writer.writerow(["Time", "Frequency_MHz", "Transcribed_Text"])
        except Exception as exc:
            logging.error("Failed to open log file: %s", exc)
            self._csv = None
        try:
            self._jsonl = open(self.jsonl_file, "a")
        except Exception as exc:
            logging.error("Failed to open jsonl log file: %s", exc)
            self._jsonl = None

    def log_event(self, frequency_hz: float, text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Log a new event with timestamp, frequency, and text.
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        freq_mhz = frequency_hz / 1e6
        log_text = text or ""
        event = {"time": timestamp, "freq": frequency_hz, "text": log_text}
        if metadata:
            event.update(metadata)
        self.events.append(event)
        with self._lock:
            self._global_events.append(event)

        if self._csv:
            writer = csv.writer(self._csv)
            writer.writerow([timestamp, f"{freq_mhz:.6f}", log_text])
            self._csv.flush()
        if self._jsonl:
            try:
                self._jsonl.write(json.dumps(event) + "\n")
                self._jsonl.flush()
            except Exception as exc:
                logging.error("Failed to write jsonl event: %s", exc)
        if self.transcript_index and log_text:
            try:
                self.transcript_index.add(log_text, {"time": timestamp, "freq": frequency_hz})
            except Exception:
                pass
        return event

    @classmethod
    def recent_events(cls, n: int = 20) -> List[Dict[str, Any]]:
        with cls._lock:
            return list(cls._global_events[-n:])

    def close(self):
        """Close files if open."""
        if self._csv:
            self._csv.close()
            self._csv = None
        if getattr(self, "_jsonl", None):
            self._jsonl.close()
            self._jsonl = None
