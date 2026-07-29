"""
Kimlik doğrulama servisi — uyelik tablosundan (PHP giris.php mantığı).
"""
from __future__ import annotations
from db.database import get_connection


def authenticate(kullanici_adi: str, sifre: str) -> dict | None:
    """
    kullanici_adi (veya eposta) + sifre ile giriş kontrolü.
    PHP giris.php: uyelik tablosu, sifre MD5 veya düz metin.
    Başarılı ise kullanıcı dict'ini döndürür, başarısız ise None.
    """
    import hashlib
    conn = get_connection()
    try:
        # Önce düz metin dene
        row = conn.execute(
            """SELECT * FROM uyelik
               WHERE (kullanici_adi = ? OR eposta = ?)
               LIMIT 1""",
            (kullanici_adi, kullanici_adi)
        ).fetchone()

        if not row:
            return None

        row_dict = dict(row)
        stored_sifre = row_dict.get("sifre", "")

        # 1. Düz metin karşılaştırma
        if stored_sifre == sifre:
            return _build_user(row_dict)

        # 2. MD5 karşılaştırma
        md5_sifre = hashlib.md5(sifre.encode()).hexdigest()
        if stored_sifre == md5_sifre:
            return _build_user(row_dict)

        # 3. SHA-256 karşılaştırma (webadmin/fppro bazı versiyonları bu algoritmayı kullanır)
        sha256_sifre = hashlib.sha256(sifre.encode()).hexdigest()
        if stored_sifre == sha256_sifre:
            return _build_user(row_dict)

        # 4. Bcrypt ($2y$ → $2b$ PHP uyumu)
        try:
            import bcrypt
            # PHP $2y$ → Python bcrypt $2b$ uyumu
            check_hash = stored_sifre.replace("$2y$", "$2b$", 1).encode()
            if bcrypt.checkpw(sifre.encode(), check_hash):
                return _build_user(row_dict)
        except Exception:
            pass

        return None
    finally:
        conn.close()


def _build_user(row: dict) -> dict:
    """Standart kullanıcı sözlüğü oluşturur.
    PG'de kolon adları küçük harf (firmaadi, hesapturu vb.)
    SQLite'da camelCase (firmaAdi, hesapTuru vb.)

    bagli_hesap mantığı:
      > 0 → o hesabın ID'si ile sorgu yap (alt kullanıcı)
      = -1 → bu ana hesap veya bağlanmamış
             → aynı musterino'da veri olan userid'i otomatik bul
    """
    bagli = int(row.get("bagli_hesap", -1) or -1)
    kendi_id = int(row.get("id", 1) or 1)
    musterino = int(row.get("musterino") or 1)

    if bagli > 0:
        # Açıkça bağlanmış → ana hesabı kullan
        user_id = bagli
    else:
        # bagli_hesap=-1: önce genel_hesap_hareketleri'nde bu musterino için
        # veri olan userid'i bul. Yoksa kendi id'ini kullan.
        try:
            conn = get_connection()
            try:
                found = conn.execute(
                    """SELECT userid FROM genel_hesap_hareketleri
                       WHERE musteri_no = ?
                       GROUP BY userid
                       ORDER BY COUNT(*) DESC
                       LIMIT 1""",
                    (musterino,)
                ).fetchone()
                user_id = int(found[0]) if found else kendi_id
                # Eğer bulunan userid kendisi değilse bagli_hesap'ı otomatik güncelle
                if user_id != kendi_id:
                    try:
                        conn.execute(
                            "UPDATE uyelik SET bagli_hesap=? WHERE id=?",
                            (user_id, kendi_id)
                        )
                        conn.commit()
                    except Exception:
                        pass
            finally:
                conn.close()
        except Exception:
            user_id = kendi_id

    return {
        "Kayitno":      kendi_id,
        "Adi":          row.get("kullanici_adi", ""),
        "GercekUserId": user_id,
        "musterino":    musterino,   # uyelik.musterino sütunundan gelir
        # PG: firmaadi, SQLite: firmaAdi — her ikisini de dene
        "firmaAdi":     row.get("firmaadi") or row.get("firmaAdi") or "IQ Finans",
        "yetki":        row.get("yetki", "0") or "0",
        # PG: hesapturu, SQLite: hesapTuru
        "hesapTuru":    row.get("hesapturu") if row.get("hesapturu") is not None
                        else row.get("hesapTuru", 0),
    }



def get_user_by_id(user_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM uyelik WHERE id = ?", (user_id,)
        ).fetchone()
        return _build_user(dict(row)) if row else None
    finally:
        conn.close()
