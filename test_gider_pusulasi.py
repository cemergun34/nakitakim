"""
Gider Pusulası tutarlarını test eder.

Kontrol edilecekler:
1. Dashboard KPI kartının gösterdiği tutar (pusulasi_gider)
2. Excel export sorgusunun ürettiği tutar
3. get_gider_pusulasi_sube_ozet() sonucu
4. get_gider_pusulasi_detay() satır sayısı ve toplamı

Kullanım:
    python test_gider_pusulasi.py [userid] [musterino] [yil] [ilk_tarih] [son_tarih]

Örnek:
    python test_gider_pusulasi.py 1 19 2026 2026-01-01 2026-07-27
"""
import sys
import os

# Proje kökü PATH'e ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.database import get_connection
from db.db_compat import yr

# --- Parametre okuma ---
userid    = int(sys.argv[1]) if len(sys.argv) > 1 else 1
musterino = int(sys.argv[2]) if len(sys.argv) > 2 else 19
yil       = int(sys.argv[3]) if len(sys.argv) > 3 else 2026
ilk_tarih = sys.argv[4]     if len(sys.argv) > 4 else f"{yil}-01-01"
son_tarih = sys.argv[5]     if len(sys.argv) > 5 else f"{yil}-12-31"

print("=" * 70)
print(f"  GİDER PUSULASI TUTAR TESTİ")
print(f"  userid={userid}  musterino={musterino}  yil={yil}")
print(f"  ilk_tarih={ilk_tarih}  son_tarih={son_tarih}")
print("=" * 70)

conn = get_connection()

# ─── TEST 1: Dashboard KPI sorgusu (tarih aralığı filtreli) ──────────────────
print("\n[TEST 1] Dashboard KPI (_get_genel_hesap_all) — tarih aralığı filtreli")
row = conn.execute(f"""
    SELECT
        COALESCE(SUM(CASE WHEN (teslim_sekli LIKE '%Parça Alımı (Cihaz)%' OR teslim_sekli LIKE '%Cihaz Alımı%') THEN gelir ELSE 0 END), 0) AS pusulasi_gelir,
        COALESCE(SUM(CASE WHEN (teslim_sekli LIKE '%Parça Alımı (Cihaz)%' OR teslim_sekli LIKE '%Cihaz Alımı%') THEN gider ELSE 0 END), 0) AS pusulasi_gider,
        COUNT(CASE WHEN (teslim_sekli LIKE '%Parça Alımı (Cihaz)%' OR teslim_sekli LIKE '%Cihaz Alımı%') THEN 1 END) AS pusulasi_kayit
    FROM genel_hesap_hareketleri
    WHERE userid = ?
      AND musteri_no = ?
      AND tarih_date >= ? AND tarih_date <= ?
""", (userid, musterino, ilk_tarih, son_tarih)).fetchone()

kpi_gelir = float(row["pusulasi_gelir"] or 0)
kpi_gider = float(row["pusulasi_gider"] or 0)
kpi_kayit = int(row["pusulasi_kayit"] or 0)
print(f"  → pusulasi_gelir : {kpi_gelir:,.2f} ₺")
print(f"  → pusulasi_gider : {kpi_gider:,.2f} ₺  ← KPI kartında gösterilen")
print(f"  → kayit          : {kpi_kayit}")

# ─── TEST 2: Excel export sorgusu (aynı tarih aralığı) ──────────────────────
print("\n[TEST 2] Excel Export SQL sorgusu — tarih aralığı filtreli")
rows_excel = conn.execute(f"""
    SELECT tarih_date AS Tarih,
           COALESCE(gelir,0) AS "Gelir (TL)",
           COALESCE(gider,0) AS "Gider (TL)",
           teslim_sekli,
           nerden_geliyor
    FROM genel_hesap_hareketleri
    WHERE userid=? AND musteri_no=?
      AND tarih_date >= ? AND tarih_date <= ?
      AND (teslim_sekli LIKE '%Cihaz Alımı%'
        OR teslim_sekli LIKE '%Parça Alımı (Cihaz)%')
    ORDER BY tarih_date ASC, id ASC
""", (userid, musterino, ilk_tarih, son_tarih)).fetchall()

excel_gelir = sum(float(r["Gelir (TL)"] or 0) for r in rows_excel)
excel_gider = sum(float(r["Gider (TL)"] or 0) for r in rows_excel)
print(f"  → Kayıt sayısı   : {len(rows_excel)}")
print(f"  → Gelir toplamı  : {excel_gelir:,.2f} ₺")
print(f"  → Gider toplamı  : {excel_gider:,.2f} ₺")

