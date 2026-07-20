from services.kredi_kart_service import get_kart_listesi

r = get_kart_listesi(19)
for item in r.get("data", []):
    banka_adi  = (item.get("bankaadi") or item.get("bankaAdi") or "").strip()
    etiket     = (item.get("banka") or "").strip()
    kart_no    = (item.get("no") or "").strip()
    hesap_kodu = (item.get("hesapkodu") or item.get("hesapKodu") or "").strip()

    parts = []
    if banka_adi:
        parts.append(f"Banka: {banka_adi}")
    if etiket and etiket.lower() != banka_adi.lower():
        parts.append(f"Etiket: {etiket}")
    if kart_no:
        parts.append(f"Kart No: {kart_no}")
    if hesap_kodu:
        parts.append(f"Hesap: {hesap_kodu}")

    if not parts:
        parts.append(etiket or "Bilinmeyen Kart")

    print("  |  ".join(parts))
