# CHANGELOG.md — История изменений LegalDesk

Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/)
Версионирование: [SemVer](https://semver.org/lang/ru/)

---

## [Unreleased]

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
