from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QGridLayout, QCheckBox
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap, QColor
import random


def register(ui, tab_widget):
    """
    Vision Sentinel plugin (simulated thumbnails).
    - Auto or manual capture fills a 3x3 grid with colored placeholders.
    """
    panel = QWidget()
    layout = QVBoxLayout(panel)
    title = QLabel("Vision Sentinel (simulated)")
    title.setObjectName("sectionTitle")
    layout.addWidget(title)

    auto_cb = QCheckBox("Auto-capture on events")
    btn_capture = QPushButton("Capture burst")
    row = QVBoxLayout()
    row.addWidget(auto_cb)
    row.addWidget(btn_capture)
    layout.addLayout(row)

    grid_host = QWidget()
    grid = QGridLayout(grid_host)
    grid.setSpacing(6)
    layout.addWidget(grid_host)

    def do_capture():
        for idx in range(6):
            pix = QPixmap(96, 64)
            color = QColor.fromHsv(random.randint(0, 359), 200, 230)
            pix.fill(color)
            label = QLabel()
            label.setPixmap(pix)
            r, c = divmod(idx, 3)
            existing = grid.itemAtPosition(r, c)
            if existing:
                old = existing.widget()
                if old:
                    old.deleteLater()
            grid.addWidget(label, r, c)
        ui.log_output.append("Vision: captured burst (simulated).")

    btn_capture.clicked.connect(do_capture)

    # Optional auto-capture timer
    timer = QTimer(panel)

    def auto_tick():
        if auto_cb.isChecked():
            do_capture()

    timer.timeout.connect(auto_tick)
    timer.start(5000)

    tab_widget.addTab(panel, "Vision")

