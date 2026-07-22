#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neon -> Windows PostgreSQL Tablo Taşıyıcı
Sorunlu 4 tabloyu SELECT/INSERT ile taşır
"""
import psycopg2
import sys

NEON = {
    "host": "ep-sparkling-bird-alczfon2-pooler.c-3.eu-central-1.aws.neon.tech",
    "port": 5432,
    "dbname": "neondb",
    "user": "neondb_owner",
    "password": "npg_AD1QJTeoksg5",
    "sslmode": "require",
    "connect_timeout": 15,
}

WINDOWS = {
    "host": "178.233.204.224",
    "port": 5432,
    "dbname": "neondb",
    "user": "postgres",
    "password": "postgres123",
    "sslmode": "disable",
    "connect_timeout": 15,
}

TABLES = [
    "key_kartlari",
    "kredikartidata",
    "vomsisbilgileri",
    "webadmin_sirket_config",
]

def migrate_table(neon_cur, win_cur, win_conn, table):
    print(f"\n[*] {table} taşınıyor...")

    # Satırları çek
    neon_cur.execute(f'SELECT * FROM "{table}"')
    rows = neon_cur.fetchall()
    cols = [desc[0] for desc in neon_cur.description]

    if not rows:
        print(f"    -> Boş tablo, atlanıyor.")
        return 0

    # Windows'ta temizle
    win_cur.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE')

    # INSERT
    col_str = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    sql = f'INSERT INTO "{table}" ({col_str}) VALUES ({placeholders})'

    try:
        win_cur.executemany(sql, rows)
        win_conn.commit()
        print(f"    -> {len(rows)} satır aktarıldı ✓")
        return len(rows)
    except Exception as e:
        win_conn.rollback()
        print(f"    -> HATA: {e}")
        # Tek tek dene
        ok = 0
        for row in rows:
            try:
                win_cur.execute(sql, row)
                win_conn.commit()
                ok += 1
            except Exception as e2:
                win_conn.rollback()
                print(f"       Satır atlandı: {e2}")
        print(f"    -> {ok}/{len(rows)} satır aktarıldı")
        return ok

def main():
    print("=" * 50)
    print("  Neon -> Windows Veri Taşıyıcı")
    print("=" * 50)

    print("\n[*] Neon'a bağlanılıyor...")
    neon_conn = psycopg2.connect(**NEON)
    neon_cur = neon_conn.cursor()
    print("    -> Neon bağlantısı OK ✓")

    print("[*] Windows'a bağlanılıyor...")
    win_conn = psycopg2.connect(**WINDOWS)
    win_cur = win_conn.cursor()
    print("    -> Windows bağlantısı OK ✓")

    total = 0
    for table in TABLES:
        total += migrate_table(neon_cur, win_cur, win_conn, table)

    neon_cur.close()
    neon_conn.close()
    win_cur.close()
    win_conn.close()

    print(f"\n{'='*50}")
    print(f"  TAMAMLANDI! Toplam {total} satır taşındı.")
    print(f"{'='*50}")

    # Doğrulama
    print("\n[*] Doğrulama yapılıyor...")
    win_conn2 = psycopg2.connect(**WINDOWS)
    win_cur2 = win_conn2.cursor()
    neon_conn2 = psycopg2.connect(**NEON)
    neon_cur2 = neon_conn2.cursor()

    print(f"\n{'Tablo':<30} {'Neon':>8} {'Windows':>10} {'Durum':>8}")
    print("-" * 60)
    for table in TABLES:
        neon_cur2.execute(f'SELECT COUNT(*) FROM "{table}"')
        n = neon_cur2.fetchone()[0]
        win_cur2.execute(f'SELECT COUNT(*) FROM "{table}"')
        w = win_cur2.fetchone()[0]
        status = "✓ EŞİT" if n == w else "✗ FARK"
        print(f"{table:<30} {n:>8} {w:>10} {status:>8}")

    win_cur2.close(); win_conn2.close()
    neon_cur2.close(); neon_conn2.close()

if __name__ == "__main__":
    main()
