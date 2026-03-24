# CONTINUITY — журнал прогресса LegalDesk

Файл обновляется при завершении каждого шага. Используется для восстановления контекста между сессиями.

## Фаза 0: Фундамент — ЗАВЕРШЕНА

**Что сделано:**
- pyproject.toml (ruff, mypy strict, pytest-cov, flask, pydantic, httpx, pydantic-settings)
- Makefile: install, lint, test, run
- .github/workflows/ci.yml
- Структура каталогов src/legaldesk/{anonymizer,legal_engine,web}
- Все __init__.py, заглушки модулей
- 13 базовых тестов — зелёные

## Фаза 1: Anonymizer — В ПРОЦЕССЕ

### Шаг 2: Typed Anonymizer — ЗАВЕРШЁН

**Файлы созданы/изменены:**
- `src/legaldesk/anonymizer/models.py` — EntityType (23 типа), DetectedSpan, AnonymizationResult
- `src/legaldesk/anonymizer/config.py` — AnonymizerConfig (pydantic-settings, env_prefix LEGALDESK_)
- `src/legaldesk/anonymizer/regex_patterns.py` — 12 паттернов (INN, SNILS, PHONE, PASSPORT, EMAIL, BANK_ACCOUNT, BANK_CARD, BIK, LICENSE_PLATE, VIN, INSURANCE_POLICY, VEHICLE_REGISTRATION)
- `src/legaldesk/anonymizer/resolver.py` — resolve_overlaps (покрытие > LLM-приоритет)
- `src/legaldesk/anonymizer/llm_client.py` — OllamaClient.detect (sync httpx, fallback на [], никогда не логирует ПДн)
- `src/legaldesk/anonymizer/anonymizer.py` — anonymize(), deanonymize(), anonymize_with_regex()

**Тесты:**
- `tests/test_resolver.py` — 7 тестов overlap resolver
- `tests/test_regex_patterns.py` — 30+ тестов паттернов
- `tests/test_anonymizer.py` — 13 тестов (roundtrip, no-leaks, degraded, mock LLM)
- `tests/test_config.py` — 4 теста конфигурации

**Архитектурные решения:**
- Позиционная замена с конца текста → корректные индексы при множественных заменах
- BANK_ACCOUNT (20 цифр) проверяется до INN (10-12 цифр) в ALL_PATTERNS
- DRIVERS_LICENSE и VEHICLE_PASSPORT не имеют regex (формат совпадает с PASSPORT/VEHICLE_REGISTRATION) — LLM различает по контексту
- degraded=True если LLM вернула пустой список при use_llm=True

**Следующий шаг (Шаг 3):** Web UI — Flask-эндпоинты, формы ввода/проверки замен, интеграция с AnonymizationResult.
