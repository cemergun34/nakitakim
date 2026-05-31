#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL womsiPos → SQLite womsi_pos aktarımı.
paytr_importer.py ile aynı mysql.connector kullanımı.
Kullanım: python3 db/womsipos_importer.py
"""
import sys
import os
import decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "iqdev21Nisan",
    "charset": "utf8mb4",
}


def _val(v):
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    if isinstance(v, decimal.Decimal):
        return float(v)
    return v


def run_import(progress_cb=None) -> dict:
    try:
        import mysql.connector
    except ImportError:
        return {
            "success": False,
            "message": "mysql-connector-python yüklü değil. pip install mysql-connector-python",
        }

    from db.database import get_connection
    from services.fiziksel_pos_service import ensure_tables

    ensure_tables()

    try:
        mysql_conn = mysql.connector.connect(**MYSQL_CONFIG)
        mysql_cur  = mysql_conn.cursor()
    except Exception as e:
        return {"success": False, "message": f"MySQL bağlantısı kurulamadı: {e}"}

    sqlite_conn = get_connection()

    try:
        # MySQL'de womsiPos var mı?
        mysql_cur.execute(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
            (MYSQL_CONFIG["database"], "womsiPos"),
        )
        if mysql_cur.fetchone()[0] == 0:
            return {"success": True, "eklenen": 0, "atlanan": 0,
                    "message": "MySQL'de womsiPos tablosu bulunamadı (boş veya yok)."}

        mysql_cur.execute("""
            SELECT userid, musterino,
                   isyeriNo, cariHesap, hesabaGecisTarihi,
                   islemTutari, islemTarihi, posNo,
                   isyeriUcretiTutar, netTutar, brand,
                   kartNo, islemTipi, aciklama, islemTarih, kayitTarihi
            FROM womsiPos ORDER BY id
        """)
        rows = mysql_cur.fetchall()
        cols = [d[0] for d in mysql_cur.description]

        if progress_cb:
            progress_cb("womsiPos", f"MySQL'den {len(rows):,} kayıt okundu")

        ins = skip = 0
        for row in rows:
            r = {cols[i]: _val(v) for i, v in enumerate(row)}
            try:
                sqlite_conn.execute("""
                    INSERT OR IGNORE INTO womsi_pos
                        (userid, musterino, isyeriNo, cariHesap, hesabaGecisTarihi,
                         islemTutari, islemTarihi, posNo,
                         isyeriUcretiTutar, netTutar, brand,
                         kartNo, islemTipi, aciklama, islemTarih, kayitTarihi)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    r.get("userid", 0), r.get("musterino", 1),
                    r.get("isyeriNo", ""), r.get("cariHesap", ""),
                    r.get("hesabaGecisTarihi", ""),
                    float(r.get("islemTutari") or 0),
                    r.get("islemTarihi", ""),
                    r.get("posNo", ""),
                    float(r.get("isyeriUcretiTutar") or 0),
                    float(r.get("netTutar") or 0),
                    r.get("brand", ""), r.get("kartNo", ""),
                    r.get("islemTipi", ""), r.get("aciklama", ""),
                    r.get("islemTarih", ""),
                    str(r.get("kayitTarihi", "") or ""),
                ))
                if sqlite_conn.execute("SELECT changes()").fetchone()[0] > 0:
                    ins += 1
                else:
                    skip += 1
            except Exception as e:
                skip += 1

        sqlite_conn.commit()

        if progress_cb:
            progress_cb("womsiPos", f"{ins:,} eklendi, {skip:,} mükerrer atlandı")

        count = sqlite_conn.execute("SELECT COUNT(*) FROM womsi_pos").fetchone()[0]
        return {
            "success": True,
            "eklenen": ins,
            "atlanan": skip,
            "toplam":  count,
            "message": f"{ins:,} kayıt eklendi, {skip:,} mükerrer atlandı. Toplam: {count:,}",
        }

    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        mysql_cur.close()
        mysql_conn.close()
        sqlite_conn.close()


if __name__ == "__main__":
    print("=" * 55)
    print("womsiPos MySQL → SQLite Aktarımı")
    print("=" * 55)

    def cb(tablo, msg):
        print(f"  ✔ {tablo:20s} → {msg}")

    r = run_import(progress_cb=cb)
    print()
    if r["success"]:
        print(f"✅ Tamamlandı: {r['message']}")
    else:
        print(f"❌ Hata: {r['message']}")
