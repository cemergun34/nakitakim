# -*- coding: utf-8 -*-
"""
Alt Hesap & Yetkilendirme Servisi — PyQt6 backend
===================================================
PHP kaynaklar:
  ajax/ayarlar/altkullaniciGetir.php   → get_alt_kullanicilar()
  ajax/ayarlar/altkullaniciKaydet.php  → kaydet_alt_kullanici()
  ajax/ayarlar/altuyelik_sil.php       → sil_alt_kullanici()

DB: alt_kullanici tablosu — SQLite ve PostgreSQL uyumlu.

Yetki değerleri:
  1  → Admin       (tüm yetkiler, düzenleme + görüntüleme)
  2  → Kullanıcı   (sadece görüntüleme)
  3  → Analist     (rapor görüntüleme)

Maksimum alt kullanıcı: 10
"""
from __future__ import annotations
import hashlib, os
from datetime import datetime
from typing import Optional

from db.database import get_connection


# ── Yetki etiket haritası ────────────────────────────────────────────────────
YETKI_ETIKET = {
    "1": "Admin", "2": "Kullanıcı", "3": "Analist",
     1:  "Admin",  2:  "Kullanıcı",  3:  "Analist",
}
YETKI_RENK = {
    "1": ("#dbeafe", "#1d4ed8"),
    "2": ("#dcfce7", "#15803d"),
    "3": ("#fef9c3", "#a16207"),
     1:  ("#dbeafe", "#1d4ed8"),
     2:  ("#dcfce7", "#15803d"),
     3:  ("#fef9c3", "#a16207"),
}
MAX_ALT_KULLANICI = 10

# ── SQLite DDL ───────────────────────────────────────────────────────────────
_SQLITE_INIT = """
CREATE TABLE IF NOT EXISTS alt_kullanici (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_userid   INTEGER NOT NULL,
    kullanici_adi   TEXT    NOT NULL,
    eposta          TEXT    NOT NULL DEFAULT '',
    sifre_hash      TEXT    DEFAULT NULL,
    uyelik_tarihi   TEXT    DEFAULT NULL,
    yetki           TEXT    DEFAULT '1'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ak_kullanici ON alt_kullanici(kullanici_adi);
CREATE INDEX IF NOT EXISTS idx_ak_parent ON alt_kullanici(parent_userid);
"""

# ── PostgreSQL DDL ───────────────────────────────────────────────────────────
# initialize_pg_schema() zaten tabloyu oluşturur; ensure_tables() yalnızca yedek.
_PG_INIT = """
CREATE TABLE IF NOT EXISTS alt_kullanici (
    id              SERIAL PRIMARY KEY,
    parent_userid   INTEGER,
    kullanici_adi   TEXT    NOT NULL,
    eposta          TEXT    NOT NULL DEFAULT '',
    sifre_hash      TEXT    DEFAULT NULL,
    uyelik_tarihi   TEXT    DEFAULT NULL,
    yetki           TEXT    DEFAULT '1',
    aktif           INTEGER DEFAULT 1
)
"""

# ── Eski PG tablolarına eksik kolonları ekle (migration) ────────────────────
_PG_MIGRATIONS = [
    "ALTER TABLE alt_kullanici ADD COLUMN IF NOT EXISTS parent_userid INTEGER",
    "ALTER TABLE alt_kullanici ADD COLUMN IF NOT EXISTS eposta TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE alt_kullanici ADD COLUMN IF NOT EXISTS sifre_hash TEXT",
    "ALTER TABLE alt_kullanici ADD COLUMN IF NOT EXISTS uyelik_tarihi TEXT",
]


def _is_pg() -> bool:
    from db.db_config import get_mode
    return get_mode() == "postgres"


def ensure_tables() -> None:
    """Tablo yoksa oluşturur; PG'de eski tabloya eksik kolonları ekler."""
    conn = get_connection()
    try:
        if _is_pg():
            conn.execute(_PG_INIT)
            conn.commit()
            # Eski tablo varsa eksik kolonları ekle (IF NOT EXISTS PG destekler)
            for stmt in _PG_MIGRATIONS:
                try:
                    conn.execute(stmt)
                    conn.commit()
                except Exception:
                    pass
        else:
            conn.executescript(_SQLITE_INIT)
            conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def _hash_sifre(sifre: str) -> str:
    """SHA-256 + salt ile şifre hash'i üretir."""
    salt = os.urandom(16).hex()
    h = hashlib.sha256((salt + sifre).encode()).hexdigest()
    return f"sha256${salt}${h}"


def _bugun() -> str:
    return datetime.now().strftime("%d.%m.%Y")


# ── 1. Listeleme ─────────────────────────────────────────────────────────────

def get_alt_kullanicilar(parent_userid: int) -> dict:
    """
    parent_userid'e bağlı tüm alt kullanıcıları döndürür.
    Döndürür: { 'success': bool, 'data': [dict, ...], 'kalan_hak': int }
    """
    ensure_tables()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, kullanici_adi, eposta, uyelik_tarihi, yetki "
            "FROM alt_kullanici WHERE parent_userid = ? ORDER BY id DESC",
            (parent_userid,)
        ).fetchall()

        data = []
        for r in rows:
            rd = dict(r)
            yetki = str(rd.get("yetki") or "1")
            data.append({
                "id":            rd["id"],
                "kullanici_adi": rd.get("kullanici_adi") or "",
                "eposta":        rd.get("eposta") or "",
                "uyelik_tarihi": rd.get("uyelik_tarihi") or "",
                "yetki":         yetki,
                "yetki_etiketi": YETKI_ETIKET.get(yetki, "Kullanıcı"),
                "yetki_bg":      YETKI_RENK.get(yetki, ("#dbeafe", "#1d4ed8"))[0],
                "yetki_fg":      YETKI_RENK.get(yetki, ("#dbeafe", "#1d4ed8"))[1],
            })

        kalan = max(0, MAX_ALT_KULLANICI - len(data))
        return {"success": True, "data": data, "kalan_hak": kalan}
    except Exception as exc:
        return {"success": False, "message": str(exc), "data": [], "kalan_hak": 0}
    finally:
        conn.close()


