# LegalDesk macOS Desktop Bundle

## Обзор

Пакет для создания установщика macOS для LegalDesk — рабочего места юриста.

**Возможности:**
- Единый инсталлятор (.dmg или .pkg) для установки приложения
- Локальный сервер запускается автоматически при запуске приложения
- Опция добавления в автозагрузку через Login Items
- Приложение в формате .app_bundle для нативной интеграции с macOS
- Корректная остановка сервера при закрытии приложения

## Требования для сборки

1. **macOS 10.15+ (Catalina)** или новее
2. **Python 3.10+** — должен быть установлен в системе
3. **Xcode Command Line Tools** — для работы с пакетами
   ```bash
   xcode-select --install
   ```
4. **PyInstaller** — устанавливается через pip
5. **Иконка в формате .icns** — должна находиться в `frontend/static/icon.icns`

## Подготовка окружения

```bash
# Установить зависимости
pip3 install -r requirements.txt
pip3 install pyinstaller

# Проверить наличие иконки (опционально создать из PNG)
# Если у вас есть icon.png, конвертируйте его:
# mkdir icon.iconset
# sips -z 512 512 icon.png --out icon.iconset/icon_512x512.png
# sips -z 256 256 icon.png --out icon.iconset/icon_256x256.png
# sips -z 128 128 icon.png --out icon.iconset/icon_128x128.png
# sips -z 64 64 icon.png --out icon.iconset/icon_64x64.png
# sips -z 32 32 icon.png --out icon.iconset/icon_32x32.png
# sips -z 16 16 icon.png --out icon.iconset/icon_16x16.png
# iconutil -c icns icon.iconset -o frontend/static/icon.icns
```

## Сборка установщика

Запустите скрипт сборки из корня проекта:

```bash
./packaging/macos/build_installer.sh
```

Скрипт выполнит:
1. Очистит временные директории
2. Запустит PyInstaller для создания .app бандла
3. Создаст DMG installer с перетаскиванием в Applications
4. Создаст PKG installer для системной установки

**Результат:**
- `dist/macos/LegalDesk-{версия}.dmg` — образ диска для ручной установки
- `dist/macos/LegalDesk-{версия}.pkg` — пакетный установщик

## Структура пакета

```
packaging/macos/
├── LegalDesk.spec      # Конфигурация PyInstaller
├── build_installer.sh  # Скрипт сборки
└── README.md           # Этот файл
```

## Установка приложения

### Вариант 1: Через DMG (рекомендуется)

1. Откройте `LegalDesk-{версия}.dmg`
2. Перетащите иконку **LegalDesk** в папку **Applications**
3. Извлеките DMG образ
4. Запустите LegalDesk из папки Applications

### Вариант 2: Через PKG

1. Дважды кликните на `LegalDesk-{версия}.pkg`
2. Следуйте инструкциям мастера установки
3. Приложение будет установлено в `/Applications/LegalDesk.app`

### Первый запуск

При первом запуске macOS может показать предупреждение о безопасности:
> "LegalDesk" cannot be opened because the developer cannot be verified.

Чтобы обойти это:
1. Откройте **System Preferences** → **Security & Privacy**
2. Нажмите **Open Anyway** рядом с сообщением о LegalDesk
3. Или кликните правой кнопкой мыши на приложении и выберите **Open**

## Автозапуск приложения

### Добавить в автозагрузку (Login Items)

**macOS Ventura и новее:**
1. Откройте **System Settings** → **General** → **Login Items**
2. В разделе "Open at Login" нажмите **+**
3. Выберите **LegalDesk** из папки Applications

**macOS Monterey и старше:**
1. Откройте **System Preferences** → **Users & Groups**
2. Выберите вашего пользователя → вкладка **Login Items**
3. Нажмите **+** и добавьте **LegalDesk**

### Альтернативно через терминал

```bash
# Добавить в автозагрузку
osascript -e 'tell application "System Events" to make login item at end with properties {path:"/Applications/LegalDesk.app", hidden:false}'

# Удалить из автозагрузки
osascript -e 'tell application "System Events" to delete login item "LegalDesk"'
```

