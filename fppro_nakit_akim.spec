# -*- mode: python ; coding: utf-8 -*-
"""
fppro_nakit_akim.spec
─────────────────────
PyInstaller spec dosyası — FPPRO IQ Finans Nakit Akış uygulaması
macOS Apple Silicon (arm64): tek .app paketi (--onedir + windowed)
Windows: tek .exe (--onefile + noconsole)

Derleme: python3 -m PyInstaller fppro_nakit_akim.spec --noconfirm
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
        ("ui/",             "ui/"),
        ("db/",             "db/"),
        ("services/",       "services/"),
        ("assets/",         "assets/"),
        ("bootstrap_fppro.py", "."),
    ],
    hiddenimports=[
        # PyQt6
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtPrintSupport",
        # DB sürücüleri
        "psycopg2",
        "psycopg2.extras",
        "psycopg2._psycopg",
        "sqlite3",
        # Üçüncü taraf
        "mysql.connector",
        "mysql.connector.plugins",
        "mysql.connector.plugins.mysql_native_password",
        "mysql.connector.plugins.caching_sha2_password",
        "openpyxl",
        "certifi",
        "lxml",
        "lxml.etree",
        "lxml._elementpath",
        # Bootstrap
        "bootstrap_fppro",
        # Servisler
        "services.auth_service",
        "services.dashboard_service",
        "services.detay_service",
        "services.efatura_service",
        "services.fiziksel_pos_service",
        "services.google_sheets_service",
        "services.gsheets_config_service",
        "services.iban_hesap_service",
        "services.kategoriler_service",
        "services.kredi_kart_service",
        "services.moy_service",
        "services.odeme_sekli_service",
        "services.paytr_service",
        "services.rapor_service",
        "services.sirket_service",
        "services.subeler_service",
        "services.vergi_muhtasar_service",
        "services.vomsis_service",
        "services.alt_hesap_service",
        "services.alt_hesap_kodu_service",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "scipy", "pandas"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == "darwin":
    # ── macOS Apple Silicon (arm64) ──────────────────────────────────────────
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
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch="arm64",        # Apple Silicon M1/M2/M3/M4
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
            "NSPrincipalClass":        "NSApplication",
            "NSAppleScriptEnabled":    False,
            "CFBundleDisplayName":     "IQ Finans",
            "CFBundleVersion":         "1.0.0",
            "CFBundleShortVersionString": "1.0",
            "LSMinimumSystemVersion":  "12.0",
            "NSHighResolutionCapable": True,
        },
    )
else:
    # ── Windows ──────────────────────────────────────────────────────────────
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
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
    )
