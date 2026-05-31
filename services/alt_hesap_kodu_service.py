# -*- coding: utf-8 -*-
"""
Alt Hesap Kodları Servisi — PyQt6 backend
========================================
PHP kaynaklar:
  ajax/parametreler/hesapKodlari.php      → get_alt_hesap_kodlari()
  ajax/ayarlar/parametreGuncelle.php      → ekle_alt_hesap_kodu()   (tablo='althesapkodu')
  ajax/ayarlar/parametreSil.php           → sil_alt_hesap_kodu()    (tablo='althesapkodu')
  Şema CSV: topluhesa_sema_pbtn          → sema_csv_indir()
  Toplu yükle: topluhesapbtn             → toplu_yukle_csv()

DB (SQLite)     : tablo = althesapkodu  — kolon = gelirGider
DB (PostgreSQL) : tablo = "altHesapKodu" — kolon = gelirgider  (PG case-insensitive, tırnaklı)
"""
from __future__ import annotations

from db.database import get_connection

# ── SQLite DDL (sadece SQLite modunda çalışır) ──────────────────────────────
_SQLITE_INIT = """
CREATE TABLE IF NOT EXISTS althesapkodu (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kod         TEXT    NOT NULL,
    aciklama    TEXT    NOT NULL,
    gelirGider  TEXT    NOT NULL,
    userid      INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_ahk_userid ON althesapkodu(userid);
"""

# ── PostgreSQL DDL (sadece PG modunda çalışır) ──────────────────────────────
# Not: Bu DDL, initialize_pg_schema() zaten tabloyu oluşturmuşsa IF NOT EXISTS ile atlanır.
_PG_INIT = """
CREATE TABLE IF NOT EXISTS "altHesapKodu" (
    id          SERIAL PRIMARY KEY,
    kod         TEXT NOT NULL,
    aciklama    TEXT NOT NULL,
    gelirgider  TEXT NOT NULL,
    userid      INTEGER DEFAULT 1
)
"""

SEMA_SUTUNLAR = ["kod", "aciklama", "gelirGider"]      # CSV şema başlıkları
SEMA_DOSYA_ADI = "alt_hesap_kodlari_sema.csv"


def _is_pg() -> bool:
    """Aktif veritabanı modunun PostgreSQL olup olmadığını döndürür."""
    from db.db_config import get_mode
    return get_mode() == "postgres"


def _tbl() -> str:
    """Mevcut moda göre doğru tablo adını döndürür."""
    return '"altHesapKodu"' if _is_pg() else "althesapkodu"


def _gg_col() -> str:
    """Mevcut moda göre doğru gelir/gider kolon adını döndürür."""
    return "gelirgider" if _is_pg() else "gelirGider"


def ensure_tables() -> None:
    """Tablo yoksa oluşturur — her iki modda çalışır."""
    conn = get_connection()
    try:
        if _is_pg():
            # PostgreSQL: executescript yerine doğrudan execute (DDL otomatik commit)
            for stmt in _PG_INIT.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        conn.execute(stmt)
                    except Exception:
                        pass
            conn.commit()
        else:
            conn.executescript(_SQLITE_INIT)
            conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# ── 1. Listeleme — PHP: hesapKodlari.php ─────────────────────────────────────

def get_alt_hesap_kodlari(userid: int) -> dict:
    """
    althesapkodu organizasyona ait ortak tanımları getirir.
    userid filtresi uygulanmaz — tüm kayıtlar gelir.
    """
    ensure_tables()
    conn = get_connection()
    tbl = _tbl()
    gg  = _gg_col()
    try:
        rows = conn.execute(
            f"SELECT id, kod, aciklama, {gg} FROM {tbl} ORDER BY kod ASC"
        ).fetchall()

        data = []
        for r in rows:
            rd = dict(r)          # sqlite3.Row → dict (.get() için gerekli)
            data.append({
                "id":         rd["id"],
                "kod":        rd.get("kod") or "",
                "aciklama":   rd.get("aciklama") or "",
                # PG'de kolon adı küçük (gelirgider), SQLite'da camelCase (gelirGider)
                "gelirGider": rd.get(gg) or rd.get("gelirGider") or rd.get("gelirgider") or "gelir",
            })
        return {"success": True, "data": data}
    except Exception as exc:
        return {"success": False, "message": str(exc), "data": []}
    finally:
        conn.close()