# ── 2. Ekleme ────────────────────────────────────────────────────────────────

def kaydet_alt_kullanici(
    parent_userid: int,
    kullanici_adi: str,
    eposta: str,
    sifre: str,
    yetki: str = "1",
) -> dict:
    """
    Yeni alt kullanıcı ekler.
    Validasyonlar:
      - Kullanıcı adı ve şifre zorunlu
      - Maksimum 10 alt kullanıcı
      - Aynı kullanici_adi zaten kayıtlı olamaz
    """
    kullanici_adi = kullanici_adi.strip()
    eposta        = (eposta or "").strip() or f"{kullanici_adi}@local"

    if not kullanici_adi or not sifre:
        return {"success": False, "message": "Kullanıcı adı ve şifre zorunludur."}

    ensure_tables()
    conn = get_connection()
    try:
        # Maksimum kullanıcı kontrolü
        cnt = conn.execute(
            "SELECT COUNT(*) FROM alt_kullanici WHERE parent_userid = ?",
            (parent_userid,)
        ).fetchone()[0]
        if cnt >= MAX_ALT_KULLANICI:
            return {"success": False, "message": "Maksimum alt kullanıcı sayısına ulaşıldı (10)."}

        # Duplicate kontrolü
        dup = conn.execute(
            "SELECT id FROM alt_kullanici WHERE kullanici_adi = ?",
            (kullanici_adi,)
        ).fetchone()
        if dup:
            return {"success": False, "message": "Bu kullanıcı adı zaten kayıtlı."}

        tarih   = _bugun()
        sifre_h = _hash_sifre(sifre)

        cur = conn.execute(
            "INSERT INTO alt_kullanici "
            "(parent_userid, kullanici_adi, eposta, sifre_hash, uyelik_tarihi, yetki) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (parent_userid, kullanici_adi, eposta, sifre_h, tarih, str(yetki))
        )
        conn.commit()

        # lastrowid: PgWrapper zaten doldurur, SQLite için fallback
        last_id = getattr(cur, "lastrowid", None)
        if last_id is None:
            try:
                last_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            except Exception:
                last_id = None

        return {
            "success":       True,
            "message":       "Kullanıcı başarıyla eklendi.",
            "id":            last_id,
            "kullanici_adi": kullanici_adi,
            "eposta":        eposta,
            "yetki":         str(yetki),
            "tarih":         tarih,
        }
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": f"Hata: {exc}"}
    finally:
        conn.close()


# ── 3. Silme ─────────────────────────────────────────────────────────────────

def sil_alt_kullanici(parent_userid: int, kullanici_id: int) -> dict:
    """
    Alt kullanıcıyı siler.
    Güvenlik: silinecek kullanıcı parent_userid'e bağlı olmalı.
    """
    ensure_tables()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM alt_kullanici WHERE id = ? AND parent_userid = ?",
            (kullanici_id, parent_userid)
        ).fetchone()
        if not row:
            return {"success": False, "message": "Kullanıcı bulunamadı ya da yetki yok."}

        conn.execute("DELETE FROM alt_kullanici WHERE id = ?", (kullanici_id,))
        conn.commit()
        return {"success": True, "message": "Kullanıcı silindi."}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


# ── 4. Şifre doğrulama (giriş ekranı için) ───────────────────────────────────

def dogrula_alt_kullanici(kullanici_adi: str, sifre: str) -> dict | None:
    """
    Kullanıcı adı + şifre ile alt kullanıcıyı doğrular.
    Başarılı ise { 'id', 'kullanici_adi', 'parent_userid', 'yetki' } döndürür.
    """
    ensure_tables()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, parent_userid, kullanici_adi, sifre_hash, yetki "
            "FROM alt_kullanici WHERE kullanici_adi = ?",
            (kullanici_adi,)
        ).fetchone()
        if not row:
            return None
        rd = dict(row)
        sifre_h = rd.get("sifre_hash") or ""

        # sha256$salt$hash formatını doğrula
        if sifre_h.startswith("sha256$"):
            try:
                _, salt, hsh = sifre_h.split("$", 2)
                check = hashlib.sha256((salt + sifre).encode()).hexdigest()
                if check == hsh:
                    return {
                        "id":            rd["id"],
                        "parent_userid": rd.get("parent_userid"),
                        "kullanici_adi": rd.get("kullanici_adi"),
                        "yetki":         str(rd.get("yetki") or "1"),
                    }
            except Exception:
                pass
        # mysql_import gibi ham değerlere karşı düz metin karşılaştırma
        elif sifre_h == sifre:
            return {
                "id":            rd["id"],
                "parent_userid": rd.get("parent_userid"),
                "kullanici_adi": rd.get("kullanici_adi"),
                "yetki":         str(rd.get("yetki") or "1"),
            }
        return None
    except Exception:
        return None
    finally:
        conn.close()
