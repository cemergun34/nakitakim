# -*- coding: utf-8 -*-
"""
Veritabanı Konfigürasyon Yöneticisi
=====================================
Mod:
  - 'sqlite'   → Lokal SQLite dosyası (varsayılan, tek kullanıcı)
  - 'postgres' → PostgreSQL sunucusu (çok kullanıcı, ağ)

Konfigürasyon dosyası: ~/NakitAkim/data/db_config.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

# Konfigürasyon dosyası konumu
_CONFIG_DIR  = Path.home() / "NakitAkim" / "data"
_CONFIG_FILE = _CONFIG_DIR / "db_config.json"

# Varsayılan değerler
_DEFAULTS: dict = {
    "mode":     "sqlite",   # 'sqlite' | 'postgres'
    "pg_host":  "localhost",
    "pg_port":  5432,
    "pg_db":    "nakit_akim",
    "pg_user":  "postgres",
    "pg_pass":  "",         # şifre (cleartext — production'da şifreleme eklenebilir)
    "pg_sslmode": "prefer", # 'disable' | 'prefer' | 'require'
}


# ── Okuma / Yazma ─────────────────────────────────────────────────────────────

def load_config() -> dict:
    """
    Konfigürasyon dosyasını okur.
    Dosya yoksa varsayılan değerleri döndürür.
    """
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not _CONFIG_FILE.exists():
        return dict(_DEFAULTS)
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Eksik anahtarları varsayılanlarla tamamla
        for k, v in _DEFAULTS.items():
            data.setdefault(k, v)
        return data
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)


def save_config(cfg: dict) -> None:
    """Konfigürasyonu dosyaya yazar."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ── Yardımcılar ────────────────────────────────────────────────────────────────

def get_mode() -> str:
    """'sqlite' veya 'postgres' döndürür."""
    return load_config().get("mode", "sqlite")


def is_postgres() -> bool:
    return get_mode() == "postgres"


def get_pg_dsn() -> str:
    """
    psycopg2.connect() için DSN string döndürür.
    Örnek: 'host=db.xxx.supabase.co port=5432 dbname=nakit_akim user=postgres password=xxx sslmode=require'
    """
    cfg = load_config()
    parts = [
        f"host={cfg['pg_host']}",
        f"port={cfg['pg_port']}",
        f"dbname={cfg['pg_db']}",
        f"user={cfg['pg_user']}",
        f"sslmode={cfg.get('pg_sslmode', 'prefer')}",
    ]
    if cfg.get("pg_pass"):
        parts.append(f"password={cfg['pg_pass']}")
    return " ".join(parts)


def get_pg_params() -> dict:
    """psycopg2.connect(**params) için dict döndürür."""
    cfg = load_config()
    params: dict = {
        "host":    cfg["pg_host"],
        "port":    int(cfg["pg_port"]),
        "dbname":  cfg["pg_db"],
        "user":    cfg["pg_user"],
        "sslmode": cfg.get("pg_sslmode", "prefer"),
        "connect_timeout": 8,
    }
    if cfg.get("pg_pass"):
        params["password"] = cfg["pg_pass"]

    # Neon SNI Hatası (Müşteri Bilgisayarı Bağlantı Sorunu) Çözümü
    host = cfg.get("pg_host", "")
    if "neon.tech" in host:
        # endpoint ID genelde host'un ilk parçasıdır (örn: ep-restless-bird-1234)
        endpoint_id = host.split(".")[0]
        params["options"] = f"project={endpoint_id}"

    return params


def test_postgres_connection() -> dict:
    """
    PostgreSQL bağlantısını test eder.
    Dönüş: {'success': bool, 'message': str, 'server_version': str}
    """
    try:
        import psycopg2  # type: ignore
    except ImportError:
        return {
            "success": False,
            "message": "psycopg2 kütüphanesi yüklü değil.\n"
                       "Terminal'de şunu çalıştırın:\n"
                       "  pip install psycopg2-binary",
            "server_version": ""
        }

    try:
        conn = psycopg2.connect(**get_pg_params())
        ver = conn.server_version          # örn: 150002 → "15.2"
        major = ver // 10000
        minor = (ver % 10000) // 100
        conn.close()
        return {
            "success": True,
            "message": f"Bağlantı başarılı!",
            "server_version": f"PostgreSQL {major}.{minor}"
        }
    except Exception as exc:
        return {
            "success": False,
            "message": str(exc),
            "server_version": ""
        }
