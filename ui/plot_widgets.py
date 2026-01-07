from __future__ import annotations

"""Reusable plotting widgets for the AstroTrace UI.

This module provides SpectrumWidget for real-time power spectrum display and
WaterfallWidget for a rolling waterfall view.
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg
import numpy as np


class SpectrumWidget(pg.PlotWidget):
    """Spectrum display with optional filled gradient and peak-hold."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.setYRange(-110, 0)  # dBFS
        self.setLabel("bottom", "Frequency", "MHz")
        self.setLabel("left", "Signal Strength", "dB")
        self.showGrid(x=True, y=True, alpha=0.2)
        self._fill_item = None
        self._peak_curve = None
        self._last_freq = None
        self._peak = None
        self.setMenuEnabled(False)
        self.setMouseEnabled(x=False, y=False)
        self.hideButtons()
        self.setClipToView(True)
        self.getPlotItem().setContentsMargins(4, 4, 4, 4)

    def update_spectrum(self, freq_axis, power):
        """Update the spectrum display with new data."""
        freq_axis = np.asarray(freq_axis, dtype=np.float32)
        power = np.asarray(power, dtype=np.float32)
        if self._last_freq is None or len(freq_axis) != len(self._last_freq):
            self._peak = power.copy()
        else:
            self._peak = np.maximum(self._peak, power)
        self._last_freq = freq_axis

        plt = self.getPlotItem()
        plt.clear()

        # Filled gradient under trace
        fill = pg.FillBetweenItem(
            pg.PlotCurveItem(freq_axis, power, pen=pg.mkPen((255, 191, 71, 220), width=1.2)),
            pg.PlotCurveItem(freq_axis, np.full_like(power, -110), pen=None),
            brush=pg.mkBrush(255, 191, 71, 60),
        )
        plt.addItem(fill)

        # Peak hold (thin line)
        peak_curve = pg.PlotCurveItem(freq_axis, self._peak, pen=pg.mkPen((255, 120, 40, 180), width=1))
        plt.addItem(peak_curve)

        # Live trace
        live_curve = pg.PlotCurveItem(freq_axis, power, pen=pg.mkPen((255, 235, 200, 255), width=1.5))
        plt.addItem(live_curve)


class WaterfallWidget(QWidget):
    """A rolling waterfall display with richer palettes and better initial fill."""

    def __init__(self, history: int = 200, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.history = history
        self.image_view = pg.ImageView(view=pg.PlotItem())
        self._gradient = "plasma"  # vibrant, perceptually uniform
        self.image_view.setPredefinedGradient(self._gradient)
        self.image_view.getView().setAspectLocked(False)
        layout = QVBoxLayout(self)
        layout.addWidget(self.image_view)
        self._buffer = None  # type: np.ndarray | None
        self._lines_seen = 0

    def add_line(self, power: np.ndarray):
        """Append one spectrum line into the waterfall."""
        power = np.asarray(power, dtype=np.float32)
        # Seed buffer with NaNs so the view is full height immediately.
        if self._buffer is None:
            self._buffer = np.full((self.history, power.size), np.nan, dtype=np.float32)
        self._buffer = np.vstack((self._buffer[1:], power[None, :]))
        self._lines_seen += 1

        # Auto-level only for initial frames to avoid a flat-color band.
        auto_levels = self._lines_seen <= 5
        self.image_view.setImage(self._buffer, autoLevels=auto_levels, autoRange=False)

    def set_gradient(self, name: str):
        """Change waterfall color map (e.g., 'inferno', 'viridis', 'jet', 'plasma')."""
        self._gradient = name
        try:
            self.image_view.setPredefinedGradient(name)
        except Exception:
            pass
