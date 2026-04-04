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
Найди ВСЕ персональные данные в тексте. Верни ТОЛЬКО JSON-массив без пояснений.

КАТЕГОРИИ:
PERSON           — ФИО в любом падеже, инициалы (Иванов И.И., Петрова Наталья Сергеевна)
DATE_OF_BIRTH    — дата рождения (01.01.1980, 1 января 1980 г.)
DATE             — прочие значимые даты (дата ДТП, дата составления документа)
ADDRESS          — адрес (регистрации, проживания, места ДТП если содержит улицу/дом)
PASSPORT         — серия и номер паспорта (45 08 123456)
SNILS            — СНИЛС (123-456-789 00)
INN              — ИНН
DRIVERS_LICENSE  — серия и номер водительского удостоверения
MEDICAL_POLICY   — номер полиса ОМС/ДМС
PHONE            — телефон (+7 999 123-45-67)
EMAIL            — email (user@example.ru)
LICENSE_PLATE    — госномер автомобиля (А123ВС77)
TRAILER_PLATE    — госномер прицепа (АА123477)
MOTORCYCLE_PLATE — госномер мотоцикла (1234АА77)
VIN              — VIN-код (17 символов: JN1VBAV11UM012345)
VEHICLE_BODY_NUMBER — номер кузова
ENGINE_NUMBER    — номер двигателя
VEHICLE_MAKE_MODEL  — марка и/или модель ТС (Toyota Camry, Лада Гранта, BMW X5)
VEHICLE_REGISTRATION — номер СТС (77 АА 123456)
VEHICLE_PASSPORT    — номер ПТС
INSURANCE_POLICY    — номер полиса ОСАГО/КАСКО (ССС 1234567890)
CASE_NUMBER         — номер административного дела
POLICE_REPORT       — номер постановления/определения ГИБДД
INSURANCE_CLAIM     — номер страхового дела / выплатного дела
BANK_ACCOUNT        — расчётный счёт (20 цифр)
BANK_CARD           — номер банковской карты
BIK                 — БИК банка

ПРАВИЛА:
- Включай все упоминания, даже в косвенных падежах
- Для каждого span указывай точные позиции start/end (индексы символов в тексте)
- Если одно и то же ПДн встречается несколько раз — указывай каждое вхождение
- VEHICLE_MAKE_MODEL: указывай только марку, только модель, или марку+модель вместе

ПРИМЕР:
Текст: «Водитель Иванов Иван Иванович, 12.05.1985 г.р., а/м Toyota Camry г/н А123ВС77»
Ответ: [
  {"text": "Иванов Иван Иванович", "type": "PERSON", "start": 9, "end": 29},
  {"text": "12.05.1985", "type": "DATE_OF_BIRTH", "start": 31, "end": 41},
  {"text": "Toyota Camry", "type": "VEHICLE_MAKE_MODEL", "start": 48, "end": 60},
  {"text": "А123ВС77", "type": "LICENSE_PLATE", "start": 64, "end": 72}
]

Формат: [{"text": "...", "type": "ТИП", "start": N, "end": N}]
Только JSON. Без пояснений.\
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
