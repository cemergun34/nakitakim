from db.database import get_connection

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id, banka, no, tag, hesapkodu, bankaadi FROM key_kartlari WHERE userid = 19 ORDER BY bankaadi, banka")
rows = cur.fetchall()

print(f"{'='*80}")
print("COMBOBOX'TA GÖRÜNECEK SATIRLAR:")
print(f"{'='*80}")
for row in rows:
    item = dict(row)
    banka_adi  = (item.get("bankaadi") or "").strip()
    etiket     = (item.get("banka") or "").strip()
    kart_no    = (item.get("no") or "").strip()
    hesap_kodu = (item.get("hesapkodu") or "").strip()

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

print()
print("RAW VERİTABANI:")
for row in rows:
    print(dict(row))
