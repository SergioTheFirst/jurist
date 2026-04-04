"""Доменные модели анонимизатора для юриста по ДТП."""

from __future__ import annotations

import sys
from enum import Enum
from typing import Literal

from pydantic import BaseModel

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    class StrEnum(str, Enum):
        """StrEnum backport for Python < 3.11."""

        def __str__(self) -> str:
            """Return the string value."""
            return str(self.value)


class EntityType(StrEnum):
    """Типы персональных данных, обнаруживаемых в документах по ДТП."""

    # Персональные
    PERSON = "PERSON"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"
    DATE = "DATE"
    ADDRESS = "ADDRESS"

    # Документы личности
    PASSPORT = "PASSPORT"
    SNILS = "SNILS"
    INN = "INN"
    DRIVERS_LICENSE = "DRIVERS_LICENSE"
    MEDICAL_POLICY = "MEDICAL_POLICY"

    # Контакты
    PHONE = "PHONE"
    EMAIL = "EMAIL"

    # Транспортное средство
    LICENSE_PLATE = "LICENSE_PLATE"
    TRAILER_PLATE = "TRAILER_PLATE"
    MOTORCYCLE_PLATE = "MOTORCYCLE_PLATE"
    VIN = "VIN"
    VEHICLE_BODY_NUMBER = "VEHICLE_BODY_NUMBER"
    ENGINE_NUMBER = "ENGINE_NUMBER"
    VEHICLE_MAKE_MODEL = "VEHICLE_MAKE_MODEL"

    # Документы на ТС
    VEHICLE_REGISTRATION = "VEHICLE_REGISTRATION"
    VEHICLE_PASSPORT = "VEHICLE_PASSPORT"
    INSURANCE_POLICY = "INSURANCE_POLICY"

    # Материалы дела
    CASE_NUMBER = "CASE_NUMBER"
    POLICE_REPORT = "POLICE_REPORT"
    INSURANCE_CLAIM = "INSURANCE_CLAIM"

    # Финансы
    BANK_ACCOUNT = "BANK_ACCOUNT"
    BANK_CARD = "BANK_CARD"
    BIK = "BIK"


class DetectedSpan(BaseModel):
    """Обнаруженный фрагмент текста, содержащий ПДн."""

    text: str
    entity_type: EntityType
    start: int
    end: int
    source: Literal["regex", "llm", "manual", "dict"]

    @property
    def span_id(self) -> str:
        """Стабильный идентификатор вхождения для HTML-форм."""
        return f"{self.start}:{self.end}:{self.source}:{self.entity_type}"


class AnonymizationResult(BaseModel):
    """Результат анонимизации текста."""

    original_text: str
    anonymized_text: str
    spans: list[DetectedSpan]
    mapping: dict[str, str]          # token → original
    reverse_mapping: dict[str, str]  # original → token
    degraded: bool
