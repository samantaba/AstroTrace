from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton, QHBoxLayout
from PyQt5.QtCore import QTimer


def register(ui, tab_widget):
    """
    Beacon Lab plugin (simulated).
    - Periodically "transmits" a frame.
    - Can simulate a reply and push to Copilot/Insights.
    """
    panel = QWidget()
    layout = QVBoxLayout(panel)
    title = QLabel("Beacon Lab (simulated)")
    title.setObjectName("sectionTitle")
    layout.addWidget(title)

    msg_edit = QLineEdit()
    msg_edit.setPlaceholderText("Message to send (simulated)")
    hop_edit = QLineEdit()
    hop_edit.setPlaceholderText("Hop plan, e.g. 100-101 MHz random")
    status = QTextEdit()
    status.setReadOnly(True)

    btn_row = QHBoxLayout()
    btn_start = QPushButton("Start Beacon")
    btn_stop = QPushButton("Stop")
    btn_reply = QPushButton("Simulate Reply")
    btn_row.addWidget(btn_start)
    btn_row.addWidget(btn_stop)
    btn_row.addWidget(btn_reply)

    layout.addWidget(msg_edit)
    layout.addWidget(hop_edit)
    layout.addLayout(btn_row)
    layout.addWidget(status)

    timer = QTimer(panel)

    def tick():
        status.append("Beacon frame sent (simulated).")
        ui.log_output.append("Beacon: simulated frame sent.")

    def start():
        msg = msg_edit.text().strip() or "Hello from AstroTrace"
        hop = hop_edit.text().strip() or "100.000-101.000 MHz random"
        status.append(f"Started beacon: '{msg}' on plan {hop}")
        timer.start(2000)

    def stop():
        timer.stop()
        status.append("Beacon stopped.")

    def reply():
        reply_text = "Simulated reply detected. Copilot would craft a response."
        status.append(reply_text)
        ui.log_output.append(reply_text)
        ui._push_ai_insight("Simulated reply received; suggest switching to RX focus.")

    timer.timeout.connect(tick)
    btn_start.clicked.connect(start)
    btn_stop.clicked.connect(stop)
    btn_reply.clicked.connect(reply)

    tab_widget.addTab(panel, "Beacon")

