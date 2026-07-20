import sys
from db.database import get_connection, ensure_pg_ready
from db.db_config import load_config

cfg = load_config()
print("Mode:", cfg.get("mode"))

# PG hazirlik
ensure_pg_ready()

conn = get_connection()
try:
    cur = conn.execute("""
        INSERT OR IGNORE INTO womsi_pos
            (userid, musterino, isyeriNo, cariHesap, hesabaGecisTarihi,
             islemTutari, islemTarihi, posNo,
             isyeriUcretiTutar, netTutar, brand,
             kartNo, islemTipi, aciklama, islemTarih, kayitTarihi)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        1, 1, "test_isyeri", "test_hesap", "2026-07-20",
        100.0, "2026-07-20", "test_pos",
        1.0, 99.0, "test_brand", "test_kart",
        "test_tip", "test_ack", "2026-07-20", "2026-07-20"
    ))
    print("Rowcount:", cur.rowcount)
except Exception as e:
    print("HATA:", e)

