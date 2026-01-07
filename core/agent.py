"""LangChain-powered assistant for radio control and summarization."""

from __future__ import annotations

from typing import Callable, List, Optional, Dict, Any

from .vector_store import TranscriptIndex


class RadioController:
    """Thin abstraction the agent uses to trigger UI actions safely."""

    def __init__(
        self,
        tune_fn: Callable[[float, Optional[str], Optional[int], Optional[float]], str],
        scan_fn: Callable[[float, float, float, Optional[str], Optional[int], Optional[float]], str],
        stop_fn: Callable[[], str],
        get_logs_fn: Callable[[int], List[Dict[str, Any]]],
        search_fn: Callable[[str, int], List[Dict[str, Any]]],
    ) -> None:
        self.tune_fn = tune_fn
        self.scan_fn = scan_fn
        self.stop_fn = stop_fn
        self.get_logs_fn = get_logs_fn
        self.search_fn = search_fn

    def tune(self, freq_mhz: float, mode: Optional[str] = None, gain: Optional[int] = None, squelch_db: Optional[float] = None) -> str:
        return self.tune_fn(freq_mhz, mode, gain, squelch_db)

    def start_scan(self, start_mhz: float, stop_mhz: float, step_mhz: float, mode: Optional[str] = None, gain: Optional[int] = None, squelch_db: Optional[float] = None) -> str:
        return self.scan_fn(start_mhz, stop_mhz, step_mhz, mode, gain, squelch_db)

    def stop(self) -> str:
        return self.stop_fn()

    def get_logs(self, n: int = 10) -> List[Dict[str, Any]]:
        return self.get_logs_fn(n)

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        return self.search_fn(query, k)


class RadioOpsAgent:
    """LangChain agent wrapper with graceful fallback when LLM is unavailable."""

    def __init__(self, controller: RadioController, transcript_index: TranscriptIndex) -> None:
        self.controller = controller
        self.transcript_index = transcript_index
        self._agent = None
        self._llm_available = False
        self._build_agent()

    def _build_agent(self):
        try:
            from langchain_community.chat_models import ChatOpenAI  # type: ignore
            from langchain.agents import Tool, initialize_agent, AgentType  # type: ignore
            from langchain.memory import ConversationBufferMemory  # type: ignore

            tools = [
                Tool(
                    name="tune_frequency",
                    func=self._tool_tune,
                    description="Tune to a single frequency. Input: '<freq_mhz> [mode] [gain] [squelch_db]'.",
                ),
                Tool(
                    name="start_scan",
                    func=self._tool_scan,
                    description="Start scanning. Input: 'start_mhz stop_mhz step_mhz [mode] [gain] [squelch_db]'.",
                ),
                Tool(
                    name="stop_radio",
                    func=lambda _: self.controller.stop(),
                    description="Stop current receiving/scanning.",
                ),
                Tool(
                    name="recent_logs",
                    func=self._tool_logs,
                    description="Get recent events/logs. Input: optional integer count.",
                ),
                Tool(
                    name="search_transcripts",
                    func=self._tool_search,
                    description="Search transcripts. Input: query string.",
                ),
            ]

            llm = ChatOpenAI(temperature=0)
            memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
            self._agent = initialize_agent(
                tools=tools,
                llm=llm,
                agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
                verbose=False,
                memory=memory,
            )
            self._llm_available = True
        except Exception:
            self._agent = None
            self._llm_available = False

    def _tool_tune(self, text: str) -> str:
        parts = text.strip().split()
        if not parts:
            return "No frequency provided."
        try:
            freq = float(parts[0])
        except ValueError:
            return "Invalid frequency."
        mode = parts[1] if len(parts) > 1 else None
        gain = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
        squelch = float(parts[3]) if len(parts) > 3 else None
        return self.controller.tune(freq, mode, gain, squelch)

    def _tool_scan(self, text: str) -> str:
        parts = text.strip().split()
        if len(parts) < 3:
            return "Provide start stop step (MHz)."
        try:
            start, stop, step = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            return "Invalid scan values."
        mode = parts[3] if len(parts) > 3 else None
        gain = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else None
        squelch = float(parts[5]) if len(parts) > 5 else None
        return self.controller.start_scan(start, stop, step, mode, gain, squelch)

    def _tool_logs(self, text: str) -> str:
        try:
            n = int(text.strip()) if text.strip() else 10
        except ValueError:
            n = 10
        events = self.controller.get_logs(n)
        if not events:
            return "No recent logs."
        lines = [f"{e.get('time')} {e.get('freq',0)/1e6:.3f} MHz: {e.get('text','')}" for e in events]
        return "\n".join(lines)

    def _tool_search(self, text: str) -> str:
        results = self.controller.search(text.strip(), k=5)
        if not results:
            return "No matches."
        lines = [f"{r.get('time','')} {r.get('freq',0)/1e6:.3f} MHz: {r.get('text','')}" for r in results]
        return "\n".join(lines)

    def handle(self, message: str) -> str:
        """Process a user message and return agent reply."""
        if self._llm_available and self._agent:
            try:
                return self._agent.run(message)
            except Exception as exc:
                return f"Agent error: {exc}"
        # Fallback heuristic commands
        msg = message.lower()
        if "scan" in msg:
            return "Agent not configured with LLM. Please start scan via UI."
        if "tune" in msg or "set" in msg:
            return "Agent not configured with LLM. Please tune via UI."
        if "log" in msg:
            events = self.controller.get_logs(5)
            return "\n".join([f"{e.get('time')} {e.get('freq',0)/1e6:.3f} MHz: {e.get('text','')}" for e in events])
        return "Agent offline (no LLM configured)."
