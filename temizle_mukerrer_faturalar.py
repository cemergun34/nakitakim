#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mükerrer Fatura Temizleme Scripti
===================================
faturalar tablosundaki gelen (gelir) ve kesilen (gider) faturalardaki
tüm mükerrer kayıtları siler.

Strateji:
  1. Hash bazlı: Aynı hash + userid grubunda en küçük id korunur, diğerleri silinir.
  2. FaturaNo bazlı: Aynı faturano + userid + gelirgidermod grubunda
     en küçük id korunur, diğerleri silinir.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import get_connection


def main():
    conn = get_connection()
    cur = conn._conn.cursor()

    print("=== MÜKERRER FATURA TEMİZLEME BAŞLIYOR ===\n")

    # Başlangıç sayısı
    cur.execute("SELECT COUNT(*) FROM faturalar")
    total_before = cur.fetchone()[0]
    print(f"Başlangıç kayıt sayısı: {total_before}\n")

    # ─── ADIM 1: Hash bazlı mükerrer silme ───────────────────────────────────
    print("ADIM 1: Hash bazlı mükerrer kayıtlar siliniyor...")
    cur.execute("""
        DELETE FROM faturalar
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY hash, userid
                           ORDER BY id ASC
                       ) AS rn
                FROM faturalar
                WHERE hash IS NOT NULL AND hash <> ''
            ) ranked
            WHERE rn > 1
        )
        RETURNING id
    """)
    deleted_hash = cur.fetchall()
    print(f"  Hash bazlı silinen: {len(deleted_hash)} kayıt")
    conn._conn.commit()

    # ─── ADIM 2: FaturaNo bazlı mükerrer silme ───────────────────────────────
    print("\nADIM 2: FaturaNo bazlı mükerrer kayıtlar siliniyor...")
    cur.execute("""
        DELETE FROM faturalar
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY faturano, userid, gelirgidermod
                           ORDER BY id ASC
                       ) AS rn
                FROM faturalar
                WHERE faturano IS NOT NULL AND faturano <> ''
            ) ranked
            WHERE rn > 1
        )
        RETURNING id
    """)
    deleted_fno = cur.fetchall()
    print(f"  FaturaNo bazlı silinen: {len(deleted_fno)} kayıt")
    conn._conn.commit()

    # ─── Sonuç ve doğrulama ──────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM faturalar")
    total_after = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT hash, userid, COUNT(*) AS cnt
            FROM faturalar
            WHERE hash IS NOT NULL AND hash <> ''
            GROUP BY hash, userid
            HAVING COUNT(*) > 1
        ) sub
    """)
    leftover_hash = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT faturano, userid, gelirgidermod, COUNT(*) AS cnt
            FROM faturalar
            WHERE faturano IS NOT NULL AND faturano <> ''
            GROUP BY faturano, userid, gelirgidermod
            HAVING COUNT(*) > 1
        ) sub
    """)
    leftover_fno = cur.fetchone()[0]

    print("\n=== SONUÇ ===")
    print(f"Toplam silinen    : {len(deleted_hash) + len(deleted_fno)} kayıt")
    print(f"  Hash bazlı      : {len(deleted_hash)}")
    print(f"  FaturaNo bazlı  : {len(deleted_fno)}")
    print(f"Kalan kayıt       : {total_after} (öncesi: {total_before})")
    print(f"Kalan hash mükerrer    : {leftover_hash}")
    print(f"Kalan faturano mükerrer: {leftover_fno}")

    if leftover_hash == 0 and leftover_fno == 0:
        print("\n✅ Tüm mükerrer kayıtlar başarıyla silindi!")
    else:
        print("\n⚠️  Bazı mükerrer kayıtlar hâlâ mevcut, kontrol edin.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