# ─── TEST 3: Yıl bazlı KPI sorgusu ──────────────────────────────────────────
print(f"\n[TEST 3] Dashboard KPI (_get_genel_hesap_all) — yıl={yil} bazlı")
row3 = conn.execute(f"""
    SELECT
        COALESCE(SUM(CASE WHEN (teslim_sekli LIKE '%Parça Alımı (Cihaz)%' OR teslim_sekli LIKE '%Cihaz Alımı%') THEN gelir ELSE 0 END), 0) AS pusulasi_gelir,
        COALESCE(SUM(CASE WHEN (teslim_sekli LIKE '%Parça Alımı (Cihaz)%' OR teslim_sekli LIKE '%Cihaz Alımı%') THEN gider ELSE 0 END), 0) AS pusulasi_gider,
        COUNT(CASE WHEN (teslim_sekli LIKE '%Parça Alımı (Cihaz)%' OR teslim_sekli LIKE '%Cihaz Alımı%') THEN 1 END) AS pusulasi_kayit
    FROM genel_hesap_hareketleri
    WHERE userid = ?
      AND musteri_no = ?
      AND {yr('tarih_date')} = ?
""", (userid, musterino, str(yil))).fetchone()
print(f"  → pusulasi_gelir : {float(row3['pusulasi_gelir'] or 0):,.2f} ₺")
print(f"  → pusulasi_gider : {float(row3['pusulasi_gider'] or 0):,.2f} ₺")
print(f"  → kayit          : {int(row3['pusulasi_kayit'] or 0)}")

# ─── TEST 4: get_gider_pusulasi_sube_ozet (yıl bazlı, sadece yıl) ───────────
print(f"\n[TEST 4] get_gider_pusulasi_sube_ozet — yıl={yil} bazlı")
from services.detay_service import get_gider_pusulasi_sube_ozet
ozet_rows = get_gider_pusulasi_sube_ozet(userid, musterino, yil)
ozet_gelir = sum(float(r["toplam_gelir"] or 0) for r in ozet_rows)
ozet_gider = sum(float(r["toplam_gider"] or 0) for r in ozet_rows)
print(f"  → Şube bazlı kayıt: {len(ozet_rows)}")
print(f"  → Toplam gelir    : {ozet_gelir:,.2f} ₺")
print(f"  → Toplam gider    : {ozet_gider:,.2f} ₺")
for r in ozet_rows:
    print(f"     • {r['sube_adi']}: gelir={float(r['toplam_gelir'] or 0):,.2f} ₺  gider={float(r['toplam_gider'] or 0):,.2f} ₺  ({r['kayit_sayisi']} kayıt)")

# ─── TEST 5: get_gider_pusulasi_detay (yıl bazlı) ───────────────────────────
print(f"\n[TEST 5] get_gider_pusulasi_detay — yıl={yil} bazlı")
from services.detay_service import get_gider_pusulasi_detay
detay_rows = get_gider_pusulasi_detay(userid, musterino, yil)
detay_gelir = sum(float(r["gelir"] or 0) for r in detay_rows)
detay_gider = sum(float(r["gider"] or 0) for r in detay_rows)
print(f"  → Satır sayısı   : {len(detay_rows)}")
print(f"  → Toplam gelir   : {detay_gelir:,.2f} ₺")
print(f"  → Toplam gider   : {detay_gider:,.2f} ₺")

# ─── KARŞILAŞTIRMA / SORUN TESPİTİ ─────────────────────────────────────────
print("\n" + "=" * 70)
print("  KARŞILAŞTIRMA SONUÇLARI")
print("=" * 70)

sorun_var = False

if abs(kpi_gider - excel_gider) > 0.01:
    print(f"\n❌ SORUN: KPI kartı gider ({kpi_gider:,.2f}₺) ≠ Excel gider ({excel_gider:,.2f}₺)")
    print(f"   Fark: {abs(kpi_gider - excel_gider):,.2f} ₺")
    sorun_var = True
else:
    print(f"\n✅ KPI kartı gider ({kpi_gider:,.2f}₺) = Excel gider ({excel_gider:,.2f}₺) — EŞLEŞIYOR")

if abs(kpi_gelir - excel_gelir) > 0.01:
    print(f"❌ SORUN: KPI kartı gelir ({kpi_gelir:,.2f}₺) ≠ Excel gelir ({excel_gelir:,.2f}₺)")
    sorun_var = True
else:
    print(f"✅ KPI kartı gelir ({kpi_gelir:,.2f}₺) = Excel gelir ({excel_gelir:,.2f}₺) — EŞLEŞIYOR")

if len(rows_excel) != kpi_kayit:
    print(f"⚠️  KPI kayıt ({kpi_kayit}) ≠ Excel kayıt ({len(rows_excel)})")
    sorun_var = True
else:
    print(f"✅ Kayıt sayısı eşleşiyor: {kpi_kayit}")

# Teslim şekli dağılımı
print("\n─── Teslim Şekli Dağılımı (Excel verisi) ───")
from collections import Counter
dagılım = Counter(r["teslim_sekli"] for r in rows_excel)
for ts, cnt in dagılım.most_common():
    print(f"   {ts!r}: {cnt} kayıt")

# nerden_geliyor dağılımı
print("\n─── Kaynak (nerden_geliyor) Dağılımı ───")
kaynaklar = Counter(r["nerden_geliyor"] for r in rows_excel)
for k, cnt in kaynaklar.most_common():
    print(f"   {k!r}: {cnt} kayıt")

if not sorun_var:
    print("\n✅ TÜM DEĞERLER TUTARLI — Sorun tespit edilmedi")
else:
    print("\n⚠️  SORUN TESPİT EDİLDİ — Yukarıdaki hataları inceleyin")

conn.close()
print()
