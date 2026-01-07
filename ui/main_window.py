from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QSplitter,
    QTabWidget,
    QLineEdit,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QAction,
    QProgressBar,
    QToolBar,
    QMessageBox,
    QFrame,
    QDockWidget,
    QScrollArea,
    QToolButton,
)
from PyQt5.QtGui import QPalette, QColor, QFont, QPixmap
from PyQt5.QtCore import pyqtSlot, Qt, QSettings
import numpy as np
import math
from pathlib import Path
from collections import deque

from core.scanner import ScannerThread
from core.agent import RadioOpsAgent, RadioController
from core.vector_store import TranscriptIndex
from core.logger import EventLogger
from core.audio_out import AudioOutput
from core.plugins import load_plugins
from ui.plot_widgets import SpectrumWidget, WaterfallWidget
from ui.control_panels import DeviceControlPanel, ScanControlPanel
from ui.chat_panel import ChatPanel
from ui.multi_channel_tab import MultiChannelTab


class SDRMainWindow(QMainWindow):
    """Main GUI window for AstroTrace."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AstroTrace")
        self.resize(1200, 780)
        self._apply_theme()
        self.settings = QSettings("AstroTrace", "AstroTraceApp")
        self._logo_path, self._bg_path = self._find_brand_assets()

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 8, 10, 10)
        main_layout.setSpacing(8)

        self._build_menu()
        self._build_toolbar()

        # Header with brand + quick status
        main_layout.addWidget(self._build_header())
        self._apply_background(central_widget)
        main_layout.addWidget(self._build_now_playing())

        # Central area: spectrum + waterfall in a vertical split
        self._splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(self._splitter, stretch=1)
        self._splitter.addWidget(self._build_signal_panel())
        self._splitter.addWidget(self._build_bottom_panel())
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)
        self._splitter.setSizes([520, 260])

        # Dockable controls (right) to maximize visualization space
        self._controls_dock = QDockWidget("RF Controls", self)
        self._controls_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self._controls_dock.setWidget(self._build_controls_widget())
        self._controls_dock.setMinimumWidth(320)
        self._controls_dock.setMaximumWidth(420)
        self._controls_dock.setFloating(False)
        self.addDockWidget(Qt.RightDockWidgetArea, self._controls_dock)

        # Runtime state
        self.scanner_thread = None
        self.transcript_index = TranscriptIndex()
        self.agent_controller = self._build_controller()
        self.agent = RadioOpsAgent(controller=self.agent_controller, transcript_index=self.transcript_index)
        self.audio_output = AudioOutput()
        self._insight_buffer = deque(maxlen=8)
        self._load_settings()

        # Signals
        self.start_button.clicked.connect(self.start_pressed)
        self.stop_button.clicked.connect(self.stop_pressed)
        self.open_bundles_button.clicked.connect(self.open_bundles)
        self.chat_panel.send_message.connect(self.handle_chat)
        self.search_btn.clicked.connect(self._run_search)
        self.search_input.returnPressed.connect(self._run_search)
        self.refresh_log_button.clicked.connect(self._refresh_log_view)
        # Start audio output if available
        if self.audio_output.available:
            self.audio_output.start()
        else:
            self.log_output.append("Audio output backend not available (install sounddevice or pyaudio).")

        # Seed notes with helpful guidance
        self._set_agent_notes(
            "Welcome to AstroTrace.\n\n"
            "Quick start:\n"
            "- Source: synthetic (works without hardware)\n"
            "- Click Start to see live spectrum + waterfall\n\n"
            "Try asking:\n"
            "- “scan 88 108 0.2 FM”\n"
            "- “show recent logs”"
        )
        self._push_ai_insight("Copilot ready. Start on synthetic to see activity immediately.")

        # Load plugins (Beacon, Vision, Anomaly, etc.)
        load_plugins(ui=self, tab_widget=self.plugin_tabs)

        # Auto-start if requested
        if getattr(self, "_auto_start_flag", False):
            self.start_pressed()

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)

    def _build_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_toolbar(self):
        toolbar = QToolBar("Presets", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        label = QLabel("Scan preset:")
        label.setStyleSheet("font-weight: 700; padding-right: 6px;")

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Select…")
        self.preset_combo.model().item(0).setEnabled(False)
        self._presets = {
            "FM Broadcast": (88.0, 108.0, 0.2, "FM"),
            "Airband": (118.0, 137.0, 0.025, "AM"),
            "NOAA WX": (162.4, 162.55, 0.025, "FM"),
            "UHF CB/GMRS": (462.0, 468.0, 0.0125, "FM"),
        }
        for name in self._presets:
            self.preset_combo.addItem(name)
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        toolbar.addWidget(label)
        toolbar.addWidget(self.preset_combo)

    def _labeled(self, text: str, widget: QWidget) -> QWidget:
        """Wrap a widget with a vertical label to save space."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lbl = QLabel(text)
        lay.addWidget(lbl)
        lay.addWidget(widget)
        return box

    def _apply_theme(self):
        """Space-inspired dark theme with warm accent."""
        palette = self.palette()
        # Deep space blues with amber accent from the logo
        palette.setColor(QPalette.Window, QColor("#0a0c14"))
        palette.setColor(QPalette.Base, QColor("#0f131d"))
        palette.setColor(QPalette.AlternateBase, QColor("#141a26"))
        palette.setColor(QPalette.Text, QColor("#f5f7fb"))
        palette.setColor(QPalette.Button, QColor("#f5a524"))       # amber accent
        palette.setColor(QPalette.ButtonText, QColor("#0a0c14"))
        palette.setColor(QPalette.Highlight, QColor("#ffb94f"))
        palette.setColor(QPalette.HighlightedText, QColor("#0a0c14"))
        self.setPalette(palette)
        self.setStyleSheet(
            """
            QWidget { color: #f5f7fb; background-color: #0a0c14; }
            QTextEdit, QLineEdit { background-color: #0f131d; border: 1px solid #1d2230; border-radius: 10px; }
            QComboBox, QSpinBox, QDoubleSpinBox { background-color: #0f131d; border: 1px solid #1d2230; border-radius: 10px; padding: 3px; }
            QPushButton { background-color: #f5a524; border: none; border-radius: 10px; padding: 9px 12px; color: #0a0c14; font-weight: 800; }
            QPushButton:disabled { background-color: #2b303f; color: #a9a9be; }
            QPushButton:hover:!disabled { background-color: #ffc75f; }
            QGroupBox, QLabel { color: #f5f7fb; }
            QTextEdit#insights { border: 1px solid #1d2230; border-radius: 14px; padding: 12px; background-color: #101724; }
            QTextEdit#notes { border: 1px solid #1d2230; border-radius: 14px; padding: 12px; background-color: #101724; }
            QLabel#sectionTitle { color: #ffd489; font-weight: 900; }
            QTabWidget::pane { border: 1px solid #1d2230; border-radius: 14px; }
            QTabBar::tab { background: #0f131d; border: 1px solid #1d2230; padding: 9px 14px; border-top-left-radius: 12px; border-top-right-radius: 12px; margin-right: 4px; }
            QTabBar::tab:selected { background: #141a26; border-bottom-color: #141a26; }
            """
        )

    def _find_brand_assets(self):
        """Locate optional logo/background assets if the user added them."""
        base = Path(__file__).resolve().parent / "assets"
        candidates_logo = [
            base / "astrotrace_logo.png",
            base / "astrotrace_logo.jpg",
            base / "astrotrace_logo_attachment.png",
            base / "astrotrace_logo_attachment.jpg",
        ]
        candidates_bg = [
            base / "astrotrace_bg.jpg",
            base / "astrotrace_bg.png",
            base / "astrotrace_bg_attachment.jpg",
            base / "astrotrace_bg_attachment.png",
            base / "astrotrace_background.jpg",
            base / "astrotrace_background.png",
        ]
        logo = next((p for p in candidates_logo if p.exists()), None)
        bg = next((p for p in candidates_bg if p.exists()), None)
        return logo, bg

    def _apply_background(self, widget: QWidget):
        """Apply a faded background image if available."""
        if self._bg_path:
            widget.setStyleSheet(
                widget.styleSheet()
                + f"""
                QWidget {{
                    background-image: url("{self._bg_path}");
                    background-repeat: no-repeat;
                    background-position: center;
                    background-attachment: fixed;
                    background-color: #0a0c14;
                }}
                """
            )

    def _build_header(self) -> QWidget:
        """Create a compact single-line header."""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background-color: #0f111a; border: 1px solid #1d2230; border-radius: 10px; padding: 6px 10px; }")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(10)

        if self._logo_path and Path(self._logo_path).exists():
            logo_lbl = QLabel()
            pix = QPixmap(str(self._logo_path)).scaledToHeight(42, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
            layout.addWidget(logo_lbl)

        title = QLabel("AstroTrace — Signal Intelligence for SDR + AI Copilot")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)

        layout.addWidget(title)
        layout.addStretch(1)
        self.status_label = QLabel("Ready • Synthetic source available")
        self.status_label.setStyleSheet("color: #ffd400; font-weight: 900;")
        layout.addWidget(self.status_label)
        return frame

    def _build_now_playing(self) -> QWidget:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: rgba(20,26,38,0.85); border: 1px solid #1d2230; border-radius: 12px; padding: 8px; }"
        )
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(12)

        self.now_freq_label = QLabel("Freq: — MHz")
        self.now_freq_label.setStyleSheet("font-weight: 800;")
        self.now_mode_label = QLabel("Mode: —")
        self.now_source_label = QLabel("Source: —")
        self.now_snippet = QLabel("Last transcript: —")
        self.now_snippet.setWordWrap(True)
        layout.addWidget(self.now_freq_label)
        layout.addWidget(self.now_mode_label)
        layout.addWidget(self.now_source_label)
        layout.addStretch(1)
        layout.addWidget(self.now_snippet, stretch=2)
        return card

    def _build_signal_panel(self) -> QWidget:
        """Signal view + dockable controls (Gqrx-style layout)."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Controls are moved into a dock; keep visualization wide.

        # Actions (aligned right to free space)
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)
        actions_row.addStretch(1)
        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.open_bundles_button = QPushButton("Open Bundles")
        actions_row.addWidget(self.start_button)
        actions_row.addWidget(self.stop_button)
        actions_row.addWidget(self.open_bundles_button)
        self.auto_start_cb = QCheckBox("Auto-start on launch")
        actions_row.addWidget(self.auto_start_cb)
        self.hunt_mode_cb = QCheckBox("Hunt mode (fast sweep)")
        actions_row.addWidget(self.hunt_mode_cb)
        layout.addLayout(actions_row)

        # Palette selector for spectrum/waterfall
        palette_row = QHBoxLayout()
        palette_row.setSpacing(8)
        palette_row.addStretch(1)
        palette_row.addWidget(QLabel("Palette"))
        self.palette_combo = QComboBox()
        self.palette_combo.addItems(["inferno", "viridis", "jet"])
        self.palette_combo.currentTextChanged.connect(self._set_palette)
        palette_row.addWidget(self.palette_combo)
        layout.addLayout(palette_row)

        # Live audio meter + device status row
        audio_row = QHBoxLayout()
        audio_row.setSpacing(8)
        self.audio_bar = QProgressBar()
        self.audio_bar.setRange(0, 100)
        self.audio_bar.setTextVisible(False)
        self.audio_bar.setFixedHeight(10)
        self.audio_label = QLabel("Audio: idle")
        audio_row.addWidget(QLabel("Audio level"))
        audio_row.addWidget(self.audio_bar, stretch=1)
        audio_row.addWidget(self.audio_label)
        layout.addLayout(audio_row)

        self.spectrum_widget = SpectrumWidget()
        self.spectrum_widget.setObjectName("spectrum")
        layout.addWidget(self.spectrum_widget, stretch=1)
        self.waterfall_widget = WaterfallWidget()
        self.waterfall_widget.setObjectName("waterfall")
        layout.addWidget(self.waterfall_widget, stretch=2)
        return container

    def _build_controls_widget(self) -> QWidget:
        """Docked controls for RF, scan, and recording."""
        # Use a scroll area to keep the dock height compact; advanced collapsed by default.
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        row1 = QHBoxLayout()
        self.freq_input = QDoubleSpinBox()
        self.freq_input.setRange(0.001, 6000.0)
        self.freq_input.setDecimals(3)
        self.freq_input.setValue(100.000)
        row1.addWidget(self._labeled("Frequency (MHz)", self.freq_input))

        self.mode_select = QComboBox()
        self.mode_select.addItems(["FM", "AM", "SSB", "CW"])
        row1.addWidget(self._labeled("Mode", self.mode_select))

        self.gain_input = QSpinBox()
        self.gain_input.setRange(0, 60)
        self.gain_input.setValue(10)
        row1.addWidget(self._labeled("Gain (dB/index)", self.gain_input))
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.squelch_input = QDoubleSpinBox()
        self.squelch_input.setRange(-120.0, 0.0)
        self.squelch_input.setDecimals(1)
        self.squelch_input.setSingleStep(1.0)
        self.squelch_input.setValue(-60.0)
        row2.addWidget(self._labeled("Squelch (dBFS)", self.squelch_input))

        self.sample_rate_input = QDoubleSpinBox()
        self.sample_rate_input.setRange(0.1, 5000.0)
        self.sample_rate_input.setDecimals(3)
        self.sample_rate_input.setSingleStep(0.1)
        self.sample_rate_input.setValue(2.400)
        row2.addWidget(self._labeled("Sample Rate (MS/s)", self.sample_rate_input))

        self.save_bundles_cb = QCheckBox("Save bundles")
        self.save_bundles_cb.setChecked(True)
        row2.addWidget(self.save_bundles_cb)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.source_select = QComboBox()
        self.source_select.addItems(["synthetic", "rtl", "soapy", "file"])
        row3.addWidget(self._labeled("Source", self.source_select))

        self.transcribe_cb = QCheckBox("Transcribe (Whisper)")
        row3.addWidget(self.transcribe_cb)
        layout.addLayout(row3)

        # Advanced toggle
        adv_btn = QToolButton()
        adv_btn.setText("Advanced ▼")
        adv_btn.setCheckable(True)
        adv_btn.setChecked(False)
        adv_btn.setStyleSheet("font-weight: 700;")
        layout.addWidget(adv_btn)

        adv_panel = QWidget()
        adv_layout = QVBoxLayout(adv_panel)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        adv_layout.setSpacing(6)

        row4 = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("Path to IQ file (for file source)")
        row4.addWidget(self.file_path, stretch=1)
        adv_layout.addLayout(row4)

        scan_row = QHBoxLayout()
        self.scan_checkbox = QCheckBox("Enable Scan Mode")
        scan_row.addWidget(self.scan_checkbox)

        self.start_freq = QDoubleSpinBox()
        self.start_freq.setRange(0.001, 6000.0)
        self.start_freq.setDecimals(3)
        self.start_freq.setValue(100.000)
        scan_row.addWidget(self._labeled("Start (MHz)", self.start_freq))

        self.stop_freq = QDoubleSpinBox()
        self.stop_freq.setRange(0.001, 6000.0)
        self.stop_freq.setDecimals(3)
        self.stop_freq.setValue(101.000)
        scan_row.addWidget(self._labeled("Stop (MHz)", self.stop_freq))
        adv_layout.addLayout(scan_row)

        scan_row2 = QHBoxLayout()
        self.step_freq = QDoubleSpinBox()
        self.step_freq.setRange(0.001, 1000.0)
        self.step_freq.setDecimals(3)
        self.step_freq.setSingleStep(0.01)
        self.step_freq.setValue(0.200)
        scan_row2.addWidget(self._labeled("Step (MHz)", self.step_freq))

        self.dwell_time = QDoubleSpinBox()
        self.dwell_time.setRange(0.0, 10.0)
        self.dwell_time.setDecimals(2)
        self.dwell_time.setSingleStep(0.25)
        self.dwell_time.setValue(0.25)
        scan_row2.addWidget(self._labeled("Dwell (s)", self.dwell_time))

        self.hold_time = QDoubleSpinBox()
        self.hold_time.setRange(0.0, 10.0)
        self.hold_time.setDecimals(2)
        self.hold_time.setSingleStep(0.25)
        self.hold_time.setValue(0.50)
        scan_row2.addWidget(self._labeled("Hold after Tx (s)", self.hold_time))
        adv_layout.addLayout(scan_row2)

        scan_row3 = QHBoxLayout()
        self.min_event_duration = QDoubleSpinBox()
        self.min_event_duration.setRange(0.0, 10.0)
        self.min_event_duration.setDecimals(2)
        self.min_event_duration.setSingleStep(0.25)
        self.min_event_duration.setValue(1.00)
        scan_row3.addWidget(self._labeled("Min event (s)", self.min_event_duration))
        scan_row3.addStretch(1)
        adv_layout.addLayout(scan_row3)

        adv_panel.setVisible(False)
        adv_btn.toggled.connect(adv_panel.setVisible)
        layout.addWidget(adv_panel)

        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(wrapper)
        scroll.setMinimumHeight(220)
        scroll.setMaximumHeight(340)
        return scroll

    def _build_bottom_panel(self) -> QWidget:
        """Bottom panel: event log + AI copilot (tabs)."""
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Event Log (left)
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(4, 0, 4, 0)
        log_layout.setSpacing(6)
        log_title = QLabel("Event Log")
        log_title.setObjectName("sectionTitle")
        log_layout.addWidget(log_title)
        log_controls = QHBoxLayout()
        self.refresh_log_button = QPushButton("Refresh")
        self.log_count_label = QLabel("")
        log_controls.addWidget(self.refresh_log_button)
        log_controls.addStretch(1)
        log_controls.addWidget(self.log_count_label)
        log_layout.addLayout(log_controls)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output)
        splitter.addWidget(log_container)

        # Copilot + plugins (right)
        tabs = QTabWidget()
        tabs.setMinimumWidth(520)
        tabs.setTabBarAutoHide(False)
        tabs.setDocumentMode(True)
        tabs.setElideMode(Qt.ElideNone)
        tabs.setStyleSheet(
            """
            QTabBar::tab { min-width: 110px; padding: 8px 12px; }
            """
        )
        try:
            tabs.tabBar().setUsesScrollButtons(True)
        except Exception:
            pass

        copilot_tab = QWidget()
        copilot_layout = QVBoxLayout(copilot_tab)
        notes_title = QLabel("What to do next")
        notes_title.setObjectName("sectionTitle")
        copilot_layout.addWidget(notes_title)
        self.agent_notes = QTextEdit()
        self.agent_notes.setObjectName("notes")
        self.agent_notes.setReadOnly(True)
        self.agent_notes.setPlaceholderText("Guidance and recommended next steps will appear here.")
        self.agent_notes.setMinimumHeight(130)
        copilot_layout.addWidget(self.agent_notes)
        self.chat_panel = ChatPanel()
        copilot_layout.addWidget(self.chat_panel, stretch=1)
        tabs.addTab(copilot_tab, "Copilot")

        self.multi_tab = MultiChannelTab()
        self.multi_tab.channels_changed.connect(self._channels_changed)
        tabs.addTab(self.multi_tab, "Channels")

        insights_tab = QWidget()
        insights_layout = QVBoxLayout(insights_tab)
        insights_title = QLabel("What AstroTrace noticed")
        insights_title.setObjectName("sectionTitle")
        insights_layout.addWidget(insights_title)
        self.ai_insights = QTextEdit()
        self.ai_insights.setObjectName("insights")
        self.ai_insights.setReadOnly(True)
        self.ai_insights.setPlaceholderText("Discoveries, hints, and summaries will collect here.")
        insights_layout.addWidget(self.ai_insights)
        tabs.addTab(insights_tab, "Insights")

        search_tab = QWidget()
        search_layout = QVBoxLayout(search_tab)
        search_title = QLabel("Search transcripts")
        search_title.setObjectName("sectionTitle")
        search_layout.addWidget(search_title)
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("e.g. 'airport', 'unit 12', 'callsign'…")
        self.search_btn = QPushButton("Search")
        search_row.addWidget(self.search_input, stretch=1)
        search_row.addWidget(self.search_btn)
        search_layout.addLayout(search_row)
        self.search_results = QTextEdit()
        self.search_results.setReadOnly(True)
        self.search_results.setPlaceholderText("Results will appear here.")
        search_layout.addWidget(self.search_results, stretch=1)
        tabs.addTab(search_tab, "Search")

        self.plugin_tabs = tabs

        splitter.addWidget(tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([240, 800])
        return splitter

    def _build_controller(self) -> RadioController:
        return RadioController(
            tune_fn=self._agent_tune,
            scan_fn=self._agent_scan,
            stop_fn=self._agent_stop,
            get_logs_fn=self._agent_get_logs,
            search_fn=self._agent_search,
        )

    def _parse_ui_params(self):
        device = {
            "frequency_mhz": float(self.freq_input.value()),
            "mode": str(self.mode_select.currentText()),
            "gain": int(self.gain_input.value()),
            "squelch_db": float(self.squelch_input.value()),
            "sample_rate_hz": float(self.sample_rate_input.value()) * 1e6,
            "source": str(self.source_select.currentText()),
            "file_path": str(self.file_path.text()).strip(),
            "save_bundles": self.save_bundles_cb.isChecked(),
            "enable_transcription": self.transcribe_cb.isChecked(),
        }
        scan = {
            "scan_mode": self.scan_checkbox.isChecked(),
            "start_mhz": float(self.start_freq.value()),
            "stop_mhz": float(self.stop_freq.value()),
            "step_mhz": float(self.step_freq.value()),
            "dwell_seconds": float(self.dwell_time.value()),
            "hold_seconds": float(self.hold_time.value()),
            "min_event_seconds": float(self.min_event_duration.value()),
            "hunt_mode": bool(self.hunt_mode_cb.isChecked()),
        }
        return device, scan

    def _start_scanner(self, device: dict, scan: dict):
        scan_mode = scan["scan_mode"]
        hunt_mode = bool(scan.get("hunt_mode"))
        # Apply hunt-mode tweaks for faster sweeps
        if hunt_mode and scan_mode:
            scan["dwell_seconds"] = min(scan["dwell_seconds"], 0.15)
            scan["step_mhz"] = max(scan["step_mhz"], 0.35)
        if scan_mode:
            freq_range = (scan["start_mhz"] * 1e6, scan["stop_mhz"] * 1e6, scan["step_mhz"] * 1e6)
        else:
            freq_range = (device["frequency_mhz"] * 1e6, device["frequency_mhz"] * 1e6, 0)

        # Cap UI redraw rate to keep the app responsive (pyqtgraph redraws can be costly).
        ui_max_fps = 24.0 if device["source"] != "synthetic" else 15.0
        self.scanner_thread = ScannerThread(
            freq_range=freq_range,
            mode=device["mode"],
            gain=device["gain"],
            squelch_db=device["squelch_db"],
            scan_mode=scan_mode,
            sample_rate=device["sample_rate_hz"],
            source_type=device["source"],
            source_args={"filename": device["file_path"] or None},
            dwell_seconds=scan["dwell_seconds"],
            hold_seconds=scan["hold_seconds"],
            enable_transcription=bool(device.get("enable_transcription", False)),
            ui_max_fps=ui_max_fps,
            min_event_seconds=scan["min_event_seconds"],
            hunt_mode=hunt_mode,
            transcript_index=self.transcript_index,
            save_bundles=device["save_bundles"],
            multi_channels=device.get("multi_channels") or [],
        )
        self.scanner_thread.signal_update.connect(self.update_spectrum)
        self.scanner_thread.signal_event.connect(self.handle_event)
        self.scanner_thread.finished.connect(self.scanner_finished)
        self.scanner_thread.audio_level.connect(self._update_audio_level)
        self.scanner_thread.device_info.connect(self._update_device_info)
        self.scanner_thread.now_playing.connect(self._update_now_playing_freqmode)
        try:
            self.scanner_thread.audio_frame.connect(self._play_audio)
        except Exception:
            pass
        self.log_output.append(f"**Started {'Scanning' if scan_mode else 'Receiving'}**")
        self.status_label.setText("Connecting to device…")
        self.scanner_thread.start()

    @pyqtSlot()
    def start_pressed(self):
        """Handle Start/Start Scan."""
        if self.scanner_thread and self.scanner_thread.isRunning():
            return
        device, scan = self._parse_ui_params()
        if scan["scan_mode"] and scan["step_mhz"] <= 0:
            self.log_output.append("Step must be > 0 for scan mode.")
            return
        device["multi_channels"] = getattr(self, "_multi_cfg", [])
        self._start_scanner(device, scan)

    @pyqtSlot()
    def stop_pressed(self):
        """Handle Stop."""
        if self.scanner_thread:
            self.scanner_thread.requestInterruption()
            self.status_label.setText("Stopping…")

    @pyqtSlot(object)
    def update_spectrum(self, spectrum_data):
        freq_axis, power = spectrum_data
        self.spectrum_widget.update_spectrum(freq_axis, power)
        try:
            self.waterfall_widget.add_line(np.asarray(power))
        except Exception:
            pass

    @pyqtSlot(object)
    def handle_event(self, event):
        if isinstance(event, dict):
            ts = event.get("time", "")
            freq_hz = event.get("freq", 0.0)
            text = event.get("text", "")
            freq_mhz = freq_hz / 1e6
            log_line = f"{ts} - {freq_mhz:.3f} MHz: {text}"
            self._update_now_playing(freq_mhz, text)
        else:
            log_line = str(event)
            if "SDR init failed" in log_line:
                self.status_label.setText(log_line)
        self.log_output.append(log_line)
        self.chat_panel.append_message("Event", log_line)
        try:
            self._update_log_count(len(EventLogger.recent_events(200)))
        except Exception:
            pass

    @pyqtSlot()
    def scanner_finished(self):
        self.log_output.append("**Stopped scanning/receiving**")
        self.scanner_thread = None
        self.status_label.setText("Stopped")

    @pyqtSlot(str)
    def handle_chat(self, message: str):
        self.chat_panel.append_message("You", message)
        reply = self.agent.handle(message)
        self.chat_panel.append_message("Agent", reply)
        self._set_agent_notes(reply)
        self._push_ai_insight(reply)

    # Agent controller callbacks
    def _agent_tune(self, freq_mhz: float, mode: str | None, gain: int | None, squelch_db: float | None) -> str:
        self.scan_checkbox.setChecked(False)
        self.freq_input.setValue(freq_mhz)
        if mode:
            idx = self.mode_select.findText(mode.upper())
            if idx >= 0:
                self.mode_select.setCurrentIndex(idx)
        if gain is not None:
            self.gain_input.setValue(gain)
        if squelch_db is not None:
            self.squelch_input.setValue(squelch_db)
        self.start_pressed()
        return f"Tuning to {freq_mhz:.3f} MHz."

    def _agent_scan(self, start_mhz: float, stop_mhz: float, step_mhz: float, mode: str | None, gain: int | None, squelch_db: float | None) -> str:
        self.scan_checkbox.setChecked(True)
        self.start_freq.setValue(start_mhz)
        self.stop_freq.setValue(stop_mhz)
        self.step_freq.setValue(step_mhz)
        if mode:
            idx = self.mode_select.findText(mode.upper())
            if idx >= 0:
                self.mode_select.setCurrentIndex(idx)
        if gain is not None:
            self.gain_input.setValue(gain)
        if squelch_db is not None:
            self.squelch_input.setValue(squelch_db)
        self.start_pressed()
        return f"Scanning {start_mhz:.3f}-{stop_mhz:.3f} MHz step {step_mhz:.3f}."

    def _agent_stop(self) -> str:
        self.stop_pressed()
        return "Stopping current operation."

    def _agent_get_logs(self, n: int = 10):
        return EventLogger.recent_events(n)

    def _agent_search(self, query: str, k: int = 5):
        return self.transcript_index.search(query, k=k)

    @pyqtSlot()
    def open_bundles(self):
        """Open the bundles directory in the system file browser."""
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl
        from pathlib import Path

        # Resolve relative to repo root (astrotrace/), not the current working directory.
        bundle_dir = (Path(__file__).resolve().parent.parent / "runs").resolve()
        bundle_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(bundle_dir)))

    def _set_agent_notes(self, text: str):
        """Replace agent notes panel content."""
        self.agent_notes.setPlainText(text.strip())

    def _push_ai_insight(self, text: str):
        """Append a friendly AI insight and refresh the insights panel."""
        clean = text.strip()
        if not clean:
            return
        self._insight_buffer.appendleft(clean)
        self.ai_insights.setPlainText("\n• ".join([""] + list(self._insight_buffer)))

    def _run_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        results = self.transcript_index.search(query, k=8)
        if not results:
            self.search_results.setPlainText("No matches yet. (Try after you’ve captured/transcribed a few events.)")
            return
        lines = []
        for r in results:
            ts = r.get("time", "")
            freq_mhz = (r.get("freq", 0.0) or 0.0) / 1e6
            text = r.get("text", "")
            if ts:
                lines.append(f"{ts} — {freq_mhz:.3f} MHz — {text}")
            else:
                lines.append(f"{freq_mhz:.3f} MHz — {text}")
        self.search_results.setPlainText("\n".join(lines))

    def _refresh_log_view(self):
        events = EventLogger.recent_events(50)
        lines = []
        for e in events:
            ts = e.get("time", "")
            freq_mhz = (e.get("freq", 0.0) or 0.0) / 1e6
            text = e.get("text", "")
            lines.append(f"{ts} - {freq_mhz:.3f} MHz: {text}")
        self.log_output.setPlainText("\n".join(lines))
        self._update_log_count(len(events))

    def _update_log_count(self, count: int):
        self.log_count_label.setText(f"{count} events")

    def _update_audio_level(self, rms: float):
        try:
            db = 20.0 * math.log10(max(rms, 1e-6))
        except Exception:
            db = -80.0
        db = max(-80.0, min(0.0, db))
        pct = int((db + 80.0) / 80.0 * 100.0)
        self.audio_bar.setValue(pct)
        if rms <= 1e-6:
            self.audio_label.setText("Audio: idle")
        else:
            self.audio_label.setText(f"Audio: {db:.1f} dBFS")
        # Audio-reactive glow on spectrum/waterfall frames
        hot = int(180 + (pct / 100.0) * 70)
        color = f"rgba(255, {hot}, 79, 0.65)"
        self.spectrum_widget.setStyleSheet(f"border: 2px solid {color}; border-radius: 8px; background-color: #0f131d;")
        self.waterfall_widget.setStyleSheet(f"border: 2px solid {color}; border-radius: 8px; background-color: #0f131d;")

    @pyqtSlot(object)
    def _play_audio(self, audio_chunk):
        """Send demodulated audio to the output device."""
        try:
            if self.audio_output and self.audio_output.available:
                self.audio_output.push(audio_chunk)
        except Exception:
            pass

    def _update_device_info(self, info: dict):
        if not isinstance(info, dict):
            self.status_label.setText(str(info))
            return
        name = info.get("name") or "Device"
        sr = info.get("sample_rate")
        cf = info.get("center_freq")
        serial = info.get("serial") or info.get("hardware") or ""
        bits = [name]
        if serial:
            bits.append(f"serial {serial}")
        if sr:
            bits.append(f"{float(sr)/1e6:.3f} MS/s")
        if cf:
            bits.append(f"{float(cf)/1e6:.3f} MHz")
        self.status_label.setText(" • ".join(bits))
        self.now_source_label.setText(f"Source: {name}")

    def _apply_preset(self, name: str):
        if not hasattr(self, "scan_checkbox"):
            return
        if not name or name.startswith("Select") or name not in self._presets:
            return
        start, stop, step, mode = self._presets[name]
        self.scan_checkbox.setChecked(True)
        self.start_freq.setValue(start)
        self.stop_freq.setValue(stop)
        self.step_freq.setValue(step)
        idx = self.mode_select.findText(mode.upper())
        if idx >= 0:
            self.mode_select.setCurrentIndex(idx)
        self.preset_combo.setCurrentText(name)

    def _set_palette(self, name: str):
        self.waterfall_widget.set_gradient(name)

    def _channels_changed(self, cfgs: list):
        """Receive channel configs from the Channels tab and stash for scanner."""
        self._multi_cfg = cfgs

    def _load_settings(self):
        try:
            self.scan_checkbox.setChecked(self.settings.value("scan_mode", False, type=bool))
            self.start_freq.setValue(float(self.settings.value("start_mhz", 100.0)))
            self.stop_freq.setValue(float(self.settings.value("stop_mhz", 101.0)))
            self.step_freq.setValue(float(self.settings.value("step_mhz", 0.2)))
            self.min_event_duration.setValue(float(self.settings.value("min_event_s", 1.0)))
            auto_start = bool(self.settings.value("auto_start", False, type=bool))
            self.auto_start_cb.setChecked(auto_start)
            self._auto_start_flag = auto_start
            self.hunt_mode_cb.setChecked(bool(self.settings.value("hunt_mode", False, type=bool)))
        except Exception:
            self._auto_start_flag = False

    def _save_settings(self):
        try:
            self.settings.setValue("scan_mode", self.scan_checkbox.isChecked())
            self.settings.setValue("start_mhz", float(self.start_freq.value()))
            self.settings.setValue("stop_mhz", float(self.stop_freq.value()))
            self.settings.setValue("step_mhz", float(self.step_freq.value()))
            self.settings.setValue("min_event_s", float(self.min_event_duration.value()))
            self.settings.setValue("auto_start", self.auto_start_cb.isChecked())
            self.settings.setValue("hunt_mode", self.hunt_mode_cb.isChecked())
        except Exception:
            pass

    def _show_about(self):
        text = (
            "<b>AstroTrace</b><br>"
            "SDR + AI Copilot for scanning, logging, and optional Whisper/LLM search.<br>"
            "Use synthetic source for demos; switch to RTL/Soapy for hardware.<br>"
            "Bundles save IQ + SigMF; transcripts are searchable."
        )
        if self._logo_path and Path(self._logo_path).exists():
            pix = QPixmap(str(self._logo_path)).scaledToWidth(240, Qt.SmoothTransformation)
            msg = QMessageBox(self)
            msg.setWindowTitle("About AstroTrace")
            msg.setIconPixmap(pix)
            msg.setText(text)
            msg.exec_()
        else:
            QMessageBox.information(self, "About AstroTrace", text)

    def _update_now_playing_freqmode(self, freq_hz: float, mode: str):
        try:
            self.now_freq_label.setText(f"Freq: {freq_hz/1e6:.3f} MHz")
            self.now_mode_label.setText(f"Mode: {mode}")
        except Exception:
            pass

    def _update_now_playing(self, freq_mhz: float, text: str):
        try:
            self.now_freq_label.setText(f"Freq: {freq_mhz:.3f} MHz")
            if text:
                sample = (text[:90] + "…") if len(text) > 90 else text
                self.now_snippet.setText(f"Last transcript: {sample}")
        except Exception:
            pass

