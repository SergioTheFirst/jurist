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

## Фаза 1: Anonymizer — ЗАВЕРШЕНА

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

### Шаг 3: Web UI + Review Gate — ЗАВЕРШЁН

**Файлы созданы/изменены:**
- `src/legaldesk/anonymizer/models.py` — добавлен `source="manual"`, свойство `span_id`
- `src/legaldesk/web/session_store.py` — SessionStore (in-memory, TTL, opaque UUID)
- `src/legaldesk/legal_engine/stub_provider.py` — StubProvider (5 хардкоженных норм по ДТП)
- `src/legaldesk/web/app.py` — create_app() factory, 6 маршрутов (/, /anonymize, /review, /approve, /result, /new)
- `src/legaldesk/web/static/pico.min.css` — локальная копия Pico CSS (CDN запрещён CONSTITUTION Art 4.3)
- `src/legaldesk/web/static/style.css` — .columns, mark.pdn, mark.token, .warning-banner, .error, .result-card, .text-display
- `src/legaldesk/web/templates/base.html` — CDN → локальный pico.min.css
- `src/legaldesk/web/templates/input.html` — ошибка + text_value, форма → /anonymize
- `src/legaldesk/web/templates/review.html` — две колонки, таблица span'ов, ручная замена, degraded_confirm
- `src/legaldesk/web/templates/result.html` — две колонки: исходный текст + карточки результатов

**Тесты:**
- `tests/test_session_store.py` — 7 тестов (create/get, expired, delete, update, cleanup)
- `tests/test_stub_provider.py` — 2 теста (returns_list, title+snippet)
- `tests/test_web.py` — 13 тестов (полный цикл, degraded, cookie PII, CDN, new clears session)

**Архитектурные решения:**
- Server-side session store: ПДн только в памяти сервера, в cookie — opaque UUID
- span_id = `{start}:{end}:{source}:{entity_type}` — стабильный идентификатор для HTML-форм
- StubProvider реализует LegalSearchProvider Protocol (duck typing)
- `_compute_approved_text()` фильтрует span'ы по выбранным checkbox'ам + поддержка manual span
- Замена из конца текста (reverse=True по start) для корректных индексов

## Фаза 4: Сборка, полировка, premium UI — ЗАВЕРШЕНА

**Файлы созданы/изменены:**
- `src/legaldesk/logging_config.py` — setup_logging() идемпотентная настройка, StreamHandler, INFO
- `src/legaldesk/web/helpers.py` — highlight_spans(), highlight_tokens() (markupsafe, XSS-safe)
- `src/legaldesk/web/app.py` — полная переработка:
  - SECRET_KEY из env LEGALDESK_SECRET_KEY, fallback secrets.token_hex(32) + WARNING
  - MAX_CONTENT_LENGTH = 100KB
  - /health endpoint (JSON, проверка Ollama API)
  - Обработка ошибок: пустой текст, >50000 символов, exception в anonymize()/search()
  - errorhandler(404), errorhandler(500) → error.html
  - Логирование (кол-ва, статусы — без ПДн)
  - Использует helpers.py вместо inline _annotate_*
- `src/legaldesk/web/static/style.css` — полностью новая дизайн-система:
  - CSS custom properties (цвета, шрифты, тени, радиусы)
  - Компоненты: .app-header, .card, .btn, .textarea, .split-view, .replacements-table
  - mark.pdn/token/manual, .badge--regex/llm/manual, .alert--warning/danger/success
  - .step-indicator (трёхшаговый wizard), .stats-bar, .result-card, .manual-add
  - .spinner, .empty-state, .error-page, .app-footer
  - @media print
- `src/legaldesk/web/static/pico.min.css` — УДАЛЁН (свой CSS вместо Pico)
- `src/legaldesk/web/templates/base.html` — header с лого + навигация, footer с версией
- `src/legaldesk/web/templates/input.html` — step-indicator (шаг 1), card, alert для ошибок
- `src/legaldesk/web/templates/review.html` — step-indicator (шаг 2), stats-bar, split-view, replacements-table с badges, manual-add, degraded checkbox
- `src/legaldesk/web/templates/result.html` — step-indicator (шаг 3), split-view с result-cards, empty-state
- `src/legaldesk/web/templates/error.html` — универсальная страница ошибки (404, 500)
- `Makefile` — добавлен make check, обновлён make run (host + port)
- `README.md` — конфигурация, первый запуск, как работает, degraded режим

**Тесты:**
- `tests/test_highlight.py` — 5 тестов (highlight_spans, XSS escape, empty, tokens, token XSS)
- `tests/test_web.py` — 9 новых тестов (health JSON, health Ollama unavailable, text too long, empty whitespace, anonymize exception, 404 page, navigation, no CDN, cookie flags)
- Итого: 95 тестов, покрытие 92%

**Архитектурные решения:**
- Полностью свой CSS — никаких внешних зависимостей (CDN, шрифты, библиотеки)
- helpers.py вынесен из app.py для чистого разделения
- setup_logging() вызывается в create_app(), идемпотентно
- В логах НИКОГДА нет ПДн — только кол-ва и флаги
- Трёхшаговый step-indicator показывает прогресс юристу

**Статус:** MVP готов. make lint && make test зелёные. 95 тестов, 92% покрытия.
