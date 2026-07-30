import sys
from services.detay_service import get_kurum_odemeleri_detay_tarih
from db.database import _CIRow
try:
    rows, toplam = get_kurum_odemeleri_detay_tarih(1, '20200101', '20300101')
    if rows:
        print("First row keys:", rows[0].keys())
        print("sonTarih:", rows[0].get("sonTarih"))
        print("sontarih:", rows[0].get("sontarih"))
    else:
        print("No rows found")
except Exception as e:
    print("Error:", e)
