"""
SQLite bağlantı yöneticisi — thread-safe singleton.
"""
import sqlite3
import os
from pathlib import Path
from db.schema import SCHEMA_SQL

# Veritabanı konumu: ~/NakitAkim/data/nakit_akim.db
DB_DIR  = Path.home() / "NakitAkim" / "data"
DB_PATH = DB_DIR / "nakit_akim.db"


def get_db_path() -> Path:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    return DB_PATH


def get_connection() -> sqlite3.Connection:
    """Her çağrıda yeni bir bağlantı döndürür (thread-safe)."""
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def initialize_db():
    """Şemayı oluşturur (uygulama ilk açılışında çağrılır)."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        print(f"[DB] Veritabanı hazır: {DB_PATH}")
    finally:
        conn.close()


def db_exists() -> bool:
    """Veritabanı dosyasının ve en az bir tablonun mevcut olup olmadığını kontrol eder."""
    if not DB_PATH.exists():
        return False
    conn = get_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='hareketler'"
        ).fetchone()[0]
        return count > 0
    finally:
        conn.close()
