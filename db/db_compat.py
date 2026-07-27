"""
db/db_compat.py — SQLite / PostgreSQL SQL uyumluluk yardımcıları
================================================================
SQLite'a özgü fonksiyonları PostgreSQL karşılıklarıyla eşleştiren
tek merkezi yer. Tüm servisler buradan import eder.

Kullanım örneği:
    from db.db_compat import yr, yr_col, mo, right4, left4, tablo_var_expr

    sql = f'''
        SELECT SUM(gelir) FROM genel_hesap_hareketleri
        WHERE {yr("tarih_date")} = ?
    '''
"""
from __future__ import annotations
from db.db_config import get_mode


def _pg() -> bool:
    return get_mode() == "postgres"


# ── Yıl / Ay ifadeleri ───────────────────────────────────────────────────────

def yr(col: str) -> str:
    """WHERE yıl filtresi — sonuç TEXT olarak döner ('2026' ile karşılaştırılabilir).
    Tarih sütunu YYYY-MM-DD formatında TEXT veya DATE tipinde olmalı."""
    if _pg():
        return f"EXTRACT(YEAR FROM ({col})::DATE)::TEXT"
    return f"strftime('%Y', {col})"


def yr_col(col: str) -> str:
    """SELECT içinde ay sütunu — TEXT."""
    return yr(col)


def mo(col: str) -> str:
    """Ay ifadesi — sonuç INTEGER (1–12)."""
    if _pg():
        return f"EXTRACT(MONTH FROM ({col})::DATE)::INTEGER"
    return f"CAST(strftime('%m', {col}) AS INTEGER)"


def mo_str(col: str) -> str:
    """Ay ifadesi — sonuç 2 haneli TEXT ('01'–'12').
    strftime('%m') ile aynı davranış."""
    if _pg():
        return f"LPAD(EXTRACT(MONTH FROM ({col})::DATE)::TEXT, 2, '0')"
    return f"strftime('%m', {col})"


# ── substr() alternatifleri ───────────────────────────────────────────────────

def left4(col: str) -> str:
    """İlk 4 karakter — TEXT'deki yılı almak için.
    SQLite: substr(col, 1, 4)  →  PG: LEFT(col, 4)"""
    if _pg():
        return f"LEFT({col}, 4)"
    return f"substr({col}, 1, 4)"


def right4(col: str) -> str:
    """Son 4 karakter — DD.MM.YYYY formatındaki son 4 karakter yıl için.
    SQLite: substr(col, -4)  →  PG: RIGHT(col, 4)"""
    if _pg():
        return f"RIGHT({col}, 4)"
    return f"substr({col}, -4)"


def substr_mid(col: str, start: int, length: int) -> str:
    """Orta n karakter.
    SQLite: substr(col, start, length)  →  PG: SUBSTRING(col FROM start FOR length)"""
    if _pg():
        return f"SUBSTRING({col} FROM {start} FOR {length})"
    return f"substr({col}, {start}, {length})"


def tarih_yil_hareketler(col: str) -> str:
    """hareketler.tarih formatı: DD.MM.YYYY  →  yılı ayıkla (7. karakterden 4 karakter).
    Örnek: '15.03.2026' → '2026'"""
    if _pg():
        return f"SUBSTRING({col} FROM 7 FOR 4)"
    return f"substr({col}, 7, 4)"


def tarih_iso_hareketler(col: str) -> str:
    """hareketler.tarih DD.MM.YYYY formatını ISO YYYY-MM-DD'ye çevirerek karşılaştırmak için.
    SQLite: substr||| birleştirme  →  PG: TO_DATE + TO_CHAR veya doğrudan birleştirme."""
    if _pg():
        # SUBSTRING ile yeniden birleştir: DD.MM.YYYY → YYYY-MM-DD
        return (
            f"(SUBSTRING({col} FROM 7 FOR 4) || '-' || "
            f" SUBSTRING({col} FROM 4 FOR 2) || '-' || "
            f" SUBSTRING({col} FROM 1 FOR 2))"
        )
    return (
        f"(substr({col},-4)||'-'||substr({col},4,2)||'-'||substr({col},1,2))"
    )


def tarih_yil_kredi(col: str) -> str:
    """kredikartiData.tarih DD.MM.YYYY formatı — son 4 karakter yıl."""
    return right4(col)


# ── Tablo varlık kontrolü ─────────────────────────────────────────────────────

def tablo_var_expr(tablo_adi: str) -> str:
    """Tablo var mı SQL ifadesi — SELECT ile kullanılır, INTEGER döner (0/1).

    Kullanım:
        count = conn.execute(tablo_var_expr('paytr')).fetchone()[0]
        if count:
            ...
    """
    if _pg():
        return (
            f"SELECT COUNT(*) FROM information_schema.tables "
            f"WHERE table_schema='public' AND table_name='{tablo_adi}'"
        )
    return (
        f"SELECT COUNT(*) FROM sqlite_master "
        f"WHERE type='table' AND name='{tablo_adi}'"
    )


# ── Kolon adı yardımcıları ───────────────────────────────────────────
# PG'de artık tüm kolonlar küçük harf normalize edildi.
# SQLite'da kolonlar hâlâ orijinal camelCase.
# Bu fonksiyonlar mod'a göre doğru adı döndürür.

def pg_musterino() -> str:
    """nakitakis_Parametre: musteriNo (SQLite) | musterino (PG)"""
    return "musterino" if _pg() else "musteriNo"


def pg_hesapkodu() -> str:
    """nakitakis_Parametre: hesapKodu (SQLite) | hesapkodu (PG)"""
    return "hesapkodu" if _pg() else "hesapKodu"


def pg_isinv() -> str:
    """nakitakis_Parametre: ilkTarih (SQLite) | ilktarih (PG)"""
    return "ilktarih" if _pg() else "ilkTarih"


def pg_gelirgider() -> str:
    """nakitakis_Parametre: gelirGider (SQLite) | gelirgider (PG)"""
    return "gelirgider" if _pg() else "gelirGider"


def numeric_cast(col: str) -> str:
    """PostgreSQL float4 (real) kolon precision kaybını önlemek için NUMERIC cast.

    PostgreSQL'de gider/gelir kolonları REAL (float4) tipinde saklanabilir.
    Büyük SUM işlemlerinde float4 precision kaybeder (ör: 11,718,076.50 → 11,718,076.00).
    Bu fonksiyon PostgreSQL'de ::NUMERIC, SQLite'da CAST(... AS REAL) döndürür.

    Kullanım:
        SUM({numeric_cast('gider')})   yerine   SUM(gider)
    """
    if _pg():
        return f"({col})::NUMERIC"
    return f"CAST({col} AS REAL)"
