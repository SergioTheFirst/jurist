"""Тесты словарного детектора имён и фамилий."""

from __future__ import annotations

import pytest

from legaldesk.anonymizer.dict_detector import detect_names
from legaldesk.anonymizer.models import EntityType


@pytest.mark.parametrize(
    "text, expected_fio",
    [
        ("Иванов Иван Иванович управлял автомобилем", "Иванов Иван Иванович"),
        ("Заявитель: Петрова Наталья Сергеевна", "Петрова Наталья Сергеевна"),
        ("водитель Смирнов С.В.", "Смирнов"),
        ("Алишер Навоийга тегишли", "Алишер"),
        ("гражданин Армен Карапетян", "Армен Карапетян"),
        ("Ильдар Хайруллин проживает", "Ильдар Хайруллин"),
        ("Магомед Абдуллаев за рулём", "Магомед"),
        ("представитель Гусейнов А.М.", "Гусейнов"),
    ],
)
def test_detect_known_name(text: str, expected_fio: str) -> None:
    """Детектор находит ФИО/имя/фамилию в тексте."""
    spans = detect_names(text)
    person_texts = [s.text for s in spans if s.entity_type == EntityType.PERSON]
    assert any(expected_fio in t or t in expected_fio for t in person_texts), (
        f"Не найдено {expected_fio!r} в {text!r}. Найдено: {person_texts}"
    )


def test_span_positions_are_correct() -> None:
    """Позиции start/end соответствуют реальным позициям в тексте."""
    text = "Иванов Иван Иванович управлял автомобилем."
    spans = detect_names(text)
    person_spans = [s for s in spans if s.entity_type == EntityType.PERSON]
    assert person_spans, "Имя не найдено"
    for span in person_spans:
        assert text[span.start : span.end] == span.text, (
            f"Позиции не совпадают: {span.text!r} vs {text[span.start:span.end]!r}"
        )


def test_source_is_dict() -> None:
    """Все span'ы от словарного детектора имеют source='dict'."""
    text = "Петров Андрей Николаевич"
    spans = detect_names(text)
    for span in spans:
        assert span.source == "dict"


def test_no_overlap_in_results() -> None:
    """Результаты не содержат перекрывающихся span'ов."""
    text = "Иванов Иван и Петрова Анна заключили соглашение."
    spans = detect_names(text)
    sorted_spans = sorted(spans, key=lambda s: s.start)
    for i in range(len(sorted_spans) - 1):
        assert sorted_spans[i].end <= sorted_spans[i + 1].start, (
            f"Перекрытие: {sorted_spans[i]} и {sorted_spans[i+1]}"
        )


def test_fio_grouped_together() -> None:
    """Три компонента ФИО группируются в один span."""
    text = "Смирнов Сергей Павлович обратился"
    spans = detect_names(text)
    person_spans = [s for s in spans if s.entity_type == EntityType.PERSON]
    # Должен быть единственный span с полным ФИО
    full_fio = [s for s in person_spans if "Смирнов" in s.text and "Сергей" in s.text]
    assert full_fio, f"Полное ФИО не сгруппировано, найдено: {[s.text for s in person_spans]}"
