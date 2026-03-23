# LegalDesk — АРМ Юриста

## Суть
Веб-приложение: юрист вставляет текст обращения → локальная LLM + regex удаляют ПДн → юрист проверяет замены → очищенный текст уходит в API КонсультантПлюс → результат отображается с восстановленными ПДн.

## Архитектура
Три модуля:
- `src/legaldesk/anonymizer/` — локальная LLM (Ollama) + regex, маппинг ПДн
- `src/legaldesk/legal_engine/` — клиент API КонсультантПлюс (абстракция LegalSearchProvider)
- `src/legaldesk/web/` — Flask + Jinja2, простой Web UI на localhost

## Стек
- Python 3.11+
- Flask + Jinja2 + Pico CSS (UI)
- Ollama localhost:11434 (локальная LLM)
- pytest + pytest-cov (тесты)
- ruff (линтер)
- mypy --strict (типизация)
- GitHub Actions (CI)

## Команды
```bash
make install    # установить зависимости
make lint       # ruff check + mypy
make test       # pytest с покрытием
make run        # запустить Flask-сервер
```

## Правила кода
- Тесты пишутся одновременно с кодом, не «потом»
- mypy strict: все функции типизированы
- ruff: без исключений
- Каждый коммит должен проходить make lint && make test
- Docstring на каждую публичную функцию
- Pydantic для моделей данных

## Структура
```
legaldesk/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── Makefile
├── .github/workflows/ci.yml
├── src/legaldesk/
│   ├── __init__.py
│   ├── anonymizer/
│   │   ├── __init__.py
│   │   ├── llm_client.py      # вызов Ollama API
│   │   ├── regex_patterns.py   # regex-страховка для ИНН, СНИЛС и т.д.
│   │   ├── anonymizer.py       # основная логика: LLM + regex → замены
│   │   └── mapping.py          # хранение и обратная подстановка токенов
│   ├── legal_engine/
│   │   ├── __init__.py
│   │   ├── provider.py         # Protocol LegalSearchProvider
│   │   └── consultant_plus.py  # реализация для КонсультантПлюс API
│   └── web/
│       ├── __init__.py
│       ├── app.py              # Flask-приложение
│       ├── templates/
│       │   ├── base.html
│       │   ├── input.html      # экран 1: ввод текста
│       │   ├── review.html     # экран 2: проверка замен
│       │   └── result.html     # экран 3: результат
│       └── static/
│           └── style.css
└── tests/
    ├── __init__.py
    ├── test_anonymizer.py
    ├── test_regex_patterns.py
    ├── test_mapping.py
    └── test_legal_engine.py
```

## Зоны данных
- КРАСНАЯ (локально): исходный текст + маппинг ПДн — никогда не уходит в сеть
- ЖЁЛТАЯ (API): очищенный текст без ПДн — можно отправлять в КонсультантПлюс

## Текущая фаза
Фаза 0: Фундамент — CI, линтеры, тесты, структура каталогов.
