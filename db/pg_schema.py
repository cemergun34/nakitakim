# -*- coding: utf-8 -*-
"""
PostgreSQL Şema Tanımları
==========================
SQLite schema.py'ın PostgreSQL karşılığı.
Tüm tablo ve kolon adları küçük harfli — tırnak gerekmez.

Dönüşümler:
  INTEGER PRIMARY KEY AUTOINCREMENT  → SERIAL PRIMARY KEY
  TEXT DEFAULT CURRENT_TIMESTAMP     → TIMESTAMPTZ DEFAULT NOW()
  PRAGMA ...                         → (kaldırıldı)
  INSERT OR IGNORE                   → ON CONFLICT DO NOTHING
  INSERT OR REPLACE                  → ON CONFLICT DO UPDATE
"""

# Her tablo için ayrı CREATE TABLE — sıralı yürütme için liste olarak
PG_TABLES: list[tuple[str, str]] = [

    ("uyelik", """
        CREATE TABLE IF NOT EXISTS uyelik (
            id                  SERIAL PRIMARY KEY,
            ad                  TEXT,
            soyad               TEXT,
            kullanici_adi       TEXT NOT NULL,
            eposta              TEXT,
            sifre               TEXT NOT NULL,
            uyelik_tarihi       TEXT,
            musteri_no          INTEGER,
            firmaadi            TEXT,
            vergino             TEXT,
            vergidairesi        TEXT,
            acikadres           TEXT,
            il                  TEXT,
            paket_turu          TEXT,
            son_odeme           TEXT,
            sirketid            INTEGER,
            hesapturu           INTEGER,
            yetki               TEXT DEFAULT '0',
            bagli_hesap         INTEGER DEFAULT -1,
            altkullanicisayisi  INTEGER DEFAULT 0,
            ilce                TEXT
        )
    """),

    ("tanim_kullanici", """
        CREATE TABLE IF NOT EXISTS tanim_kullanici (
            kayitno                  SERIAL PRIMARY KEY,
            meslek_menusubu_kodu     TEXT,
            adi                      TEXT,
            gsm_no                   TEXT,
            sifre                    TEXT,
            sifre_durumu             TEXT,
            musteriler               TEXT,
            kullanici_menuleri       TEXT,
            kurum_durumu             TEXT
        )
    """),

    ("subeler", """
        CREATE TABLE IF NOT EXISTS subeler (
            id       INTEGER PRIMARY KEY,
            subeack  TEXT NOT NULL,
            userid   INTEGER,
            topluid  TEXT
        )
    """),

    ("kategoriler", """
        CREATE TABLE IF NOT EXISTS kategoriler (
            id          INTEGER PRIMARY KEY,
            kategoriack TEXT NOT NULL,
            userid      INTEGER,
            topluid     TEXT
        )
    """),

    ("odemesekli", """
        CREATE TABLE IF NOT EXISTS odemesekli (
            id             INTEGER PRIMARY KEY,
            odemesekliack  TEXT NOT NULL,
            userid         INTEGER,
            durummodu      TEXT,
            topluid        TEXT
        )
    """),

    ("althesapkodu", """
        CREATE TABLE IF NOT EXISTS althesapkodu (
            id          SERIAL PRIMARY KEY,
            kod         TEXT NOT NULL,
            aciklama    TEXT NOT NULL,
            gelirgider  TEXT NOT NULL,
            userid      INTEGER DEFAULT 1
        )
    """),

    ("hareketler", """
        CREATE TABLE IF NOT EXISTS hareketler (
            id              SERIAL PRIMARY KEY,
            tarih           TEXT,
            hesapkodu       TEXT,
            sube            TEXT,
            odeme_sekli1    TEXT,
            alinan_tutar1   REAL,
            aciklama        TEXT,
            formid          TEXT,
            gelirgider      TEXT,
            kategori_id     INTEGER,
            teslim_sekli    TEXT,
            faturano        TEXT,
            faturaunvan     TEXT,
            musterino       INTEGER DEFAULT 1,
            kaynak          TEXT,
            kartid          INTEGER,
            carihesapid     INTEGER,
            vadetarihi      TEXT,
            resmiacik       TEXT,
            topluid         TEXT,
            womsiskey       TEXT,
            userid          INTEGER
        )
    """),

    ("genel_hesap_hareketleri", """
        CREATE TABLE IF NOT EXISTS genel_hesap_hareketleri (
            id              SERIAL PRIMARY KEY,
            tarih           TEXT,
            tarih_date      TEXT,
            form_id         TEXT,
            sube            TEXT,
            kategori        TEXT,
            teslim_sekli    TEXT,
            teslim_sekli_id INTEGER,
            aciklama        TEXT,
            odeme_sekli     TEXT,
            gelir           REAL,
            gider           REAL,
            nerden_geliyor  TEXT,
            alt_hesap_kodu_id INTEGER,
            userid          INTEGER,
            musteri_no      INTEGER,
            kayit_tarihi    TEXT DEFAULT NOW()::TEXT
        )
    """),

    ("faturalar", """
        CREATE TABLE IF NOT EXISTS faturalar (
            id              SERIAL PRIMARY KEY,
            userid          INTEGER,
            unvan           TEXT,
            vergino         TEXT,
            vergidairesi    TEXT,
            toplam          TEXT,
            fatura          TEXT,
            tarih           TEXT,
            yuklenmetarihi  TEXT,
            hash            TEXT,
            gruplama        TEXT,
            gizle           TEXT,
            faturano        TEXT,
            musterino       INTEGER,
            gelirgidermod   TEXT,
            faturamod       TEXT,
            formno          TEXT,
            kaynak          TEXT,
            xml_dosya       TEXT
        )
    """),

    ("carihesaplar", """
        CREATE TABLE IF NOT EXISTS carihesaplar (
            id          SERIAL PRIMARY KEY,
            unvan       TEXT,
            vergidaire  TEXT,
            vergino     TEXT,
            tcno        TEXT,
            userid      INTEGER,
            logtarih    TEXT,
            hesapkodu   TEXT
        )
    """),

    ("nakitakis_hareket", """
        CREATE TABLE IF NOT EXISTS nakitakis_hareket (
            id              SERIAL PRIMARY KEY,
            faturano        TEXT,
            musterino       TEXT,
            hesapkodu       TEXT,
            hesapadi        TEXT,
            gercek          REAL,
            plan            REAL,
            tarih           TEXT,
            sozlesmetarih   TEXT,
            sontarih        TEXT,
            sube            TEXT,
            kategori        TEXT,
            aciklama        TEXT,
            odeme_sekli     TEXT,
            teslim_sekli    TEXT
        )
    """),

    ("nakitakis_parametre", """
        CREATE TABLE IF NOT EXISTS nakitakis_parametre (
            id              SERIAL PRIMARY KEY,
            musterino       INTEGER,
            hesapkodu       TEXT,
            hesapack        TEXT,
            unvan           TEXT,
            vergino         TEXT,
            ilktarih        TEXT,
            sontarih        TEXT,
            sozlesmeno      TEXT,
            sozlesmetarih   TEXT,
            tutar           REAL,
            gelirgider      TEXT,
            aciklama        TEXT,
            iqmod           TEXT
        )
    """),

    ("sirket_profili", """
        CREATE TABLE IF NOT EXISTS sirket_profili (
            id           SERIAL PRIMARY KEY,
            userid       INTEGER NOT NULL UNIQUE,
            unvan        TEXT    NOT NULL DEFAULT '',
            vergino      TEXT    NOT NULL DEFAULT '',
            tckn         TEXT             DEFAULT '',
            vergidairesi TEXT             DEFAULT '',
            adres        TEXT             DEFAULT '',
            il           TEXT             DEFAULT '',
            ilce         TEXT             DEFAULT ''
        )
    """),

    ("vomsisbilgileri", """
        CREATE TABLE IF NOT EXISTS vomsisbilgileri (
            id       SERIAL PRIMARY KEY,
            userid   INTEGER NOT NULL UNIQUE,
            appkey   TEXT    NOT NULL DEFAULT '',
            seckey   TEXT    NOT NULL DEFAULT '',
            url      TEXT    NOT NULL DEFAULT 'https://developers.vomsis.com/api/v2',
            kayit_tarihi TEXT DEFAULT NOW()::TEXT,
            guncelleme_tarihi TEXT DEFAULT NOW()::TEXT
        )
    """),

    ("moy_bilgileri", """
        CREATE TABLE IF NOT EXISTS moy_bilgileri (
            id          SERIAL PRIMARY KEY,
            musterino   INTEGER NOT NULL UNIQUE,
            url         TEXT    NOT NULL DEFAULT '',
            username    TEXT    NOT NULL DEFAULT '',
            sifre       TEXT    NOT NULL DEFAULT '',
            moykayitno  TEXT             DEFAULT '',
            tarih       TEXT             DEFAULT NOW()::TEXT
        )
    """),

    ("vergimuhtasar", """
        CREATE TABLE IF NOT EXISTS vergimuhtasar (
            id           SERIAL PRIMARY KEY,
            userid       INTEGER NOT NULL,
            musteri_no   INTEGER,
            hesapkodu    TEXT    NOT NULL,
            ack          TEXT,
            donem        TEXT    NOT NULL,
            gaytutar     REAL,
            vergkestutar REAL,
            eklenme_tarihi TEXT DEFAULT NOW()::TEXT
        )
    """),

    ("key_kartlari", """
        CREATE TABLE IF NOT EXISTS key_kartlari (
            id        SERIAL PRIMARY KEY,
            banka     TEXT    NOT NULL,
            no        TEXT    NOT NULL DEFAULT '',
            tag       TEXT,
            userid    INTEGER NOT NULL,
            hesapkodu TEXT            DEFAULT '',
            bankaadi  TEXT            DEFAULT '',
            iban      TEXT            DEFAULT ''
        )
    """),

    ("kredikartidata", """
        CREATE TABLE IF NOT EXISTS kredikartidata (
            id            SERIAL PRIMARY KEY,
            userid        TEXT,
            musterino     TEXT,
            tarih         TEXT,
            aciklama      TEXT,
            tutar         TEXT,
            carihesapid   TEXT,
            hesapkodu     TEXT,
            alinan_tutar1 REAL,
            womsiskey     TEXT    NOT NULL DEFAULT '',
            islem         INTEGER,
            banka         TEXT    NOT NULL DEFAULT ''
        )
    """),

    ("paytr", """
        CREATE TABLE IF NOT EXISTS paytr (
            id                SERIAL PRIMARY KEY,
            userid            INTEGER NOT NULL,
            musterino         TEXT    NOT NULL DEFAULT '',
            islemtarihi       TEXT    DEFAULT NULL,
            siparisno         TEXT    DEFAULT NULL,
            islemtutari       REAL    DEFAULT 0.0,
            odemetutari       REAL    DEFAULT 0.0,
            kur               TEXT    DEFAULT 'TL',
            magazano          TEXT    DEFAULT NULL,
            adsoyad           TEXT    DEFAULT NULL,
            nettutar          REAL    DEFAULT 0.0,
            kesintitutari     REAL    DEFAULT 0.0,
            kesintiorani      TEXT    DEFAULT NULL,
            kartbankasi       TEXT    DEFAULT NULL,
            kartmarkasi       TEXT    DEFAULT NULL,
            kartno            TEXT    DEFAULT NULL,
            odemetipi         TEXT    DEFAULT NULL,
            karttipi          TEXT    DEFAULT NULL,
            taksitsayisi      INTEGER DEFAULT 0,
            guncelleme_tarihi TEXT    DEFAULT NOW()::TEXT,
            created_at        TEXT    DEFAULT NOW()::TEXT,
            UNIQUE (userid, siparisno)
        )
    """),

    ("paytr_sync_log", """
        CREATE TABLE IF NOT EXISTS paytr_sync_log (
            id              SERIAL PRIMARY KEY,
            userid          INTEGER NOT NULL,
            musterino       TEXT    NOT NULL DEFAULT '',
            son_sync_tarihi TEXT    DEFAULT NULL,
            updated_at      TEXT    DEFAULT NOW()::TEXT,
            UNIQUE (userid, musterino)
        )
    """),

    ("apisanalpos", """
        CREATE TABLE IF NOT EXISTS apisanalpos (
            id                    SERIAL PRIMARY KEY,
            userid                INTEGER NOT NULL,
            musterino             TEXT    NOT NULL DEFAULT '1',
            firma_adi             TEXT    DEFAULT '',
            magaza_no             TEXT    DEFAULT '',
            magaza_parola         TEXT    DEFAULT '',
            magaza_gizli_anahtar  TEXT    DEFAULT '',
            kayit_tarihi          TEXT    DEFAULT NOW()::TEXT
        )
    """),

    ("womsi_pos", """
        CREATE TABLE IF NOT EXISTS womsi_pos (
            id                  SERIAL PRIMARY KEY,
            userid              INTEGER,
            isyerino            TEXT,
            carihesap           TEXT,
            hesabagecistarihi   TEXT,
            islemtutari         REAL,
            islemtarihi         TEXT,
            posno               TEXT,
            isyeriucretitutar   REAL,
            nettutar            REAL,
            brand               TEXT,
            kartno              TEXT,
            islemtipi           TEXT,
            aciklama            TEXT
        )
    """),

    ("alt_kullanici", """
        CREATE TABLE IF NOT EXISTS alt_kullanici (
            id              SERIAL PRIMARY KEY,
            parent_userid   INTEGER,
            kullanici_adi   TEXT    NOT NULL,
            eposta          TEXT    NOT NULL DEFAULT '',
            sifre_hash      TEXT    DEFAULT NULL,
            uyelik_tarihi   TEXT    DEFAULT NULL,
            yetki           TEXT    DEFAULT '1',
            aktif           INTEGER DEFAULT 1
        )
    """),

    ("ibanhesapbilgileri", """
        CREATE TABLE IF NOT EXISTS ibanhesapbilgileri (
            id               SERIAL PRIMARY KEY,
            userid           INTEGER NOT NULL,
            ibanhesapbaslik  TEXT NOT NULL,
            carihesapid      INTEGER NOT NULL,
            bankaadi         TEXT NOT NULL,
            subeadi          TEXT,
            bankahesapno     TEXT,
            ibanno           TEXT NOT NULL
        )
    """),
]

