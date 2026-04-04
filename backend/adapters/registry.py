"""Adapter registry for KP, local LLM, and demo analysis modes."""

from __future__ import annotations

from enum import Enum
import os
from typing import Any

from backend.adapters.consultant_plus import ConsultantPlusAdapter, HttpAdapter, StubAdapter
from backend.adapters.local_llm import LocalLLMAdapter


class AnalysisMode(str, Enum):
    """Supported analysis modes exposed to the frontend."""

    AUTO = "auto"
    KP = "kp"
    LLM = "llm"
    DEMO = "demo"


class AdapterRegistry:
    """Select the correct analysis backend based on user mode."""

    def __init__(self) -> None:
        self._kp = HttpAdapter()
        self._llm = LocalLLMAdapter()
        self._stub = StubAdapter()

    def get(self, mode: AnalysisMode) -> ConsultantPlusAdapter:
        """Return the adapter matching the requested mode."""

        if mode == AnalysisMode.DEMO:
            return self._stub
        if mode == AnalysisMode.KP:
            if not self._kp.is_available():
                raise ValueError("Режим КП выбран, но KP_API_KEY не задан или равен DEMO_KEY.")
            return self._kp
        if mode == AnalysisMode.LLM:
            if not self._llm.is_available():
                raise ValueError("Режим LLM выбран, но LLM_BASE_URL не задан в окружении.")
            return self._llm
        if self._kp.is_available():
            return self._kp
        if self._llm.is_available():
            return self._llm
        return self._stub

    def status(self) -> dict[str, Any]:
        """Return adapter availability details for the health endpoint."""

        llm_url = os.getenv("LLM_BASE_URL", "").strip()
        llm_model = os.getenv("LLM_MODEL", "").strip()
        return {
            "kp_available": self._kp.is_available(),
            "llm_available": self._llm.is_available(),
            "kp_mode": "live" if self._kp.is_available() else "unavailable",
            "llm_url": llm_url,
            "llm_model": llm_model,
            "default_mode": os.getenv("ANALYSIS_MODE", AnalysisMode.AUTO.value).strip().lower() or AnalysisMode.AUTO.value,
        }


registry = AdapterRegistry()
