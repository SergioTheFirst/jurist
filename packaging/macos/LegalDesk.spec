# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules


project_root = Path(SPECPATH).resolve().parents[1]
launcher_script = project_root / "desktop" / "launcher.py"

datas = [
    (str(project_root / "frontend" / "static"), "frontend/static"),
]
binaries = []
hiddenimports = []

for package in (
    "backend",
    "desktop",
    "jaraco.text",
    "jaraco.context",
    "jaraco.functools",
    "more_itertools",
    "backports.tarfile",
    "fastapi",
    "starlette",
    "uvicorn",
    "httpx",
    "natasha",
    "navec",
    "slovnet",
    "razdel",
    "ipymarkup",
    "pymorphy2",
    "pymorphy2_dicts_ru",
    "pdfplumber",
    "fitz",
    "PIL",
    "docx",
    "striprtf",
    "odf",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

hiddenimports += collect_submodules("uvicorn.protocols")
hiddenimports += collect_submodules("uvicorn.loops")
hiddenimports += collect_submodules("uvicorn.lifespan")
hiddenimports += collect_submodules("uvicorn.logging")
datas += collect_data_files("pytesseract")


a = Analysis(
    [str(launcher_script)],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    name="LegalDesk",
    exclude_binaries=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LegalDesk",
)

# Создаём полноценный .app бандл для macOS
app = BUNDLE(
    coll,
    name="LegalDesk.app",
    icon=None,  # Можно указать путь к .icns файлу: 'icon.icns'
    bundle_identifier="com.legaldesk.app",
    info_plist={
        "NSHighResolutionCapable": "True",
        "LSBackgroundOnly": "False",
        "LSMinimumSystemVersion": "10.15",
        "NSPrincipalClass": "NSApplication",
        "CFBundleName": "LegalDesk",
        "CFBundleDisplayName": "LegalDesk",
        "CFBundleIdentifier": "com.legaldesk.app",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": "LegalDesk",
    },
)