## Управление сервером

### Запуск
- Дважды кликните на **LegalDesk.app** в Finder
- Через Spotlight: нажмите `Cmd+Space`, введите "LegalDesk"
- Автоматически при входе в систему (если добавлено в Login Items)

### Остановка

**Способ 1: Через интерфейс**
- Используйте кнопку выхода в веб-интерфейсе

**Способ 2: Через терминал**
```bash
# Остановить сервер
pkill -f "LegalDesk.*launcher"

# Или более мягко
osascript -e 'quit app "LegalDesk"'
```

**Способ 3: Через Activity Monitor**
1. Откройте **Activity Monitor** (Cmd+Space → "Activity Monitor")
2. Найдите процесс **LegalDesk**
3. Нажмите **✕** → **Quit** или **Force Quit**

## Отладка

Логи работы сохраняются в:
- `~/Library/Application Support/LegalDesk/logs/launcher.log` — лог лаунчера
- `~/Library/Application Support/LegalDesk/logs/server.log` — лог сервера

Просмотр логов:
```bash
# Просмотреть логи в реальном времени
tail -f ~/Library/Application\ Support/LegalDesk/logs/launcher.log

# Посмотреть последние 100 строк
tail -n 100 ~/Library/Application\ Support/LegalDesk/logs/server.log
```

## Troubleshooting

### Приложение не запускается

**Проверьте консоль ошибок:**
```bash
# Запустить из терминала для просмотра ошибок
/Applications/LegalDesk.app/Contents/MacOS/LegalDesk
```

**Проверьте права доступа:**
```bash
chmod +x /Applications/LegalDesk.app/Contents/MacOS/LegalDesk
```

### Сервер не запускается

**Проверьте логи:**
```bash
cat ~/Library/Application\ Support/LegalDesk/logs/server.log
```

**Проверьте, не занят ли порт 8000:**
```bash
lsof -i :8000
```

Если порт занят, освободите его или измените порт в настройках.

### Gatekeeper блокирует запуск

Если macOS блокирует запуск неподписанного приложения:

```bash
# Временно отключить проверку (не рекомендуется для продакшена)
sudo spctl --master-disable

# Или удалить атрибут карантина
xattr -cr /Applications/LegalDesk.app
```

### Проблемы с зависимостями

Если приложение падает с ошибкой импорта:

```bash
# Переустановить зависимости
pip3 install -r requirements.txt --force-reinstall

# Пересобрать приложение
./packaging/macos/build_installer.sh
```

## Удаление приложения

### Ручное удаление

```bash
# Удалить приложение
rm -rf /Applications/LegalDesk.app

# Удалить данные (опционально)
rm -rf ~/Library/Application\ Support/LegalDesk

# Удалить из автозагрузки
osascript -e 'tell application "System Events" to delete login item "LegalDesk"'
```

### Через PKG uninstaller (если создан)

Если вы создали uninstaller pkg, запустите его для удаления.

## Создание подписанного приложения (для распространения)

Для распространения вне Mac App Store требуется подпись:

```bash
# Получить сертификат разработчика в Xcode

# Подписать приложение
codesign --deep --force --verify --verbose \
    --sign "Developer ID Application: Your Name" \
    /Applications/LegalDesk.app

# Проверить подпись
codesign --verify --verbose /Applications/LegalDesk.app

# Создать DMG с подписью
hdiutil create -volname "LegalDesk" \
    -srcfolder /Applications/LegalDesk.app \
    -ov -format UDZO \
    LegalDesk.dmg

# Подписать DMG
codesign --sign "Developer ID Application: Your Name" LegalDesk.dmg

# Отправить на нотариальное заверение (требуется Apple Developer аккаунт)
xcrun notarytool submit LegalDesk.dmg \
    --apple-id "your@apple.id" \
    --password "app-specific-password" \
    --team-id "TEAM_ID" \
    --wait

# Прикрепить тикет нотариуса
xcrun stapler staple LegalDesk.dmg
```

## Лицензия

© LegalDesk Team. Все права защищены.
