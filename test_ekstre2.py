from services.dashboard_service import get_kredi_karti_kart_ozet, get_kredi_karti_ekstre_detay

print("=== ÖZET ===")
ozet = get_kredi_karti_kart_ozet(19, 1, 2026)
for r in ozet:
    banka = r.get("banka", "") or r.get("Banka", "")
    hk    = r.get("hesapkodu") or ""
    print(f"banka='{banka}'  hesapkodu='{hk}'  kayit={r.get('kayit_sayisi')}")

print()
for r in ozet:
    banka = r.get("banka", "") or r.get("Banka", "")
    hk    = r.get("hesapkodu") or ""
    eks = get_kredi_karti_ekstre_detay(19, 1, banka, 2026, hesapkodu=hk or None)
    print(f"  → banka='{banka}' hk='{hk}' → {len(eks)} ekstre satırı")
