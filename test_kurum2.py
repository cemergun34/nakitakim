import sys
from db.database import get_connection
conn = get_connection()
rows = conn.execute("SELECT id, sontarih, sozlesmeno, sozlesmetarih FROM nakitakis_parametre WHERE sontarih IS NOT NULL AND sontarih != '' LIMIT 5").fetchall()
print("Non-empty sontarih rows:", [dict(r) for r in rows])
