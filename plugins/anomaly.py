from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QPushButton, QListWidgetItem
import random


def register(ui, tab_widget):
    """
    Anomaly Radar plugin (simulated).
    - Generates random anomaly bins.
    """
    panel = QWidget()
    layout = QVBoxLayout(panel)
    title = QLabel("Anomaly Radar (simulated)")
    title.setObjectName("sectionTitle")
    layout.addWidget(title)

    list_widget = QListWidget()
    btn_sim = QPushButton("Simulate anomalies")
    layout.addWidget(list_widget)
    layout.addWidget(btn_sim)

    def add_entry(freq_mhz: float, score: float):
        item = QListWidgetItem(f"{freq_mhz:.3f} MHz  •  anomaly score {score:.2f}")
        list_widget.addItem(item)

    def maybe_clear():
        if list_widget.count() > 20:
            list_widget.clear()

    def simulate():
        maybe_clear()
        for _ in range(3):
            freq = random.uniform(88.0, 108.0)
            score = random.uniform(0.6, 0.99)
            add_entry(freq, score)
        ui.log_output.append("Anomaly radar: added simulated anomalies.")

    btn_sim.clicked.connect(simulate)
    tab_widget.addTab(panel, "Anomaly")

