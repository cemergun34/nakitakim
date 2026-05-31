# -*- coding: utf-8 -*-
"""
IBAN Hesap Bilgileri Servisi — PyQt6 backend
============================================
PHP kaynaklar:
  ajax/parametreler/ibanHesaplariGetir.php   → get_iban_hesaplari()
  ajax/ayarlar/ibanhesapkaydet.php           → ekle_iban_hesap()
  ajax/ayarlar/parametreSil.php              → sil_iban_hesap()   (tablo='ibanhesapbilgileri')
"""
from __future__ import annotations

from db.database import get_connection

_SQL_INIT = """
CREATE TABLE IF NOT EXISTS ibanhesapbilgileri (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    userid           INTEGER NOT NULL,
    ibanHesapbaslik  TEXT NOT NULL,
    cariHesapid      INTEGER NOT NULL,
    bankaAdi         TEXT NOT NULL,
    subeAdi          TEXT,
    bankaHesapno     TEXT,
    ibanNo           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_iban_userid ON ibanhesapbilgileri(userid);
"""


def ensure_tables() -> None:
    conn = get_connection()
    try:
        conn.executescript(_SQL_INIT)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def get_iban_hesaplari(userid: int) -> dict:
    """
    SQLite: SELECT i.*, c.unvan FROM ibanhesapbilgileri i
            LEFT JOIN carihesaplar c ON i.cariHesapid = c.id
            WHERE i.userid = ? ORDER BY i.id DESC
    """
    ensure_tables()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT i.id, i.ibanHesapbaslik, i.cariHesapid, i.bankaAdi, i.subeAdi, "
            "i.bankaHesapno, i.ibanNo, c.unvan FROM ibanhesapbilgileri i "
            "LEFT JOIN carihesaplar c ON i.cariHesapid = c.id "
            "WHERE i.userid = ? ORDER BY i.id DESC",
            (userid,)
        ).fetchall()
        
        data = [
            {
                "id": r["id"],
                "ibanHesapbaslik": r["ibanHesapbaslik"] or "",
                "cariHesapid": r["cariHesapid"],
                "bankaAdi": r["bankaAdi"] or "",
                "subeAdi": r["subeAdi"] or "",
                "bankaHesapno": r["bankaHesapno"] or "",
                "ibanNo": r["ibanNo"] or "",
                "unvan": r["unvan"] or f"Bilinmeyen Cari (ID: {r['cariHesapid']})"
            }
            for r in rows
        ]
        return {"success": True, "data": data}
    except Exception as exc:
        return {"success": False, "message": str(exc), "data": []}
    finally:
        conn.close()


def ekle_iban_hesap(
    userid: int,
    baslik: str,
    cari_id: int,
    banka_adi: str,
    sube_adi: str,
    hesap_no: str,
    iban_no: str
) -> dict:
    """Yeni bir IBAN hesabı ekler."""
    baslik = baslik.strip()
    banka_adi = banka_adi.strip()
    sube_adi = sube_adi.strip()
    hesap_no = hesap_no.strip()
    iban_no = iban_no.strip()

    if not baslik or not cari_id or not banka_adi or not iban_no:
        return {"success": False, "message": "Başlık, Cari Hesap, Banka Adı ve IBAN alanları zorunludur."}

    ensure_tables()
    conn = get_connection()
    try:
        # Duplicate kontrolü (aynı IBAN no)
        ex = conn.execute(
            "SELECT id FROM ibanhesapbilgileri WHERE userid = ? AND ibanNo = ?",
            (userid, iban_no)
        ).fetchone()
        if ex:
            return {"success": False, "message": "Bu IBAN numarası zaten kayıtlı."}

        conn.execute(
            "INSERT INTO ibanhesapbilgileri (userid, ibanHesapbaslik, cariHesapid, bankaAdi, subeAdi, bankaHesapno, ibanNo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (userid, baslik, cari_id, banka_adi, sube_adi, hesap_no, iban_no)
        )
        conn.commit()
        last_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"success": True, "id": last_id}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


def sil_iban_hesap(userid: int, iban_id: int) -> dict:
    """IBAN hesabını siler."""
    ensure_tables()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM ibanhesapbilgileri WHERE id = ? AND userid = ?",
            (iban_id, userid)
        ).fetchone()
        if not row:
            return {"success": False, "message": "IBAN kaydı bulunamadı."}

        conn.execute("DELETE FROM ibanhesapbilgileri WHERE id = ? AND userid = ?", (iban_id, userid))
        conn.commit()
        return {"success": True}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


def get_cari_hesaplar(userid: int) -> list[dict]:
    """Cari hesaplar listesini dropdown için döndürür."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, unvan FROM carihesaplar WHERE userid = ? ORDER BY unvan ASC",
            (userid,)
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()
