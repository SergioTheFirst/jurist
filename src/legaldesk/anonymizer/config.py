"""Конфигурация анонимизатора через переменные окружения."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AnonymizerConfig(BaseSettings):
    """Настройки Ollama и pipeline анонимизации.

    Все поля переопределяются через env-переменные с префиксом LEGALDESK_
    или через файл .env в корне проекта.
    """

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_models_path: str = r"C:\Users\Администратор\.ollama\models"
    ollama_timeout: float = 60.0
    use_llm: bool = True

    model_config = SettingsConfigDict(
        env_prefix="LEGALDESK_",
        env_file=".env",
        env_file_encoding="utf-8",
    )
