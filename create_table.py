from db.database import get_connection

sql = """
CREATE TABLE IF NOT EXISTS moy_beyannameler (
    id               SERIAL PRIMARY KEY,
    musteri_no       INTEGER NOT NULL,
    kayit_no         INTEGER NOT NULL UNIQUE,
    belge_tipi       TEXT,
    belge_turu       TEXT,
    donem_no         TEXT,
    donem_adi        TEXT,
    onay_tarihi      TEXT,
    belge_no         TEXT,
    belge_durumu     TEXT,
    beyan_tarih_1    TEXT,
    beyan_tarih_2    TEXT,
    sube_adi         TEXT,
    sube_alanlar     TEXT,
    musteri_unvani   TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_moy_beyannameler_musteri
    ON moy_beyannameler(musteri_no, beyan_tarih_1, beyan_tarih_2);
"""

conn = get_connection()
try:
    conn.execute(sql)
    conn.commit()
    print("Tablo basariyla olusturuldu.")
except Exception as e:
    # Maybe it's sqlite
    print("Postgres hatasi:", e)
    sql_sqlite = sql.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT").replace("TIMESTAMP", "TEXT")
    conn.rollback()
    conn.execute(sql_sqlite)
    conn.commit()
    print("Tablo SQLite ile olusturuldu.")
