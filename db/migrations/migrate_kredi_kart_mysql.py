#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL → SQLite Kredi Kartı Migration Scripti
Taşınan tablolar:
  - key_kartlari   (kart tanımları)
  - kredikartiData (banka ekstre kayıtları)
"""
import json
import sys
from pathlib import Path

# Proje kök dizini
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from db.database import get_connection
from db.schema import SCHEMA_SQL

EXPORT_FILE = Path("/tmp/kredi_mysql_export.json")


def migrate():
    print("=" * 60)
    print("MySQL → SQLite Kredi Kartı Migration")
    print("=" * 60)

    # JSON dosyasını yükle
    if not EXPORT_FILE.exists():
        print(f"❌  Export dosyası bulunamadı: {EXPORT_FILE}")
        sys.exit(1)

    with open(EXPORT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    key_kartlari   = data.get("key_kartlari", [])
    kredi_data     = data.get("kredikartiData", [])

    print(f"📦  MySQL'den alınan veri:")
    print(f"    key_kartlari   : {len(key_kartlari)} kayıt")
    print(f"    kredikartiData : {len(kredi_data)} kayıt")
    print()

    conn = get_connection()

    # Şemayı uygula (tablolar yoksa oluşturur)
    conn.executescript(SCHEMA_SQL)
    conn.commit()

    # ── 1. key_kartlari ────────────────────────────────────────────────
    print("▶  key_kartlari aktarılıyor...")
    eklenen_kart = atlandı_kart = 0

    for row in key_kartlari:
        # MySQL id'sini kullan (aynen koru)
        mysql_id   = row.get("id")
        banka      = row.get("banka") or ""
        no         = row.get("no") or ""
        tag        = row.get("tag") or ""
        userid     = int(row.get("userid") or 0)
        hesapKodu  = row.get("hesapKodu") or ""
        bankaAdi   = row.get("bankaAdi") or ""
        iban       = row.get("iban") or ""

        # Zaten var mı? (userid + banka + no üçlüsüne göre)
        mevcut = conn.execute(
            "SELECT id FROM key_kartlari WHERE userid=? AND banka=? AND no=?",
            (userid, banka, no)
        ).fetchone()

        if mevcut:
            atlandı_kart += 1
            continue

        conn.execute(
            "INSERT INTO key_kartlari (id, banka, no, tag, userid, hesapKodu, bankaAdi, iban) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (mysql_id, banka, no, tag, userid, hesapKodu, bankaAdi, iban)
        )
        eklenen_kart += 1

    conn.commit()
    print(f"    ✅  {eklenen_kart} eklendi, {atlandı_kart} zaten mevcut atlandı")

    # ── 2. kredikartiData ──────────────────────────────────────────────
    print()
    print("▶  kredikartiData aktarılıyor...")
    eklenen_data = atlandı_data = hatali_data = 0

    for row in kredi_data:
        userid_val    = str(row.get("userid") or "")
        musterino     = str(row.get("musterino") or "")
        tarih         = row.get("tarih") or ""
        aciklama      = row.get("aciklama") or ""
        tutar         = row.get("Tutar") or ""
        carihesapId   = row.get("carihesapId") or ""
        hesapKodu     = row.get("hesapKodu") or ""
        alinan_tutar1 = float(row.get("alinan_tutar1") or 0)
        womsiskey     = row.get("womsiskey") or ""
        islem         = row.get("islem")
        banka         = row.get("Banka") or ""

        # Mükerrer kontrolü: womsiskey (benzersiz anahtar — PHP ile aynı mantık)
        if womsiskey:
            mevcut = conn.execute(
                "SELECT id FROM kredikartiData WHERE womsiskey=?",
                (womsiskey,)
            ).fetchone()
            if mevcut:
                atlandı_data += 1
                continue

        # womsiskey boşsa: tarih + aciklama + tutar üçlüsüyle kontrol
        else:
            mevcut = conn.execute(
                "SELECT id FROM kredikartiData WHERE userid=? AND tarih=? AND alinan_tutar1=? AND aciklama=?",
                (userid_val, tarih, alinan_tutar1, aciklama)
            ).fetchone()
            if mevcut:
                atlandı_data += 1
                continue

        try:
            conn.execute(
                "INSERT INTO kredikartiData "
                "(userid, musterino, tarih, aciklama, Tutar, carihesapId, "
                " hesapKodu, alinan_tutar1, womsiskey, islem, Banka) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (userid_val, musterino, tarih, aciklama, tutar,
                 carihesapId, hesapKodu, alinan_tutar1,
                 womsiskey, islem, banka)
            )
            eklenen_data += 1
        except Exception as exc:
            hatali_data += 1
            print(f"    ⚠️  Satır eklenemedi: {exc}")

    conn.commit()
    conn.close()

    print(f"    ✅  {eklenen_data} eklendi, {atlandı_data} zaten mevcut atlandı"
          + (f", {hatali_data} hatalı" if hatali_data else ""))

    print()
    print("=" * 60)
    print(f"🎉  Migration tamamlandı!")
    print(f"    Toplam eklenen : {eklenen_kart + eklenen_data} kayıt")
    print(f"    Toplam atlanan : {atlandı_kart + atlandı_data} kayıt")
    print("=" * 60)


if __name__ == "__main__":
    migrate()
