"""Клиент Ollama API для обнаружения ПДн в тексте."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

import httpx

from legaldesk.anonymizer.models import DetectedSpan, EntityType

if TYPE_CHECKING:
    from legaldesk.anonymizer.config import AnonymizerConfig

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Ты — система обнаружения персональных данных в юридических документах по ДТП.
Найди ВСЕ персональные данные в тексте. Категории:
PERSON — ФИО в любом падеже, инициалы
DATE_OF_BIRTH — дата рождения
ADDRESS — любой адрес (регистрации, проживания, места ДТП если содержит дом/квартиру)
PASSPORT — серия и номер паспорта
SNILS — СНИЛС
INN — ИНН
DRIVERS_LICENSE — серия и номер водительского удостоверения
MEDICAL_POLICY — номер полиса ОМС/ДМС
PHONE — телефон
EMAIL — email
LICENSE_PLATE — госномер автомобиля
VIN — VIN-код
VEHICLE_BODY_NUMBER — номер кузова
ENGINE_NUMBER — номер двигателя
VEHICLE_REGISTRATION — номер СТС
VEHICLE_PASSPORT — номер ПТС
INSURANCE_POLICY — номер полиса ОСАГО/КАСКО
CASE_NUMBER — номер административного дела
POLICE_REPORT — номер постановления/определения ГИБДД
INSURANCE_CLAIM — номер страхового дела, выплатного дела, направления на ремонт
BANK_ACCOUNT — расчётный счёт
BANK_CARD — номер банковской карты
BIK — БИК банка
Верни ТОЛЬКО JSON-массив. Формат: [{"text": "найденное", "type": "ТИП", "start": N, "end": N}]
Без пояснений. Только JSON.\
"""


class OllamaClient:
    """Синхронный клиент Ollama для NER-задач."""

    def __init__(self, config: AnonymizerConfig) -> None:
        self._config = config

    def detect(self, text: str) -> tuple[list[DetectedSpan], bool]:
        """Обнаружить ПДн в тексте с помощью LLM.

        Returns:
            (spans, is_degraded) — список span'ов и флаг деградации.
            При любой ошибке возвращает ([], True). Текст в лог НЕ пишется.
        """
        try:
            raw_response = self._call_api(text)
            spans = self._parse_response(raw_response)
            return spans, False
        except Exception:
            logger.warning("LLM detection failed, falling back to regex-only mode")
            return [], True

    def _call_api(self, text: str) -> str:
        """Выполнить POST-запрос к Ollama API и вернуть поле response."""
        prompt = f"{_SYSTEM_PROMPT}\n\nТекст:\n{text}"
        with httpx.Client(timeout=self._config.ollama_timeout) as client:
            response = client.post(
                f"{self._config.ollama_base_url}/api/generate",
                json={
                    "model": self._config.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return str(data.get("response", ""))

    def _parse_response(self, raw: str) -> list[DetectedSpan]:
        """Распарсить JSON из ответа LLM (включая извлечение из markdown-блока)."""
        json_text = _extract_json_from_text(raw)
        items: Any = json.loads(json_text)
        if not isinstance(items, list):
            return []

        spans: list[DetectedSpan] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                entity_type = EntityType(item["type"])
                span = DetectedSpan(
                    text=str(item["text"]),
                    entity_type=entity_type,
                    start=int(item["start"]),
                    end=int(item["end"]),
                    source="llm",
                )
                spans.append(span)
            except (KeyError, ValueError, TypeError):
                logger.warning("Skipping invalid entity item from LLM response")
        return spans


def _extract_json_from_text(text: str) -> str:
    """Извлечь JSON-массив из текста, в том числе из markdown-блока."""
    # Попытка 1: markdown-блок ```json ... ``` или ``` ... ```
    md_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if md_match:
        return md_match.group(1).strip()
    # Попытка 2: найти первый JSON-массив
    arr_match = re.search(r"\[[\s\S]*\]", text)
    if arr_match:
        return arr_match.group(0)
    return text
