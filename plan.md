# Шаг 2: Typed Anonymizer — план реализации

## Обзор
Полная доменная модель анонимизатора: Pydantic-модели, расширенные regex, overlap resolver, OllamaClient, pipeline anonymize/deanonymize.

## Файлы к созданию/изменению

### 1. src/legaldesk/anonymizer/models.py (новый)
Pydantic-модели:
- `EntityType(StrEnum)` — PERSON, ADDRESS, PASSPORT, INN, SNILS, PHONE, EMAIL, BANK_ACCOUNT
- `DetectedSpan(BaseModel)` — text, entity_type, start, end, source (Literal["regex","llm"])
- `AnonymizationResult(BaseModel)` — original_text, anonymized_text, spans, mapping (token→original), reverse_mapping (original→token), degraded

### 2. src/legaldesk/anonymizer/regex_patterns.py (обновить)
Добавить:
- `PASSPORT_PATTERN` — `\d{2}\s?\d{2}\s?\d{6}`
- `EMAIL_PATTERN` — `[\w.-]+@[\w.-]+\.\w+`
- `BANK_ACCOUNT_PATTERN` — `\b\d{20}\b`

Ключи ALL_PATTERNS → значения EntityType (строковые). Порядок: BANK_ACCOUNT перед INN (20 цифр до 10-12), но с позиционной заменой порядок менее критичен.

### 3. src/legaldesk/anonymizer/resolver.py (новый)
`resolve_overlaps(spans: list[DetectedSpan]) -> list[DetectedSpan]`:
- Сортировка по start, затем по длине desc
- Жадный проход: если текущий span пересекается с предыдущим принятым — оставить тот, у которого больше покрытие; при равном покрытии LLM > regex
- Результат: отсортированный список без пересечений

### 4. src/legaldesk/anonymizer/llm_client.py (переписать)
Класс `OllamaClient`:
- `__init__(base_url, model="llama3.1:8b", timeout=60.0)`
- `detect(text: str) -> list[DetectedSpan]` — sync httpx POST, парсинг JSON (включая извлечение из markdown ```)
- При ошибках → пустой список, логирование без ПДн

### 5. src/legaldesk/anonymizer/anonymizer.py (переписать)
- `anonymize(text, use_llm=True) -> AnonymizationResult` — regex + LLM + resolve_overlaps + позиционная замена с конца
- `deanonymize(text, mapping) -> str` — обратная подстановка
- Сохранить `anonymize_with_regex` для обратной совместимости (делегирует в anonymize с use_llm=False)

### 6. Тесты
- `tests/test_resolver.py` (новый) — no_overlaps, full_overlap, partial_overlap, equal_overlap_llm_wins
- `tests/test_regex_patterns.py` — добавить passport, email, bank_account
- `tests/test_anonymizer.py` — regex_finds_all_types, no_pdn_leaks, roundtrip, degraded_mode, llm_invalid_json
- LLM мок через monkeypatch на OllamaClient.detect

### 7. Порядок реализации
1. models.py
2. regex_patterns.py
3. resolver.py
4. llm_client.py
5. anonymizer.py
6. Все тесты
7. make lint && make test
8. Commit + push