# ── 2. Ekleme — PHP: parametreGuncelle.php (tablo='althesapkodu') ─────────────

def ekle_alt_hesap_kodu(userid: int, kod: str, aciklama: str, gelir_gider: str) -> dict:
    """
    Yeni hesap kodu ekler. userid=1 (master) kullanılır — organizasyon geneli tanım.
    """
    kod        = kod.strip()
    aciklama   = aciklama.strip()
    gelir_gider = gelir_gider.strip().lower()

    if not kod or not aciklama or not gelir_gider:
        return {"success": False, "message": "Tüm alanları doldurunuz."}

    ensure_tables()
    conn = get_connection()
    tbl = _tbl()
    gg  = _gg_col()
    # Hesap kodları organizasyon geneli — master userid=1 ile kaydedilir
    MASTER_USERID = 1
    try:
        # Duplicate kontrolü — sadece kod bazında (userid'den bağımsız)
        ex = conn.execute(
            f"SELECT id FROM {tbl} WHERE kod = ?",
            (kod,)
        ).fetchone()
        if ex:
            return {"success": False, "message": "Bu hesap kodu zaten kayıtlı."}

        cur = conn.execute(
            f"INSERT INTO {tbl} (kod, aciklama, {gg}, userid) VALUES (?, ?, ?, ?)",
            (kod, aciklama, gelir_gider, MASTER_USERID)
        )
        conn.commit()

        last_id = getattr(cur, "lastrowid", None)
        if last_id is None:
            try:
                last_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            except Exception:
                last_id = None

        return {
            "success":    True,
            "id":         last_id,
            "kod":        kod,
            "aciklama":   aciklama,
            "gelirGider": gelir_gider,
        }
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": f"Hata: {exc}"}
    finally:
        conn.close()


# ── 3. Silme — PHP: parametreSil.php (tablo='althesapkodu') ──────────────────

def sil_alt_hesap_kodu(userid: int, kayit_id: int) -> dict:
    """
    Hesap tanımını siler. userid filtresi uygulanmaz — id yeterli.
    """
    ensure_tables()
    conn = get_connection()
    tbl = _tbl()
    try:
        row = conn.execute(
            f"SELECT id FROM {tbl} WHERE id = ?",
            (kayit_id,)
        ).fetchone()
        if not row:
            return {"success": False, "message": "Hesap tanımı bulunamadı."}

        conn.execute(f"DELETE FROM {tbl} WHERE id = ?", (kayit_id,))
        conn.commit()
        return {"success": True}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


# ── 4. Toplu CSV yükleme — PHP: topluhesapbtn ────────────────────────────────

def toplu_yukle_csv(userid: int, dosya_yolu: str) -> dict:
    """
    CSV dosyasından toplu hesap kodu yükler. Organizasyon geneli — userid=1 ile kaydedilir.
    CSV format: kod, aciklama, gelirGider
    """
    import csv
    ensure_tables()
    conn = get_connection()
    tbl = _tbl()
    gg  = _gg_col()
    MASTER_USERID = 1
    try:
        with open(dosya_yolu, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            added = skipped = 0
            for row in reader:
                kod  = (row.get("kod") or "").strip()
                ack  = (row.get("aciklama") or "").strip()
                gval = (row.get("gelirGider") or row.get("gelirgider") or "").strip().lower()

                if not kod or not ack or not gval:
                    skipped += 1
                    continue

                # Duplicate kontrolü — kod bazında
                ex = conn.execute(
                    f"SELECT id FROM {tbl} WHERE kod=?",
                    (kod,)
                ).fetchone()
                if ex:
                    skipped += 1
                    continue

                conn.execute(
                    f"INSERT INTO {tbl} (kod, aciklama, {gg}, userid) VALUES (?,?,?,?)",
                    (kod, ack, gval, MASTER_USERID)
                )
                added += 1
        conn.commit()
        return {"success": True, "added": added, "skipped": skipped}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()
