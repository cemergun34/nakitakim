"""
Şubeler Servisi — PyQt6 backend
================================
PHP kaynaklar:
  ajax/parametreler/subelerGetir.php  → get_subeler()
  ajax/ayarlar/parametreGuncelle.php  → ekle_sube()   (tablo='Subeler', sutun='subeAck')
  ajax/ayarlar/parametreSil.php       → sil_sube()    (tablo='Subeler')
  Şema CSV: toplu_sube_sema_pbtn      → sema_csv_indir()
  Toplu yükle: subelertoplubtn        → toplu_yukle_csv()

DB: SQLite → Subeler tablosu (PHP: Subeler WHERE userid = userid)
"""
from __future__ import annotations

from db.database import get_connection

_SQL_INIT = """
CREATE TABLE IF NOT EXISTS Subeler (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    subeAck   TEXT    NOT NULL,
    userid    INTEGER NOT NULL,
    topluid   TEXT    DEFAULT NULL,
    musterino INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_sub_userid ON Subeler(userid);
"""

SEMA_SUTUNLAR = ["subeAck"]          # CSV şema başlıkları
SEMA_DOSYA_ADI = "subeler_sema.csv"  # PHP: toplu_sube_sema_pbtn dosya adı


def ensure_tables() -> None:
    conn = get_connection()
    try:
        conn.executescript(_SQL_INIT)
        conn.commit()
    finally:
        conn.close()


# ── 1. Listeleme — PHP: subelerGetir.php ────────────────────────────────────

def get_subeler(userid: int, musterino: int = 1) -> dict:
    """
    PHP: SELECT * FROM subeler WHERE userid = :userId ORDER BY id DESC
    Döner: { 'success': bool, 'data': [{'id':…, 'subeAck':…}, …] }
    """
    ensure_tables()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, subeAck, topluid FROM subeler "
            "WHERE userid = ? AND musterino = ? ORDER BY id DESC",
            (userid, musterino)
        ).fetchall()
        data = [
            {"id": r["id"], "subeAck": r["subeAck"] or "", "topluid": r["topluid"]}
            for r in rows
        ]
        return {"success": True, "data": data}
    except Exception as exc:
        return {"success": False, "message": str(exc), "data": []}
    finally:
        conn.close()


# ── 2. Ekleme — PHP: parametreGuncelle.php (tablo='Subeler', sutun='subeAck') ──

def ekle_sube(userid: int, sube_ack: str, musterino: int = 1) -> dict:
    """
    PHP: INSERT INTO subeler (subeAck, userid, musterino) VALUES (:deger, :userid, :musterino)
    """
    sube_ack = sube_ack.strip()
    if not sube_ack:
        return {"success": False, "message": "Boş değer gönderilemez."}

    ensure_tables()
    conn = get_connection()
    try:
        # Duplicate kontrolü
        ex = conn.execute(
            "SELECT id FROM subeler WHERE userid = ? AND subeAck = ? AND musterino = ?",
            (userid, sube_ack, musterino)
        ).fetchone()
        if ex:
            return {"success": False, "message": "Bu şube adı zaten kayıtlı."}

        conn.execute(
            "INSERT INTO subeler (subeAck, userid, musterino) VALUES (?, ?, ?)",
            (sube_ack, userid, musterino)
        )
        conn.commit()
        last_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"success": True, "id": last_id, "subeAck": sube_ack}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": f"Hata: {exc}"}
    finally:
        conn.close()


# ── 3. Silme — PHP: parametreSil.php (tablo='Subeler') ─────────────────────

def sil_sube(userid: int, sube_id: int, musterino: int = 1) -> dict:
    """
    PHP: DELETE FROM subeler WHERE userid = :userid AND id = :id AND musterino = :musterino
    """
    ensure_tables()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM subeler WHERE id = ? AND userid = ? AND musterino = ?",
            (sube_id, userid, musterino)
        ).fetchone()
        if not row:
            return {"success": False, "message": "Şube bulunamadı."}

        conn.execute(
            "DELETE FROM subeler WHERE id = ? AND userid = ? AND musterino = ?",
            (sube_id, userid, musterino)
        )
        conn.commit()
        return {"success": True}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


# ── 4. Toplu CSV yükleme — PHP: subelertoplubtn ─────────────────────────────

def toplu_yukle_csv(userid: int, dosya_yolu: str, musterino: int = 1) -> dict:
    """
    PHP: subelertoplubtn → CSV satır satır INSERT INTO subeler (subeAck, userid, musterino)
    CSV format: subeAck (tek sütun)
    """
    import csv
    ensure_tables()
    conn = get_connection()
    try:
        with open(dosya_yolu, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            added = skipped = 0
            for row in reader:
                ack = (row.get("subeAck") or "").strip()
                if not ack:
                    skipped += 1
                    continue
                ex = conn.execute(
                    "SELECT id FROM subeler WHERE userid=? AND subeAck=? AND musterino=?",
                    (userid, ack, musterino)
                ).fetchone()
                if ex:
                    skipped += 1
                    continue
                conn.execute(
                    "INSERT INTO subeler (subeAck, userid, musterino) VALUES (?,?,?)",
                    (ack, userid, musterino)
                )
                added += 1
        conn.commit()
        return {"success": True, "added": added, "skipped": skipped}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()
