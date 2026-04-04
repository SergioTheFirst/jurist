"""ConsultantPlus adapters: demo stub and configurable HTTP integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import logging
import os
from typing import Any

import httpx

from backend.runtime_paths import kp_pattern_cache_path

logger = logging.getLogger(__name__)


@dataclass
class LegalAnalysisResult:
    """Normalized legal analysis payload used by the application."""

    summary: str
    relevant_laws: list[dict[str, Any]]
    court_practice: list[dict[str, Any]]
    recommendations: str
    source: str = "КонсультантПлюс"
    raw_response: dict[str, Any] | None = None


class ConsultantPlusAdapter(ABC):
    """Common interface for all legal analysis backends."""

    @abstractmethod
    async def analyze(self, anonymized_text: str, api_key: str) -> LegalAnalysisResult:
        """Analyze anonymized legal text and return a normalized result."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the adapter is configured for use."""


class StubAdapter(ConsultantPlusAdapter):
    """Deterministic demo adapter used when no external backend is available."""

    def is_available(self) -> bool:
        return True

    async def analyze(self, anonymized_text: str, api_key: str) -> LegalAnalysisResult:
        _ = api_key
        logger.info("StubAdapter: using demo legal analysis")

        topic = self._detect_topic(anonymized_text.lower())
        return LegalAnalysisResult(
            summary=self._get_summary(topic),
            relevant_laws=self._get_laws(topic),
            court_practice=self._get_practice(topic),
            recommendations=self._get_recommendations(topic),
            source="КонсультантПлюс [ДЕМО]",
            raw_response={"topic": topic},
        )

    @staticmethod
    def _detect_topic(text: str) -> str:
        if any(word in text for word in ["труд", "увольнен", "работник", "зарплат"]):
            return "labor"
        if any(word in text for word in ["договор", "сделк", "поставк", "аренд"]):
            return "civil"
        if any(word in text for word in ["налог", "ндс", "прибыл", "ифнс"]):
            return "tax"
        return "general"

    @staticmethod
    def _get_summary(topic: str) -> str:
        summaries = {
            "labor": "Документ содержит признаки трудового спора. Проверьте основания увольнения и соблюдение процедур ТК РФ.",
            "civil": "Документ относится к гражданско-правовым отношениям. Проверьте предмет договора, сроки и порядок ответственности сторон.",
            "tax": "Документ затрагивает налоговые правоотношения. Требуется сверка с актуальной редакцией НК РФ и фактами хозяйственной операции.",
            "general": "Система работает в демо-режиме. Для реального анализа подключите КонсультантПлюс или локальную LLM.",
        }
        return summaries.get(topic, summaries["general"])

    @staticmethod
    def _get_laws(topic: str) -> list[dict[str, str]]:
        mapping = {
            "labor": [
                {"title": "Трудовой кодекс РФ", "article": "ст. 81", "text": "Основания расторжения трудового договора по инициативе работодателя."},
                {"title": "Трудовой кодекс РФ", "article": "ст. 140", "text": "Сроки расчета с работником при увольнении."},
            ],
            "civil": [
                {"title": "Гражданский кодекс РФ", "article": "ст. 450", "text": "Основания изменения и расторжения договора."},
                {"title": "Гражданский кодекс РФ", "article": "ст. 393", "text": "Возмещение убытков при неисполнении обязательства."},
            ],
            "tax": [
                {"title": "Налоговый кодекс РФ", "article": "ст. 75", "text": "Пени за несвоевременную уплату налога."},
                {"title": "Налоговый кодекс РФ", "article": "гл. 25", "text": "Налог на прибыль организаций."},
            ],
            "general": [
                {"title": "Демо-режим", "article": "—", "text": "Подключите реальный источник анализа для актуальных норм и практики."},
            ],
        }
        return mapping.get(topic, mapping["general"])

    @staticmethod
    def _get_practice(topic: str) -> list[dict[str, str]]:
        if topic == "labor":
            return [{"case": "Спор об увольнении", "court": "Суд общей юрисдикции", "outcome": "Проверяется соблюдение процедуры и доказанность основания увольнения."}]
        if topic == "civil":
            return [{"case": "Спор о расторжении договора", "court": "Арбитражный суд", "outcome": "Исследуется существенность нарушения условий договора."}]
        if topic == "tax":
            return [{"case": "Налоговый спор", "court": "Арбитражный суд", "outcome": "Оцениваются документы, реальность операции и добросовестность налогоплательщика."}]
        return [{"case": "Данные недоступны", "court": "—", "outcome": "В демо-режиме судебная практика ограничена шаблонным ответом."}]

    @staticmethod
    def _get_recommendations(topic: str) -> str:
        specific = {
            "labor": "1. Проверьте процедуру увольнения.\n2. Сверьте сроки расчета.\n3. Соберите доказательства дисциплинарного проступка либо основания спора.",
            "civil": "1. Проверьте существенные условия договора.\n2. Оцените основания расторжения или взыскания убытков.\n3. Сопоставьте фактические обстоятельства с условиями сделки.",
            "tax": "1. Сверьте спорную операцию с подтверждающими документами.\n2. Проверьте применимую редакцию НК РФ.\n3. Подготовьте позицию по реальности операции и налоговой выгоде.",
            "general": "Подключите реальный КП API или локальную LLM для production-анализа.",
        }
        return specific.get(topic, specific["general"])


