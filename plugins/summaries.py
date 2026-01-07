from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit
import os

try:
    from langchain_community.chat_models import ChatOpenAI  # type: ignore
except Exception:
    ChatOpenAI = None

from core.logger import EventLogger


def _fallback_summary(events):
    if not events:
        return "No recent events."
    lines = []
    lines.append(f"{len(events)} events in the recent window.")
    freqs = [e.get("freq", 0.0) / 1e6 for e in events if "freq" in e]
    if freqs:
        freqs = sorted(freqs)
        lines.append(f"Freq span: {freqs[0]:.3f}–{freqs[-1]:.3f} MHz")
    texts = [e.get("text", "") for e in events if e.get("text")]
    if texts:
        sample = texts[-1][:120]
        lines.append(f"Last text: {sample}")
    return "\n".join(lines)


def _llm_summary(events):
    if not ChatOpenAI:
        return None
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    try:
        llm = ChatOpenAI(temperature=0)
        bullets = []
        for e in events:
            bullets.append(f"{e.get('time','')}: {e.get('freq',0)/1e6:.3f} MHz: {e.get('text','')}")
        prompt = "Summarize these SDR events into brief takeaways and next steps:\n" + "\n".join(bullets)
        return llm.predict(prompt)
    except Exception:
        return None


def register(ui, tab_widget):
    """
    Summarize recent events (LLM if available, else heuristic).
    """
    panel = QWidget()
    layout = QVBoxLayout(panel)
    title = QLabel("Summaries")
    title.setObjectName("sectionTitle")
    layout.addWidget(title)

    btn = QPushButton("Summarize recent events")
    output = QTextEdit()
    output.setReadOnly(True)

    layout.addWidget(btn)
    layout.addWidget(output)

    def run_summary():
        events = EventLogger.recent_events(30)
        text = _llm_summary(events) or _fallback_summary(events)
        output.setPlainText(text)
        ui.log_output.append("Summary refreshed.")

    btn.clicked.connect(run_summary)
    tab_widget.addTab(panel, "Summaries")

