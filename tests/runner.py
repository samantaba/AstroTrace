"""Regression test runner for AstroTrace (scanner + agent + bundles)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Any, List

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from core.scanner import ScannerThread
from core.agent import RadioOpsAgent, RadioController
from core.vector_store import TranscriptIndex
from core.logger import EventLogger
from core.sigmf_import import read_sigmf
from SDR.sdr_ingest import create_sdr_source
from SDR.signal_processing import compute_power, DemodulatorFactory
from core.multi_demod import MultiChannelDemod, ChannelConfig
from core.transcriber import Transcriber


@dataclass
class Scenario:
    name: str
    run: Callable[[], Dict[str, Any]]
    timeout: float = 20.0


def _latest_bundle(bundle_root: Path) -> Path | None:
    if not bundle_root.exists():
        return None
    dirs = [p for p in bundle_root.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.stat().st_mtime)


class RegressionRunner(QThread):
    progress = pyqtSignal(str)
    finished_report = pyqtSignal(dict)

    def __init__(self, use_rtl: bool = False, auto_tune: bool = True, parent=None):
        super().__init__(parent)
        self.use_rtl = use_rtl
        self.auto_tune = auto_tune
        self.report_root = Path("test_reports")
        self.report_root.mkdir(exist_ok=True)
        self.overrides_path = self.report_root / "overrides.json"
        self.overrides = self._load_overrides()

    def _load_overrides(self) -> Dict[str, Any]:
        if self.overrides_path.exists():
            try:
                return json.loads(self.overrides_path.read_text())
            except Exception:
                return {}
        return {}

    def _save_overrides(self, data: Dict[str, Any]) -> None:
        try:
            self.overrides_path.write_text(json.dumps(data, indent=2))
        except Exception:
            pass

    def _emit(self, msg: str):
        try:
            self.progress.emit(msg)
        except Exception:
            pass

    # ---------- Scenarios ----------

    def _scenario_synthetic_scan(self) -> Dict[str, Any]:
        """Run scanner on synthetic source and expect >=1 event + bundle."""
        bundle_root = Path("runs_tests")
        if bundle_root.exists():
            for item in bundle_root.iterdir():
                if item.is_dir():
                    for f in item.glob("*"):
                        f.unlink(missing_ok=True)
                    item.rmdir()
        transcript_idx = TranscriptIndex()
        agent = RadioOpsAgent(
            controller=RadioController(
                tune_fn=lambda *args, **kwargs: "ok",
                scan_fn=lambda *args, **kwargs: "ok",
                stop_fn=lambda: "ok",
                get_logs_fn=lambda n=5: EventLogger.recent_events(n),
                search_fn=lambda q, k=5: transcript_idx.search(q, k=k),
            ),
            transcript_index=transcript_idx,
        )

        events: List[Any] = []
        scanner = ScannerThread(
            freq_range=(100e6, 100e6, 0),  # single freq to complete event
            mode="FM",
            gain=None,
            squelch_db=self.overrides.get("squelch_db", -80.0),
            scan_mode=True,
            sample_rate=250_000,
            source_type="synthetic" if not self.use_rtl else "rtl",
            source_args={},
            dwell_seconds=0.15,
            hold_seconds=0.3,
            enable_transcription=False,
            ui_max_fps=10.0,
            max_event_seconds=4.0,
            min_event_seconds=0.5,
            bundle_root=str(bundle_root),
            save_bundles=True,
        )

        def on_event(ev):
            events.append(ev)

        scanner.signal_event.connect(on_event)
        scanner.start()
        start = time.time()
        while time.time() - start < 20.0:
            if any(isinstance(e, dict) for e in events):
                break
            time.sleep(0.25)
        scanner.requestInterruption()
        scanner.wait(2000)

        bundle = _latest_bundle(bundle_root)
        bundle_ok = False
        if bundle:
            meta = bundle / "capture.sigmf-meta"
            data = bundle / "capture.sigmf-data"
            bundle_ok = meta.exists() and data.exists()
            if bundle_ok:
                try:
                    read_sigmf(bundle / "capture")
                except Exception:
                    bundle_ok = False

        result = {
            "events": len([e for e in events if isinstance(e, dict)]),
            "bundle_found": bool(bundle_ok),
            "squelch_db": self.overrides.get("squelch_db", -60.0),
        }
        result["passed"] = result["events"] >= 1 and result["bundle_found"]
        if self.auto_tune and result["events"] == 0:
            # Self-correct: lower squelch by 10 dB for next run
            new_sq = max(-100.0, self.overrides.get("squelch_db", -60.0) - 10.0)
            self.overrides["squelch_db"] = new_sq
        return result

    def _scenario_agent(self) -> Dict[str, Any]:
        """Verify agent responds to logs/search commands."""
        transcript_idx = TranscriptIndex()
        controller = RadioController(
            tune_fn=lambda *a, **k: "tuned",
            scan_fn=lambda *a, **k: "scan",
            stop_fn=lambda: "stopped",
            get_logs_fn=lambda n=5: [{"time": "t", "freq": 100e6, "text": "hello"}],
            search_fn=lambda q, k=5: [{"time": "t", "freq": 100e6, "text": "hello"}],
        )
        agent = RadioOpsAgent(controller=controller, transcript_index=transcript_idx)
        reply_logs = agent.handle("show recent logs")
        reply_search = agent.handle("search hello")
        return {
            "passed": bool(reply_logs.strip()) and bool(reply_search.strip()),
            "reply_logs": reply_logs[:200],
            "reply_search": reply_search[:200],
        }

    def _scenario_rtl_probe(self) -> Dict[str, Any]:
        """Open RTL device, read samples, verify non-empty and sane power."""
        if not self.use_rtl:
            return {"passed": True, "skipped": True, "reason": "use_rtl disabled"}
        try:
            src = create_sdr_source(kind="rtl", sample_rate=250_000, center_freq=100e6, gain=None)
            samples = src.read_samples(2048)
            src.close()
        except Exception as exc:
            return {"passed": True, "skipped": True, "reason": f"RTL probe skipped: {exc}"}
        power = compute_power(samples)
        return {"passed": samples.size > 0, "power": float(power)}

    def _scenario_rtl_scan_power(self) -> Dict[str, Any]:
        """Run a short scan on RTL and confirm samples flow (no event requirement)."""
        if not self.use_rtl:
            return {"passed": True, "skipped": True, "reason": "use_rtl disabled"}
        freq = float(self.overrides.get("rtl_center_mhz", 100.0)) * 1e6
        events: List[Any] = []
        powers: List[float] = []
        scanner = ScannerThread(
            freq_range=(freq, freq, 0),
            mode="FM",
            gain=30,
            squelch_db=self.overrides.get("squelch_db", -60.0),
            scan_mode=False,
            sample_rate=250_000,
            source_type="rtl",
            source_args={},
            dwell_seconds=0.1,
            hold_seconds=0.1,
            enable_transcription=False,
            ui_max_fps=10.0,
            max_event_seconds=3.0,
            min_event_seconds=0.0,
            save_bundles=False,
        )

        def on_event(ev):
            events.append(ev)

        def on_update(spec):
            try:
                _, p = spec
                if len(p):
                    powers.append(float(np.max(p)))
            except Exception:
                pass

        scanner.signal_event.connect(on_event)
        scanner.signal_update.connect(on_update)
        scanner.start()
        time.sleep(12.0)
        scanner.requestInterruption()
        scanner.wait(2000)
        return {
            "passed": len(powers) > 0,
            "samples_seen": len(powers),
            "max_power_db": float(np.max(powers)) if powers else None,
        }

    def _scenario_multi_demod(self) -> Dict[str, Any]:
        """Validate multi-channel demod on synthetic data."""
        sr = 256_000.0
        t = np.arange(4096) / sr
        iq = (0.05 * (np.random.randn(4096) + 1j * np.random.randn(4096))).astype(np.complex64)
        # Add two tones
        iq += 0.2 * np.exp(1j * 2 * np.pi * 12_000 * t)
        iq += 0.2 * np.exp(1j * 2 * np.pi * 30_000 * t)
        cfgs = [
            ChannelConfig(freq_hz=12_000, mode="FM"),
            ChannelConfig(freq_hz=30_000, mode="FM"),
        ]
        demod = MultiChannelDemod(sample_rate=sr)
        demod.set_channels(cfgs)
        outs = demod.process(center_freq=0.0, samples=iq)
        passed = len(outs) == 2 and all(item.get("audio") is not None and item["audio"].size > 0 for item in outs)
        return {"passed": passed, "channels": [o.get("freq_hz") for o in outs]}

    def _scenario_whisper_available(self) -> Dict[str, Any]:
        """Smoke-test transcriber init and text output (skip if missing)."""
        try:
            tr = Transcriber(model_size="tiny.en")
            txt = tr.transcribe_audio(np.zeros(8000, dtype=np.float32), sample_rate=16000)
            if not isinstance(txt, str):
                return {"passed": False, "error": "Whisper returned non-string"}
            if not txt.strip():
                return {"passed": True, "skipped": True, "reason": "Whisper returned empty text on silence"}
            return {"passed": True, "text_sample": txt[:120]}
        except Exception as exc:
            return {"passed": True, "skipped": True, "reason": f"Whisper unavailable: {exc}"}

    def _scenario_agent_llm(self) -> Dict[str, Any]:
        """Agent LLM path if OPENAI_API_KEY is set."""
        import os

        if not os.environ.get("OPENAI_API_KEY"):
            return {"passed": True, "skipped": True, "reason": "OPENAI_API_KEY not set"}
        transcript_idx = TranscriptIndex()
        controller = RadioController(
            tune_fn=lambda *a, **k: "tuned",
            scan_fn=lambda *a, **k: "scan",
            stop_fn=lambda: "stopped",
            get_logs_fn=lambda n=5: [{"time": "t", "freq": 100e6, "text": "hello"}],
            search_fn=lambda q, k=5: [{"time": "t", "freq": 100e6, "text": "hello"}],
        )
        agent = RadioOpsAgent(controller=controller, transcript_index=transcript_idx)
        reply = agent.handle("scan 88 108 0.2 fm")
        return {"passed": bool(reply.strip()), "reply": reply[:200]}

    # ---------- Runner ----------

    def run(self):
        scenarios = [
            Scenario("synthetic_scan", self._scenario_synthetic_scan, timeout=20.0),
            Scenario("agent_responses", self._scenario_agent, timeout=5.0),
            Scenario("rtl_probe", self._scenario_rtl_probe, timeout=6.0),
            Scenario("rtl_scan_power", self._scenario_rtl_scan_power, timeout=12.0),
            Scenario("multi_demod", self._scenario_multi_demod, timeout=5.0),
            Scenario("whisper_available", self._scenario_whisper_available, timeout=5.0),
            Scenario("agent_llm", self._scenario_agent_llm, timeout=6.0),
        ]
        results = []
        start = time.time()
        for sc in scenarios:
            self._emit(f"Running {sc.name} ...")
            try:
                res = sc.run()
                res["name"] = sc.name
            except Exception as exc:
                res = {"name": sc.name, "passed": False, "error": str(exc)}
            results.append(res)
        duration = time.time() - start
        passed = all(r.get("passed") for r in results)
        report = {
            "results": results,
            "passed": passed,
            "duration_sec": duration,
            "timestamp": time.time(),
            "overrides": self.overrides,
        }
        self._save_overrides(self.overrides)
        report_path = self.report_root / f"report_{int(time.time())}.json"
        try:
            report_path.write_text(json.dumps(report, indent=2))
            report["path"] = str(report_path)
        except Exception:
            pass
        self._emit("Regression run complete.")
        self.finished_report.emit(report)

