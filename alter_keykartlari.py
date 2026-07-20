from db.database import get_connection

conn = get_connection()
try:
    cur = conn.cursor()
    
    # Sütunu ekle
    cur.execute("ALTER TABLE key_kartlari ADD COLUMN IF NOT EXISTS musterino INTEGER DEFAULT 1")
    
    # Mevcut tüm kayıtlara 1 yaz
    cur.execute("UPDATE key_kartlari SET musterino = 1 WHERE musterino IS NULL")
    
    conn.commit()
    
    # Kontrol
    cur.execute("SELECT id, banka, no, musterino FROM key_kartlari ORDER BY id")
    rows = cur.fetchall()
    print(f"Toplam {len(rows)} kayıt:")
    for row in rows:
        print(dict(row))
        
except Exception as e:
    print("ERROR:", e)
finally:
    conn.close()
