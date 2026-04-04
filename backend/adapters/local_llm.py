"""Local LLM adapter using Ollama or OpenAI-compatible endpoints."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
import re
from typing import Any

import httpx

from backend.adapters.consultant_plus import ConsultantPlusAdapter, LegalAnalysisResult


logger = logging.getLogger(__name__)


class LegalPromptBuilder:
    """Build structured Russian legal prompts for local LLM analysis."""

    SYSTEM_PROMPT = """Ты — опытный российский юрист-аналитик.
Твоя задача: анализировать юридические документы и давать
структурированные заключения строго по российскому законодательству.

Правила:
- Ссылайся только на реальные нормы РФ (ГК, ТК, НК, УК, КоАП и др.)
- Указывай конкретные статьи с их номерами
- Если норма неприменима — прямо говори об этом
- Не придумывай несуществующих законов
- Отвечай строго в указанном JSON-формате
- Язык ответа: русский"""

    USER_PROMPT_TEMPLATE = """Проанализируй следующий юридический текст и дай заключение.

ТЕКСТ ДОКУМЕНТА:
{text}

Ответь ТОЛЬКО валидным JSON (без markdown, без пояснений вне JSON):
{{
  "summary": "краткое юридическое резюме документа (2-3 предложения)",
  "legal_area": "отрасль права: трудовое|гражданское|налоговое|уголовное|административное|иное",
  "relevant_laws": [
    {{
      "title": "название нормативного акта",
      "article": "номер статьи",
      "text": "краткое содержание нормы применительно к документу"
    }}
  ],
  "court_practice": [
    {{
      "case": "тип спора или типовое дело",
      "court": "типичная инстанция",
      "outcome": "типичный исход"
    }}
  ],
  "recommendations": "детальные рекомендации для юриста (что проверить, на что обратить внимание)",
  "risks": "юридические риски, выявленные в документе",
  "confidence": 0.85
}}"""

    def build(self, anonymized_text: str) -> tuple[str, str]:
        """Return the system prompt and task prompt."""

        text = anonymized_text[:8000] if len(anonymized_text) > 8000 else anonymized_text
        return self.SYSTEM_PROMPT, self.USER_PROMPT_TEMPLATE.format(text=text)


prompt_builder = LegalPromptBuilder()


@dataclass
class LLMConfig:
    """Connection settings for a local LLM service."""

    base_url: str
    model: str
    timeout: int = 120
    max_tokens: int = 2000
    temperature: float = 0.1


class LocalLLMAdapter(ConsultantPlusAdapter):
    """Adapter for Ollama and OpenAI-compatible local chat APIs."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self._config = config or self._config_from_env()

    @staticmethod
    def _config_from_env() -> LLMConfig:
        return LLMConfig(
            base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434"),
            model=os.getenv("LLM_MODEL", "llama3"),
            timeout=int(os.getenv("LLM_TIMEOUT", "120")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2000")),
        )

    def is_available(self) -> bool:
        return bool(os.getenv("LLM_BASE_URL", "").strip())

    async def _call_ollama(self, config: LLMConfig, system: str, user: str) -> str:
        """Use the native Ollama chat API."""

        base_url = config.base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=config.timeout) as client:
            response = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": config.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": config.temperature,
                        "num_predict": config.max_tokens,
                    },
                },
            )
            response.raise_for_status()
            payload = response.json()
            return str(payload["message"]["content"])

    async def _call_openai_compat(self, config: LLMConfig, system: str, user: str) -> str:
        """Use an OpenAI-compatible local API."""

        base_url = config.base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=config.timeout) as client:
            response = await client.post(
                f"{base_url}/v1/chat/completions",
                json={
                    "model": config.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                },
                headers={"Authorization": "Bearer local"},
            )
            response.raise_for_status()
            payload = response.json()
            return str(payload["choices"][0]["message"]["content"])

    async def _call_llm(self, system: str, user: str) -> str:
        """Try Ollama first, then OpenAI-compatible fallback."""

        errors: list[str] = []
        config = self._config

        for caller in (self._call_ollama, self._call_openai_compat):
            try:
                return await caller(config, system, user)
            except Exception as exc:  # pragma: no cover - network-dependent
                errors.append(str(exc))

        raise RuntimeError(
            f"Локальная LLM недоступна по адресу {config.base_url}.\n"
            f"Проверьте, что Ollama/LM Studio запущена.\n"
            f"Ошибки: {'; '.join(errors)}"
        )

    @staticmethod
    def _parse_llm_response(raw: str) -> dict[str, Any]:
        """Extract JSON from raw LLM output, including fenced markdown."""

        cleaned = re.sub(r"```(?:json)?", "", raw).strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError(f"LLM вернул невалидный JSON: {raw[:200]}")
        try:
            parsed = json.loads(match.group())
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON parse error: {exc}\nRaw: {raw[:300]}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("LLM response JSON must be an object")
        return parsed

    async def analyze(self, anonymized_text: str, api_key: str) -> LegalAnalysisResult:
        """Run legal analysis through a local LLM endpoint."""

        _ = api_key
        system_prompt, user_prompt = prompt_builder.build(anonymized_text)
        raw = await self._call_llm(system_prompt, user_prompt)

        try:
            data = self._parse_llm_response(raw)
        except ValueError as exc:
            logger.error("LLM response parse failed: %s", exc)
            return LegalAnalysisResult(
                summary="LLM вернула нечитаемый ответ. Повторите запрос.",
                relevant_laws=[],
                court_practice=[],
                recommendations=raw[:500],
                source=f"Локальная LLM · {self._config.model} [ошибка парсинга]",
                raw_response={"raw": raw},
            )

        risks = str(data.get("risks") or "").strip()
        recommendations = str(data.get("recommendations") or "")
        if risks:
            recommendations = f"{recommendations}\n\nРИСКИ: {risks}" if recommendations else f"РИСКИ: {risks}"

        return LegalAnalysisResult(
            summary=str(data.get("summary") or ""),
            relevant_laws=list(data.get("relevant_laws") or []),
            court_practice=list(data.get("court_practice") or []),
            recommendations=recommendations,
            source=f"Локальная LLM · {self._config.model}",
            raw_response=data,
        )
