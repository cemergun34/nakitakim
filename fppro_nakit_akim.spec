# -*- mode: python ; coding: utf-8 -*-
"""
fppro_nakit_akim.spec
─────────────────────
PyInstaller spec dosyası — FPPRO IQ Finans Nakit Akış uygulaması
macOS: tek .app paketi (--onedir + windowed)
Windows: tek .exe (--onefile + noconsole)

Derleme: python3 -m PyInstaller fppro_nakit_akim.spec
"""

import sys
from pathlib import Path

HERE = Path(".").resolve()

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[str(HERE)],
    binaries=[],
    datas=[
        # Uygulama içi varlıklar
        ("ui/", "ui/"),
        ("db/", "db/"),
        ("services/", "services/"),
        ("bootstrap_fppro.py", "."),
        ("bootstrap_fppro_secrets.py", "."),
    ],
    hiddenimports=[
        # PyQt6 eklentileri
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtPrintSupport",
        # DB sürücüleri
        "psycopg2",
        "psycopg2.extras",
        "psycopg2._psycopg",
        "sqlite3",
        # Diğer bağımlılıklar
        "mysql.connector",
        "mysql.connector.plugins",
        "mysql.connector.plugins.mysql_native_password",
        "mysql.connector.plugins.caching_sha2_password",
        "lxml",
        "lxml.etree",
        "lxml._elementpath",
        # Bootstrap
        "bootstrap_fppro",
        # Servisler
        "services.gsheets_config_service",
        "services.google_sheets_service",
        "services.vomsis_service",
        "services.paytr_service",
        "services.moy_service",
        "services.sirket_service",
        "services.auth_service",
        "services.dashboard_service",
        "services.efatura_service",
        "services.fiziksel_pos_service",
        "services.kredi_kart_service",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "scipy"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == "darwin":
    # ── macOS: .app paketi ───────────────────────────────────────────────────
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="IQFinans",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,           # Terminal penceresi açma
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon="assets/nakitakim.icns",
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="IQFinans",
    )
    app = BUNDLE(
        coll,
        name="IQFinans.app",
        icon="assets/nakitakim.icns",
        bundle_identifier="com.fppro.iqfinans",
        info_plist={
            "NSPrincipalClass": "NSApplication",
            "NSAppleScriptEnabled": False,
            "CFBundleDisplayName": "IQ Finans",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0",
        },
    )
else:
    # ── Windows: tek .exe ────────────────────────────────────────────────────
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="IQFinans",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,           # Konsol penceresi açma
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
    )
