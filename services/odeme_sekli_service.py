# -*- coding: utf-8 -*-
"""
Ödeme Şekilleri Servisi — PyQt6 backend
======================================
PHP kaynaklar:
  ajax/parametreler/odemeSekilleriGetir.php  → get_odeme_sekilleri()
  ajax/ayarlar/parametreGuncelle.php          → ekle_odeme_sekli()   (tablo='odemesekli')
  ajax/ayarlar/parametreSil.php               → sil_odeme_sekli()    (tablo='odemesekli')
  Şema CSV: toplu_ode_sema_pbtn              → sema_csv_indir()
  Toplu yükle: odemesekilleritoplubtn         → toplu_yukle_csv()

DB: SQLite → odemesekli tablosu (PHP: odemesekli WHERE userid = userid)
"""
from __future__ import annotations

import csv
from db.database import get_connection

_SQL_INIT = """
CREATE TABLE IF NOT EXISTS odemesekli (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    odemesekliAck  TEXT NOT NULL,
    userid         INTEGER,
    durumModu      TEXT,
    topluid        TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_os_userid ON odemesekli(userid);
"""

SEMA_SUTUNLAR = ["odemesekliAck", "durumModu"]
SEMA_DOSYA_ADI = "odeme_sekilleri_sema.csv"


def ensure_tables() -> None:
    conn = get_connection()
    try:
        conn.executescript(_SQL_INIT)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# ── 1. Listeleme ─────────────────────────────────────────────────────────────

def get_odeme_sekilleri(userid: int) -> dict:
    """
    SQLite: SELECT id, odemesekliAck, durumModu FROM odemesekli WHERE userid = ? ORDER BY id DESC
    """
    ensure_tables()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, odemesekliAck, durumModu, topluid FROM odemesekli "
            "WHERE userid = ? ORDER BY id DESC",
            (userid,)
        ).fetchall()
        
        data = [
            {
                "id": r["id"],
                "odemesekliAck": r["odemesekliAck"] or "",
                "durumModu": r["durumModu"] or "hepsi",
                "topluid": r["topluid"]
            }
            for r in rows
        ]
        return {"success": True, "data": data}
    except Exception as exc:
        return {"success": False, "message": str(exc), "data": []}
    finally:
        conn.close()


# ── 2. Ekleme ────────────────────────────────────────────────────────────────

def ekle_odeme_sekli(userid: int, ack: str, mod: str) -> dict:
    """
    SQLite: INSERT INTO odemesekli (odemesekliAck, durumModu, userid) VALUES (?, ?, ?)
    """
    ack = ack.strip()
    mod = mod.strip().lower()

    if not ack or not mod:
        return {"success": False, "message": "Lütfen tüm alanları doldurun."}

    ensure_tables()
    conn = get_connection()
    try:
        # Duplicate kontrolü (aynı açıklama ve mod)
        ex = conn.execute(
            "SELECT id FROM odemesekli WHERE userid = ? AND odemesekliAck = ? AND durumModu = ?",
            (userid, ack, mod)
        ).fetchone()
        if ex:
            return {"success": False, "message": "Bu ödeme şekli zaten kayıtlı."}

        conn.execute(
            "INSERT INTO odemesekli (odemesekliAck, durumModu, userid) VALUES (?, ?, ?)",
            (ack, mod, userid)
        )
        conn.commit()
        last_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"success": True, "id": last_id, "odemesekliAck": ack, "durumModu": mod}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": f"Hata: {exc}"}
    finally:
        conn.close()


# ── 3. Silme ─────────────────────────────────────────────────────────────────

def sil_odeme_sekli(userid: int, os_id: int) -> dict:
    """
    SQLite: DELETE FROM odemesekli WHERE userid = ? AND id = ?
    """
    ensure_tables()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM odemesekli WHERE id = ? AND userid = ?",
            (os_id, userid)
        ).fetchone()
        if not row:
            return {"success": False, "message": "Ödeme şekli bulunamadı."}

        conn.execute("DELETE FROM odemesekli WHERE id = ? AND userid = ?", (os_id, userid))
        conn.commit()
        return {"success": True}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


# ── 4. Toplu CSV yükleme ──────────────────────────────────────────────────────

def toplu_yukle_csv(userid: int, dosya_yolu: str) -> dict:
    """
    CSV format: odemesekliAck, durumModu
    """
    ensure_tables()
    conn = get_connection()
    try:
        with open(dosya_yolu, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            added = skipped = 0
            for row in reader:
                ack = (row.get("odemesekliAck") or "").strip()
                mod = (row.get("durumModu") or "hepsi").strip().lower()
                
                if not ack:
                    skipped += 1
                    continue
                    
                ex = conn.execute(
                    "SELECT id FROM odemesekli WHERE userid=? AND odemesekliAck=? AND durumModu=?",
                    (userid, ack, mod)
                ).fetchone()
                if ex:
                    skipped += 1
                    continue
                    
                conn.execute(
                    "INSERT INTO odemesekli (odemesekliAck, durumModu, userid) VALUES (?,?,?)",
                    (ack, mod, userid)
                )
                added += 1
        conn.commit()
        return {"success": True, "added": added, "skipped": skipped}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()