class HttpAdapter(ConsultantPlusAdapter):
    """Configurable ConsultantPlus HTTP adapter with pattern detection."""

    PATTERNS: list[dict[str, Any]] = [
        {
            "name": "КП:Технология",
            "base": "https://api.consultant.ru",
            "auth_header": "X-Api-Key",
            "search_path": "/search",
            "search_param": "query",
        },
        {
            "name": "КП:SaaS",
            "base": "https://www.consultant.ru/api",
            "auth_header": "Authorization",
            "auth_prefix": "Bearer ",
            "analyze_path": "/analyze",
        },
    ]

    def __init__(self) -> None:
        self._working_pattern: dict[str, Any] | None = None
        self._pattern_cache_path = kp_pattern_cache_path()

    def is_available(self) -> bool:
        key = os.getenv("KP_API_KEY", "")
        return bool(key) and key != "DEMO_KEY" and len(key) > 10

    async def _detect_pattern(self, api_key: str) -> dict[str, Any]:
        """Try to identify the KP API variant and cache a successful match."""

        if self._working_pattern:
            return self._working_pattern

        cached = self._read_cached_pattern()
        if cached is not None:
            self._working_pattern = cached
            return cached

        for pattern in self.PATTERNS:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"{pattern['base']}/ping",
                        headers=self._build_headers(pattern, api_key),
                    )
                if response.status_code in (200, 404):
                    self._cache_pattern(pattern)
                    logger.info("Detected ConsultantPlus API pattern: %s", pattern["name"])
                    return pattern
            except Exception as exc:  # pragma: no cover - network-dependent
                logger.debug("Pattern probe failed for %s: %s", pattern["name"], exc)

        raise RuntimeError(
            "Не удалось определить тип API КонсультантПлюс.\n"
            "Проверьте ключ и сетевой доступ к consultant.ru.\n"
            "Убедитесь, что ключ относится к КП:Технология или web.consultant.ru."
        )

    def _read_cached_pattern(self) -> dict[str, Any] | None:
        try:
            if not self._pattern_cache_path.exists():
                return None
            cached = json.loads(self._pattern_cache_path.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and cached.get("name"):
                return cached
        except Exception as exc:  # pragma: no cover - best-effort cache read
            logger.debug("Unable to read cached KP pattern: %s", exc)
        return None

    def _cache_pattern(self, pattern: dict[str, Any]) -> None:
        self._working_pattern = pattern
        try:
            self._pattern_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._pattern_cache_path.write_text(json.dumps(pattern, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:  # pragma: no cover - best-effort cache write
            logger.debug("Unable to write KP pattern cache: %s", exc)

    @staticmethod
    def _build_headers(pattern: dict[str, Any], api_key: str) -> dict[str, str]:
        prefix = pattern.get("auth_prefix", "")
        return {
            pattern["auth_header"]: f"{prefix}{api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _search_laws(
        self,
        client: httpx.AsyncClient,
        pattern: dict[str, Any],
        api_key: str,
        query: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Search for relevant laws and return both normalized and raw payload."""

        headers = self._build_headers(pattern, api_key)
        try:
            if "search_path" in pattern:
                response = await client.get(
                    f"{pattern['base']}{pattern['search_path']}",
                    params={pattern["search_param"]: query, "limit": 8, "type": "law"},
                    headers=headers,
                    timeout=30.0,
                )
            else:
                response = await client.post(
                    f"{pattern['base']}{pattern['analyze_path']}",
                    json={"query": query, "include_laws": True},
                    headers=headers,
                    timeout=30.0,
                )
            response.raise_for_status()
            data = response.json()
            return self._normalize_laws(data), data
        except httpx.HTTPStatusError as exc:
            raise self._map_http_error(exc) from exc

    async def _search_practice(
        self,
        client: httpx.AsyncClient,
        pattern: dict[str, Any],
        api_key: str,
        query: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """Try to fetch court practice; return an empty list on soft failure."""

        headers = self._build_headers(pattern, api_key)
        try:
            if "search_path" in pattern:
                response = await client.get(
                    f"{pattern['base']}{pattern['search_path']}",
                    params={pattern["search_param"]: query, "limit": 5, "type": "case"},
                    headers=headers,
                    timeout=20.0,
                )
            else:
                response = await client.post(
                    f"{pattern['base']}{pattern['analyze_path']}",
                    json={"query": query, "include_practice": True},
                    headers=headers,
                    timeout=20.0,
                )
            response.raise_for_status()
            data = response.json()
            return self._normalize_practice(data), data
        except Exception as exc:  # pragma: no cover - network-dependent
            logger.warning("Court practice fetch failed for %s: %s", pattern["name"], exc)
            return [], None

    @staticmethod
    def _normalize_laws(data: dict[str, Any]) -> list[dict[str, str]]:
        """Normalize known KP response variants to the internal schema."""

        laws: list[dict[str, str]] = []

        for doc in data.get("documents", []):
            laws.append(
                {
                    "title": str(doc.get("title") or doc.get("name") or ""),
                    "article": str(doc.get("article") or doc.get("section") or ""),
                    "text": str(doc.get("snippet") or doc.get("text") or "")[:300],
                }
            )

        result = data.get("result", {})
        for law in result.get("laws", []):
            laws.append(
                {
                    "title": str(law.get("title") or ""),
                    "article": str(law.get("article") or ""),
                    "text": str(law.get("description") or law.get("text") or "")[:300],
                }
            )

        return laws[:8]

    @staticmethod
    def _normalize_practice(data: dict[str, Any]) -> list[dict[str, str]]:
        """Normalize court practice entries from known KP payloads."""

        practice: list[dict[str, str]] = []
        combined = list(data.get("cases", [])) + list(data.get("result", {}).get("practice", []))
        for item in combined:
            practice.append(
                {
                    "case": str(item.get("number") or item.get("case") or ""),
                    "court": str(item.get("court") or ""),
                    "outcome": str(item.get("outcome") or item.get("result") or ""),
                }
            )
        return practice[:5]

    async def analyze(self, anonymized_text: str, api_key: str) -> LegalAnalysisResult:
        """Analyze text using the detected ConsultantPlus API variant."""

        detected = await self._detect_pattern(api_key)
        candidates = [detected, *[pattern for pattern in self.PATTERNS if pattern["name"] != detected["name"]]]
        last_error: Exception | None = None

        for index, pattern in enumerate(candidates):
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    laws, laws_raw = await self._search_laws(client, pattern, api_key, anonymized_text)
                    practice, practice_raw = await self._search_practice(client, pattern, api_key, anonymized_text)

                self._cache_pattern(pattern)
                return LegalAnalysisResult(
                    summary=self._build_summary(laws, practice),
                    relevant_laws=laws,
                    court_practice=practice,
                    recommendations=self._build_recommendations(laws),
                    source="КонсультантПлюс",
                    raw_response={
                        "pattern": pattern["name"],
                        "laws": laws_raw,
                        "practice": practice_raw,
                    },
                )
            except RuntimeError as exc:
                last_error = exc
                message = str(exc)
                can_retry = index == 0 and ("401" in message or "403" in message or "недействителен" in message.lower() or "доступ запрещ" in message.lower())
                if can_retry:
                    logger.warning("ConsultantPlus pattern %s rejected auth, trying fallback pattern", pattern["name"])
                    continue
                break
            except Exception as exc:  # pragma: no cover - network-dependent
                last_error = exc
                break

        raise RuntimeError(
            str(last_error)
            if last_error is not None
            else "Не удалось выполнить запрос к КонсультантПлюс."
        )

    @staticmethod
    def _build_summary(laws: list[dict[str, Any]], practice: list[dict[str, Any]]) -> str:
        if not laws:
            return "Релевантные нормы не найдены. Уточните запрос."
        titles = [str(item.get("title") or "") for item in laws[:3] if item.get("title")]
        return (
            f"Найдено {len(laws)} релевантных нормативных акта(ов). "
            f"Основные: {', '.join(titles) if titles else 'без уточнения'}. "
            f"Судебная практика: {len(practice)} дел(а)."
        )

    @staticmethod
    def _build_recommendations(laws: list[dict[str, Any]]) -> str:
        if not laws:
            return "Рекомендуется уточнить юридическую квалификацию вопроса."
        return (
            "На основании найденных норм рекомендуется:\n"
            "1. Проверить актуальность редакций указанных нормативных актов.\n"
            "2. Уточнить применимость норм к конкретным обстоятельствам дела.\n"
            "3. Сопоставить найденные нормы с судебной практикой и доказательствами по делу."
        )

    @staticmethod
    def _map_http_error(exc: httpx.HTTPStatusError) -> RuntimeError:
        status = exc.response.status_code
        if status == 401:
            return RuntimeError("API-ключ КонсультантПлюс недействителен (401)")
        if status == 403:
            return RuntimeError("Доступ запрещён (403). Проверьте права ключа.")
        if status == 429:
            return RuntimeError("Превышен лимит запросов КП (429). Подождите.")
        return RuntimeError(f"Ошибка КонсультантПлюс ({status}): {exc.response.text[:200]}")


def get_adapter() -> ConsultantPlusAdapter:
    """Return the real HTTP adapter when configured, otherwise the demo stub."""

    http_adapter = HttpAdapter()
    if http_adapter.is_available():
        logger.info("Using ConsultantPlus HttpAdapter")
        return http_adapter
    logger.warning("ConsultantPlus HttpAdapter unavailable, falling back to StubAdapter")
    return StubAdapter()


consultant_adapter = get_adapter()
