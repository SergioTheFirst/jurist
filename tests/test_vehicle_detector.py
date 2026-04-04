"""Тесты словарного детектора марок/моделей ТС."""

from __future__ import annotations

import pytest

from legaldesk.anonymizer.dict_detector import detect_vehicles
from legaldesk.anonymizer.models import EntityType


@pytest.mark.parametrize(
    "text",
    [
        "а/м Toyota Camry г/н А123ВС77",
        "автомобиль Лада Гранта государственный номер Х001ХХ77",
        "ТС BMW X5 VIN XWE123456789",
        "водитель управлял автомобилем Hyundai Solaris",
        "ДТП произошло с участием КIA Rio и Ford Focus",
        "транспортное средство Lada Vesta а/м",
        "Haval F7 автомобиль попал в ДТП",
        "машина Volkswagen Polo, госномер В234СВ99",
    ],
)
def test_detect_known_vehicle(text: str) -> None:
    """Детектор находит марку/модель в тексте с контекстным словом."""
    spans = detect_vehicles(text)
    assert any(s.entity_type == EntityType.VEHICLE_MAKE_MODEL for s in spans), (
        f"Не найдено VEHICLE_MAKE_MODEL в: {text!r}"
    )


def test_span_positions_are_correct() -> None:
    """Позиции start/end соответствуют реальным позициям в тексте."""
    text = "а/м Toyota Camry г/н А123ВС77"
    spans = detect_vehicles(text)
    vm_spans = [s for s in spans if s.entity_type == EntityType.VEHICLE_MAKE_MODEL]
    assert vm_spans, "Марка/модель не найдена"
    for span in vm_spans:
        assert text[span.start : span.end] == span.text, (
            f"Позиции не совпадают: {span.text!r} vs {text[span.start:span.end]!r}"
        )


def test_no_false_positive_without_context() -> None:
    """Без контекстного слова одиночная марка не должна быть найдена."""
    # Текст о компании Toyota без контекста ТС
    text = "Компания Toyota объявила о новых инвестициях в производство."
    spans = detect_vehicles(text)
    assert not any(s.entity_type == EntityType.VEHICLE_MAKE_MODEL for s in spans), (
        "Ложное срабатывание без контекста ТС"
    )


def test_source_is_dict() -> None:
    """Все span'ы от словарного детектора имеют source='dict'."""
    text = "автомобиль Kia Rio попал в ДТП"
    spans = detect_vehicles(text)
    for span in spans:
        assert span.source == "dict"


def test_no_overlap_in_results() -> None:
    """Результаты не содержат перекрывающихся span'ов."""
    text = "а/м Toyota Camry и Lada Granta участвовали в ДТП"
    spans = detect_vehicles(text)
    sorted_spans = sorted(spans, key=lambda s: s.start)
    for i in range(len(sorted_spans) - 1):
        assert sorted_spans[i].end <= sorted_spans[i + 1].start, (
            f"Перекрытие: {sorted_spans[i]} и {sorted_spans[i+1]}"
        )
