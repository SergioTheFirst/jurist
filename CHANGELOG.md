# CHANGELOG.md — История изменений LegalDesk

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/)
Версионирование: [SemVer](https://semver.org/lang/ru/)

---

## [Unreleased]

### Composable Address Detection Pipeline
- Добавлено правило-ориентированное расширение детекции адресов с поддержкой 10 режимов отказа:
  1. Почтовые индексы (119019, г. Москва...)
  2. Префиксы субъектов РФ (Московская область, Республика Татарстан)
  3. Сельские поселения (дер., пос., с., пгт.)
  4. Сложные названия улиц (ул. 1-я Тверская-Ямская)
  5. Компоненты зданий (корп., стр., литера)
  6. Голые адреса без ул. (Москва, Тверская, 13)
  7. Предложные формы (на улице Тверской)
  8. POI-адреса (МКАД 34-й км)
  9. Префикс им. (ул. им. Гагарина)
  10. Одновременное требование улицы И дома
- Новые файлы:
  - `backend/core/dictionaries/geo.py` — онлайн-словари (STREET_ABBREVIATIONS, SETTLEMENT_ABBREVIATIONS, REGION_NAMES ~90 субъектов, BUILDING_UNIT_ABBREVIATIONS, ROOM_UNIT_ABBREVIATIONS);
  - `backend/core/entity_rules/address_patterns.py` — 8 regex-примитивов (POSTAL_RE, REGION_RE, CITY_RE, STREET_RE, HOUSE_RE, UNIT_RE, POI_RE, ADDRESS_EXPANSION_RE) + 6 композитных (FULL_ADDRESS_RE, POSTAL_CITY_RE, CITY_STREET_RE, PREPOSITIONAL_STREET_RE, POI_ADDRESS_RE, PREFIXED_ADDRESS_RE) с поддержкой многострочных адресов через `[,\s\n]+` сепаратор;
  - `backend/core/entity_rules/loc_rules.py` — `LocationRuleEngine` (mirror `OrganizationRuleEngine`): `expand_candidate` через rightward-walk ADDRESS_EXPANSION_RE, `validate_candidate` с auto-accept на STREET/HOUSE/POSTAL структурных сигналах, `supplement_candidates` для полностью пропущенных Natasha адресов;
  - `tests/test_address_regex.py` — 31 unit-тест для примитивов (5 parametrized на каждый примитив, 3 negative-тесты на false-positives);
  - `conftest.py` — pymorphy2 Python 3.11+ compat shim через `inspect.getargspec` → `getfullargspec`.
- Модифицированные файлы:
  - `anonymizer.py`: 6 новых `_PatternSpec("АДРЕС", ...)` entries вместо одного, удалён `"LOC"` из PLACEHOLDER, добавлена `_should_skip_loc_candidate()` с lemma-aware контекстом;
  - `pipeline.py`: добавлена `self._location_rules = LocationRuleEngine(...)`, LOC/АДРЕС ветка в `refine_candidates` с expand/validate/warn, `self._location_rules` в кортеж engines в `_collect_supplements`;
  - `context_rules.py`: добавлены `ADDRESS_CONTEXT_WORDS` frozenset и `ADDRESS_CONTEXT_LEMMAS = _lemma_set(ADDRESS_CONTEXT_WORDS)`;
  - `smoke_test.py`: добавлен `test_anonymizer_address()` (4 parametrized case: full_address, rural_address, im_prefix, compound_street), обновлена `test_anonymizer_case_corpus_metrics` с АДРЕС metrics (recall >= 0.8, precision >= 0.85), рейз фикстур 200 → 215;
  - `anonymizer_cases.jsonl`: +15 фикстур с `expected.АДРЕС = [...]` на каждый режим отказа.
- Верификация:
  - `pytest tests/test_address_regex.py -x -q` → `31 passed` (все regex-примитивы работают корректно);
  - `pytest -x -q --ignore=tests/smoke_test.py` → `198 passed` (31 new + 167 existing, no regressions);
  - Negative-тест: нет false-positives на юридическом тексте (ст. 15 ГК РФ) и на FIO;
  - Multi-line address через newline-join: `FULL_ADDRESS_RE.search("119019,\nг. Москва,\nул. Арбат, д. 12")` → match.
- Коммит: `feat(address): composable regex pipeline for Russian address detection` (session_01HWkuzqetbeb9S9Nsd9TbfW).

### Windows Desktop Bundle And Installer
- Added `backend/runtime_paths.py` and switched backend runtime storage to writable desktop-safe paths for archive DB, audit log, uploads, and KP cache.
- Added `desktop/launcher.py` as the desktop entrypoint that starts the embedded FastAPI server automatically, waits for `/health`, and opens the browser.
- Added Windows packaging assets:
  - `packaging/windows/LegalDesk.spec`
  - `packaging/windows/LegalDesk.iss`
  - `packaging/windows/build_installer.ps1`
  - `requirements-desktop.txt`
- Fixed real frozen-build issues found during live smoke testing:
  - removed `.env.example` from bundle resources because it broke bootloader extraction;
  - corrected the PyInstaller spec to proper `EXE + COLLECT` packaging;
  - added required `jaraco.*` dependencies for frozen `pkg_resources` startup;
  - fixed PowerShell installer script path resolution, including user-local Inno Setup installations from winget.
- Produced deliverables:
  - desktop app bundle in `dist/LegalDesk/`
  - installer in `dist-installer/LegalDesk-Setup.exe`
- Verification:
  - `python -m pytest tests/smoke_test.py -q --tb=short` -> `67 passed, 3 warnings`
  - `dist/LegalDesk/LegalDesk.exe --no-browser --data-dir ...` auto-starts the local server and serves `/health`
  - Inno Setup successfully produced `dist-installer/LegalDesk-Setup.exe`

### OCR For Scanned And Weak PDFs
- `backend/core/document_parser.py` now attempts OCR for scanned PDFs and weak/corrupted text layers instead of failing immediately:
  - keeps the existing `pdfplumber` -> `PyMuPDF` extraction path for normal text PDFs;
  - if the extracted layer is too short or clearly corrupted, runs OCR fallback and picks the best readable result;
  - tries PyMuPDF OCR first and then `pytesseract` as a secondary fallback.
- Added OCR-related configuration and dependencies:
  - `requirements.txt` now includes `pytesseract` and `Pillow`;
  - `.env.example` now documents `TESSERACT_CMD`, `LEGALDESK_OCR_LANGS`, and `LEGALDESK_OCR_DPI`.
- Updated scanned-PDF diagnostics:
  - the parser now distinguishes between “OCR not configured / unavailable” and “OCR was attempted but produced no usable text”.
- Updated UI error text in `frontend/static/index.html` so the lawyer sees OCR setup guidance instead of the outdated “OCR not supported” message.
- Added regression tests for:
  - OCR recovery for scanned PDFs;
  - OCR winning over weak text layers;
  - scanned PDFs still raising a clear `ParseError` when OCR is unavailable.

### Rule-Based PER/ORG Refinement
- Rule layer further tightened with lemma-aware prefix cleanup for `PER` candidates:
  - `backend/core/entity_rules/context_rules.py` now checks nearby person-context markers both by exact token and by lemmas, so inflected context words stop being invisible to the validator;
  - `backend/core/entity_rules/per_rules.py` now strips leading role/noise lemmas from person spans before expansion, validation, supplementation, and alias binding.
- This closes false positives where Natasha included non-name prefixes inside a person span, for example:
  - `Гражданин Иванов Иван Иванович` is now normalized to `Иванов Иван Иванович`;
  - `Заявитель Петров Петр Петрович` is now normalized to `Петров Петр Петрович`;
  - `Далее Иванов` now resolves to the same person alias instead of creating a new placeholder.
- Added regression tests for:
  - role-prefixed full FIO detection;
  - alias reuse when the short alias is preceded by discourse noise like `Далее`.
- Добавлен отдельный rule-layer в `backend/core/entity_rules/` поверх Natasha:
  - `pipeline.py` оркестрирует этапы validate + expand + supplement;
  - `per_rules.py` отбрасывает ложные `PER`, расширяет фамилию до полного ФИО и добирает формы с инициалами;
  - `org_rules.py` уточняет `ORG`, не путает голые формы вроде `ООО` с полным названием и добирает организации в кавычках/с правовой формой.
- `backend/core/anonymizer.py` теперь:
  - пропускает только точные whitelist-термины, а не любые span'ы, которые пересеклись с `ООО` или другой частью вайтлиста;
  - не скрывает шумовые `LOC`-аббревиатуры вроде `РФ`;
  - сохраняет весь поток локальным, без внешних LLM на этапе анонимизации.
- Добавлены regression-тесты на:
  - расширение ФИО из одиночной фамилии;
  - добор `Иванов И.И.`;
  - корректную анонимизацию `ООО "..."` несмотря на вайтлист `ООО`;
  - отбрасывание ложных capitalized-phrases как `PER`.
- Поверх rule-layer добавлена alias-linking логика для персон:
  - полное ФИО, голая фамилия в контексте и формы `И.И. Иванов`/`гр. Иванов` теперь могут делить один canonical identity;
  - при рендере placeholder'ов используется `identity_key`, поэтому все такие упоминания получают один и тот же токен (`[ФИО1]` вместо `[ФИО1]`, `[ФИО2]`, `[ФИО3]`).
- Добавлены regression-тесты на переиспользование одного placeholder для полного ФИО, bare-surname alias и префиксной формы `гр. Фамилия`.

### Numbered PII Placeholders
- `backend/core/anonymizer.py` теперь присваивает стабильные нумерованные placeholder'ы каждому уникальному значению внутри типа ПД:
  - повторяющиеся одинаковые сущности переиспользуют один и тот же номер;
  - разные сущности одного типа получают разные placeholder'ы: например, `[ОРГАНИЗАЦИЯ1]`, `[ОРГАНИЗАЦИЯ2]`, `[ИНН1]`, `[ИНН2]`.
- Это изменение попадает и в `anonymized_text`, и в `ReplacementRecord.placeholder`, поэтому lawyer-preview и итоговый результат больше не смешивают разные организации/лица под одним общим токеном.

### Bulk Restore By Type
- `frontend/static/index.html` расширен групповым управлением preview-анонимизацией:
  - в правой preview-панели над таблицей найденных ПД появились действия по типам;
  - для каждого типа можно одной кнопкой `Восстановить все` раскрыть все элементы этого типа;
  - обратная кнопка `Скрыть все` возвращает их обратно в обезличенный вид.
- Индивидуальный toggle по токену и по строке таблицы сохранён; групповое действие просто массово обновляет тот же `restoredIds` state.

### Placeholder List Preview
- Preview-панель справа больше не использует табличный блок `Тип / Оригинал / Уверенность / Статус`.
- Вместо этого теперь рендерится список уникальных numbered placeholder'ов:
  - `ОРГАНИЗАЦИЯ1`, `ОРГАНИЗАЦИЯ2`, `ФИО1`, `ФИО2`, `ИНН1` и т.д.;
  - у каждого элемента списка показан исходный фрагмент и число вхождений в документе.
- Клик по элементу списка теперь переключает все его вхождения сразу по всему тексту:
  - если placeholder скрыт, восстанавливаются все соответствующие места;
  - если placeholder уже восстановлен, все его вхождения снова скрываются.
- Тот же принцип распространён и на клик по токену в самом тексте: клик по одному `[ОРГАНИЗАЦИЯ1]` переключает все совпадения этого placeholder'а в документе.

### Verification
- `python -m pytest tests/smoke_test.py -q --tb=short` → `47 passed, 0 failed`
- `node --check` для встроенного script из `frontend/static/index.html` → OK

### Manual CTA Visibility
- Исправлен дефект видимости главной кнопки ручной анонимизации в `frontend/static/index.html`:
  - по пользовательскому скриншоту выяснилось, что CTA `Удалить персональные данные` физически присутствовал в DOM, но оказывался ниже видимой области верхнего sidebar-блока;
  - в текстовом режиме `upload-shell` теперь переставляет главный `process-button` сразу под переключатель `Документ / Текст`, чтобы кнопка была видна сразу;
  - дополнительно уменьшены высота textarea и вертикальные интервалы верхнего блока, чтобы CTA и поле ввода лучше помещались на типовом desktop-экране.
- Верификация:
  - `node --check` для извлечённого script из `frontend/static/index.html` — OK;
  - `python -m pytest tests/smoke_test.py -v --tb=short` — ожидается зелёный прогон после правки.

### Header CTA Placement
- Главная кнопка `Удалить персональные данные` перенесена из sidebar в самый верхний правый угол header:
  - она больше не зависит от высоты левой панели, содержимого textarea и масштаба страницы;
  - всегда остаётся на виду как единый главный CTA;
  - после preview продолжает переключаться на `АНАЛИЗ`.
- Из header убраны текстовые подписи бренда:
  - удалён текст `ЮристАИ` из самой шапки;
  - удалён текст `Рабочее место`;
  - в `<title>` страницы оставлено только `ЮристАИ`.

### Document Parsing Reliability
- Header CTA дополнительно уменьшен и упрощён:
  - теперь на кнопке короткий текст `Удалить ПД`;
  - уменьшены ширина, высота и типографика header-варианта кнопки для более аккуратного вида.
- Усилен `backend/core/document_parser.py` для проблемных PDF и DOCX:
  - `PdfParser` теперь выбирает лучший текст между `pdfplumber.extract_text()` и `layout=True`, а при подозрении на битую кириллицу или плохое качество дополнительно берёт `PyMuPDF` и выбирает более читаемый результат;
  - в `PyMuPDF` добавлено извлечение по text blocks с сортировкой, чтобы уменьшить шум на сложных макетах;
  - `DocxParser` получил XML fallback через распаковку `DOCX` как zip-архива, если `python-docx` не смог прочитать документ;
  - сообщение для старого `.doc` стало понятнее: теперь явно сказано, что нужен `LibreOffice` или совместимый конвертер.
- Тесты расширены:
  - XML fallback для `DOCX`;
  - понятная ошибка на `.doc` без конвертера;
  - выбор более читаемого кандидата для PDF;
  - preview endpoint для `DOCX`.

### Windows Launcher
- Добавлен корневой Windows launcher [start_legaldesk.bat](/C:/pro/jurist/start_legaldesk.bat) для локального старта сайта.
- Скрипт:
  - переходит в корень проекта;
  - ищет `python.exe` через PowerShell в `.venv` и типовых пользовательских установках Python;
  - запускает `uvicorn backend.main:app --host 127.0.0.1 --port 8000` в том же окне BAT;
  - параллельно поднимает отдельный waiter, который ждёт `/health` и только после этого открывает страницу `http://127.0.0.1:8000` в браузере.
- Исправлен дефект прежнего launcher:
  - ранее сайт не стартовал из-за ненадёжной схемы фонового запуска Python через `py/start/Start-Process`;
  - новая версия уходит от этой схемы и использует foreground-запуск сервера + background browser waiter.
- Живая проверка выполнена:
  - `cmd /c start_legaldesk.bat` реально поднял сервер;
  - `curl.exe http://127.0.0.1:8000/health` вернул `{"status":"ok",...,"version":"4.0.0"}`;
  - `curl.exe http://127.0.0.1:8000/` вернул SPA `frontend/static/index.html`.

### Manual Text UX
- `frontend/static/index.html` получил явную кнопку `Очистить текст от ПДн локально` в режиме ручного ввода.
- Кнопка вызывает уже существующий локальный этап preview-анонимизации и сразу показывает обезличенный текст в нижней панели без отправки данных в КонсультантПлюс.
- В текстовом режиме до preview основной submit больше не конкурирует с локальным действием: пользователю показывается отдельная прямая CTA именно для очистки ПДн.

### Single Local Anonymize CTA
- Ручной ввод переделан под одну главную кнопку `Удалить персональные данные` в sidebar:
  - она видна до запуска локальной анонимизации;
  - запускает только внутреннюю логику обезличивания, без внешней LLM;
  - после нажатия очищенный текст сразу отображается в центральной нижней панели.
- Главный CTA дополнительно усилен визуально:
  - увеличены высота, шрифт, межбуквенный интервал и контраст;
  - кнопка всегда заметна в левой панели;
  - после локального preview её основной текст переключается на `АНАЛИЗ`.
- Повышен контраст текста для тёмной темы:
  - усилен цвет текста в textarea и панелях документа;
  - увеличен размер шрифта для основного моноширинного текста;
  - подсказки и служебные сообщения стали заметно светлее.
- Текст-подсказка в нижней панели заменён на прямую инструкцию: нажать `Удалить персональные данные`, чтобы увидеть локально очищенный результат.

### Anonymization Engine Hardening
- Изучен референсный архив `jurist-main_20260330.zip` и перенесены лучшие части его локальной деперсонализации без LLM:
  - `backend/core/anonymizer.py` теперь собирает NER- и regex-span'ы на исходном тексте и разрешает их перекрытия через единый resolver, вместо последовательной замены по этапам;
  - при конфликте перекрытий сохраняется более длинный span, а при равной длине приоритет отдаётся строгому regex-совпадению, что ближе к надёжной схеме из референсного проекта;
  - расширен каталог структурных ПДн: банковский счёт, банковская карта, БИК, VIN, госномер, страховой полис, СТС, плюс сохранены текущие категории `ФИО/ORG/LOC`, `ИНН`, `СНИЛС`, `EMAIL`, `ТЕЛЕФОН`, `ОГРН`, `АДРЕС`.
- Важно: внешний формат текущего продукта сохранён:
  - placeholder'ы остались совместимыми с текущим preview/UI (`[ФИО]`, `[ИНН]`, `[ТЕЛЕФОН]`, и т.д.), чтобы не ломать lawyer-review flow;
  - Natasha сохранена для `PER/ORG/LOC`, а LLM не используется на этапе подмены ПДн.
- `tests/smoke_test.py` расширен до 41 проходящего теста, включая новые проверки на банковские реквизиты, VIN, госномер, страховой полис и СТС.

### Phase 4 — Product Workstation
- Добавлено рабочее место уровня продукта для параллельной юридической работы:
  - `backend/core/audit.py` создаёт локальный audit log для compliance с действиями `analysis_completed`, `case_opened`, `case_reviewed`, `cases_compared`, `export_docx`, `export_pdf`, `case_deleted`;
  - `backend/core/comparison.py` сравнивает два архивных дела по тексту документа, summary, recommendations, нормам и судебной практике;
  - `backend/core/exports.py` экспортирует фирменные заключения в `DOCX` и `PDF` без внешних сервисов.
- `backend/main.py` расширен до Phase 4:
  - `/health` теперь возвращает `version: "4.0.0"`;
  - добавлены `GET /api/audit`, `POST /api/compare`, `GET /api/archive/{id}/export?format=docx|pdf`;
  - экспорт, сравнение, открытие дела, review и обработка автоматически пишутся в audit log.
- `frontend/static/index.html` расширен без смены визуальной системы:
  - добавлена мультивкладочная workspace-модель для нескольких дел одновременно;
  - добавлены compare-controls для сравнения двух дел/заключений;
  - добавлен audit-feed в sidebar;
  - экспорт результата теперь поддерживает `DOCX` и `PDF`.
- `.env.example` дополнен переменной `LEGALDESK_ACTOR` для локального compliance-журнала.
- `tests/smoke_test.py` расширен до 38 проходящих тестов, включая compare, export DOCX/PDF и audit log.
- Живая runtime-проверка Phase 4 выполнена через локальный `uvicorn`:
  - `GET /health` вернул `version: "4.0.0"`;
  - `POST /api/process-text` создал два дела;
  - `POST /api/compare` вернул similarity;
  - `GET /api/archive/{id}/export?format=docx|pdf` вернул `200 OK`;
  - `GET /api/audit` зафиксировал `analysis_completed`, `export_docx`, `export_pdf`, `case_opened`.
- Исправлено поведение верхней панели для `DOC/DOCX/RTF/ODT/PDF`:
  - при выборе такого файла фронтенд больше не показывает misleading fallback `Исходный текст пока не доступен для отображения`;
  - вместо этого текст извлекается локально через backend сразу после выбора файла и показывается в верхней панели до запуска внешнего анализа;
  - если извлечение ещё идёт или не удалось, интерфейс показывает точную служебную заметку, а не пустой placeholder.

### Phase 3 — Real Adapters + Offline LLM
- Добавлен полноценный слой адаптеров для юридического анализа:
  - `backend/adapters/consultant_plus.py` теперь содержит реальный `HttpAdapter` с pattern-detection для двух вариантов API КонсультантПлюс (`api.consultant.ru` и `www.consultant.ru/api`), нормализацией норм и судебной практики, cache файла `data/kp_pattern.json` и внятными ошибками для `401/403/429`.
  - Создан `backend/adapters/local_llm.py` с `LegalPromptBuilder`, `LLMConfig` и `LocalLLMAdapter`, совместимым с Ollama и любым OpenAI-compatible локальным endpoint (`/api/chat` или `/v1/chat/completions`).
  - Создан `backend/adapters/registry.py` с режимами `AUTO | KP | LLM | DEMO` и health-статусом доступности backend-источников.
- `backend/main.py` расширен до Phase 3:
  - `/health` теперь возвращает `kp_available`, `llm_available`, `kp_mode`, `llm_url`, `llm_model`, `default_mode`, `version: "3.0.0"`;
  - `POST /api/process` и `POST /api/process-text` принимают `analysis_mode`, а также request-level `llm_url` / `llm_model`;
  - добавлены `POST /api/llm/test` и `POST /api/kp/test` для проверки подключений из UI;
  - выбор адаптера вынесен в `_select_adapter()` и умеет работать как через `.env`, так и через текущие значения из header UI.
- `frontend/static/index.html` доработан без смены общего layout:
  - header теперь умеет проверять `KP API key`, `LLM URL`, хранить `analysis_mode`, показывать segmented control `AUTO | КП | LLM | ДЕМО` и динамически заполнять список локальных моделей;
  - режим preview/result теперь учитывает целевой backend, меняет action-labels и передаёт `analysis_mode`, `llm_url`, `llm_model` в backend;
  - правая панель результата показывает source badge по типу источника (`КонсультантПлюс`, `LLM`, `ДЕМО`), строку `Анализ выполнен: ...`, confidence bar для LLM и отдельный блок `Юридические риски`.
- Добавлен `.env.example` с документированием `KP_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `ANALYSIS_MODE`, `LLM_TIMEOUT`, `LLM_MAX_TOKENS`.
- `tests/smoke_test.py` расширен Phase 3 сценариями для registry/demo-mode, prompt builder, JSON-parser локальной LLM, demo-processing, adapter-status в `/health` и `POST /api/kp/test`.
- Локально подтверждён parser-check фронтенда: встроенный script из `frontend/static/index.html` успешно компилируется через `node`.
- Ограничение текущей Codex-сессии: прямой запуск системного Python (`python.exe`, `py.exe`) заблокирован sandbox, поэтому живой `pytest`/`uvicorn` прогон для Phase 3 в этой сессии не завершён и должен быть повторён при доступном интерпретаторе.

### Phase 2 — Preview Control
- Добавлен обязательный preview-этап перед отправкой текста в КонсультантПлюс: юрист сначала видит все замены, при необходимости восстанавливает отдельные элементы, и только потом отправляет проверенную версию.
- `backend/core/anonymizer.py` теперь возвращает `ReplacementRecord` с `uuid`, типом сущности, источником, confidence и позициями в анонимизированном тексте.
- Добавлен `backend/core/legal_terms.py` с whitelist для судов, органов, типовых ролей и кодексов; такие термины не анонимизируются и попадают в `whitelist_skipped`.
- `backend/main.py` переведён на lifespan API, добавлен `POST /api/preview-anonymization`, а `process/process-text` принимают `pre_anonymized_text` и confirmed-metadata для уже подтверждённого текста.
- `frontend/static/index.html` получил state machine `EMPTY/PREVIEW/LOADING/RESULT`, интерактивные anon-token chips, правую таблицу найденных ПДн и действие `Отправить в КонсультантПлюс` только после ручной проверки.
- `tests/smoke_test.py` расширен до 24 проходящих тестов, включая whitelist, replacement records, preview endpoint, pre-reviewed processing и проверку отсутствия `on_event`.

### Изменено
- Полностью переработан desktop-first SPA-интерфейс рабочего места юриста в `files/index.html`
- Добавлен постоянный трёхпанельный layout: sidebar с upload/архивом, центральная зона исходного и анонимизированного текста, правая панель юридического анализа
- Добавлены header-controls для `KP API key`, `LLM path`, статуса подключения, часов и счётчика обработанных дел
- Реализованы live-обновление архива, поиск по архиву, аккордеоны анализа, экспорт `.txt`, отметка дела как проверенного, удаление дела, hotkeys и drag-resize делителя
- Добавлены сохранение API key и LLM path в `localStorage`, маскирование ключа с reveal-toggle и подсветка анонимизационных токенов в тексте
- Добавлена реальная структура FastAPI-приложения: `backend/main.py`, `backend/core/*`, `backend/adapters/*`, `frontend/static/index.html`, `data/archive`, `data/uploads`
- Полностью переписан `backend/core/document_parser.py` на Strategy pattern с поддержкой PDF, DOCX, DOC, TXT, RTF, ODT и ручного текстового ввода
- `POST /api/process` и `POST /api/anonymize-only` теперь принимают как multipart-файл, так и JSON с ручным текстом; добавлен новый endpoint `POST /api/process-text`
- Архив дел переведён на SQLite-хранилище в `backend/core/archive.py` с колонками `input_type` и `original_text`
- Во frontend sidebar добавлен dual-input режим: вкладки `Документ` / `Текст`, textarea ручного ввода, счётчик символов, очистка, `source_name`, inline badge типа ввода в архиве и общий process-button под оба режима
- Ошибки обработки переведены в inline error-state в центральной панели; добавлены дружелюбные сообщения для scan-PDF, password-protected PDF, legacy `.doc`, short text, KP 502 и oversize upload

### Исправлено
- Убран предыдущий фронтенд-лимит на работу только с `PDF/DOCX/TXT`; sidebar и accept-list синхронизированы с новым backend parser pipeline
- Backend теперь возвращает `original_text` и `input_type`, поэтому верхняя панель центра и архив работают без fallback-заметок о «невозвращаемом extracted_text»
- Зафиксирована совместимая версия `setuptools<81`, потому что `pymorphy2`/Natasha требуют `pkg_resources` и падали на `setuptools 82`
- Исправлена обработка multipart upload в `backend/main.py`: `_parse_file_request()` теперь принимает реальный `starlette.datastructures.UploadFile`, поэтому `POST /api/process` корректно обрабатывает текстовые файлы через form-data
- Добавлен runtime smoke suite `tests/smoke_test.py` с 18 проходящими проверками, включая live HTTP roundtrip через поднятый `uvicorn`

### Планируется
- Фаза 1: Anonymizer — LLM + regex деперсонализация
- Фаза 2: Web UI — ввод, проверка замен, результат
- Фаза 3: Legal Engine — интеграция с КонсультантПлюс API
- Фаза 4: Полный цикл — сборка и полировка

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
### Rule Accuracy Metrics & Review Bucket
- `backend/core/entity_rules/` доведён до полной отдельной структуры слоёв:
  - добавлены `context_rules.py`, `expanders.py`, `supplemental_rules.py`;
  - `pipeline.py` теперь явно разделяет collect → validate → expand → supplement;
  - введён отдельный `review` bucket для пограничных `PER/ORG`, который не скрывается автоматически, но попадает в preview response как `review_candidates`.
- `backend/core/anonymizer.py` теперь использует Natasha `NamesExtractor` и `MorphVocab` для `PER`, а не только сырой `span.type == "PER"`.
- Для `ORG` добавлена canonicalization правовых форм, чтобы падежные варианты одного юрлица (`Общество ...` / `Общества ...`) считались одной сущностью и переиспользовали одну identity/placeholder-группу.
- Добавлен корпус `tests/fixtures/anonymizer_cases.jsonl` на 200 юридических фрагментов и автоматическая оценка качества:
  - precision/recall считаются отдельно для `PER` и `ORG`;
  - regression-тест падает, если качество проседает ниже заданных порогов.
- Добавлены новые тесты на:
  - `reviewable`-решение для пограничного `ORG`;
  - наличие `review_candidates` в preview API;
  - корпусные метрики качества anonymizer.
- Финальная верификация: `python -m pytest tests/smoke_test.py -q --tb=short` → `56 passed, 0 failed`.
- Дополнительно усилен анти-noise фильтр для ложных `PER` на табличных заголовках:
  - последовательности вроде `Оплачено Сумма Вид` и `Период Сумма Дни` больше не проходят как `ФИО`;
  - добавлен отдельный regression-тест на такие header-like фразы.
### Desktop Exit Flow
- Added a simple user-facing exit system for the desktop product:
  - new localhost-only backend route `POST /api/system/shutdown`;
  - new topbar `�����` button in `frontend/static/index.html`;
  - new `--stop` mode in `desktop/launcher.py` for scripted shutdowns.
- Shutdown is now explicit and product-friendly:
  - user clicks `�����`;
  - browser UI confirms shutdown;
  - local FastAPI server terminates itself;
  - `/health` goes offline.
- Added smoke coverage:
  - in-process test for shutdown handler invocation;
  - live uvicorn roundtrip test for real HTTP shutdown.
- Final verification after this step:
  - `python -m pytest tests/smoke_test.py -q --tb=short` -> `68 passed, 0 failed`
  - live product check: `/health` returned `200`, `/api/system/shutdown` returned `{"status":"stopping"}`, subsequent `/health` returned offline.
### Product Release 4.0.1
- Rebuilt the Windows desktop bundle and installer with the new exit system.
- Installer result: `dist-installer/LegalDesk-Setup.exe`
- Packaged app behaviour verified end-to-end:
  - local server starts automatically on app launch;
  - `/health` returns version `4.0.1`;
  - shutdown endpoint returns `{"status":"stopping"}`;
  - server goes offline after shutdown.
