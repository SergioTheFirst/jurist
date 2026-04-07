#!/bin/bash
# Build script for LegalDesk macOS application bundle and DMG installer
# Этот скрипт создаёт .app приложение, которое запускается БЕЗ установленного Python

set -e

echo "=== LegalDesk macOS Build Script ==="

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
APP_NAME="LegalDesk"
VERSION=$(python3 -c "import sys; sys.path.insert(0, '$PROJECT_ROOT'); from backend.main import app_version; print(app_version)" 2>/dev/null || echo "1.0.0")

# Directories
BUILD_DIR="$PROJECT_ROOT/build/macos"
DIST_DIR="$PROJECT_ROOT/dist/macos"
APP_DIR="$DIST_DIR/${APP_NAME}.app"
DMG_DIR="$BUILD_DIR/dmg"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Check for macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "ERROR: This script MUST be run on macOS to create a working .app bundle."
    echo "The resulting application will NOT work if built on Linux or Windows."
    exit 1
fi

# Check for required tools
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is required but not installed."
    exit 1
fi

if ! command -v pyinstaller &> /dev/null; then
    echo "Installing PyInstaller..."
    pip3 install --user pyinstaller
fi

# Step 1: Run PyInstaller to create the standalone .app bundle
# Это создаст приложение со встроенным Python и всеми зависимостями
echo "Building standalone application with PyInstaller..."
cd "$PROJECT_ROOT"

pyinstaller --clean \
    --name "$APP_NAME" \
    --onedir \
    --windowed \
    --osx-bundle-identifier="com.legaldesk.app" \
    --add-data="frontend/static:frontend/static" \
    --hidden-import="backend" \
    --hidden-import="uvicorn.protocols" \
    --hidden-import="uvicorn.loops" \
    --hidden-import="uvicorn.lifespan" \
    --hidden-import="uvicorn.logging" \
    --specpath="$BUILD_DIR" \
    --distpath="$DIST_DIR" \
    --workpath="$BUILD_DIR/work" \
    desktop/launcher.py

# Verify app bundle was created
if [ ! -d "$APP_DIR" ]; then
    echo "ERROR: Application bundle was not created at $APP_DIR"
    exit 1
fi

echo "✓ Application bundle created: $APP_DIR"
echo "  This is a standalone app with embedded Python - no installation required!"

# Step 2: Create DMG installer (optional, for distribution)
echo ""
echo "Creating DMG installer for easy distribution..."

# Create temporary directory for DMG contents
mkdir -p "$DMG_DIR"
cp -r "$APP_DIR" "$DMG_DIR/"

# Create Applications symlink in DMG
ln -s /Applications "$DMG_DIR/Applications"

# Create the DMG file
DMG_FILE="$DIST_DIR/${APP_NAME}-${VERSION}.dmg"

hdiutil create -volname "$APP_NAME" \
    -srcfolder "$DMG_DIR" \
    -ov -format UDZO \
    "$DMG_FILE"

echo "✓ DMG installer created: $DMG_FILE"

# Step 3: Create optional PKG installer
echo ""
echo "Creating PKG installer (for system-wide installation)..."

PKG_ROOT="$BUILD_DIR/pkg-root"
PKG_SCRIPTS="$BUILD_DIR/pkg-scripts"
mkdir -p "$PKG_ROOT/Applications/${APP_NAME}.app"
mkdir -p "$PKG_SCRIPTS"

# Copy app to package root
cp -r "$APP_DIR" "$PKG_ROOT/Applications/"

# Create postinstall script
cat > "$PKG_SCRIPTS/postinstall" << 'POSTINSTALL'
#!/bin/bash

APP_NAME="LegalDesk"
APP_DIR="/Applications/${APP_NAME}.app"

# Start the server after installation
if [ -d "$APP_DIR" ]; then
    open "$APP_DIR"
fi

exit 0
POSTINSTALL

chmod +x "$PKG_SCRIPTS/postinstall"

# Create preinstall script
cat > "$PKG_SCRIPTS/preinstall" << 'PREINSTALL'
#!/bin/bash
pkill -f "LegalDesk.*launcher" 2>/dev/null || true
sleep 2
exit 0
PREINSTALL

chmod +x "$PKG_SCRIPTS/preinstall"

# Build the PKG
PKG_FILE="$DIST_DIR/${APP_NAME}-${VERSION}.pkg"

pkgbuild --root "$PKG_ROOT" \
    --scripts "$PKG_SCRIPTS" \
    --identifier "com.legaldesk.installer" \
    --version "$VERSION" \
    --install-location "/" \
    "$PKG_FILE"

echo "✓ PKG installer created: $PKG_FILE"

# Summary
echo ""
echo "=== Build Complete ==="
echo ""
echo "📦 Созданные файлы:"
echo "   Приложение: $APP_DIR"
echo "   DMG:        $DMG_FILE"
echo "   PKG:        $PKG_FILE"
echo ""
echo "🚀 Как запустить БЕЗ установки Python:"
echo ""
echo "   Вариант 1 (из .app):"
echo "   $ open \"$APP_DIR\""
echo ""
echo "   Вариант 2 (из DMG):"
echo "   1. Откройте $DMG_FILE"
echo "   2. Перетащите LegalDesk в Applications"
echo "   3. Запустите из Applications"
echo ""
echo "   Вариант 3 (из PKG):"
echo "   1. Дважды кликните на $PKG_FILE"
echo "   2. Следуйте инструкциям установщика"
echo ""
echo "✅ Приложение полностью автономное - Python не требуется!"
echo "   Все зависимости встроены внутрь .app бандла."
echo ""
