"""Reusable control panels for the AstroTrace UI."""

from PyQt5.QtWidgets import (
    QWidget,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
)
from PyQt5.QtCore import Qt


class DeviceControlPanel(QWidget):
    """Controls for manual tuning, mode selection, and device settings."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QFormLayout()
        layout.setLabelAlignment(Qt.AlignRight)

        self.freq_input = QDoubleSpinBox()
        self.freq_input.setRange(0.001, 6000.0)
        self.freq_input.setDecimals(3)
        self.freq_input.setSingleStep(0.1)
        self.freq_input.setValue(100.000)
        layout.addRow(QLabel("Frequency (MHz)"), self.freq_input)

        self.mode_select = QComboBox()
        self.mode_select.addItems(["FM", "AM", "SSB", "CW"])
        layout.addRow(QLabel("Mode"), self.mode_select)

        self.gain_input = QSpinBox()
        self.gain_input.setRange(0, 60)
        self.gain_input.setValue(10)
        layout.addRow(QLabel("Gain (dB/index)"), self.gain_input)

        self.squelch_input = QDoubleSpinBox()
        self.squelch_input.setRange(-120.0, 0.0)
        self.squelch_input.setDecimals(1)
        self.squelch_input.setSingleStep(1.0)
        self.squelch_input.setValue(-60.0)
        layout.addRow(QLabel("Squelch (dBFS)"), self.squelch_input)

        self.sample_rate_input = QDoubleSpinBox()
        self.sample_rate_input.setRange(0.1, 5_000.0)
        self.sample_rate_input.setDecimals(3)
        self.sample_rate_input.setSingleStep(0.1)
        self.sample_rate_input.setValue(2.400)
        layout.addRow(QLabel("Sample Rate (MS/s)"), self.sample_rate_input)

        self.bundle_checkbox = QCheckBox("Save bundles (SigMF)")
        self.bundle_checkbox.setChecked(True)
        layout.addRow(QLabel("Recording"), self.bundle_checkbox)

        self.source_select = QComboBox()
        # Default to synthetic so the UI works out-of-the-box without SDR drivers/hardware.
        self.source_select.addItems(["synthetic", "rtl", "soapy", "file"])
        layout.addRow(QLabel("Source"), self.source_select)

        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("Path to IQ file (for file source)")
        layout.addRow(QLabel("IQ File"), self.file_path)

        self.transcribe_checkbox = QCheckBox("Transcribe voice (Whisper)")
        self.transcribe_checkbox.setChecked(False)
        layout.addRow(QLabel("AI"), self.transcribe_checkbox)

        wrapper = QVBoxLayout(self)
        wrapper.addLayout(layout)
        wrapper.addStretch(1)

    def values(self) -> dict:
        """Return current control values as a dict."""
        return {
            "frequency_mhz": float(self.freq_input.value()),
            "mode": str(self.mode_select.currentText()),
            "gain": int(self.gain_input.value()),
            "squelch_db": float(self.squelch_input.value()),
            "sample_rate_hz": float(self.sample_rate_input.value()) * 1e6,
            "source": str(self.source_select.currentText()),
            "file_path": str(self.file_path.text()).strip(),
            "save_bundles": self.bundle_checkbox.isChecked(),
            "enable_transcription": self.transcribe_checkbox.isChecked(),
        }


class ScanControlPanel(QWidget):
    """Controls for scan mode configuration."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QFormLayout()
        layout.setLabelAlignment(Qt.AlignRight)

        self.scan_checkbox = QCheckBox("Enable Scan Mode")
        layout.addRow(QLabel("Mode"), self.scan_checkbox)

        self.start_freq = QDoubleSpinBox()
        self.start_freq.setRange(0.001, 6000.0)
        self.start_freq.setDecimals(3)
        self.start_freq.setValue(100.000)
        layout.addRow(QLabel("Start (MHz)"), self.start_freq)

        self.stop_freq = QDoubleSpinBox()
        self.stop_freq.setRange(0.001, 6000.0)
        self.stop_freq.setDecimals(3)
        self.stop_freq.setValue(101.000)
        layout.addRow(QLabel("Stop (MHz)"), self.stop_freq)

        self.step_freq = QDoubleSpinBox()
        self.step_freq.setRange(0.001, 1000.0)
        self.step_freq.setDecimals(3)
        self.step_freq.setSingleStep(0.01)
        self.step_freq.setValue(0.200)
        layout.addRow(QLabel("Step (MHz)"), self.step_freq)

        self.dwell_time = QDoubleSpinBox()
        self.dwell_time.setRange(0.0, 10.0)
        self.dwell_time.setDecimals(2)
        self.dwell_time.setSingleStep(0.25)
        self.dwell_time.setValue(0.25)
        layout.addRow(QLabel("Dwell (s)"), self.dwell_time)

        self.hold_time = QDoubleSpinBox()
        self.hold_time.setRange(0.0, 10.0)
        self.hold_time.setDecimals(2)
        self.hold_time.setSingleStep(0.25)
        self.hold_time.setValue(0.50)
        layout.addRow(QLabel("Hold after Tx (s)"), self.hold_time)

        wrapper = QVBoxLayout(self)
        wrapper.addLayout(layout)
        wrapper.addStretch(1)

    def values(self) -> dict:
        """Return scan configuration as a dict."""
        return {
            "scan_mode": self.scan_checkbox.isChecked(),
            "start_mhz": float(self.start_freq.value()),
            "stop_mhz": float(self.stop_freq.value()),
            "step_mhz": float(self.step_freq.value()),
            "dwell_seconds": float(self.dwell_time.value()),
            "hold_seconds": float(self.hold_time.value()),
        }

