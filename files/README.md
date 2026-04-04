# ⚖ Рабочее место юриста

Локальное веб-приложение для юридической обработки документов.

## Архитектура безопасности

```
[Документ PDF/DOCX/TXT]
        ↓
[Извлечение текста — ЛОКАЛЬНО]
        ↓
[Анонимизация ПДн — ЛОКАЛЬНО, без сети]
  · Natasha NER (ФИО, организации, адреса)
  · Regex (ИНН, СНИЛС, телефоны, email, паспорт)
        ↓
[Очищенный текст → КонсультантПлюс API]
        ↓
[Результат: нормы + практика + заключение]
        ↓
[Юрист: финальная проверка]
```

## Установка

```bash
# 1. Клонируйте / распакуйте проект
cd legal_workspace

# 2. Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Установите зависимости
pip install -r requirements.txt

# 4. Настройте API-ключ
cp .env.example .env
# Отредактируйте .env — укажите KP_API_KEY
```

## Запуск

```bash
# Из корня проекта (legal_workspace/)
KP_API_KEY=ВАШ_КЛЮЧ uvicorn backend.main:app --port 8000

# Или через .env файл
uvicorn backend.main:app --port 8000
```

Откройте браузер: http://localhost:8000

## Подключение реального API КонсультантПлюс

1. Уточните тип API у менеджера КП (КП:Технология или web.consultant.ru)
2. Получите документацию
3. Реализуйте `HttpAdapter` в `backend/adapters/consultant_plus.py`
4. Измените `is_available()` на `return True`

## Структура проекта

```
legal_workspace/
├── backend/
│   ├── main.py                    # FastAPI приложение
│   ├── core/
│   │   ├── anonymizer.py          # Анонимизация ПДн (Natasha + Regex)
│   │   ├── document_parser.py     # Парсинг PDF/DOCX/TXT
│   │   └── archive.py             # SQLite архив дел
│   └── adapters/
│       └── consultant_plus.py     # Адаптер КП (Stub + Http)
├── frontend/static/
│   └── index.html                 # Веб-интерфейс
├── data/
│   ├── archive/                   # SQLite база дел
│   └── uploads/                   # Временные файлы
├── requirements.txt
└── .env.example
```

## Данные о конфиденциальности

- ПДн **никогда** не покидают локальный компьютер
- В КонсультантПлюс отправляется только анонимизированный текст
- Архив дел хранится в локальной SQLite БД (`data/archive/cases.db`)
- Загруженные файлы автоматически удаляются после обработки