# İndeksler (tablolar oluşturulduktan sonra)
PG_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_hareketler_musteri_tarih ON hareketler(musterino, tarih);",
    "CREATE INDEX IF NOT EXISTS idx_hareketler_gelirgider ON hareketler(gelirgider);",
    "CREATE INDEX IF NOT EXISTS idx_ghh_userid_nerden_tarih ON genel_hesap_hareketleri(userid, nerden_geliyor, tarih_date);",
    "CREATE INDEX IF NOT EXISTS idx_faturalar_userid_tarih ON faturalar(userid, tarih);",
    "CREATE INDEX IF NOT EXISTS idx_vomsis_userid ON vomsisbilgileri(userid);",
    'CREATE INDEX IF NOT EXISTS idx_moy_musteri ON moy_bilgileri(musterino);',
    'CREATE INDEX IF NOT EXISTS idx_vergimuhtasar_userid_donem ON vergimuhtasar(userid, donem);',
    "CREATE INDEX IF NOT EXISTS idx_key_kartlari_userid ON key_kartlari(userid);",
    'CREATE INDEX IF NOT EXISTS idx_kredikarti_userid_tarih ON kredikartidata(userid, tarih);',
    'CREATE INDEX IF NOT EXISTS idx_kredikarti_womsiskey ON kredikartidata(womsiskey);',
    "CREATE INDEX IF NOT EXISTS idx_paytr_userid_islemtarihi ON paytr(userid, islemtarihi);",
    "CREATE INDEX IF NOT EXISTS idx_paytr_sync_log_userid ON paytr_sync_log(userid, musterino);",
    "CREATE INDEX IF NOT EXISTS idx_apisanalpos_userid ON apisanalpos(userid);",
    'CREATE INDEX IF NOT EXISTS idx_iban_userid ON ibanhesapbilgileri(userid);',
]

# Taşıma dışı bırakılacak tablolar (sistem tabloları)
SKIP_TABLES = {"sqlite_sequence"}
