"""Regex-примитивы и композитные варианты для детекции российских адресов.

Стратегия:
  * Каждый примитив (POSTAL/REGION/CITY/STREET/HOUSE/UNIT/POI) компилируется
    отдельно и используется `LocationRuleEngine.expand_candidate` для расширения
    Natasha-LOC кандидатов.
  * Композитные варианты (FULL_ADDRESS_RE и т.п.) регистрируются как отдельные
    _PatternSpec в `backend/core/anonymizer.py`. Порядок от широкого к узкому —
    `_resolve_overlaps` отдаёт победу самому длинному покрытию.
  * Все разделители между компонентами — `[,;\s]+`, что автоматически
    пропускает `\n`: многострочные адреса из DOCX больше не ломают матч.
  * IGNORECASE применяется точечно через `(?i:...)` только к сокращениям,
    чтобы заглавная первая буква в именах собственных оставалась обязательной
    (иначе 'ул.бабушка' тоже был бы адресом).
"""

from __future__ import annotations

import re

from backend.core.dictionaries.geo import (
    BUILDING_UNIT_ABBREVIATIONS,
    REGION_SUFFIXES,
    ROOM_UNIT_ABBREVIATIONS,
    SETTLEMENT_ABBREVIATIONS,
    STREET_ABBREVIATIONS,
)


def _alt(values: frozenset[str] | tuple[str, ...] | set[str]) -> str:
    """Alternation string sorted longest-first and re.escape-escaped."""

    return "|".join(re.escape(value) for value in sorted(values, key=len, reverse=True))


# ---------------------------------------------------------------------------
# Alphabet fragments — enforce capitalized first letter for proper names
# ---------------------------------------------------------------------------
_NAME_TOKEN = r"[А-ЯЁ][А-Яа-яЁё-]{1,40}"
_NAME_SEQUENCE = rf"{_NAME_TOKEN}(?:[\s\-]{_NAME_TOKEN}){{0,3}}"

# Case-insensitive alternations for abbreviations / suffixes
_STREET_ABBR_CI = f"(?i:{_alt(STREET_ABBREVIATIONS)})"
_SETTLEMENT_ABBR_CI = f"(?i:{_alt(SETTLEMENT_ABBREVIATIONS)})"
# Main building prefixes (exclude bare "к" — it only works as corpus in annex)
_BUILDING_ABBR_CI = f"(?i:{_alt(BUILDING_UNIT_ABBREVIATIONS - {'к'})})"
_BUILDING_ANNEX_CI = r"(?i:корпус|корп|стр|строение|литера|лит|к)"
_ROOM_ABBR_CI = f"(?i:{_alt(ROOM_UNIT_ABBREVIATIONS)})"
_REGION_SUFFIX_CI = f"(?i:{_alt(REGION_SUFFIXES)})"

# Between-component separator (comma, semicolon, any whitespace incl. newline)
_SEP = r"[,;\s]+"


# ---------------------------------------------------------------------------
# Primitive source strings (used to build primitives AND composites)
# ---------------------------------------------------------------------------
_POSTAL = r"\b\d{6}\b"

# Leading boundary: ensures abbrevs like "д" / "ул" don't match inside words
# like "МКАД" or "аульск". Uses negative lookbehind on word chars.
_LB = r"(?<![А-Яа-яЁёA-Za-z])"

# City / settlement: abbrev + capitalized name (supports multi-word & hyphen)
_CITY = (
    rf"{_LB}{_SETTLEMENT_ABBR_CI}\b\.?\s*"
    rf"{_NAME_SEQUENCE}"
)

# Region: either "Name (область|край|р-н|...)" OR "Республика Name"
_REGION = (
    rf"(?:"
    rf"{_LB}{_NAME_TOKEN}\s+{_REGION_SUFFIX_CI}\b\.?"
    rf"|"
    rf"{_LB}(?i:республик[аи]|область|округ|край)\s+{_NAME_TOKEN}(?:-{_NAME_TOKEN})?"
    rf")"
)

# Street: abbrev + optional "им." + optional ordinal "1-я" + name
_STREET = (
    rf"{_LB}{_STREET_ABBR_CI}\b\.?\s*"
    rf"(?:им\.?\s*)?"
    rf"(?:\d+-?[а-яё]{{1,3}}\s+)?"
    rf"{_NAME_SEQUENCE}"
)

