"""Тесты pipeline анонимизации."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from legaldesk.anonymizer.anonymizer import anonymize, anonymize_with_regex, deanonymize
from legaldesk.anonymizer.config import AnonymizerConfig
from legaldesk.anonymizer.models import DetectedSpan, EntityType

# Конфиг без LLM для детерминированных тестов
_NO_LLM = AnonymizerConfig(use_llm=False)

# Текст со всеми regex-типами ПДн
_DTP_TEXT = (
    "ИНН 123456789012, СНИЛС 123-456-789 00, тел. +7 (999) 123-45-67, "
    "паспорт 45 06 123456, email: test@example.ru, "
    "р/с 40817810099910004312, БИК 044525225, карта 4276 1234 5678 9012, "
    "госномер А123ВС777, VIN 1HGBH41JXMN109186, "
    "ОСАГО ТТТ 1234567890, СТС 77 МА 123456"
)

# Значения ПДн, которых не должно быть в анонимизированном тексте
_PII_VALUES = [
    "123456789012",
    "123-456-789 00",
    "+7 (999) 123-45-67",
    "45 06 123456",
    "test@example.ru",
    "40817810099910004312",
    "044525225",
    "4276 1234 5678 9012",
    "А123ВС777",
    "1HGBH41JXMN109186",
    "ТТТ 1234567890",
    "77 МА 123456",
]


# ---------------------------------------------------------------------------
# Тесты anonymize_with_regex (backward compat)
# ---------------------------------------------------------------------------

def test_anonymize_inn_12() -> None:
    """ИНН физлица (12 цифр) заменяется токеном."""
    text = "ИНН клиента: 123456789012"
    result, mapping = anonymize_with_regex(text)
    assert "123456789012" not in result
    assert "[INN_" in result
    assert mapping.restore(result) == text


def test_anonymize_snils() -> None:
    """СНИЛС заменяется токеном."""
    text = "СНИЛС: 123-456-789 00"
    result, mapping = anonymize_with_regex(text)
    assert "123-456-789 00" not in result
    assert "[SNILS_" in result
    assert mapping.restore(result) == text


def test_anonymize_phone() -> None:
    """Телефонный номер заменяется токеном."""
    text = "Телефон: +7 (999) 123-45-67"
    result, mapping = anonymize_with_regex(text)
    assert "+7 (999) 123-45-67" not in result
    assert "[PHONE_" in result
    assert mapping.restore(result) == text


def test_anonymize_no_pdn() -> None:
    """Текст без ПДн остаётся без изменений."""
    text = "Прошу разъяснить порядок обжалования."
    result, mapping = anonymize_with_regex(text)
    assert result == text
    assert mapping.entries == {}


# ---------------------------------------------------------------------------
# Тесты нового pipeline anonymize()
# ---------------------------------------------------------------------------

def test_regex_all_types() -> None:
    """Regex находит все 12 типов ПДн с фиксированным форматом."""
    result = anonymize(_DTP_TEXT, config=_NO_LLM)
    found_types = {span.entity_type for span in result.spans}
    expected = {
        EntityType.INN,
        EntityType.SNILS,
        EntityType.PHONE,
        EntityType.PASSPORT,
        EntityType.EMAIL,
        EntityType.BANK_ACCOUNT,
        EntityType.BIK,
        EntityType.BANK_CARD,
        EntityType.LICENSE_PLATE,
        EntityType.VIN,
        EntityType.INSURANCE_POLICY,
        EntityType.VEHICLE_REGISTRATION,
    }
    assert expected.issubset(found_types), (
        f"Не найдены типы: {expected - found_types}"
    )


def test_no_pdn_leaks() -> None:
    """После анонимизации ни одно ПДн не присутствует в anonymized_text."""
    result = anonymize(_DTP_TEXT, config=_NO_LLM)
    for pii in _PII_VALUES:
        assert pii not in result.anonymized_text, (
            f"ПДн '{pii}' обнаружено в анонимизированном тексте"
        )


def test_roundtrip() -> None:
    """anonymize → deanonymize возвращает исходный текст."""
    result = anonymize(_DTP_TEXT, config=_NO_LLM)
    restored = deanonymize(result.anonymized_text, result.mapping)
    assert restored == _DTP_TEXT


def test_token_format() -> None:
    """Токены имеют формат [ENTITY_TYPE_001]."""
    result = anonymize("ИНН 123456789012", config=_NO_LLM)
    assert "[INN_001]" in result.anonymized_text


def test_same_pii_gets_same_token() -> None:
    """Одинаковый ПДн в разных местах → один токен."""
    text = "ИНН 123456789012 и снова ИНН 123456789012"
    result = anonymize(text, config=_NO_LLM)
    tokens = [t for t in result.mapping if "INN" in t]
    assert len(tokens) == 1


def test_no_pdn_text_unchanged() -> None:
    """Текст без ПДн анонимизируется в себя."""
    text = "Прошу разъяснить порядок обжалования."
    result = anonymize(text, config=_NO_LLM)
    assert result.anonymized_text == text
    assert result.spans == []
    assert not result.degraded


def test_degraded_mode(monkeypatch: object) -> None:  # type: ignore[type-arg]
    """Ollama недоступна → degraded=True, regex всё равно работает."""
    from legaldesk.anonymizer.llm_client import OllamaClient

    def _fake_detect(
        self: OllamaClient, text: str
    ) -> tuple[list[DetectedSpan], bool]:
        return [], True

    import pytest
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(OllamaClient, "detect", _fake_detect)
        config = AnonymizerConfig(use_llm=True)
        result = anonymize("ИНН 123456789012", config=config)

    assert result.degraded is True
    assert "123456789012" not in result.anonymized_text


def test_llm_bad_json(monkeypatch: object) -> None:  # type: ignore[type-arg]
    """Мусорный ответ LLM → graceful fallback, degraded=True."""
    from legaldesk.anonymizer.llm_client import OllamaClient

    def _fake_detect(
        self: OllamaClient, text: str
    ) -> tuple[list[DetectedSpan], bool]:
        return [], True  # симулирует ошибку парсинга JSON внутри OllamaClient

    import pytest
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(OllamaClient, "detect", _fake_detect)
        config = AnonymizerConfig(use_llm=True)
        result = anonymize("test@example.ru ИНН 123456789012", config=config)

    assert result.degraded is True
    assert "123456789012" not in result.anonymized_text
    assert "test@example.ru" not in result.anonymized_text


def test_ollama_client_returns_empty_on_connect_error() -> None:
    """OllamaClient.detect возвращает ([], True) при ошибке соединения."""
    from legaldesk.anonymizer.llm_client import OllamaClient

    config = AnonymizerConfig(ollama_base_url="http://127.0.0.1:1", use_llm=True)
    client = OllamaClient(config)
    spans, degraded = client.detect("тест")
    assert spans == []
    assert degraded is True


def test_ollama_client_bad_json_response() -> None:
    """OllamaClient.detect возвращает ([], True) при невалидном JSON."""
    from legaldesk.anonymizer.llm_client import OllamaClient

    config = AnonymizerConfig(use_llm=True)
    client = OllamaClient(config)

    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "не JSON"}
    mock_response.raise_for_status.return_value = None

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    mock_ctx.post.return_value = mock_response

    with patch("httpx.Client", return_value=mock_ctx):
        spans, degraded = client.detect("Иванов")

    assert spans == []
    assert degraded is True


def test_deanonymize_restores_all_tokens() -> None:
    """deanonymize заменяет все токены в произвольном тексте."""
    mapping = {"[INN_001]": "123456789012", "[PHONE_001]": "+7 (999) 000-00-00"}
    text = "ИНН: [INN_001], тел: [PHONE_001]"
    result = deanonymize(text, mapping)
    assert "123456789012" in result
    assert "+7 (999) 000-00-00" in result
