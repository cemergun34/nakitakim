"""
SQLite şema tanımları — iqdev21Nisan MySQL veritabanından dönüştürülmüştür.
MySQL'den SQLite'a ilk yükleme için importer.py kullanılır.
"""

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS uyelik (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ad                  TEXT,
    soyad               TEXT,
    kullanici_adi       TEXT NOT NULL,
    eposta              TEXT,
    sifre               TEXT NOT NULL,
    uyelik_tarihi       TEXT,
    musteri_no          INTEGER,
    firmaAdi            TEXT,
    vergiNo             TEXT,
    vergiDairesi        TEXT,
    acikAdres           TEXT,
    il                  TEXT,
    paket_turu          TEXT,
    son_odeme           TEXT,
    sirketId            INTEGER,
    hesapTuru           INTEGER,
    yetki               TEXT DEFAULT '0',
    bagli_hesap         INTEGER DEFAULT -1,
    altKullaniciSayisi  INTEGER DEFAULT 0,
    ilce                TEXT
);

CREATE TABLE IF NOT EXISTS tanim_kullanici (
    Kayitno         INTEGER PRIMARY KEY AUTOINCREMENT,
    Meslek_Menusubu_kodu TEXT,
    Adi             TEXT,
    GSM_No          TEXT,
    Sifre           TEXT,
    Sifre_Durumu    TEXT,
    Musteriler      TEXT,
    Kullanici_Menuleri TEXT,
    Kurum_Durumu    TEXT
);

CREATE TABLE IF NOT EXISTS Subeler (
    id       INTEGER PRIMARY KEY,
    subeAck  TEXT NOT NULL,
    userid   INTEGER,
    topluid  TEXT
);

CREATE TABLE IF NOT EXISTS kategoriler (
    id          INTEGER PRIMARY KEY,
    kategoriAck TEXT NOT NULL,
    userid      INTEGER,
    topluid     TEXT
);

CREATE TABLE IF NOT EXISTS odemeSekli (
    id             INTEGER PRIMARY KEY,
    odemesekliAck  TEXT NOT NULL,
    userid         INTEGER,
    durumModu      TEXT,
    topluid        TEXT
);

CREATE TABLE IF NOT EXISTS altHesapKodu (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kod         TEXT NOT NULL,
    aciklama    TEXT NOT NULL,
    gelirGider  TEXT NOT NULL,   -- 'gelir' | 'gider'
    userid      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS hareketler (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tarih           TEXT,
    hesapKodu       TEXT,
    sube            TEXT,
    odeme_sekli1    TEXT,
    alinan_tutar1   REAL,
    aciklama        TEXT,
    formId          TEXT,
    gelirGider      TEXT,        -- 'gelir' | 'gider'
    kategori_id     INTEGER,
    teslim_sekli    TEXT,
    faturaNo        TEXT,
    faturaUnvan     TEXT,
    musteriNo       INTEGER DEFAULT 1,
    kaynak          TEXT,
    kartId          INTEGER,
    carihesapId     INTEGER,
    vadeTarihi      TEXT,
    resmiAcik       TEXT,
    topluid         TEXT,
    womsisKey       TEXT,
    userid          INTEGER
);

CREATE TABLE IF NOT EXISTS genel_hesap_hareketleri (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tarih           TEXT,
    tarih_date      TEXT,        -- ISO format YYYY-MM-DD
    form_id         TEXT,
    sube            TEXT,
    kategori        TEXT,
    teslim_sekli    TEXT,
    teslim_sekli_id INTEGER,
    aciklama        TEXT,
    odeme_sekli     TEXT,
    gelir           REAL,
    gider           REAL,
    nerden_geliyor  TEXT,        -- 'kasa' | 'gider' | 'genelHesap'
    alt_hesap_kodu_id INTEGER,
    userid          INTEGER,
    musteri_no      INTEGER,
    kayit_tarihi    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS faturalar (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    userid          INTEGER,
    unvan           TEXT,
    vergino         TEXT,
    vergiDairesi    TEXT,
    toplam          TEXT,
    fatura          TEXT,
    tarih           TEXT,
    yuklenmeTarihi  TEXT,
    hash            TEXT,
    gruplama        TEXT,
    gizle           TEXT,
    faturano        TEXT,
    musterino       INTEGER,
    gelirGiderMod   TEXT,        -- 'gelir' | 'gider'
    faturaMod       TEXT,
    formNo          TEXT,
    kaynak          TEXT,
    xml_dosya       TEXT
);

CREATE TABLE IF NOT EXISTS nakitakis_Hareket (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    faturano        TEXT,
    musteriNo       TEXT,
    hesapKodu       TEXT,
    hesapadi        TEXT,
    gercek          REAL,
    plan            REAL,
    tarih           TEXT,
    sozlesmeTarih   TEXT,
    sonTarih        TEXT,
    sube            TEXT,
    kategori        TEXT,
    aciklama        TEXT,
    odeme_sekli     TEXT,
    teslim_sekli    TEXT
);

CREATE TABLE IF NOT EXISTS nakitakis_Parametre (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    musteriNo       INTEGER,
    hesapKodu       TEXT,
    hesapAck        TEXT,
    unvan           TEXT,
    vergiNo         TEXT,
    ilkTarih        TEXT,
    sonTarih        TEXT,
    sozlesmeNo      TEXT,
    sozlesmeTarih   TEXT,
    tutar           REAL
);

-- İndeksler
CREATE INDEX IF NOT EXISTS idx_hareketler_musteri_tarih 
    ON hareketler(musteriNo, tarih);
CREATE INDEX IF NOT EXISTS idx_hareketler_gelirGider 
    ON hareketler(gelirGider);
CREATE INDEX IF NOT EXISTS idx_ghh_userid_nerden_tarih 
    ON genel_hesap_hareketleri(userid, nerden_geliyor, tarih_date);
CREATE INDEX IF NOT EXISTS idx_faturalar_userid_tarih 
    ON faturalar(userid, tarih);
"""
