"""Chat panel for interacting with the LangChain agent."""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLineEdit, QPushButton, QHBoxLayout
from PyQt5.QtCore import pyqtSignal


class ChatPanel(QWidget):
    """Simple chat UI: history pane + input box."""

    send_message = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.history = QTextEdit()
        self.history.setReadOnly(True)
        layout.addWidget(self.history)

        input_layout = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask the agent to tune, scan, summarize…")
        self.send_btn = QPushButton("Send")
        input_layout.addWidget(self.input)
        input_layout.addWidget(self.send_btn)
        layout.addLayout(input_layout)

        self.send_btn.clicked.connect(self._emit_message)
        self.input.returnPressed.connect(self._emit_message)

    def _emit_message(self):
        text = self.input.text().strip()
        if text:
            self.send_message.emit(text)
            self.input.clear()

    def append_message(self, sender: str, text: str):
        """Append a message to the history."""
        self.history.append(f"<b>{sender}:</b> {text}")

