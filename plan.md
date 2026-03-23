# Фаза 1: Anonymizer — план реализации

## 1. regex_patterns.py — добавить новые паттерны

Добавить к существующим (ИНН, СНИЛС, ТЕЛЕФОН) четыре новых паттерна:

- **ПАСПОРТ**: `r"\b\d{2}\s?\d{2}\s?\d{6}\b"` — серия и номер паспорта РФ (XX XX XXXXXX, с пробелами или без)
- **EMAIL**: `r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b"` — стандартный email
- **БАНК_СЧЁТ**: `r"\b[0-9]{20}\b"` — расчётный счёт (ровно 20 цифр)
- **АДРЕС**: regex по ключевым словам — `r"(?:ул\.|д\.|кв\.|г\.|пр-т|пер\.|наб\.|пл\.)\s*[^\s,;]+(?:[\s,]+(?:ул\.|д\.|кв\.|г\.|пр-т|пер\.|наб\.|пл\.)\s*[^\s,;]+)*"` — ловит фрагменты вида «г. Москва, ул. Ленина, д. 5, кв. 12». Это самый сложный паттерн; нужно собрать цепочку «ключевое_слово + значение» через запятую/пробел.

Обновить `ALL_PATTERNS` — добавить все новые ключи.

**Важно**: порядок в `ALL_PATTERNS` имеет значение — БАНК_СЧЁТ (20 цифр) должен проверяться ДО ИНН (10-12 цифр), чтобы 20-значный номер не разбивался на два ИНН. Нужно переупорядочить словарь: БАНК_СЧЁТ → ИНН → остальные. Либо (лучше) заменить `str.replace` на позиционную замену в anonymizer.py (см. шаг 3).

## 2. llm_client.py — реализация вызова Ollama API

Файл: `src/legaldesk/anonymizer/llm_client.py`

```
OLLAMA_DEFAULT_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3"
TIMEOUT = 60.0

@dataclass
class LlmEntity:
    text: str
    entity_type: str
    start: int
    end: int

def find_entities_with_llm(text: str, base_url: str = OLLAMA_DEFAULT_URL, model: str = OLLAMA_MODEL) -> list[LlmEntity]:
```

- POST на `{base_url}/api/generate` с JSON `{"model": model, "prompt": <system_prompt + text>, "stream": false}`
- Промпт из ТЗ: «Найди все персональные данные... Только JSON, без пояснений.»
- Парсинг JSON из ответа (`response["response"]`), маппинг в `list[LlmEntity]`
- `try/except` на `httpx.ConnectError`, `httpx.TimeoutException`, `json.JSONDecodeError` — при любой ошибке возвращаем `[]` (fallback на regex)
- httpx.Client с timeout=60s

Типизация: `LlmEntity` — обычный `dataclass` (не Pydantic, т.к. это внутренний DTO).

## 3. anonymizer.py — объединение LLM + regex с дедупликацией

Текущая `anonymize_with_regex` остаётся как есть (обратная совместимость для тестов).

Добавить главную функцию:

```
def anonymize(text: str, use_llm: bool = True, ollama_url: str = OLLAMA_DEFAULT_URL) -> tuple[str, TokenMapping]:
```

Логика:
1. **LLM-этап** (если `use_llm=True`): вызвать `find_entities_with_llm(text)` → получить `list[LlmEntity]` с позициями `(start, end, text, type)`
2. **Regex-этап**: прогнать все паттерны из `ALL_PATTERNS` по тексту → получить `list[tuple[start, end, text, category]]`
3. **Дедупликация**: объединить оба списка. Если интервалы пересекаются — оставить тот, у которого длиннее span (или LLM-приоритет при равной длине). Сортировка по `start` desc.
4. **Позиционная замена**: идти с конца текста, заменять каждый `(start, end)` → `mapping.add(original, category)`. Замена с конца гарантирует, что позиции остаются корректными.

Это решает проблему порядка паттернов из шага 1 — позиционная замена вместо `str.replace`.

`anonymize_with_regex` рефакторить на ту же позиционную логику для консистентности.

## 4. Тесты

### tests/test_regex_patterns.py — дополнить

Добавить тесты для каждого нового паттерна:
- `test_passport_with_spaces` — "45 06 123456"
- `test_passport_no_spaces` — "4506123456"
- `test_email_simple` — "user@example.com"
- `test_email_with_dots` — "first.last@mail.ru"
- `test_bank_account_20_digits` — "40817810099910004312"
- `test_address_street` — "г. Москва, ул. Ленина, д. 5, кв. 12"
- Негативные тесты: строка из 8 цифр не матчится как паспорт, 19 цифр не матчится как счёт

### tests/test_anonymizer.py — дополнить

- Тесты `anonymize()` с `use_llm=False` — проверить что regex находит паспорт, email, счёт, адрес
- Тест roundtrip: `anonymize → mapping.restore == оригинал`
- Тест «в очищенном тексте нет ни одного ПДн из исходника» — собрать все оригиналы из mapping.entries, проверить что ни один не в результате
- Тест `anonymize()` с `use_llm=True` но мок Ollama — проверить объединение LLM + regex

### tests/test_llm_client.py — новый файл

- Мок httpx через `httpx.MockTransport` (встроенный, не нужна доп. зависимость — но проверить; если нет — использовать `unittest.mock.patch`)
- `test_find_entities_success` — мок возвращает валидный JSON с сущностями
- `test_find_entities_ollama_unavailable` — мок кидает ConnectError → результат `[]`
- `test_find_entities_timeout` — мок кидает TimeoutException → результат `[]`
- `test_find_entities_invalid_json` — мок возвращает невалидный JSON → результат `[]`

### tests/test_mapping.py — без изменений

Существующие тесты покрывают mapping достаточно.

## 5. Порядок реализации

1. `regex_patterns.py` — добавить паттерны + обновить ALL_PATTERNS
2. `llm_client.py` — реализовать LlmEntity + find_entities_with_llm
3. `anonymizer.py` — рефакторить на позиционную замену, добавить anonymize()
4. Тесты: test_regex_patterns.py → test_llm_client.py → test_anonymizer.py
5. `make lint && make test` — убедиться что всё зелёное

## 6. Зависимости

- `pytest-httpx` НЕ нужен — используем `unittest.mock.patch` для мока httpx.Client
- Новых зависимостей не требуется — httpx уже в pyproject.toml
