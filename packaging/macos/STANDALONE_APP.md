# 🍎 LegalDesk для macOS — Запуск без установленного Python

## 📦 Что это такое?

LegalDesk теперь может работать как **полностью автономное приложение** на macOS.  
Вам **НЕ НУЖНО** устанавливать Python или какие-либо зависимости вручную.

Всё необходимое (Python, библиотеки, сервер) встроено внутрь `.app` бандла.

---

## 🚀 Быстрый старт

### Вариант 1: Скачать готовое приложение (если есть сборка)

1. Скачайте файл `LegalDesk-{версия}.dmg`
2. Откройте DMG файл двойным кликом
3. Перетащите иконку **LegalDesk** в папку **Applications**
4. Запустите из Applications (первый запуск потребует подтверждения)

### Вариант 2: Собрать самостоятельно

Если вы разработчик или хотите собрать последнюю версию:

```bash
# 1. Перейдите в директорию проекта
cd /path/to/legaldesk

# 2. Запустите скрипт сборки
./packaging/macos/build_installer.sh

# 3. Готово! Приложение будет в:
#    dist/macos/LegalDesk.app
#    dist/macos/LegalDesk-{версия}.dmg
```

---

## 📋 Требования для сборки

| Требование | Статус |
|------------|--------|
| macOS 10.15 или новее | ✅ Обязательно |
| Python 3.10+ | ✅ Нужен только для сборки |
| Xcode Command Line Tools | ✅ Установить: `xcode-select --install` |

**Важно:** Сборка должна выполняться **ТОЛЬКО на macOS**.  
Приложение, собранное на Linux или Windows, **НЕ БУДЕТ РАБОТАТЬ** на Mac.

---

## 🔧 Как это работает?

### PyInstaller создаёт standalone-приложение

Скрипт `build_installer.sh` использует **PyInstaller** для:

1. **Анализа зависимостей** — сканирует все импорты в коде
2. **Упаковки Python** — встраивает интерпретатор Python внутрь бандла
3. **Сбора библиотек** — копирует все нужные модули (FastAPI, uvicorn, natasha и др.)
4. **Создания .app бандла** — формирует нативный macOS-бандл с правильной структурой
5. **Генерации установщиков** — создаёт DMG и PKG для удобной дистрибуции

### Структура .app бандла

```
LegalDesk.app/
├── Contents/
│   ├── Info.plist              # Метаданные приложения
│   ├── MacOS/
│   │   └── LegalDesk           # Исполняемый бинарник (встроенный Python + код)
│   ├── Resources/
│   │   ├── frontend/static/    # Статические файлы веб-интерфейса
│   │   └── icon.icns           # Иконка приложения
│   └── Frameworks/             # Встроенные библиотеки Python
│       ├── libpython3.10.dylib
│       └── ... другие зависимости
```

---

## 💻 Использование

### Запуск приложения

```bash
# Из терминала
open /Applications/LegalDesk.app

# Или через Finder: Applications → LegalDesk
```

### Что происходит при запуске?

1. ✅ Запускается встроенный Python
2. ✅ Автоматически стартует локальный сервер (backend)
3. ✅ Открывается браузер с веб-интерфейсом (http://localhost:8000)
4. ✅ Приложение работает в фоне, доступно из менюбара

### Остановка сервера

```bash
# Через терминал
pkill -f "LegalDesk.*launcher"

# Или завершите приложение через Cmd+Q
```

---

## 🛠 Настройка и кастомизация

### Изменение версии приложения

Отредактируйте `LegalDesk.spec`:

```python
app = BUNDLE(
    coll,
    name="LegalDesk.app",
    bundle_identifier="com.legaldesk.app",
    info_plist={
        "CFBundleVersion": "1.0.0",          # Номер билда
        "CFBundleShortVersionString": "1.0.0", # Версия для пользователя
        # ...
    },
)
```

### Добавление иконки

1. Создайте файл `icon.icns` (можно использовать [icns.io](https://www.icns.io/))
2. Положите в `packaging/macos/icon.icns`
3. Раскомментируйте строку в `LegalDesk.spec`:
   ```python
   icon='icon.icns',
   ```

### Добавление дополнительных файлов

Если нужно включить другие ресурсы:

```python
# В LegalDesk.spec
datas = [
    ('frontend/static', 'frontend/static'),
    ('config/default.yaml', 'config'),  # Добавить конфиг
    ('models/', 'models'),              # Добавить модели
]
```

---

## 📁 Файлы проекта

| Файл | Назначение |
|------|------------|
| `LegalDesk.spec` | Конфигурация PyInstaller |
| `build_installer.sh` | Скрипт сборки (создаёт .app, .dmg, .pkg) |
| `run_legaldesk.sh` | Быстрый запуск без сборки (требует установленный Python) |
| `README.md` | Эта инструкция |

---

## ❓ Частые вопросы

### Q: Можно ли собрать на Linux для macOS?
**A:** Нет. PyInstaller создаёт платформо-зависимые бинарники. Сборка должна быть на macOS.

### Q: Почему размер приложения такой большой (~100MB)?
**A:** Потому что внутри весь Python и все библиотеки. Это цена за автономность.

### Q: Можно ли уменьшить размер?
**A:** Да, можно:
- Использовать `--exclude-module` для ненужных модулей
- Включить сжатие UPX (`--upx-dir=/path/to/upx`)
- Удалить неиспользуемые словари (например, pymorphy2_dicts_ru можно оптимизировать)

### Q: Приложение не запускается, ошибка "App is damaged"?
**A:** macOS блокирует неподписанные приложения. Решение:
```bash
# Временно отключить проверку (не рекомендуется для продакшена)
sudo xattr -rd com.apple.quarantine /Applications/LegalDesk.app

# Или подписать приложение (нужен Apple Developer аккаунт)
codesign --deep --force --sign "Your Name" /Applications/LegalDesk.app
```

### Q: Как добавить автозагрузку при старте системы?
**A:** Используйте LaunchAgent:
```bash
cat > ~/Library/LaunchAgents/com.legaldesk.app.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.legaldesk.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/LegalDesk.app/Contents/MacOS/LegalDesk</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>Hidden</key>
    <true/>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.legaldesk.app.plist
```

---

## 🔐 Подпись и нотариальное заверение (для дистрибуции)

Для распространения вне App Store:

1. **Подпишите приложение:**
   ```bash
   codesign --deep --force --verify --verbose \
     --sign "Developer ID Application: Your Name (TEAM_ID)" \
     /Applications/LegalDesk.app
   ```

2. **Отправьте на нотариальное заверение:**
   ```bash
   xcrun notarytool submit LegalDesk-1.0.0.dmg \
     --apple-id "your@apple.id" \
     --password "app-specific-password" \
     --team-id "TEAM_ID" \
     --wait
   ```

3. **Прикрепите статус нотариуса:**
   ```bash
   xcrun stapler staple /Applications/LegalDesk.app
   ```

---

## 📞 Поддержка

Если возникли проблемы:

1. Проверьте логи в `~/Library/Application Support/LegalDesk/logs/`
2. Запустите с флагом отладки:
   ```bash
   /Applications/LegalDesk.app/Contents/MacOS/LegalDesk --debug
   ```
3. Откройте issue в репозитории проекта

---

## 📝 Лицензия

LegalDesk распространяется под той же лицензией, что и основной проект.
