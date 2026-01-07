from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget
import os
import re


def _fallback_plan(goal: str):
    # Simple heuristic scan plan
    numbers = re.findall(r"(\d+\.?\d*)", goal)
    band = "88-108 MHz" if len(numbers) < 2 else f"{numbers[0]}-{numbers[1]} MHz"
    return [
        f"Band: {band}",
        "Step: 0.2 MHz",
        "Dwell: 0.25 s",
        "Gain: auto",
        "Mode: FM unless narrow",
        "Hold: 0.5 s after activity",
    ]


def _llm_plan(goal: str):
    try:
        from langchain_community.chat_models import ChatOpenAI  # type: ignore
    except Exception:
        return None
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    try:
        llm = ChatOpenAI(temperature=0)
        prompt = (
            "Generate a concise SDR scan plan as bullet lines: band, step, dwell, gain, mode, hold, notes. "
            f"Goal: {goal}"
        )
        text = llm.predict(prompt)
        lines = [ln.strip("- ").strip() for ln in text.splitlines() if ln.strip()]
        return lines or None
    except Exception:
        return None


def register(ui, tab_widget):
    """
    LLM-generated scanning playbooks (with offline fallback).
    """
    panel = QWidget()
    layout = QVBoxLayout(panel)
    title = QLabel("Scan Playbooks (LLM + fallback)")
    title.setObjectName("sectionTitle")
    layout.addWidget(title)

    goal_edit = QLineEdit()
    goal_edit.setPlaceholderText("Describe your goal, e.g. 'listen for repeating tones 88-108 MHz tonight'")
    btn = QPushButton("Generate plan")
    list_widget = QListWidget()

    layout.addWidget(goal_edit)
    layout.addWidget(btn)
    layout.addWidget(list_widget)

    def generate():
        goal = goal_edit.text().strip() or "Look for activity in 88-108 MHz."
        lines = _llm_plan(goal) or _fallback_plan(goal)
        list_widget.clear()
        for ln in lines:
            list_widget.addItem(ln)
        ui.log_output.append("Playbook generated.")

    btn.clicked.connect(generate)
    tab_widget.addTab(panel, "Playbooks")

