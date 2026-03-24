# CHANGELOG.md — История изменений LegalDesk

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/)
Версионирование: [SemVer](https://semver.org/lang/ru/)

---

## [Unreleased]

### Планируется
- Фаза 5: Интеграция с реальным API КонсультантПлюс

---

## [0.2.0] — 2026-03-24

### Добавлено
- Premium UI: полностью собственная дизайн-система (CSS custom properties, компоненты)
- GET /health endpoint: JSON со статусом Ollama, версией, degraded mode
- Обработка ошибок: пустой текст, текст >50000, exception в anonymize/search, 404, 500
- Логирование: setup_logging(), кол-ва и статусы без ПДн
- helpers.py: highlight_spans(), highlight_tokens() (XSS-safe через markupsafe)
- Step indicator: трёхшаговый визуальный прогресс (ввод → проверка → результат)
- Шаблон error.html для 404/500 страниц
- SECRET_KEY из env LEGALDESK_SECRET_KEY (dev fallback + WARNING)
- MAX_CONTENT_LENGTH = 100KB
- make check (lint + test)
- 14 новых тестов (health, ошибки, XSS, cookie flags, highlight helpers)

### Изменено
- Полная переработка CSS: удалён Pico CSS, собственная дизайн-система с нуля
- Все шаблоны переработаны: header + навигация, step-indicator, split-view, badges, stats-bar
- app.py: рефакторинг с helpers.py, логированием, обработкой ошибок
- Makefile: обновлён make run (host + port + debug), добавлен make check
- README.md: env переменные, первый запуск, degraded режим

### Удалено
- pico.min.css (заменён собственным CSS)

---

## [0.1.1] — 2026-03-24

### Добавлено
- Web UI с Review Gate: 6 маршрутов Flask (/, /anonymize, /review, /approve, /result, /new)
- Server-side in-memory SessionStore с TTL (ПДн не в cookie)
- StubProvider: 5 хардкоженных норм права по ДТП
- Шаблоны: input.html, review.html, result.html
- `span_id` свойство в DetectedSpan, `source="manual"` для ручных замен
- 22 новых теста (7 session_store, 2 stub_provider, 13 web)

---

## [0.1.0] — 2026-03-23

### Добавлено
- Typed Anonymizer: EntityType (23 типа ПДн для ДТП-домена)
- Regex-паттерны для 12 типов ПДн (INN, SNILS, PHONE, PASSPORT, EMAIL и др.)
- OllamaClient: sync httpx клиент для Ollama API с graceful degradation
- Overlap resolver: большее покрытие побеждает, LLM > regex при равенстве
- AnonymizerConfig (pydantic-settings, env_prefix LEGALDESK_)
- Pipeline: anonymize(), deanonymize(), anonymize_with_regex()
- Структура проекта: src/legaldesk/{anonymizer,legal_engine,web}
- pyproject.toml: Flask, Pydantic, httpx, ruff, mypy strict, pytest-cov
- Makefile: install, lint, test, run
- CI: GitHub Actions (lint + test на каждый push)
- CLAUDE.md, CONSTITUTION.md, AGENTS.md, CONTINUITY.md
- 54+ тестов, покрытие 87%+

### Статус
- make lint: чисто
- make test: 54+ passed
