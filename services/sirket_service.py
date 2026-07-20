"""
Şirket Profili Servisi — sirket_profili tablosu CRUD.
Fatura otomatik sınıflandırmasında VKN/TCKN karşılaştırması için kullanılır.
"""
from __future__ import annotations
from db.database import get_connection


def get_sirket_profili(userid: int, musterino: int = 1) -> dict:
    """
    Kullanıcıya ve müşteriye ait şirket profilini döndürür.
    Önce userid + musterino ile dener; bulamazsa yalnızca userid ile fallback yapar.
    Kayıt yoksa boş dict döner.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM sirket_profili WHERE userid=? AND musterino=?",
            (userid, musterino)
        ).fetchone()
        if row:
            return dict(row)
        # Geriye dönük uyumluluk: musterino kolonu henüz güncellenmemiş kayıtlar
        row = conn.execute(
            "SELECT * FROM sirket_profili WHERE userid=?", (userid,)
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def save_sirket_profili(userid: int, unvan: str, vergino: str,
                        tckn: str = "", vergidairesi: str = "",
                        adres: str = "", il: str = "", ilce: str = "",
                        musterino: int = 1) -> bool:
    """
    Şirket profilini kaydeder (INSERT OR REPLACE).
    Başarılıysa True döner.
    """
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO sirket_profili
                (userid, unvan, vergino, tckn, vergidairesi, adres, il, ilce, musterino)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(userid) DO UPDATE SET
                unvan        = excluded.unvan,
                vergino      = excluded.vergino,
                tckn         = excluded.tckn,
                vergidairesi = excluded.vergidairesi,
                adres        = excluded.adres,
                il           = excluded.il,
                ilce         = excluded.ilce,
                musterino    = excluded.musterino
        """, (userid, unvan.strip(), vergino.strip(), tckn.strip(),
              vergidairesi.strip(), adres.strip(), il.strip(), ilce.strip(),
              musterino))
        conn.commit()
        return True
    except Exception as exc:
        print(f"[SirketProfili] Kayıt hatası: {exc}")
        conn.rollback()
        return False
    finally:
        conn.close()


def detect_fatura_mod(xml_supplier_vkn: str, xml_supplier_tc: str,
                      xml_customer_vkn: str, xml_customer_tc: str,
                      userid: int, musterino: int = 1) -> str | None:
    """
    XML'deki taraf bilgilerini şirket profiliyle karşılaştırarak
    faturanın modunu otomatik tespit eder.

    Returns:
        'gelir'  → Şirket kesen taraf (Kesilen / Satış faturası)
        'gider'  → Şirket alan taraf  (Gelen / Alış faturası)
        None     → Eşleşme yok (atla / hata)
    """
    profil = get_sirket_profili(userid, musterino)
    if not profil:
        return None  # Profil tanımlanmamış

    sirket_vkn  = (profil.get("vergino") or "").strip()
    sirket_tckn = (profil.get("tckn")    or "").strip()

    sup_vkn = (xml_supplier_vkn or "").strip()
    sup_tc  = (xml_supplier_tc  or "").strip()
    cus_vkn = (xml_customer_vkn or "").strip()
    cus_tc  = (xml_customer_tc  or "").strip()

    # Tedarikçi = Şirket → Biz kestik → GELİR
    if sirket_vkn and (sup_vkn == sirket_vkn):
        return "gelir"
    if sirket_tckn and (sup_tc == sirket_tckn):
        return "gelir"

    # Alıcı = Şirket → Bize kesildi → GİDER
    if sirket_vkn and (cus_vkn == sirket_vkn):
        return "gider"
    if sirket_tckn and (cus_tc == sirket_tckn):
        return "gider"

    return None  # Eşleşme yok
