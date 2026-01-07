from __future__ import annotations

from typing import List
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PyQt5.QtCore import pyqtSignal, Qt

from ui.plot_widgets import SpectrumWidget


class MultiChannelTab(QWidget):
    """
    UI for multi-channel demod management:
    - Spectrum view (reuses main spectrum)
    - Channel table to add/remove channels (freq/mode/squelch)
    Emits `channels_changed` with a list of dicts.
    """

    channels_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # Controls row
        controls = QHBoxLayout()
        self.freq_input = QDoubleSpinBox()
        self.freq_input.setRange(0.001, 6000.0)
        self.freq_input.setDecimals(3)
        self.freq_input.setValue(100.000)
        self.mode_select = QComboBox()
        self.mode_select.addItems(["FM", "AM", "SSB", "CW"])
        self.squelch_input = QDoubleSpinBox()
        self.squelch_input.setRange(-120.0, 0.0)
        self.squelch_input.setDecimals(1)
        self.squelch_input.setSingleStep(1.0)
        self.squelch_input.setValue(-60.0)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Name/label (optional)")
        add_btn = QPushButton("Add channel")
        add_btn.clicked.connect(self._add_channel)
        controls.addWidget(QLabel("Freq (MHz)"))
        controls.addWidget(self.freq_input)
        controls.addWidget(QLabel("Mode"))
        controls.addWidget(self.mode_select)
        controls.addWidget(QLabel("Squelch (dBFS)"))
        controls.addWidget(self.squelch_input)
        controls.addWidget(self.name_input, stretch=1)
        controls.addWidget(add_btn)
        layout.addLayout(controls)

        # Channel table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Freq MHz", "Mode", "Squelch dBFS", "Name"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setSelectionMode(self.table.SingleSelection)
        layout.addWidget(self.table, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()
        self.remove_btn = QPushButton("Remove selected")
        self.remove_btn.clicked.connect(self._remove_selected)
        self.apply_btn = QPushButton("Apply to scanner")
        self.apply_btn.clicked.connect(self._emit_channels)
        btn_row.addStretch(1)
        btn_row.addWidget(self.remove_btn)
        btn_row.addWidget(self.apply_btn)
        layout.addLayout(btn_row)
        self._update_buttons()

    def _add_channel(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(f"{self.freq_input.value():.3f}"))
        self.table.setItem(row, 1, QTableWidgetItem(self.mode_select.currentText()))
        self.table.setItem(row, 2, QTableWidgetItem(f"{self.squelch_input.value():.1f}"))
        self.table.setItem(row, 3, QTableWidgetItem(self.name_input.text().strip()))
        self._emit_channels()

    def _remove_selected(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)
        self._emit_channels()

    def _emit_channels(self):
        cfgs: List[dict] = []
        for r in range(self.table.rowCount()):
            try:
                freq = float(self.table.item(r, 0).text())
                mode = self.table.item(r, 1).text().strip()
                squelch = float(self.table.item(r, 2).text())
                name = self.table.item(r, 3).text().strip()
                cfgs.append(
                    {
                        "freq_hz": freq * 1e6,
                        "mode": mode,
                        "squelch_db": squelch,
                        "enabled": True,
                        "name": name,
                    }
                )
            except Exception:
                continue
        self.channels_changed.emit(cfgs)
        self._update_buttons()

    def _update_buttons(self):
        has_rows = self.table.rowCount() > 0
        self.remove_btn.setEnabled(has_rows)
        self.apply_btn.setEnabled(has_rows)

