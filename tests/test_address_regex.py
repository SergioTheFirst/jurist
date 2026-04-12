"""Unit tests for composable address regex primitives in address_patterns.py."""

from __future__ import annotations

import pytest

from backend.core.entity_rules.address_patterns import (
    ADDRESS_EXPANSION_RE,
    CITY_STREET_RE,
    FULL_ADDRESS_RE,
    HOUSE_RE,
    POI_ADDRESS_RE,
    POSTAL_CITY_RE,
    POSTAL_RE,
    PREFIXED_ADDRESS_RE,
    PREPOSITIONAL_STREET_RE,
    REGION_RE,
    STREET_RE,
    UNIT_RE,
)


# ---------------------------------------------------------------------------
# Primitive tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("индекс 119019, город", "119019"),
        ("почта 453100 доставка", "453100"),
        ("код 12345 слишком короткий", None),
        ("код 1234567 слишком длинный", None),
    ],
    ids=["six_digit", "rural_postal", "too_short", "too_long"],
)
def test_postal_re(text: str, expected: str | None) -> None:
    """POSTAL_RE matches exactly 6-digit postal codes."""

    match = POSTAL_RE.search(text)
    if expected is None:
        assert match is None, f"Unexpected match: {match.group() if match else ''}"
    else:
        assert match is not None, f"Postal code not found in: {text!r}"
        assert match.group().strip() == expected


@pytest.mark.parametrize(
    "text, must_contain",
    [
        ("Московская область, г. Подольск", "Московская область"),
        ("Республика Татарстан, г. Казань", "Республика Татарстан"),
        ("Краснодарский край, ст-ца Динская", "Краснодарский край"),
    ],
    ids=["oblast", "republic", "kray"],
)
def test_region_re(text: str, must_contain: str) -> None:
    """REGION_RE matches Russian federation subjects."""

    match = REGION_RE.search(text)
    assert match is not None, f"Region not found in: {text!r}"
    assert must_contain in match.group()


@pytest.mark.parametrize(
    "text, must_contain",
    [
        ("ул. Ленина, д. 5", "ул. Ленина"),
        ("ул. им. Гагарина, д. 4", "ул. им. Гагарина"),
        ("ул. 1-я Тверская-Ямская, д. 11", "ул. 1-я Тверская-Ямская"),
        ("проспект Мира, д. 10", "проспект Мира"),
        ("пер. Садовый, д. 3", "пер. Садовый"),
    ],
    ids=["simple", "im_prefix", "compound", "prospekt", "pereulok"],
)
def test_street_re(text: str, must_contain: str) -> None:
    """STREET_RE matches street abbreviations with names."""

    match = STREET_RE.search(text)
    assert match is not None, f"Street not found in: {text!r}"
    assert must_contain in match.group()


@pytest.mark.parametrize(
    "text, must_contain",
    [
        ("д. 12, кв. 5", "д. 12"),
        ("дом 7А корп. 2", "дом 7А корп. 2"),
        ("д. 7 корп. 2 стр. 1 литера А", "д. 7 корп. 2 стр. 1 литера А"),
        ("д.15 без пробела", "д.15"),
    ],
    ids=["simple_house", "with_korpus", "full_building", "no_space"],
)
def test_house_re(text: str, must_contain: str) -> None:
    """HOUSE_RE matches building numbers with optional annexes."""

    match = HOUSE_RE.search(text)
    assert match is not None, f"House not found in: {text!r}"
    assert must_contain in match.group()


def test_house_re_no_false_positive_mkad() -> None:
    """HOUSE_RE must not match 'Д' inside 'МКАД'."""

    text = "на МКАД 34-й км"
    match = HOUSE_RE.search(text)
    if match is not None:
        assert "МКАД" not in text[max(0, match.start() - 3):match.start()], (
            f"False positive: HOUSE_RE matched inside МКАД: {match.group()!r}"
        )


@pytest.mark.parametrize(
    "text, expected",
    [
        ("кв. 5, этаж 2", "кв. 5"),
        ("оф. 312 в здании", "оф. 312"),
        ("помещение 1А", "помещение 1А"),
    ],
    ids=["apartment", "office", "room"],
)
def test_unit_re(text: str, expected: str) -> None:
    """UNIT_RE matches room/apartment/office units."""

    match = UNIT_RE.search(text)
    assert match is not None, f"Unit not found in: {text!r}"
    assert expected in match.group()


# ---------------------------------------------------------------------------
# Composite pattern tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "119019, г. Москва, ул. Арбат, д. 12, кв. 5",
        "453100, Республика Башкортостан, г. Стерлитамак, ул. Ленина, д. 3",
        "г. Москва, ул. Тверская, д. 7 корп. 2 стр. 1",
        "дер. Ласково, д. 7",
    ],
    ids=["full_with_postal", "with_region", "building_parts", "rural"],
)
def test_full_address_re(text: str) -> None:
    """FULL_ADDRESS_RE matches complete Russian addresses."""

    match = FULL_ADDRESS_RE.search(text)
    assert match is not None, f"Full address not found in: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "на улице Тверской напротив дома 5",
        "по проспекту Мира около перекрёстка",
    ],
    ids=["na_ulitse", "po_prospektu"],
)
def test_prepositional_street_re(text: str) -> None:
    """PREPOSITIONAL_STREET_RE matches prepositional street references."""

    match = PREPOSITIONAL_STREET_RE.search(text)
    assert match is not None, f"Prepositional street not found in: {text!r}"


def test_poi_address_re() -> None:
    """POI_ADDRESS_RE matches point-of-interest references."""

    match = POI_ADDRESS_RE.search("Авария произошла на МКАД 34-й км")
    assert match is not None, "POI address not found"
    assert "МКАД" in match.group()


def test_prefixed_address_re() -> None:
    """PREFIXED_ADDRESS_RE matches address: prefix patterns."""

    text = "адрес: г. Москва, ул. Ленина, д. 5"
    match = PREFIXED_ADDRESS_RE.search(text)
    assert match is not None, f"Prefixed address not found in: {text!r}"


def test_multiline_address() -> None:
    """Addresses split across lines must still match (DOCX paragraph join)."""

    text = "119019,\nг. Москва,\nул. Арбат, д. 12"
    match = FULL_ADDRESS_RE.search(text)
    assert match is not None, "Multi-line address not found"
    assert "Арбат" in match.group()


# ---------------------------------------------------------------------------
# Negative tests — things that must NOT match
# ---------------------------------------------------------------------------


def test_no_false_positive_on_legal_text() -> None:
    """Legal prose without addresses should not trigger composite patterns."""

    text = "Согласно ст. 15 ГК РФ ответчик обязан возместить убытки."
    assert FULL_ADDRESS_RE.search(text) is None
    assert CITY_STREET_RE.search(text) is None
    assert POSTAL_CITY_RE.search(text) is None


def test_no_false_positive_on_person_name() -> None:
    """Person names should not be matched by address patterns."""

    text = "Заявитель Иванов Иван Иванович подал заявление"
    assert FULL_ADDRESS_RE.search(text) is None
