#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PayTR MySQL → SQLite Aktarım Scripti
=====================================
MySQL (XAMPP/iqdev21Nisan) veritabanındaki:
  - paytr          tablosunu (1254 kayıt)
  - apisanalpos    tablosunu (API anahtarları dahil)
  - paytr_sync_log tablosunu

SQLite (~/NakitAkim/data/nakit_akim.db) veritabanına aktarır.

Kullanım:
    python3 db/paytr_importer.py

Gereksinim:
    pip install mysql-connector-python
"""
import sys
import decimal

# XAMPP MySQL config (db/importer.py ile aynı)
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "iqdev21Nisan",
    "charset": "utf8mb4",
}


def _val(v):
    """MySQL değerini SQLite-uyumlu Python tipine çevirir."""
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    if isinstance(v, decimal.Decimal):
        return float(v)
    return v


def import_paytr(mysql_cur, sqlite_conn) -> tuple[int, int]:
    """
    MySQL paytr → SQLite paytr
    INSERT OR IGNORE (siparisno benzersizliği UNIQUE(userid, siparisno))
    Döndürür: (eklenen, atlanan)
    """
    mysql_cur.execute("SELECT * FROM `paytr`")
    rows = mysql_cur.fetchall()
    if not rows:
        return 0, 0

    cols = [d[0] for d in mysql_cur.description]

    # SQLite sütunları (schema.py ile eşleşen)
    SQLITE_COLS = [
        "id", "userid", "musterino", "islemtarihi", "siparisno",
        "islemtutari", "odemetutari", "kur", "magazano", "adsoyad",
        "nettutar", "kesintitutari", "kesintiorani", "kartbankasi",
        "kartmarkasi", "kartno", "odemetipi", "karttipi", "taksitsayisi",
        "guncelleme_tarihi", "created_at",
    ]
    # MySQL → SQLite sütun eşleşmesi (aynı adlı olanlar otomatik)
    col_map = {c: c for c in SQLITE_COLS if c in cols}

    eklenen = atlanan = 0
    for row in rows:
        row_dict = {cols[i]: _val(v) for i, v in enumerate(row)}

        vals = [row_dict.get(sc) for sc in SQLITE_COLS if sc in col_map]
        mapped_cols = [sc for sc in SQLITE_COLS if sc in col_map]

        ph = ", ".join(["?"] * len(mapped_cols))
        col_str = ", ".join(mapped_cols)
        sql = f"INSERT OR IGNORE INTO paytr ({col_str}) VALUES ({ph})"
        try:
            cur = sqlite_conn.execute(sql, vals)
            changed = cur.rowcount if (hasattr(cur, "rowcount") and cur.rowcount != -1) else sqlite_conn.execute("SELECT changes()").fetchone()[0]
            if changed > 0:
                eklenen += 1
            else:
                atlanan += 1
        except Exception:
            atlanan += 1

    return eklenen, atlanan


def import_apisanalpos(mysql_cur, sqlite_conn) -> tuple[int, int]:
    """
    MySQL apisanalpos → SQLite apisanalpos
    INSERT OR REPLACE (id PK ile)
    Döndürür: (eklenen, atlanan)
    """
    mysql_cur.execute("SELECT * FROM `apisanalpos`")
    rows = mysql_cur.fetchall()
    if not rows:
        return 0, 0

    cols = [d[0] for d in mysql_cur.description]

    # SQLite sütunları (schema.py + musterino dahil)
    SQLITE_COLS = [
        "id", "userid", "musterino", "firma_adi",
        "magaza_no", "magaza_parola", "magaza_gizli_anahtar",
        "kayit_tarihi",
    ]

    # created_at → kayit_tarihi alias
    alias = {"created_at": "kayit_tarihi"}

    eklenen = atlanan = 0
    for row in rows:
        row_dict = {cols[i]: _val(v) for i, v in enumerate(row)}

        # Alias uygula
        for mysql_col, sqlite_col in alias.items():
            if mysql_col in row_dict and sqlite_col not in row_dict:
                row_dict[sqlite_col] = row_dict[mysql_col]

        mapped_cols = [sc for sc in SQLITE_COLS if sc in row_dict]
        vals = [row_dict[sc] for sc in mapped_cols]

        ph = ", ".join(["?"] * len(mapped_cols))
        col_str = ", ".join(mapped_cols)
        sql = f"INSERT OR REPLACE INTO apisanalpos ({col_str}) VALUES ({ph})"
        try:
            sqlite_conn.execute(sql, vals)
            eklenen += 1
        except Exception:
            atlanan += 1

    return eklenen, atlanan


def import_paytr_sync_log(mysql_cur, sqlite_conn) -> tuple[int, int]:
    """
    MySQL paytr_sync_log → SQLite paytr_sync_log
    INSERT OR REPLACE
    Döndürür: (eklenen, atlanan)
    """
    # MySQL'de tablo var mı?
    mysql_cur.execute(
        "SELECT COUNT(*) FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
        (MYSQL_CONFIG["database"], "paytr_sync_log"),
    )
    if mysql_cur.fetchone()[0] == 0:
        return 0, 0

    mysql_cur.execute("SELECT * FROM `paytr_sync_log`")
    rows = mysql_cur.fetchall()
    if not rows:
        return 0, 0

    cols = [d[0] for d in mysql_cur.description]

    SQLITE_COLS = ["id", "userid", "musterino", "son_sync_tarihi", "updated_at"]

    eklenen = atlanan = 0
    for row in rows:
        row_dict = {cols[i]: _val(v) for i, v in enumerate(row)}
        mapped_cols = [sc for sc in SQLITE_COLS if sc in row_dict]
        vals = [row_dict[sc] for sc in mapped_cols]

        ph = ", ".join(["?"] * len(mapped_cols))
        col_str = ", ".join(mapped_cols)
        sql = f"INSERT OR REPLACE INTO paytr_sync_log ({col_str}) VALUES ({ph})"
        try:
            sqlite_conn.execute(sql, vals)
            eklenen += 1
        except Exception:
            atlanan += 1

    return eklenen, atlanan


def run_paytr_import(progress_cb=None) -> dict:
    """
    Ana aktarım fonksiyonu.
    progress_cb(tablo, msg) → opsiyonel geri çağırım.

    Döndürür:
        {
            'success': bool,
            'paytr_eklenen': int, 'paytr_atlanan': int,
            'apisanalpos_eklenen': int, 'apisanalpos_atlanan': int,
            'sync_log_eklenen': int,
            'message': str,
            'errors': [str, ...]
        }
    """
    try:
        import mysql.connector
    except ImportError:
        return {
            "success": False,
            "message": "mysql-connector-python yüklü değil. pip install mysql-connector-python",
            "errors": ["mysql-connector-python import hatası"],
        }

    from db.database import get_connection
    from services.paytr_service import ensure_tables

    # SQLite tablolarını hazırla
    ensure_tables()

    # SQLite'daki mevcut apisanalpos tablosuna musterino sütunu ekle (varsa devam et)
    sqlite_conn = get_connection()
    try:
        sqlite_conn.execute("ALTER TABLE apisanalpos ADD COLUMN musterino TEXT NOT NULL DEFAULT '1'")
        sqlite_conn.commit()
    except Exception:
        pass  # Sütun zaten varsa devam et

    errors = []

    try:
        mysql_conn = mysql.connector.connect(**MYSQL_CONFIG)
        mysql_cur = mysql_conn.cursor()
    except Exception as e:
        sqlite_conn.close()
        return {
            "success": False,
            "message": f"MySQL bağlantısı kurulamadı: {e}",
            "errors": [str(e)],
        }

    # ─── paytr tablosu ───────────────────────────────────────────────
    try:
        pe, pa = import_paytr(mysql_cur, sqlite_conn)
        if progress_cb:
            progress_cb("paytr", f"{pe} eklendi, {pa} mükerrer atlandı")
    except Exception as e:
        pe = pa = 0
        errors.append(f"paytr: {e}")
        if progress_cb:
            progress_cb("paytr", f"HATA: {e}")

    # ─── apisanalpos tablosu ─────────────────────────────────────────
    try:
        ae, aa = import_apisanalpos(mysql_cur, sqlite_conn)
        if progress_cb:
            progress_cb("apisanalpos", f"{ae} API kaydı eklendi/güncellendi")
    except Exception as e:
        ae = aa = 0
        errors.append(f"apisanalpos: {e}")
        if progress_cb:
            progress_cb("apisanalpos", f"HATA: {e}")

    # ─── paytr_sync_log tablosu ──────────────────────────────────────
    try:
        se, _ = import_paytr_sync_log(mysql_cur, sqlite_conn)
        if progress_cb:
            progress_cb("paytr_sync_log", f"{se} sync log kaydı eklendi")
    except Exception as e:
        se = 0
        errors.append(f"paytr_sync_log: {e}")
        if progress_cb:
            progress_cb("paytr_sync_log", f"HATA: {e}")

    sqlite_conn.commit()
    sqlite_conn.close()
    mysql_cur.close()
    mysql_conn.close()

    toplam = pe + ae + se
    msg = (
        f"paytr: {pe} kayıt, "
        f"apisanalpos: {ae} API kaydı, "
        f"paytr_sync_log: {se} sync kaydı aktarıldı."
    )
    if errors:
        msg += f"  ⚠ {len(errors)} hata oluştu."

    return {
        "success": len(errors) == 0,
        "paytr_eklenen": pe,
        "paytr_atlanan": pa,
        "apisanalpos_eklenen": ae,
        "apisanalpos_atlanan": aa,
        "sync_log_eklenen": se,
        "message": msg,
        "errors": errors,
    }


if __name__ == "__main__":
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    print("=" * 60)
    print("PayTR MySQL → SQLite Aktarım")
    print("=" * 60)

    def cb(tablo, msg):
        print(f"  ✔ {tablo:20s} → {msg}")

    result = run_paytr_import(progress_cb=cb)

    print()
    if result["success"]:
        print(f"✅ Tamamlandı: {result['message']}")
    else:
        print(f"⚠  Kısmen tamamlandı: {result['message']}")
        for err in result.get("errors", []):
            print(f"   ✗ {err}")

    print()
    print(f"  paytr        : {result.get('paytr_eklenen', 0)} eklendi, {result.get('paytr_atlanan', 0)} mükerrer")
    print(f"  apisanalpos  : {result.get('apisanalpos_eklendi', result.get('apisanalpos_eklenen', 0))} eklendi")
    print(f"  paytr_sync_log: {result.get('sync_log_eklenen', 0)} eklendi")
