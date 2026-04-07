# Как запустить LegalDesk на macOS

## Быстрый старт (без сборки установщика)

Самый простой способ запустить LegalDesk на macOS:

```bash
cd /path/to/legaldesk
./packaging/macos/run_legaldesk.sh
```

Это запустит сервер и откроет браузер автоматически.

## Полная сборка установщика

Если вы хотите создать полноценный .app бандл и DMG/PKG установщик:

### Требования

1. **macOS 10.15+** (Catalina или новее)
2. **Python 3.10+**
3. **Xcode Command Line Tools**:
   ```bash
   xcode-select --install
   ```

### Шаг 1: Установка зависимостей

```bash
# Перейдите в директорию проекта
cd /path/to/legaldesk

# Установите зависимости
pip3 install -r requirements.txt
pip3 install pyinstaller
```

### Шаг 2: Запуск сборки

```bash
# Запустите скрипт сборки
./packaging/macos/build_installer.sh
```

После завершения сборки вы получите:
- `dist/macos/LegalDesk-{версия}.dmg` — образ диска
- `dist/macos/LegalDesk-{версия}.pkg` — пакетный установщик

### Шаг 3: Установка

**Вариант A: Через DMG**
1. Откройте `dist/macos/LegalDesk-{версия}.dmg`
2. Перетащите LegalDesk в папку Applications
3. Запустите из Applications

**Вариант B: Через PKG**
1. Дважды кликните на `dist/macos/LegalDesk-{версия}.pkg`
2. Следуйте инструкциям установщика

### Первый запуск

При первом запуске macOS может показать предупреждение безопасности. Чтобы его обойти:

1. Кликните правой кнопкой мыши на `LegalDesk.app`
2. Выберите **Open**
3. Нажмите **Open** в диалоге подтверждения

Или через терминал:
```bash
open /Applications/LegalDesk.app
```

## Управление приложением

### Запуск
- Из папки Applications
- Через Spotlight (Cmd+Space → "LegalDesk")
- Через терминал: `open /Applications/LegalDesk.app`

### Остановка
```bash
# Через терминал
pkill -f "LegalDesk.*launcher"

# Или через AppleScript
osascript -e 'quit app "LegalDesk"'
```

### Автозагрузка

Добавить в автозагрузку при входе в систему:

**Через интерфейс:**
1. System Settings → General → Login Items
2. Нажмите + и добавьте LegalDesk

**Через терминал:**
```bash
osascript -e 'tell application "System Events" to make login item at end with properties {path:"/Applications/LegalDesk.app", hidden:false}'
```

## Логи

Логи находятся в:
```
~/Library/Application Support/LegalDesk/logs/
```

Просмотреть логи:
```bash
tail -f ~/Library/Application\ Support/LegalDesk/logs/server.log
```

## Удаление

```bash
# Удалить приложение
rm -rf /Applications/LegalDesk.app

# Удалить данные (опционально)
rm -rf ~/Library/Application\ Support/LegalDesk
```

---

**Примечание:** Для сборки .app бандла и DMG требуется macOS. На Linux или Windows можно только подготовить файлы, но не создать рабочий бандл.
