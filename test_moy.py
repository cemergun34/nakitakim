from services.moy_service import moy_kaydet_veriler
import sys

def progress(msg):
    print(msg)

# Musteri_No from db. 1 is typically the primary test user.
res = moy_kaydet_veriler(1, 2026, progress_cb=progress)
print(res)

from db.database import get_connection
conn = get_connection()
count = conn.execute("SELECT COUNT(*) as c FROM moy_beyannameler").fetchone()
print("moy_beyannameler count:", count["c"])
