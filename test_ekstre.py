from db.database import get_connection
from services.dashboard_service import get_kredi_karti_kart_ozet, get_kredi_karti_ekstre_detay

print("=== ÖZET ===")
ozet = get_kredi_karti_kart_ozet(19, 1, 2026)
for r in ozet:
    print(type(r), r)

print()
print("=== EKSTRE (YapıKredi, hesapkodu=309.01.008) ===")
eks = get_kredi_karti_ekstre_detay(19, 1, "YapıKredi", 2026, hesapkodu="309.01.008")
print(f"{len(eks)} kayıt")
for r in eks[:3]:
    print(type(r), r)

print()
print("=== EKSTRE (İş Bankası, hesapkodu yok) ===")
eks2 = get_kredi_karti_ekstre_detay(19, 1, "İş Bankası", 2026)
print(f"{len(eks2)} kayıt")
