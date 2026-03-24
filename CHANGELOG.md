# CHANGELOG.md — История изменений LegalDesk

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/)
Версионирование: [SemVer](https://semver.org/lang/ru/)

---

## [Unreleased]

### Планируется
- Фаза 3: Legal Engine — интеграция с КонсультантПлюс API
- Фаза 4: Полный цикл — сборка и полировка

---

## [0.3.0] — 2026-03-24

### Добавлено
- Web UI с Review Gate: 6 маршрутов Flask (/, /anonymize, /review, /approve, /result, /new)
- Server-side in-memory SessionStore с TTL (ПДн не в cookie)
- StubProvider: 5 хардкоженных норм права по ДТП
- Шаблоны: input.html (ввод + ошибка), review.html (две колонки, таблица span'ов, ручная замена, degraded_confirm), result.html (карточки)
- Pico CSS подключён локально (CDN запрещён CONSTITUTION Art 4.3)
- Стили: .columns, mark.pdn, mark.token, .warning-banner, .error, .result-card, .text-display
- `span_id` свойство в DetectedSpan, `source="manual"` для ручных замен
- 22 новых теста (7 session_store, 2 stub_provider, 13 web)

---

## [0.2.0] — 2026-03-23

### Добавлено
- Typed Anonymizer: EntityType (23 типа ПДн для ДТП-домена)
- Regex-паттерны для 12 типов ПДн (INN, SNILS, PHONE, PASSPORT, EMAIL и др.)
- OllamaClient: sync httpx клиент для Ollama API с graceful degradation
- Overlap resolver: большее покрытие побеждает, LLM > regex при равенстве
- AnonymizerConfig (pydantic-settings, env_prefix LEGALDESK_)
- Pipeline: anonymize(), deanonymize(), anonymize_with_regex()
- 54+ тестов (resolver, regex, pipeline, config)

---

## [0.1.0] — 2026-03-23

### Добавлено
- Структура проекта: src/legaldesk/{anonymizer,legal_engine,web}
- pyproject.toml: Flask, Pydantic, httpx, ruff, mypy strict, pytest-cov
- Makefile: install, lint, test, run
- CI: GitHub Actions (lint + test на каждый push)
- Заглушки всех модулей
- 13 тестов, покрытие 87%
- CLAUDE.md — инструкции для Claude Code
- CONSTITUTION.md — конституция проекта
- AGENTS.md — роли агентов
- CONTINUITY.md — контекст для продолжения работы

### Статус
- make lint: ✅ чисто
- make test: ✅ 13 passed
- Покрытие: 87%
