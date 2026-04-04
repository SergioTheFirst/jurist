"""Тесты regex-паттернов для дат и адресов."""

from __future__ import annotations

import pytest

from legaldesk.anonymizer.regex_patterns import (
    ADDRESS_PATTERN,
    CASE_NUMBER_PATTERN,
    DATE_PATTERN,
    DATE_VERBAL_PATTERN,
    LICENSE_PLATE_PATTERN,
    TRAILER_PLATE_PATTERN,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("ДТП произошло 12.05.2021 года", "12.05.2021"),
        ("дата рождения 01.01.1980", "01.01.1980"),
        ("25/06/2023 оформлен протокол", "25/06/2023"),
        ("31-12-2020 последний день", "31-12-2020"),
    ],
)
def test_date_pattern(text: str, expected: str) -> None:
    """DATE_PATTERN находит даты в формате ДД.ММ.ГГГГ."""
    match = DATE_PATTERN.search(text)
    assert match is not None, f"Дата не найдена в: {text!r}"
    assert match.group() == expected


@pytest.mark.parametrize(
    "text, must_contain",
    [
        ("событие произошло 5 января 2021 года", "января 2021"),
        ("12 марта 2020 г.", "марта 2020"),
        ("31 декабря 2019 г.", "декабря 2019"),
    ],
)
def test_date_verbal_pattern(text: str, must_contain: str) -> None:
    """DATE_VERBAL_PATTERN находит словесные даты."""
    match = DATE_VERBAL_PATTERN.search(text)
    assert match is not None, f"Словесная дата не найдена в: {text!r}"
    assert must_contain in match.group()


@pytest.mark.parametrize(
    "text",
    [
        "ул. Ленина д. 5",
        "г. Москва проспект Мира",
        "г Краснодар ул. Красная д.1 кв.10",
        "пер. Садовый д. 3а/2",
    ],
)
def test_address_pattern(text: str) -> None:
    """ADDRESS_PATTERN находит фрагменты адресов."""
    match = ADDRESS_PATTERN.search(text)
    assert match is not None, f"Адрес не найден в: {text!r}"


@pytest.mark.parametrize(
    "plate",
    [
        "АА123477",
        "ВВ123499",
    ],
)
def test_trailer_plate_pattern(plate: str) -> None:
    """TRAILER_PLATE_PATTERN находит номера прицепов."""
    match = TRAILER_PLATE_PATTERN.search(plate)
    assert match is not None, f"Номер прицепа не найден: {plate!r}"


@pytest.mark.parametrize(
    "plate",
    [
        "А123ВС77",
        "Е567КМ199",
    ],
)
def test_license_plate_pattern(plate: str) -> None:
    """LICENSE_PLATE_PATTERN находит стандартные госномера."""
    match = LICENSE_PLATE_PATTERN.search(plate)
    assert match is not None, f"Госномер не найден: {plate!r}"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("дело А40-12345/2020", "А40-12345/2020"),
        ("дело 1-23/21", "1-23/21"),
    ],
)
def test_case_number_pattern(text: str, expected: str) -> None:
    """CASE_NUMBER_PATTERN находит номера дел."""
    match = CASE_NUMBER_PATTERN.search(text)
    assert match is not None, f"Номер дела не найден в: {text!r}"
    assert match.group() == expected
