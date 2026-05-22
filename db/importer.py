"""
MySQL → SQLite veri aktarım aracı.
Kullanım: python -m db.importer
"""
import sys
import mysql.connector
from db.database import get_connection, initialize_db

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "iqdev21Nisan",
    "charset": "utf8mb4",
}

# (mysql_tablo, sqlite_tablo, sütun_haritası_fonksiyonu)
TABLES = [
    "uyelik",
    "tanim_kullanici",
    "Subeler",
    "kategoriler",
    "odemeSekli",
    "altHesapKodu",
    "hareketler",
    "genel_hesap_hareketleri",
    "faturalar",
    "nakitakis_Hareket",
    "nakitakis_Parametre",
]


def get_mysql_connection():
    return mysql.connector.connect(**MYSQL_CONFIG)


def import_table(mysql_cur, sqlite_conn, table_name: str, progress_cb=None):
    """Bir tabloyu MySQL'den okuyup SQLite'a yazar."""
    mysql_cur.execute(f"SELECT * FROM `{table_name}`")
    rows = mysql_cur.fetchall()
    if not rows:
        return 0

    cols = [desc[0] for desc in mysql_cur.description]
    placeholders = ", ".join(["?"] * len(cols))
    col_str = ", ".join([f'"{c}"' for c in cols])
    sql = f'INSERT OR REPLACE INTO "{table_name}" ({col_str}) VALUES ({placeholders})'

    import decimal
    data = []
    for row in rows:
        processed = []
        for val in row:
            if isinstance(val, bytes):
                val = val.decode("utf-8", errors="replace")
            elif isinstance(val, decimal.Decimal):
                val = float(val)
            processed.append(val)
        data.append(tuple(processed))

    sqlite_conn.executemany(sql, data)
    if progress_cb:
        progress_cb(table_name, len(data))
    return len(data)


def run_import(progress_cb=None):
    """
    Tam import.
    progress_cb(table_name: str, count: int) → isteğe bağlı geri çağırım.
    """
    initialize_db()

    mysql_conn = get_mysql_connection()
    mysql_cur = mysql_conn.cursor()
    sqlite_conn = get_connection()

    total = 0
    errors = []

    for table in TABLES:
        try:
            # MySQL'de tablo var mı?
            mysql_cur.execute(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
                (MYSQL_CONFIG["database"], table),
            )
            if mysql_cur.fetchone()[0] == 0:
                if progress_cb:
                    progress_cb(table, -1)  # -1 = bulunamadı
                continue

            count = import_table(mysql_cur, sqlite_conn, table, progress_cb)
            total += count
        except Exception as e:
            errors.append(f"{table}: {e}")
            if progress_cb:
                progress_cb(table, -2)  # -2 = hata

    sqlite_conn.commit()
    mysql_cur.close()
    mysql_conn.close()
    sqlite_conn.close()

    return total, errors


if __name__ == "__main__":
    def cb(tbl, cnt):
        if cnt == -1:
            print(f"  ⚠ {tbl} MySQL'de bulunamadı")
        elif cnt == -2:
            print(f"  ✗ {tbl} HATA")
        else:
            print(f"  ✔ {tbl}: {cnt} kayıt")

    print("MySQL → SQLite aktarım başlatılıyor...")
    total, errs = run_import(cb)
    print(f"\nTamamlandı. Toplam {total} kayıt aktarıldı.")
    if errs:
        print("Hatalar:")
        for e in errs:
            print(f"  - {e}")
