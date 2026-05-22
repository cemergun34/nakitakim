"""
Kimlik doğrulama servisi — uyelik tablosundan (PHP giris.php mantığı).
"""
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

        # 3. Bcrypt ($2y$ → $2b$ PHP uyumu)
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
    """Standart kullanıcı sözlüğü oluşturur."""
    # bagli_hesap > 0 ise o hesabın ID'si, değilse kendi ID
    bagli = int(row.get("bagli_hesap", -1))
    user_id = bagli if bagli > 0 else int(row.get("id", 1))
    return {
        "Kayitno":      int(row.get("id", 1)),
        "Adi":          row.get("kullanici_adi", ""),
        "GercekUserId": user_id,           # musteri_no
        "firmaAdi":     row.get("firmaAdi", "IQ Finans"),
        "yetki":        row.get("yetki", "0"),
        "hesapTuru":    row.get("hesapTuru", 0),
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
