"""Тесты конфигурации AnonymizerConfig."""

from __future__ import annotations

from legaldesk.anonymizer.config import AnonymizerConfig


def test_default_values() -> None:
    """Дефолтные значения конфига без переменных окружения."""
    # Убеждаемся, что тест не зависит от реального .env файла
    config = AnonymizerConfig(
        _env_file=None,  # type: ignore[call-arg]
    )
    assert config.ollama_base_url == "http://localhost:11434"
    assert config.ollama_model == "llama3.1:8b"
    assert config.ollama_timeout == 60.0
    assert config.use_llm is True


def test_override_via_env(monkeypatch: object) -> None:  # type: ignore[type-arg]
    """Значения переопределяются через переменные окружения."""
    import pytest
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("LEGALDESK_OLLAMA_MODEL", "mistral:7b")
        mp.setenv("LEGALDESK_USE_LLM", "false")
        mp.setenv("LEGALDESK_OLLAMA_TIMEOUT", "30.0")
        config = AnonymizerConfig(_env_file=None)  # type: ignore[call-arg]

    assert config.ollama_model == "mistral:7b"
    assert config.use_llm is False
    assert config.ollama_timeout == 30.0


def test_env_file_loading(tmp_path: object) -> None:  # type: ignore[type-arg]
    """Значения загружаются из файла .env."""
    import pathlib

    import pytest

    env_file = pathlib.Path(str(tmp_path)) / ".env"
    env_file.write_text(
        "LEGALDESK_OLLAMA_MODEL=codellama:7b\nLEGALDESK_USE_LLM=false\n",
        encoding="utf-8",
    )

    with pytest.MonkeyPatch.context() as mp:
        # Очищаем env-переменные чтобы файл был основным источником
        mp.delenv("LEGALDESK_OLLAMA_MODEL", raising=False)
        mp.delenv("LEGALDESK_USE_LLM", raising=False)
        config = AnonymizerConfig(_env_file=str(env_file))  # type: ignore[call-arg]

    assert config.ollama_model == "codellama:7b"
    assert config.use_llm is False


def test_use_llm_false_constructor() -> None:
    """Можно передать use_llm=False напрямую в конструктор."""
    config = AnonymizerConfig(use_llm=False, _env_file=None)  # type: ignore[call-arg]
    assert config.use_llm is False
