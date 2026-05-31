# -*- coding: utf-8 -*-
"""
Kategoriler Servisi — PyQt6 backend
==================================
PHP kaynaklar:
  ajax/parametreler/kategorilerGetir.php  → get_kategoriler()
  ajax/ayarlar/parametreGuncelle.php      → ekle_kategori()   (tablo='kategoriler', sutun='kategoriAck')
  ajax/ayarlar/parametreSil.php           → sil_kategori()    (tablo='kategoriler')
  Şema CSV: toplu_kate_sema_pbtn          → sema_csv_indir()
  Toplu yükle: kategorilertoplubtn        → toplu_yukle_csv()

DB: SQLite → kategoriler tablosu (PHP: kategoriler WHERE userid = userid)
"""
from __future__ import annotations

from db.database import get_connection

_SQL_INIT = """
CREATE TABLE IF NOT EXISTS kategoriler (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kategoriAck TEXT    NOT NULL,
    userid      INTEGER,
    topluid     TEXT    DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_kat_userid ON kategoriler(userid);
"""

SEMA_SUTUNLAR = ["kategoriAck"]      # CSV şema başlıkları
SEMA_DOSYA_ADI = "kategoriler_sema.csv"


def ensure_tables() -> None:
    conn = get_connection()
    try:
        conn.executescript(_SQL_INIT)
        conn.commit()
    finally:
        conn.close()


# ── 1. Listeleme — PHP: kategorilerGetir.php ────────────────────────────────────

def get_kategoriler(userid: int) -> dict:
    """
    PHP: SELECT * FROM kategoriler WHERE userid = :userId
    Her zaman id=3 en başta olacak şekilde sıralanır (PHP usort mantığı).
    Döner: { 'success': bool, 'data': [{'id':…, 'kategoriAck':…}, …] }
    """
    ensure_tables()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, kategoriAck, topluid FROM kategoriler "
            "WHERE userid = ? ORDER BY id DESC",
            (userid,)
        ).fetchall()
        
        data = [
            {"id": r["id"], "kategoriAck": r["kategoriAck"] or "", "topluid": r["topluid"]}
            for r in rows
        ]
        
        # PHP usort: id=3 her zaman en başta olacak
        def _sort_key(item):
            return 0 if item["id"] == 3 else 1

        data.sort(key=_sort_key)
        
        return {"success": True, "data": data}
    except Exception as exc:
        return {"success": False, "message": str(exc), "data": []}
    finally:
        conn.close()


# ── 2. Ekleme — PHP: parametreGuncelle.php (tablo='kategoriler', sutun='kategoriAck') ──

def ekle_kategori(userid: int, kategori_ack: str) -> dict:
    """
    PHP: INSERT INTO kategoriler (kategoriAck, userid) VALUES (:deger, :userid)
    """
    kategori_ack = kategori_ack.strip()
    if not kategori_ack:
        return {"success": False, "message": "Boş değer gönderilemez."}

    ensure_tables()
    conn = get_connection()
    try:
        # Duplicate kontrolü
        ex = conn.execute(
            "SELECT id FROM kategoriler WHERE userid = ? AND kategoriAck = ?",
            (userid, kategori_ack)
        ).fetchone()
        if ex:
            return {"success": False, "message": "Bu kategori adı zaten kayıtlı."}

        conn.execute(
            "INSERT INTO kategoriler (kategoriAck, userid) VALUES (?, ?)",
            (kategori_ack, userid)
        )
        conn.commit()
        last_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"success": True, "id": last_id, "kategoriAck": kategori_ack}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": f"Hata: {exc}"}
    finally:
        conn.close()


# ── 3. Silme — PHP: parametreSil.php (tablo='kategoriler') ─────────────────────

def sil_kategori(userid: int, kategori_id: int) -> dict:
    """
    PHP: DELETE FROM kategoriler WHERE userid = :userid AND id = :id
    """
    ensure_tables()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM kategoriler WHERE id = ? AND userid = ?",
            (kategori_id, userid)
        ).fetchone()
        if not row:
            return {"success": False, "message": "Kategori bulunamadı."}

        conn.execute("DELETE FROM kategoriler WHERE id = ? AND userid = ?", (kategori_id, userid))
        conn.commit()
        return {"success": True}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


# ── 4. Toplu CSV yükleme — PHP: kategorilertoplubtn ─────────────────────────────

def toplu_yukle_csv(userid: int, dosya_yolu: str) -> dict:
    """
    PHP: kategorilertoplubtn → CSV satır satır INSERT INTO kategoriler (kategoriAck, userid)
    CSV format: kategoriAck (tek sütun)
    """
    import csv
    ensure_tables()
    conn = get_connection()
    try:
        with open(dosya_yolu, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            added = skipped = 0
            for row in reader:
                ack = (row.get("kategoriAck") or "").strip()
                if not ack:
                    skipped += 1
                    continue
                ex = conn.execute(
                    "SELECT id FROM kategoriler WHERE userid=? AND kategoriAck=?",
                    (userid, ack)
                ).fetchone()
                if ex:
                    skipped += 1
                    continue
                conn.execute(
                    "INSERT INTO kategoriler (kategoriAck, userid) VALUES (?,?)",
                    (ack, userid)
                )
                added += 1
        conn.commit()
        return {"success": True, "added": added, "skipped": skipped}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()
