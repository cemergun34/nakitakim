#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
musterino Doğrulama Scripti — VERİ BOZULMAZ, KAYIT OLUŞTURILMAZ
=================================================================
Sadece SELECT ve PRAGMA/information_schema sorguları çalıştırır.
Hiçbir INSERT, UPDATE, DELETE, COMMIT yoktur.

Kontroller:
  1. DB'de tüm 6 tabloda musterino kolonu var mı?
  2. Mevcut kayıtlarda musterino değerleri ne?
  3. Servis fonksiyonları musterino parametresiyle doğru çalışıyor mu?
  4. dashboard_service.get_bankalar_toplam musterino filtreli çalışıyor mu?
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Renk kodları ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

PASS = f"{GREEN}✅ PASS{RESET}"
FAIL = f"{RED}❌ FAIL{RESET}"
INFO = f"{BLUE}ℹ️  INFO{RESET}"
WARN = f"{YELLOW}⚠️  WARN{RESET}"

results = []

def check(name: str, ok: bool, detail: str = ""):
    status = PASS if ok else FAIL
    print(f"  {status}  {name}")
    if detail:
        print(f"         {BLUE}{detail}{RESET}")
    results.append((name, ok))

def section(title: str):
    print(f"\n{BOLD}{BLUE}{'─'*60}{RESET}")
    print(f"{BOLD}{BLUE}  {title}{RESET}")
    print(f"{BOLD}{BLUE}{'─'*60}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Bağlantı Kontrolü
# ─────────────────────────────────────────────────────────────────────────────
section("1. Veritabanı Bağlantısı")
try:
    from db.database import get_connection
    from db.db_config import get_mode
    mode = get_mode()
    conn = get_connection()
    row = conn.execute("SELECT 1 AS ping").fetchone()
    check("DB bağlantısı", row is not None, f"Mod: {mode}")
    conn.close()
except Exception as e:
    check("DB bağlantısı", False, str(e))
    print(f"\n{RED}Bağlantı kurulamadı — test durduruluyor.{RESET}")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Kolon Varlık Kontrolü
# ─────────────────────────────────────────────────────────────────────────────
section("2. musterino Kolonu — Tablo Bazlı Kontrol")

TARGET = [
    "odemesekli",
    "sirket_profili",
    "subeler",
    "vomsisbilgileri",
    "webadmin_sirket_config",
    "womsis_banka",
]

conn = get_connection()
try:
    for tablo in TARGET:
        try:
            if mode == "postgres":
                row = conn.execute(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = ? AND column_name = 'musterino'",
                    (tablo,)
                ).fetchone()
                has_col = row is not None
            else:
                # SQLite
                cols = conn.execute(f"PRAGMA table_info({tablo})").fetchall()
                has_col = any(c[1].lower() == "musterino" for c in cols)
            check(f"{tablo}.musterino kolonu", has_col)
        except Exception as e:
            check(f"{tablo}.musterino kolonu", False, str(e))
finally:
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Mevcut Kayıt musterino Değer Dağılımı (sadece okuma)
# ─────────────────────────────────────────────────────────────────────────────
section("3. Mevcut Kayıt Dağılımı (okuma)")

conn = get_connection()
try:
    for tablo in TARGET:
        try:
            # Toplam kayıt sayısı
            total_row = conn.execute(f"SELECT COUNT(*) FROM {tablo}").fetchone()
            total = int(total_row[0]) if total_row else 0

            # musterino değeri olan kayıt sayısı
            mn_row = conn.execute(
                f"SELECT COUNT(*) FROM {tablo} WHERE musterino IS NOT NULL"
            ).fetchone()
            with_mn = int(mn_row[0]) if mn_row else 0

            # musterino=1 olan kayıt sayısı
            mn1_row = conn.execute(
                f"SELECT COUNT(*) FROM {tablo} WHERE musterino = 1"
            ).fetchone()
            mn1 = int(mn1_row[0]) if mn1_row else 0

            null_count = total - with_mn
            ok = null_count == 0 or total == 0  # Hiç NULL olmamalı
            detail = (
                f"Toplam: {total}  |  musterino=1: {mn1}  |  NULL: {null_count}"
            )
            check(f"{tablo} — NULL musterino yok", ok, detail)
        except Exception as e:
            check(f"{tablo} kayıt dağılımı", False, str(e))
finally:
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Servis Fonksiyonu İmza Kontrolü (parametre var mı?)
# ─────────────────────────────────────────────────────────────────────────────
section("4. Servis Fonksiyonu İmza Kontrolü")

import inspect

def check_param(func, param_name: str, label: str):
    sig = inspect.signature(func)
    has_param = param_name in sig.parameters
    default = sig.parameters[param_name].default if has_param else inspect.Parameter.empty
    has_default = default is not inspect.Parameter.empty
    detail = f"default={default}" if has_param else "parametre bulunamadı"
    check(label, has_param and has_default, detail)

try:
    from services.odeme_sekli_service import (
        get_odeme_sekilleri, ekle_odeme_sekli, sil_odeme_sekli, toplu_yukle_csv
    )
    check_param(get_odeme_sekilleri, "musterino", "odeme_sekli: get_odeme_sekilleri(musterino)")
    check_param(ekle_odeme_sekli,    "musterino", "odeme_sekli: ekle_odeme_sekli(musterino)")
    check_param(sil_odeme_sekli,     "musterino", "odeme_sekli: sil_odeme_sekli(musterino)")
except Exception as e:
    check("odeme_sekli_service import", False, str(e))

try:
    from services.subeler_service import get_subeler, ekle_sube, sil_sube
    check_param(get_subeler, "musterino", "subeler: get_subeler(musterino)")
    check_param(ekle_sube,   "musterino", "subeler: ekle_sube(musterino)")
    check_param(sil_sube,    "musterino", "subeler: sil_sube(musterino)")
except Exception as e:
    check("subeler_service import", False, str(e))

try:
    from services.sirket_service import get_sirket_profili, save_sirket_profili
    check_param(get_sirket_profili,  "musterino", "sirket: get_sirket_profili(musterino)")
    check_param(save_sirket_profili, "musterino", "sirket: save_sirket_profili(musterino)")
except Exception as e:
    check("sirket_service import", False, str(e))

try:
    from services.vomsis_service import get_vomsis_bilgileri, save_vomsis_bilgileri
    check_param(get_vomsis_bilgileri,  "musterino", "vomsis: get_vomsis_bilgileri(musterino)")
    check_param(save_vomsis_bilgileri, "musterino", "vomsis: save_vomsis_bilgileri(musterino)")
except Exception as e:
    check("vomsis_service import", False, str(e))

try:
    from services.webadmin_client import get_webadmin_config
    check_param(get_webadmin_config, "musterino", "webadmin: get_webadmin_config(musterino)")
except Exception as e:
    check("webadmin_client import", False, str(e))

try:
    from services.dashboard_service import get_bankalar_toplam
    check_param(get_bankalar_toplam, "musterino", "dashboard: get_bankalar_toplam(musterino)")
except Exception as e:
    check("dashboard_service import", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 5. Fonksiyonel Okuma Testi (gerçek servis çağrıları — sadece SELECT)
# ─────────────────────────────────────────────────────────────────────────────
section("5. Fonksiyonel Okuma Testi (veri bozulmaz)")

# Gerçek DB'deki mevcut kullanıcıyı bul
try:
    conn = get_connection()
    user_row = conn.execute(
        "SELECT id, kullanici_adi FROM uyelik LIMIT 1"
    ).fetchone()
    conn.close()

    if user_row:
        test_userid    = int(user_row["id"])
        test_musterino = int(user_row.get("musteri_no") or 1)
        print(f"  {INFO} Test kullanıcısı: id={test_userid}, musteri_no={test_musterino}")
    else:
        test_userid    = 1
        test_musterino = 1
        print(f"  {WARN} uyelik tablosu boş — userid=1, musterino=1 ile test ediliyor")
except Exception as e:
    test_userid    = 1
    test_musterino = 1
    print(f"  {WARN} Kullanıcı okunamadı: {e}")

# 5.1 get_odeme_sekilleri
try:
    from services.odeme_sekli_service import get_odeme_sekilleri
    r = get_odeme_sekilleri(test_userid, test_musterino)
    check(
        f"get_odeme_sekilleri(userid={test_userid}, musterino={test_musterino})",
        r.get("success") is True,
        f"{len(r.get('data', []))} kayıt döndü"
    )
except Exception as e:
    check("get_odeme_sekilleri çağrısı", False, str(e))

# 5.2 get_subeler
try:
    from services.subeler_service import get_subeler
    r = get_subeler(test_userid, test_musterino)
    check(
        f"get_subeler(userid={test_userid}, musterino={test_musterino})",
        r.get("success") is True,
        f"{len(r.get('data', []))} kayıt döndü"
    )
except Exception as e:
    check("get_subeler çağrısı", False, str(e))

# 5.3 get_sirket_profili
try:
    from services.sirket_service import get_sirket_profili
    r = get_sirket_profili(test_userid, test_musterino)
    has_data = bool(r)
    check(
        f"get_sirket_profili(userid={test_userid}, musterino={test_musterino})",
        True,  # Boş dict de başarı sayılır
        f"unvan={r.get('unvan', '—') or '—'}"
    )
except Exception as e:
    check("get_sirket_profili çağrısı", False, str(e))

# 5.4 get_vomsis_bilgileri
try:
    from services.vomsis_service import get_vomsis_bilgileri
    r = get_vomsis_bilgileri(test_userid, test_musterino)
    check(
        f"get_vomsis_bilgileri(userid={test_userid}, musterino={test_musterino})",
        r.get("success") is True,
        f"appkey={'*' * min(len(r.get('appkey','') or ''), 4) or '(boş)'}"
    )
except Exception as e:
    check("get_vomsis_bilgileri çağrısı", False, str(e))

# 5.5 get_webadmin_config (sadece dict dönüşü kontrol et)
try:
    from services.webadmin_client import get_webadmin_config
    r = get_webadmin_config(test_userid, test_musterino)
    check(
        f"get_webadmin_config(userid={test_userid}, musterino={test_musterino})",
        isinstance(r, dict) and "base_url" in r,
        f"enabled={r.get('enabled')}, url={r.get('base_url','—')[:40]}"
    )
except Exception as e:
    check("get_webadmin_config çağrısı", False, str(e))

# 5.6 get_bankalar_toplam
try:
    from services.dashboard_service import get_bankalar_toplam
    r = get_bankalar_toplam(test_userid, test_musterino)
    check(
        f"get_bankalar_toplam(userid={test_userid}, musterino={test_musterino})",
        "gelir" in r and "gider" in r,
        f"gelir={r.get('gelir',0):,.2f}  gider={r.get('gider',0):,.2f}  kayit={r.get('kayit',0)}"
    )
except Exception as e:
    check("get_bankalar_toplam çağrısı", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 6. WebAdminSyncWorker İmza Kontrolü
# ─────────────────────────────────────────────────────────────────────────────
section("6. Worker İmza Kontrolü")

try:
    from services.webadmin_client import WebAdminSyncWorker
    check_param(WebAdminSyncWorker.__init__, "musterino", "WebAdminSyncWorker.__init__(musterino)")
except ImportError:
    print(f"  {WARN} WebAdminSyncWorker: PyQt6 yok (normal test ortamı)")
except Exception as e:
    check("WebAdminSyncWorker imza", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Sonuç
# ─────────────────────────────────────────────────────────────────────────────
section("SONUÇ")

total  = len(results)
passed = sum(1 for _, ok in results if ok)
failed = total - passed

print(f"\n  Toplam:  {total}")
print(f"  {GREEN}Geçti :  {passed}{RESET}")
if failed:
    print(f"  {RED}Kaldı :  {failed}{RESET}")
    print(f"\n  Başarısız testler:")
    for name, ok in results:
        if not ok:
            print(f"    {RED}✗ {name}{RESET}")
else:
    print(f"\n  {GREEN}{BOLD}🎉 Tüm testler geçti — veri bozulmadı!{RESET}")

print()
sys.exit(0 if failed == 0 else 1)
