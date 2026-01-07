"""Regression test plugin: runs end-to-end checks and produces reports."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QCheckBox,
    QHBoxLayout,
)
from PyQt5.QtCore import Qt

from tests.runner import RegressionRunner


def _summarize_report(report: dict) -> str:
    lines = []
    lines.append(f"Passed: {report.get('passed')}")
    lines.append(f"Duration: {report.get('duration_sec', 0):.1f}s")
    for res in report.get("results", []):
        ok = "PASS" if res.get("passed") else "FAIL"
        lines.append(f"- {res.get('name')}: {ok}")
        if not res.get("passed"):
            err = res.get("error") or ""
            lines.append(f"  reason: {err}")
    if "path" in report:
        lines.append(f"Report: {report['path']}")
    return "\n".join(lines)


def register(ui, tab_widget):
    panel = QWidget()
    layout = QVBoxLayout(panel)
    title = QLabel("Regression Tests")
    title.setObjectName("sectionTitle")
    layout.addWidget(title)

    desc = QLabel("Run automated scenarios (scanner + agent + RTL probe + multi-demod). Generates JSON reports.")
    desc.setWordWrap(True)
    layout.addWidget(desc)

    opts_row = QHBoxLayout()
    use_rtl = QCheckBox("Use RTL hardware")
    use_rtl.setChecked(True)
    auto_tune = QCheckBox("Auto-tune squelch on failure")
    auto_tune.setChecked(True)
    opts_row.addWidget(use_rtl)
    opts_row.addWidget(auto_tune)
    opts_row.addStretch(1)
    layout.addLayout(opts_row)

    run_btn = QPushButton("Run regression")
    layout.addWidget(run_btn)

    log = QTextEdit()
    log.setReadOnly(True)
    log.setMinimumHeight(180)
    layout.addWidget(log)

    last_report_btn = QPushButton("Open last report")
    layout.addWidget(last_report_btn)

    runner_ref = {"runner": None}

    def append(msg: str):
        log.append(msg)
        try:
            ui.log_output.append(msg)
        except Exception:
            pass

    def on_finished(report: dict):
        append("Regression completed.")
        append(_summarize_report(report))
        runner_ref["runner"] = None

    def start_run():
        if runner_ref["runner"] is not None:
            append("Run already in progress.")
            return
        runner = RegressionRunner(use_rtl=use_rtl.isChecked(), auto_tune=auto_tune.isChecked())
        runner.progress.connect(append)
        runner.finished_report.connect(on_finished)
        runner_ref["runner"] = runner
        append("Starting regression run ...")
        runner.start()

    def open_last():
        reports_dir = Path("test_reports")
        if not reports_dir.exists():
            append("No reports yet.")
            return
        reports = sorted(reports_dir.glob("report_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not reports:
            append("No reports yet.")
            return
        path = reports[0]
        append(f"Last report: {path}")
        try:
            import json
            data = json.loads(path.read_text())
            log.setPlainText(_summarize_report(data))
        except Exception as exc:
            append(f"Failed to open report: {exc}")

    run_btn.clicked.connect(start_run)
    last_report_btn.clicked.connect(open_last)

    tab_widget.addTab(panel, "Regression")

