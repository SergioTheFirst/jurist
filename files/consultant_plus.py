"""
Адаптер КонсультантПлюс.

Архитектура: паттерн Adapter + Strategy.
- ConsultantPlusAdapter — интерфейс (Protocol)
- StubAdapter — заглушка для разработки/тестирования
- HttpAdapter — реальный HTTP-клиент (подключается после идентификации API)

Для подключения реального API: реализуйте HttpAdapter и замените в get_adapter().
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


@dataclass
class LegalAnalysisResult:
    """Результат юридического анализа от КП."""
    summary: str                          # Краткое заключение
    relevant_laws: list[dict]             # [{"title": str, "article": str, "text": str}]
    court_practice: list[dict]            # [{"case": str, "court": str, "outcome": str}]
    recommendations: str                  # Рекомендации для юриста
    source: str = "КонсультантПлюс"
    raw_response: Optional[dict] = None   # Сырой ответ API для отладки


class ConsultantPlusAdapter(ABC):
    """Базовый интерфейс адаптера."""

    @abstractmethod
    async def analyze(self, anonymized_text: str, api_key: str) -> LegalAnalysisResult:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass


class StubAdapter(ConsultantPlusAdapter):
    """
    Заглушка для разработки.
    Возвращает структурированный демо-ответ.
    Замените на HttpAdapter после идентификации реального API.
    """

    def is_available(self) -> bool:
        return True

    async def analyze(self, anonymized_text: str, api_key: str) -> LegalAnalysisResult:
        logger.info("StubAdapter: симуляция запроса к КонсультантПлюс")

        # Определяем тематику по ключевым словам для более релевантной заглушки
        text_lower = anonymized_text.lower()
        topic = self._detect_topic(text_lower)

        return LegalAnalysisResult(
            summary=self._get_summary(topic),
            relevant_laws=self._get_laws(topic),
            court_practice=self._get_practice(topic),
            recommendations=self._get_recommendations(topic),
            source="КонсультантПлюс [ДЕМО — реальный API не подключён]",
        )

    def _detect_topic(self, text: str) -> str:
        if any(w in text for w in ["труд", "увольнен", "работник", "зарплат"]):
            return "трудовой"
        if any(w in text for w in ["договор", "сделка", "поставк", "арен"]):
            return "гражданский"
        if any(w in text for w in ["налог", "ндс", "прибыль", "ифнс"]):
            return "налоговый"
        return "общий"

    def _get_summary(self, topic: str) -> str:
        summaries = {
            "трудовой": "Документ содержит признаки трудового спора. Необходимо проверить соблюдение процедур ТК РФ.",
            "гражданский": "Документ касается гражданско-правовых отношений. Требуется анализ условий договора.",
            "налоговый": "Обнаружены налоговые правоотношения. Рекомендуется сверка с актуальной редакцией НК РФ.",
            "общий": "Документ обработан. Для точного анализа подключите реальный API КонсультантПлюс.",
        }
        return summaries.get(topic, summaries["общий"])

    def _get_laws(self, topic: str) -> list[dict]:
        laws = {
            "трудовой": [
                {"title": "Трудовой кодекс РФ", "article": "ст. 81", "text": "Расторжение трудового договора по инициативе работодателя"},
                {"title": "Трудовой кодекс РФ", "article": "ст. 140", "text": "Сроки расчёта при увольнении"},
            ],
            "гражданский": [
                {"title": "Гражданский кодекс РФ", "article": "ст. 450", "text": "Основания изменения и расторжения договора"},
                {"title": "Гражданский кодекс РФ", "article": "ст. 393", "text": "Обязанность должника возместить убытки"},
            ],
            "налоговый": [
                {"title": "Налоговый кодекс РФ (часть 1)", "article": "ст. 75", "text": "Пеня за несвоевременную уплату налога"},
                {"title": "Налоговый кодекс РФ (часть 2)", "article": "гл. 25", "text": "Налог на прибыль организаций"},
            ],
            "общий": [
                {"title": "⚠️ Демо-режим", "article": "—", "text": "Подключите реальный API КонсультантПлюс для получения актуальных норм"},
            ],
        }
        return laws.get(topic, laws["общий"])

    def _get_practice(self, topic: str) -> list[dict]:
        return [
            {
                "case": "⚠️ Данные недоступны в демо-режиме",
                "court": "—",
                "outcome": "Подключите реальный API КонсультантПлюс"
            }
        ]

    def _get_recommendations(self, topic: str) -> str:
        return (
            "⚠️ ВНИМАНИЕ: Система работает в демо-режиме.\n"
            "Реальный анализ будет доступен после подключения API КонсультантПлюс.\n\n"
            "Для подключения:\n"
            "1. Уточните тип API (КП:Технология / web.consultant.ru)\n"
            "2. Получите документацию у вашего менеджера КонсультантПлюс\n"
            "3. Замените StubAdapter на HttpAdapter в backend/adapters/consultant_plus.py"
        )


class HttpAdapter(ConsultantPlusAdapter):
    """
    Реальный HTTP-адаптер.
    Раскомментируйте и реализуйте после получения документации API КП.

    Возможные варианты API КП:
    - КП:Технология — XML/SOAP или REST, корпоративная интеграция
    - web.consultant.ru — REST API для онлайн-версии
    """

    BASE_URL = "https://api.consultant.ru/v1"  # Уточните у КП

    def is_available(self) -> bool:
        return False  # Изменить на True после настройки

    async def analyze(self, anonymized_text: str, api_key: str) -> LegalAnalysisResult:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "text": anonymized_text,
            "include_laws": True,
            "include_practice": True,
            "language": "ru",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/analyze",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        # TODO: Адаптируйте маппинг под реальную структуру ответа КП
        return LegalAnalysisResult(
            summary=data.get("summary", ""),
            relevant_laws=data.get("laws", []),
            court_practice=data.get("practice", []),
            recommendations=data.get("recommendations", ""),
            raw_response=data,
        )


def get_adapter() -> ConsultantPlusAdapter:
    """Фабрика: возвращает реальный адаптер если доступен, иначе заглушку."""
    http = HttpAdapter()
    if http.is_available():
        logger.info("Используется HttpAdapter (реальный API КП)")
        return http
    logger.warning("HttpAdapter недоступен — используется StubAdapter (демо-режим)")
    return StubAdapter()


# Singleton
consultant_adapter = get_adapter()
