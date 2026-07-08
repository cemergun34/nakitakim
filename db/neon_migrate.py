#!/usr/bin/env python3
"""SQLite → Neon hızlı toplu aktarım scripti."""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import DB_PATH, _get_pg_connection

TABLES = [
    'uyelik', 'tanim_kullanici', 'Subeler', 'kategoriler', 'odemeSekli',
    'altHesapKodu', 'hareketler', 'genel_hesap_hareketleri', 'faturalar',
    'cariHesaplar', 'nakitakis_Hareket', 'nakitakis_Parametre',
    'sirket_profili', 'vomsisBilgileri', 'moy_bilgileri', 'VergiMuhtasar',
    'key_kartlari', 'kredikartiData', 'paytr', 'paytr_sync_log',
    'apisanalpos', 'ibanHesapBilgileri', 'alt_kullanici', 'womsi_pos'
]

sqlite_conn = sqlite3.connect(str(DB_PATH))
sqlite_conn.row_factory = sqlite3.Row
pg = _get_pg_connection()
raw = pg._conn

print("=" * 55)
print("SQLite → Neon Toplu Aktarım")
print("=" * 55)

total = 0
for table in TABLES:
    try:
        rows = sqlite_conn.execute(f'SELECT * FROM "{table}"').fetchall()
        if not rows:
            print(f"  ⬜ {table:30s} boş, atlandı")
            continue

        cols = list(rows[0].keys())
        col_str = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join(["%s"] * len(cols))
        sql = (
            f'INSERT INTO "{table}" ({col_str}) VALUES ({placeholders}) '
            f'ON CONFLICT DO NOTHING'
        )

        data = [tuple(row) for row in rows]
        cur = raw.cursor()
        # executemany → tek seferde tüm satırları gönder
        from psycopg2.extras import execute_batch
        execute_batch(cur, sql, data, page_size=500)
        raw.commit()

        # Reset sequence (identity) to match max ID
        pg_tablo = table.lower()
        pk_col = "kayitno" if pg_tablo == "tanim_kullanici" else "id"
        try:
            cur.execute(f"SELECT setval(pg_get_serial_sequence('\"{pg_tablo}\"', '{pk_col}'), COALESCE(MAX(\"{pk_col}\"), 1)) FROM \"{pg_tablo}\"")
            raw.commit()
        except Exception:
            pass

        cur.close()
        total += len(data)
        print(f"  ✅ {table:30s} {len(data):>6,} kayıt aktarıldı")
    except Exception as e:
        raw.rollback()
        print(f"  ❌ {table:30s} HATA: {e}")

sqlite_conn.close()
raw.close()
print("=" * 55)
print(f"TOPLAM: {total:,} kayıt Neon'a aktarıldı! 🎉")
