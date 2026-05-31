#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL → SQLite Eksik Verileri Göç Ettirme Scripti
==================================================
Bu script, MySQL veritabanından eksik kalan verileri (Subeler, cariHesaplar ve faturalar)
SQLite veritabanına aktarır.

Kullanım:
    python3 db/full_migrator.py
"""
import sqlite3
import mysql.connector
import decimal

MYSQL_CFG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "iqdev21Nisan",
    "charset": "utf8mb4",
}

SQLITE_PATH = "/Users/cemergun/NakitAkim/data/nakit_akim.db"


def _val(v):
    """MySQL değerini SQLite uyumlu tipe çevirir."""
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    if isinstance(v, decimal.Decimal):
        return float(v)
    return v


def migrate_table(mysql_cur, sqlite_conn, table_name):
    print(f"\n▶  {table_name} tablosu aktarılıyor...")
    
    # SQLite'daki mevcut sütunları sorgula
    sqlite_cur = sqlite_conn.cursor()
    try:
        sqlite_cur.execute(f"PRAGMA table_info(`{table_name}`)")
        sqlite_cols = [r[1] for r in sqlite_cur.fetchall()]
    except Exception as exc:
        print(f"  ❌ SQLite'ta {table_name} tablosu sorgulanamadı: {exc}")
        return
        
    if not sqlite_cols:
        print(f"  ❌ SQLite'ta {table_name} tablosu şeması boş veya tablo mevcut değil.")
        return

    # MySQL'den verileri çek
    try:
        mysql_cur.execute(f"SELECT * FROM `{table_name}`")
        rows = mysql_cur.fetchall()
        mysql_cols = [desc[0] for desc in mysql_cur.description]
    except Exception as exc:
        print(f"  ❌ MySQL'den {table_name} tablosu okunamadı: {exc}")
        return

    if not rows:
        print(f"  ℹ  MySQL'de {table_name} tablosunda veri yok.")
        return

    # Hem MySQL hem SQLite tarafında ortak olan sütunları belirle
    common_cols = [c for c in sqlite_cols if c in mysql_cols]
    if not common_cols:
        print(f"  ❌ {table_name} için ortak sütun bulunamadı!")
        return

    print(f"  Ortak sütunlar: {', '.join(common_cols)}")
    
    col_str = ", ".join([f"`{c}`" for c in common_cols])
    ph_str = ", ".join(["?"] * len(common_cols))
    insert_sql = f"INSERT OR REPLACE INTO `{table_name}` ({col_str}) VALUES ({ph_str})"

    added_count = 0
    
    # SQLite'a toplu yazma
    data_to_insert = []
    for row in rows:
        row_dict = {mysql_cols[i]: _val(val) for i, val in enumerate(row)}
        vals = tuple(row_dict.get(c) for c in common_cols)
        data_to_insert.append(vals)

    try:
        sqlite_conn.executemany(insert_sql, data_to_insert)
        sqlite_conn.commit()
        added_count = len(data_to_insert)
        print(f"  ✅ Başarıyla {added_count} kayıt aktarıldı/güncellendi.")
    except Exception as exc:
        sqlite_conn.rollback()
        print(f"  ❌ Toplu ekleme hatası: {exc}")

    return added_count


def main():
    print("=" * 60)
    print("MySQL → SQLite Veri Göçü (Eksik Veri Entegrasyonu)")
    print("=" * 60)

    try:
        mysql_conn = mysql.connector.connect(**MYSQL_CFG)
        mysql_cur = mysql_conn.cursor()
    except Exception as exc:
        print(f"❌ MySQL bağlantısı başarısız: {exc}")
        return

    try:
        sqlite_conn = sqlite3.connect(SQLITE_PATH)
    except Exception as exc:
        print(f"❌ SQLite bağlantısı başarısız: {exc}")
        mysql_cur.close()
        mysql_conn.close()
        return

    tables_to_migrate = ["Subeler", "cariHesaplar", "faturalar", "altHesapKodu", "odemeSekli", "ibanHesapBilgileri"]

    for table in tables_to_migrate:
        migrate_table(mysql_cur, sqlite_conn, table)

    # Bağlantıları kapat
    mysql_cur.close()
    mysql_conn.close()
    sqlite_conn.close()
    
    print("\n" + "=" * 60)
    print("🎉 Tüm eksik veriler başarıyla göç ettirildi!")
    print("=" * 60)


if __name__ == "__main__":
    main()
