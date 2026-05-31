#!/usr/bin/env python3
"""
Supabase'deki büyük-küçük harf sorunlarını otomatik düzeltir.
Çalıştırmak için: python3 db/migrations/fix_pg_case.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from db.db_config import get_pg_params

def fix():
    try:
        import psycopg2
    except ImportError:
        print("❌ psycopg2 yüklü değil: pip install psycopg2-binary")
        return

    params = get_pg_params()
    print(f"🔗  Bağlanılıyor: {params['host']}:{params['port']}/{params['dbname']}")

    try:
        conn = psycopg2.connect(**params)
        conn.autocommit = False
        cur = conn.cursor()
    except Exception as e:
        print(f"❌ Bağlantı hatası: {e}")
        return

    fixes = []

    # ── 1. vomsisBilgileri tablosu ───────────────────────────────────────────
    # Büyük harfli (tırnaklı) tablo var mı?
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
          AND LOWER(table_name) = 'vomsisbilgileri'
    """)
    rows = cur.fetchall()
    existing_names = [r[0] for r in rows]

    if '"vomsisBilgileri"' in [f'"{n}"' for n in existing_names] or \
       any(n != 'vomsisbilgileri' for n in existing_names):
        # Tırnaklı (büyük harf korumalı) tablo var, sorgu tırnaksız çalışmıyor
        for name in existing_names:
            if name == 'vomsisbilgileri':
                print(f"✅  vomsisBilgileri zaten küçük harf (tırnaksız) — OK")
            else:
                print(f"⚠️   Tablo '{name}' bulundu. Yeniden adlandırılıyor → vomsisbilgileri...")
                try:
                    cur.execute(f'ALTER TABLE "{name}" RENAME TO vomsisbilgileri_new')
                    cur.execute('ALTER TABLE vomsisbilgileri_new RENAME TO "vomsisBilgileri"')
                    conn.commit()
                    fixes.append(f"vomsisBilgileri tablo adı düzeltildi")
                    print(f"✅  Tablo yeniden adlandırıldı.")
                except Exception as e:
                    conn.rollback()
                    print(f"❌  Rename başarısız: {e}")
    elif not existing_names:
        print("ℹ️   vomsisBilgileri tablosu yok — şema init ile oluşturulacak.")
    else:
        print(f"✅  vomsisBilgileri tablosu: {existing_names[0]} — OK")

    # ── 2. moy_bilgileri.musteriNo / moyKayitNo kolonları ────────────────────
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'moy_bilgileri'
    """)
    cols = [r[0] for r in cur.fetchall()]

    if not cols:
        print("ℹ️   moy_bilgileri tablosu yok — şema init ile oluşturulacak.")
    else:
        print(f"ℹ️   moy_bilgileri kolonları: {cols}")

        # musteriNo kontrolü
        if 'musterino' in cols and 'musteriNo' not in cols:
            print("⚠️   moy_bilgileri.musterino → musteriNo yeniden adlandırılıyor...")
            try:
                cur.execute('ALTER TABLE moy_bilgileri RENAME COLUMN musterino TO "musteriNo"')
                conn.commit()
                fixes.append('moy_bilgileri.musterino → musteriNo')
                print("✅  musteriNo düzeltildi.")
            except Exception as e:
                conn.rollback()
                print(f"❌  Rename hatası: {e}")
        elif 'musteriNo' in cols:
            print("✅  moy_bilgileri.musteriNo — OK")
        else:
            print("⚠️   moy_bilgileri.musteriNo kolonu hiç yok!")

        # moyKayitNo kontrolü
        if 'moykayitno' in cols and 'moyKayitNo' not in cols:
            print("⚠️   moy_bilgileri.moykayitno → moyKayitNo yeniden adlandırılıyor...")
            try:
                cur.execute('ALTER TABLE moy_bilgileri RENAME COLUMN moykayitno TO "moyKayitNo"')
                conn.commit()
                fixes.append('moy_bilgileri.moykayitno → moyKayitNo')
                print("✅  moyKayitNo düzeltildi.")
            except Exception as e:
                conn.rollback()
                print(f"❌  Rename hatası: {e}")
        elif 'moyKayitNo' in cols:
            print("✅  moy_bilgileri.moyKayitNo — OK")
        else:
            print("⚠️   moy_bilgileri.moyKayitNo kolonu hiç yok!")

    cur.close()
    conn.close()

    print("\n" + "="*50)
    if fixes:
        print(f"🎉  {len(fixes)} düzeltme yapıldı:")
        for f in fixes:
            print(f"   • {f}")
    else:
        print("✅  Düzeltme gerekmedi, her şey OK.")
    print("="*50)


if __name__ == "__main__":
    fix()
