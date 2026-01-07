from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QPushButton


def register(ui, tab_widget):
    """
    Recommendation cards for the Copilot area.
    """
    panel = QWidget()
    layout = QVBoxLayout(panel)
    title = QLabel("Recommendations")
    title.setObjectName("sectionTitle")
    layout.addWidget(title)

    list_widget = QListWidget()
    layout.addWidget(list_widget)

    def refresh():
        list_widget.clear()
        list_widget.addItem("If you see bursts near 100 MHz, widen step to 0.5 MHz.")
        list_widget.addItem("Try dwell 0.5 s for slow sweeps; raise gain +6 dB.")
        list_widget.addItem("Search transcripts for 'SOS' or 'TEST'.")
        list_widget.addItem("Switch Source to rtl when hardware is connected.")

    btn = QPushButton("Refresh suggestions")
    btn.clicked.connect(refresh)
    layout.addWidget(btn)

    refresh()
    tab_widget.addTab(panel, "Recs")