# House: main building number + up to 4 optional annex parts (корп/стр/литера)
_HOUSE = (
    rf"{_LB}{_BUILDING_ABBR_CI}\b\.?\s*\d+[А-Яа-яA-Za-z]?"
    rf"(?:[,\s]+{_LB}{_BUILDING_ANNEX_CI}\b\.?\s*(?:\d+[А-Яа-яA-Za-z]?|[А-ЯA-Z]))"
    rf"{{0,4}}"
)

# Room / office / помещение
_UNIT = rf"{_LB}{_ROOM_ABBR_CI}\b\.?\s*\d+[А-Яа-яA-Za-z]?"

# Points of interest (ring roads, km markers)
_POI = (
    r"(?:МКАД|КАД|ТТК|ВКАД|Садов(?:ое|ого)\s+кольц[оеа])"
    r"(?:[,\s]+\d+(?:-?[йеояго])?\s*км)?"
)


# ---------------------------------------------------------------------------
# Compiled primitives (used by LocationRuleEngine for span expansion)
# ---------------------------------------------------------------------------
POSTAL_RE = re.compile(_POSTAL)
REGION_RE = re.compile(_REGION)
CITY_RE = re.compile(_CITY)
STREET_RE = re.compile(_STREET)
HOUSE_RE = re.compile(_HOUSE)
UNIT_RE = re.compile(_UNIT)
POI_RE = re.compile(_POI)

# Union primitive — any address component; drives the rightward/leftward walk
ADDRESS_EXPANSION_RE = re.compile(
    f"(?:{_POSTAL}|{_REGION}|{_CITY}|{_STREET}|{_HOUSE}|{_UNIT}|{_POI})"
)


# ---------------------------------------------------------------------------
# Composite variants (ordered from widest to narrowest)
# ---------------------------------------------------------------------------

# 1. FULL: POSTAL? + REGION* + CITY? + STREET? + HOUSE + UNIT?
FULL_ADDRESS_RE = re.compile(
    rf"(?:{_POSTAL}{_SEP})?"
    rf"(?:{_REGION}{_SEP}){{0,3}}"
    rf"(?:{_CITY}{_SEP})?"
    rf"(?:{_STREET}{_SEP})?"
    rf"{_HOUSE}"
    rf"(?:{_SEP}{_UNIT})?"
)

# 2. POSTAL + REGION? + CITY — when street is in a different paragraph
POSTAL_CITY_RE = re.compile(
    rf"{_POSTAL}{_SEP}"
    rf"(?:{_REGION}{_SEP}){{0,2}}"
    rf"{_CITY}"
)

# 3. CITY + STREET (no house number)
CITY_STREET_RE = re.compile(
    rf"{_CITY}{_SEP}{_STREET}(?![А-Яа-яЁё])"
)

# 4. Prepositional / inflected form: "на улице Тверской", "по Ленинскому проспекту"
PREPOSITIONAL_STREET_RE = re.compile(
    r"(?:на|по)\s+"
    r"(?:"
    r"(?i:улиц[еуою]|проспект[еу]|шоссе|набережн[ойую]|бульвар[еу]|переулк[еу]|площад[ии])"
    r"\s+[А-ЯЁ][А-Яа-яЁё-]+"
    r"(?:[\s-][А-ЯЁ][А-Яа-яЁё-]+){0,2}"
    r"|"
    r"[А-ЯЁ][А-Яа-яЁё-]+(?:[\s-][А-ЯЁ][А-Яа-яЁё-]+){0,2}"
    r"\s+(?i:улиц[еуою]|проспект[еу]|шоссе|набережн[ойую]|бульвар[еу]|переулк[еу]|площад[ии])"
    r")"
)

# 5. POI-based
POI_ADDRESS_RE = re.compile(_POI)

# 6. Prefixed with "адрес:" — narrow fallback for lowercase "адрес: ..."
PREFIXED_ADDRESS_RE = re.compile(
    rf"(?i:адрес)[:\s]+"
    rf"(?:{_POSTAL}{_SEP})?"
    rf"(?:{_REGION}{_SEP}){{0,3}}"
    rf"(?:{_CITY}{_SEP})?"
    rf"{_STREET}"
    rf"(?:{_SEP}{_HOUSE})?"
    rf"(?:{_SEP}{_UNIT})?"
)
