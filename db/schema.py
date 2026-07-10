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

CREATE TABLE IF NOT EXISTS womsis_banka (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tarih           TEXT,
    aciklama        TEXT,
    gelirgider      TEXT,
    tutar           REAL,
    kaynak          TEXT,
    womsiskey       TEXT,
    userid          INTEGER,
    sube            TEXT,
    faturaunvan     TEXT,
    bakiye          REAL,
    iban            TEXT,
    hesap_turu      TEXT,
    dekont_no       TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
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

CREATE TABLE IF NOT EXISTS cariHesaplar (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    unvan       TEXT,
    vergiDaire  TEXT,
    vergiNo     TEXT,
    tcno        TEXT,
    userid      INTEGER,
    logtarih    TEXT,
    hesapKodu   TEXT
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
    tutar           REAL,
    gelirGider      TEXT,   -- 'gelir' | 'gider'
    aciklama        TEXT,
    iQmod           TEXT    -- 'hareket' | ...
);

CREATE TABLE IF NOT EXISTS sirket_profili (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    userid       INTEGER NOT NULL UNIQUE,
    unvan        TEXT    NOT NULL DEFAULT '',
    vergino      TEXT    NOT NULL DEFAULT '',
    tckn         TEXT             DEFAULT '',
    vergidairesi TEXT             DEFAULT '',
    adres        TEXT             DEFAULT '',
    il           TEXT             DEFAULT '',
    ilce         TEXT             DEFAULT ''
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

CREATE TABLE IF NOT EXISTS vomsisBilgileri (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    userid   INTEGER NOT NULL UNIQUE,
    appkey   TEXT    NOT NULL DEFAULT '',
    seckey   TEXT    NOT NULL DEFAULT '',
    url      TEXT    NOT NULL DEFAULT 'https://developers.vomsis.com/api/v2',
    kayit_tarihi TEXT DEFAULT CURRENT_TIMESTAMP,
    guncelleme_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vomsis_userid
    ON vomsisBilgileri(userid);

CREATE TABLE IF NOT EXISTS moy_bilgileri (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    musteriNo   INTEGER NOT NULL UNIQUE,
    url         TEXT    NOT NULL DEFAULT '',
    username    TEXT    NOT NULL DEFAULT '',
    sifre       TEXT    NOT NULL DEFAULT '',
    moyKayitNo  TEXT             DEFAULT '',
    tarih       TEXT             DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_moy_musteri
    ON moy_bilgileri(musteriNo);

-- ── Vergi Muhtasar ─────────────────────────────────────────────────────────
-- PHP: VergiMuhtasar MySQL tablosunun karşılığı
-- UPSERT anahtarı: (userid, hesapkodu, donem)
CREATE TABLE IF NOT EXISTS VergiMuhtasar (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    userid       INTEGER NOT NULL,
    musteri_no   INTEGER,
    hesapkodu    TEXT    NOT NULL,
    ack          TEXT,
    donem        TEXT    NOT NULL,
    gaytutar     REAL,
    vergkestutar REAL,
    eklenme_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vergimuhtasar_userid_donem
    ON VergiMuhtasar(userid, donem);

-- ── Kredi Kartı Tanımları ─────────────────────────────────────────────────
-- PHP: key_kartlari MySQL tablosunun karşılığı
-- Kullanıcıya ait kayıtlı kart tanımları (banka, hesap kodu, IBAN vb.)
CREATE TABLE IF NOT EXISTS key_kartlari (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    banka     TEXT    NOT NULL,          -- Kart etiketi (Örn: "Yapı Kredi-1234")
    no        TEXT    NOT NULL DEFAULT '',
    tag       TEXT,
    userid    INTEGER NOT NULL,
    hesapKodu TEXT             DEFAULT '',
    bankaAdi  TEXT             DEFAULT '', -- Banka adı (Örn: "Yapı Kredi", "İş Bankası")
    iban      TEXT             DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_key_kartlari_userid
    ON key_kartlari(userid);

-- ── Kredi Kartı Ekstre Verileri ───────────────────────────────────────────
-- PHP: kredikartiData MySQL tablosunun karşılığı
-- CSV/PDF/XLSX dosyalarından aktarılan banka ekstresi kayıtları
CREATE TABLE IF NOT EXISTS kredikartiData (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    userid       TEXT,
    musterino    TEXT,
    tarih        TEXT,
    aciklama     TEXT,
    Tutar        TEXT,
    carihesapId  TEXT,
    hesapKodu    TEXT,
    alinan_tutar1 REAL,
    womsiskey    TEXT    NOT NULL DEFAULT '',
    islem        INTEGER,
    Banka        TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_kredikarti_userid_tarih
    ON kredikartiData(userid, tarih);
CREATE INDEX IF NOT EXISTS idx_kredikarti_womsiskey
    ON kredikartiData(womsiskey);

-- ── PayTR Sanal Pos İşlem Dökümü ──────────────────────────────────────────
-- PHP: ajax/paytr_sync_chunk.php → CREATE TABLE paytr
-- PayTR API'den veya manuel import ile gelen sanal pos işlemleri
CREATE TABLE IF NOT EXISTS paytr (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
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
    guncelleme_tarihi TEXT    DEFAULT CURRENT_TIMESTAMP,
    created_at        TEXT    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (userid, siparisno)
);

CREATE INDEX IF NOT EXISTS idx_paytr_userid_islemtarihi
    ON paytr(userid, islemtarihi);

-- ── PayTR Senkronizasyon Logu ─────────────────────────────────────────────
-- PHP: ajax/paytr_sync_chunk.php → CREATE TABLE paytr_sync_log
-- Son başarılı senkronizasyon tarihi (dashboard kartı için)
CREATE TABLE IF NOT EXISTS paytr_sync_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    userid          INTEGER NOT NULL,
    musterino       TEXT    NOT NULL DEFAULT '',
    son_sync_tarihi TEXT    DEFAULT NULL,
    updated_at      TEXT    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (userid, musterino)
);

CREATE INDEX IF NOT EXISTS idx_paytr_sync_log_userid
    ON paytr_sync_log(userid, musterino);

-- ── API Sanal Pos Kimlik Bilgileri ────────────────────────────────────────
-- PHP: apisanalpos MySQL tablosunun karşılığı
-- PayTR entegrasyonu için Mağaza No / Parola / Gizli Anahtar
CREATE TABLE IF NOT EXISTS apisanalpos (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    userid                INTEGER NOT NULL,
    musterino             TEXT    NOT NULL DEFAULT '1',
    firma_adi             TEXT    DEFAULT '',
    magaza_no             TEXT    DEFAULT '',
    magaza_parola         TEXT    DEFAULT '',
    magaza_gizli_anahtar  TEXT    DEFAULT '',
    kayit_tarihi          TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_apisanalpos_userid
    ON apisanalpos(userid);

-- ── IBAN Hesap Bilgileri ───────────────────────────────────────────────────
-- PHP: ibanHesapBilgileri MySQL tablosunun karşılığı
CREATE TABLE IF NOT EXISTS ibanHesapBilgileri (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    userid           INTEGER NOT NULL,
    ibanHesapbaslik  TEXT NOT NULL,
    cariHesapid      INTEGER NOT NULL,
    bankaAdi         TEXT NOT NULL,
    subeAdi          TEXT,
    bankaHesapno     TEXT,
    ibanNo           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_iban_userid
    ON ibanHesapBilgileri(userid);

-- ── Alt Kullanıcı Yetkileri ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alt_kullanici (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_userid   INTEGER NOT NULL,
    kullanici_adi   TEXT    NOT NULL,
    eposta          TEXT    NOT NULL DEFAULT '',
    sifre_hash      TEXT    DEFAULT NULL,
    uyelik_tarihi   TEXT    DEFAULT NULL,
    yetki           TEXT    DEFAULT '1'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ak_kullanici ON alt_kullanici(kullanici_adi);
CREATE INDEX IF NOT EXISTS idx_ak_parent ON alt_kullanici(parent_userid);

-- ── Varsayılan Super Admin Kullanıcısı ───────────────────────────────────────
-- Yalnızca 'superadmin' adlı kullanıcı yoksa eklenir (yetki='superadmin', sifre='123')
INSERT INTO uyelik (
    kullanici_adi, sifre, yetki, firmaAdi,
    hesapTuru, bagli_hesap, altKullaniciSayisi
)
SELECT 'superadmin', '123', 'superadmin', 'IQ Finans', 0, -1, 0
WHERE NOT EXISTS (
    SELECT 1 FROM uyelik WHERE kullanici_adi = 'superadmin'
);

"""
