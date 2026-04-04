"""Context dictionaries and lemma-aware helpers used by local entity rules."""

from __future__ import annotations

from backend.core.entity_rules.common import (
    contains_any_lemma,
    extract_window,
    lemmatize_text_tokens,
    normalize_entity_text,
)


PROCEDURAL_ROLES = {
    "истец",
    "ответчик",
    "заявитель",
    "представитель",
    "адвокат",
    "директор",
    "работник",
    "работодатель",
    "арендатор",
    "арендодатель",
    "заказчик",
    "исполнитель",
    "покупатель",
    "продавец",
    "сторона",
    "свидетель",
    "гражданин",
    "гражданка",
}

GOVERNMENT_BODIES = {
    "прокуратура",
    "следственный комитет",
    "роскомнадзор",
    "министерство",
    "минюст",
    "росреестр",
    "фнс",
    "фсб",
    "мвд",
    "гибдд",
    "администрация",
    "департамент",
    "управление",
    "служба",
    "комитет",
}

COURT_TERMS = {
    "верховный",
    "арбитражный",
    "конституционный",
    "суд",
    "судебный",
}

LEGAL_CODES = {
    "гк",
    "гк рф",
    "тк",
    "тк рф",
    "нк",
    "нк рф",
    "ук",
    "ук рф",
    "коап",
    "гпк",
    "гпк рф",
    "упк",
    "упк рф",
    "апк",
    "апк рф",
    "кодекс",
}

GENERIC_LEGAL_TERMS = {
    "договор",
    "соглашение",
    "приложение",
    "федерация",
    "российский",
    "город",
    "улица",
    "компания",
    "общество",
    "банк",
    "далее",
    "ранее",
    "также",
}

TABLE_HEADER_TERMS = {
    "оплачено",
    "сумма",
    "вид",
    "период",
    "день",
    "месяц",
    "год",
    "остаток",
    "начислено",
    "удержано",
    "итого",
    "всего",
    "тариф",
    "ставка",
    "платеж",
    "оплата",
    "выплата",
    "начисление",
    "удержание",
    "размер",
    "количество",
    "дата",
    "номер",
    "счет",
    "счёт",
    "услуга",
    "показатель",
    "баланс",
    "приход",
    "расход",
}

PERSON_CONTEXT_WORDS = {
    "гражданин",
    "гражданка",
    "гр.",
    "гр-н",
    "представитель",
    "заявитель",
    "истец",
    "ответчик",
    "адвокат",
    "подписал",
    "подписала",
    "подписавший",
    "доверенность",
    "директор",
    "генеральный",
    "паспорт",
    "телефон",
    "почта",
    "адрес",
    "зарегистрирован",
    "проживает",
    "проживающий",
    "свидетель",
    "направил",
    "направила",
    "подал",
    "подала",
    "явился",
    "явилась",
}

PERSON_ALIAS_PREFIXES = (
    "гр",
    "гр-н",
    "гражданин",
    "гражданка",
    "представитель",
    "заявитель",
    "адвокат",
    "директор",
)

ORG_SHORT_FORMS = (
    "ООО",
    "АО",
    "ПАО",
    "ОАО",
    "ЗАО",
    "НКО",
    "ГУП",
    "МУП",
    "АНО",
    "ФГУП",
    "ГБУ",
    "МБУ",
    "ИП",
)

ORG_LONG_FORMS = (
    "Общество с ограниченной ответственностью",
    "Акционерное общество",
    "Публичное акционерное общество",
    "Закрытое акционерное общество",
    "Открытое акционерное общество",
)

ORG_KEYWORDS = {
    "банк",
    "компания",
    "общество",
    "министерство",
    "департамент",
    "управление",
    "служба",
    "администрация",
    "комитет",
    "инспекция",
    "фонд",
    "агентство",
    "предприятие",
    "центр",
}


def _lemma_set(terms: set[str] | tuple[str, ...]) -> set[str]:
    lemmas: set[str] = set()
    for term in terms:
        lemmas.update(lemmatize_text_tokens(term))
    return lemmas


PROCEDURAL_ROLE_LEMMAS = _lemma_set(PROCEDURAL_ROLES)
GOVERNMENT_BODY_LEMMAS = _lemma_set(GOVERNMENT_BODIES)
COURT_TERM_LEMMAS = _lemma_set(COURT_TERMS)
LEGAL_CODE_LEMMAS = _lemma_set(LEGAL_CODES)
GENERIC_LEGAL_LEMMAS = _lemma_set(GENERIC_LEGAL_TERMS)
TABLE_HEADER_LEMMAS = _lemma_set(TABLE_HEADER_TERMS)
ORG_KEYWORD_LEMMAS = _lemma_set(ORG_KEYWORDS)
PERSON_CONTEXT_LEMMAS = _lemma_set(PERSON_CONTEXT_WORDS)

PERSON_STOPWORD_LEMMAS = (
    PROCEDURAL_ROLE_LEMMAS
    | GOVERNMENT_BODY_LEMMAS
    | COURT_TERM_LEMMAS
    | LEGAL_CODE_LEMMAS
    | GENERIC_LEGAL_LEMMAS
    | TABLE_HEADER_LEMMAS
)

ORG_STOPWORD_LEMMAS = PROCEDURAL_ROLE_LEMMAS | GOVERNMENT_BODY_LEMMAS | COURT_TERM_LEMMAS | LEGAL_CODE_LEMMAS
ROLE_OR_GENERIC_LEMMAS = PROCEDURAL_ROLE_LEMMAS | GOVERNMENT_BODY_LEMMAS | GENERIC_LEGAL_LEMMAS | TABLE_HEADER_LEMMAS


def has_nearby_context(text: str, start: int, end: int, words: set[str]) -> bool:
    """Return True when nearby text contains any normalized context marker."""

    context = extract_window(text, start, end)
    if any(word in context for word in words):
        return True
    return contains_any_lemma(context, _lemma_set(words))


def contains_any_normalized(value: str, terms: set[str]) -> bool:
    """Return True when normalized text contains any normalized dictionary term."""

    lowered = normalize_entity_text(value)
    return any(term in lowered for term in terms)


def contains_any_lemma_term(value: str, lemmas: set[str]) -> bool:
    """Return True when any token lemma of the value belongs to the lemma set."""

    return contains_any_lemma(value, lemmas)
