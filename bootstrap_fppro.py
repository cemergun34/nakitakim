"""
bootstrap_fppro.py
─────────────────────────────────────────────────────────────────────────────
FPPRO ELEKTRONİK DIŞ TİC. SAN. LTD. ŞTİ. — Fabrika Ayarları

Bu modül uygulamanın ilk açılışında otomatik çalışarak
yeni bir bilgisayara kurulumda TÜM API / bağlantı bilgilerini
sıfırdan girmek zorunda kalmaksızın hazır hale getirir.

Kapsam:
  ✔  PostgreSQL bağlantı bilgileri  (db_config.json)
  ✔  Google Sheets sheet ID'leri   (gsheets_config.json)
  ✔  VOMSİS API anahtarları        (vomsisBilgileri tablosu)
  ✔  PayTR sanal POS bilgileri     (apisanalpos tablosu)
  ✔  MOY muhasebe bağlantısı       (moy_bilgileri tablosu)
  ✔  Şirket profili                (sirket_profili tablosu)

⚠  Hassas bilgiler (şifreler, API anahtarları) bu dosyada BULUNMAZ.
   Bunlar bootstrap_fppro_secrets.py dosyasından okunur.
   Secrets dosyası .gitignore'dadır — git'e gönderilmez.

Sentinel:  ~/NakitAkim/data/.fppro_bootstrapped
  • Dosya varsa bootstrap atlanır (sadece ilk kurulumda çalışır).
  • Zorla yeniden çalıştırmak için: run_bootstrap(force=True)
─────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Yollar ───────────────────────────────────────────────────────────────────
_DATA_DIR      = Path.home() / "NakitAkim" / "data"
_SENTINEL_PATH = _DATA_DIR / ".fppro_bootstrapped"
_DB_CFG_PATH   = _DATA_DIR / "db_config.json"
_GS_CFG_PATH   = _DATA_DIR / "gsheets_config.json"


# ── Secrets dosyasını yükle ───────────────────────────────────────────────────
def _load_secrets():
    """
    bootstrap_fppro_secrets.py dosyasını import eder.
    Derleme sonrası .app içinde de çalışır (PyInstaller --add-data ile gömülür).
    """
    try:
        import bootstrap_fppro_secrets as s
        return s
    except ImportError:
        logger.error(
            "[Bootstrap] bootstrap_fppro_secrets.py bulunamadı! "
            "Derleme yapmadan önce bu dosyanın projenizde olduğundan emin olun."
        )
        return None


# ── Google Sheets (şifre gerektirmiyor — herkese açık CSV URL) ───────────────
_FPPRO_GSHEETS_CONFIG: dict = {
    "kasa_sheet_id":        "10L3gSinp4cY6dwDzmZvjCtpZK6ykmMiG9xXxXFgfbVA",
    "kasa_tab_name":        "Kasa",
    "gider_sheet_id":       "1bxN5D_UEtgzxBJd6hQyhZzeKHP5QAXTgEGyTnBH45Tk",
    "genel_hesap_sheet_id": "1cdV-a6yyYeFm8TIMipaEhphmV-IfIGD_y7os8IkSAsA",
}

# ── Şirket Profili (şifre gerektirmiyor) ─────────────────────────────────────
_FPPRO_SIRKET: dict = {
    "userid":       1,
    "unvan":        "FPPRO ELEKTRONİK DIŞ TİC. SAN. LTD. ŞTİ.",
    "vergino":      "3881403207",
    "tckn":         "",
    "vergidairesi": "şişli",
    "adres":        "",
    "il":           "istanbul",
    "ilce":         "şişli",
}


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı: JSON dosyasına yaz
# ─────────────────────────────────────────────────────────────────────────────

def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("[Bootstrap] %s yazıldı.", path.name)


# ─────────────────────────────────────────────────────────────────────────────
# Adım 1 — DB config (JSON)
# ─────────────────────────────────────────────────────────────────────────────

def _bootstrap_db_config(s) -> None:
    cfg = {
        "mode":       "postgres",
        "pg_host":    s.PG_HOST,
        "pg_port":    s.PG_PORT,
        "pg_db":      s.PG_DB,
        "pg_user":    s.PG_USER,
        "pg_pass":    s.PG_PASS,
        "pg_sslmode": s.PG_SSLMODE,
    }
    _write_json(_DB_CFG_PATH, cfg)


# ─────────────────────────────────────────────────────────────────────────────
# Adım 2 — Google Sheets config (JSON)
# ─────────────────────────────────────────────────────────────────────────────

def _bootstrap_gsheets_config() -> None:
    _write_json(_GS_CFG_PATH, _FPPRO_GSHEETS_CONFIG)


# ─────────────────────────────────────────────────────────────────────────────
# Adım 3 — VOMSİS (DB tablosu)
# ─────────────────────────────────────────────────────────────────────────────

def _bootstrap_vomsis(conn, s) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = conn.execute(
        "SELECT id FROM vomsisBilgileri WHERE userid=? LIMIT 1", (1,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE vomsisBilgileri SET appkey=?, seckey=?, url=?, guncelleme_tarihi=? WHERE userid=?",
            (s.VOMSIS_APPKEY, s.VOMSIS_SECKEY, s.VOMSIS_URL, now, 1)
        )
    else:
        conn.execute(
            "INSERT INTO vomsisBilgileri (userid, appkey, seckey, url, guncelleme_tarihi) VALUES (?,?,?,?,?)",
            (1, s.VOMSIS_APPKEY, s.VOMSIS_SECKEY, s.VOMSIS_URL, now)
        )
    conn.commit()
    logger.info("[Bootstrap] VOMSİS kaydedildi.")


# ─────────────────────────────────────────────────────────────────────────────
# Adım 4 — PayTR (apisanalpos tablosu)
# ─────────────────────────────────────────────────────────────────────────────

def _bootstrap_paytr(conn, s) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = conn.execute(
        "SELECT id FROM apisanalpos WHERE userid=? LIMIT 1", (1,)
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE apisanalpos
               SET musterino=?, firma_adi=?, magaza_no=?,
                   magaza_parola=?, magaza_gizli_anahtar=?, kayit_tarihi=?
               WHERE userid=?""",
            ("1", "paytr", s.PAYTR_MAGAZA_NO,
             s.PAYTR_MAGAZA_PAROLA, s.PAYTR_MAGAZA_GIZLI_ANAHTAR, now, 1)
        )
    else:
        conn.execute(
            """INSERT INTO apisanalpos
               (userid, musterino, firma_adi, magaza_no, magaza_parola, magaza_gizli_anahtar, kayit_tarihi)
               VALUES (?,?,?,?,?,?,?)""",
            (1, "1", "paytr", s.PAYTR_MAGAZA_NO,
             s.PAYTR_MAGAZA_PAROLA, s.PAYTR_MAGAZA_GIZLI_ANAHTAR, now)
        )
    conn.commit()
    logger.info("[Bootstrap] PayTR kaydedildi.")


# ─────────────────────────────────────────────────────────────────────────────
# Adım 5 — MOY muhasebe (moy_bilgileri tablosu)
# ─────────────────────────────────────────────────────────────────────────────

def _bootstrap_moy(conn, s) -> None:
    from db.db_config import get_mode
    _pg = get_mode() == "postgres"
    col_mno  = "musterino"  if _pg else "musteriNo"
    col_mkno = "moykayitno" if _pg else "moyKayitNo"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = conn.execute(
        f'SELECT id FROM moy_bilgileri WHERE "{col_mno}"=? LIMIT 1', (1,)
    ).fetchone()
    if existing:
        conn.execute(
            f'UPDATE moy_bilgileri SET url=?, username=?, sifre=?, "{col_mkno}"=? WHERE "{col_mno}"=?',
            (s.MOY_URL, s.MOY_USERNAME, s.MOY_SIFRE, s.MOY_KAYIT_NO, 1)
        )
    else:
        conn.execute(
            f'INSERT INTO moy_bilgileri ("{col_mno}", url, username, sifre, "{col_mkno}") VALUES (?,?,?,?,?)',
            (1, s.MOY_URL, s.MOY_USERNAME, s.MOY_SIFRE, s.MOY_KAYIT_NO)
        )
    conn.commit()
    logger.info("[Bootstrap] MOY kaydedildi.")


# ─────────────────────────────────────────────────────────────────────────────
# Adım 6 — Şirket profili (sirket_profili tablosu)
# ─────────────────────────────────────────────────────────────────────────────

def _bootstrap_sirket(conn) -> None:
    s = _FPPRO_SIRKET
    existing = conn.execute(
        "SELECT id FROM sirket_profili WHERE userid=? LIMIT 1", (s["userid"],)
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE sirket_profili
               SET unvan=?, vergino=?, tckn=?, vergidairesi=?, adres=?, il=?, ilce=?
               WHERE userid=?""",
            (s["unvan"], s["vergino"], s["tckn"], s["vergidairesi"],
             s["adres"], s["il"], s["ilce"], s["userid"])
        )
    else:
        conn.execute(
            """INSERT INTO sirket_profili
               (userid, unvan, vergino, tckn, vergidairesi, adres, il, ilce)
               VALUES (?,?,?,?,?,?,?,?)""",
            (s["userid"], s["unvan"], s["vergino"], s["tckn"],
             s["vergidairesi"], s["adres"], s["il"], s["ilce"])
        )
    conn.commit()
    logger.info("[Bootstrap] Şirket profili kaydedildi.")


# ─────────────────────────────────────────────────────────────────────────────
# Ana fonksiyon — main.py'den çağrılır
# ─────────────────────────────────────────────────────────────────────────────

def run_bootstrap(force: bool = False) -> bool:
    """
    FPPRO fabrika ayarlarını yükler.

    Parameters
    ----------
    force : bool
        True ise sentinel dosyası olsa bile tekrar çalışır.

    Returns
    -------
    bool — True: bootstrap çalıştı, False: daha önce yapıldı, atlandı.
    """
    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not force and _SENTINEL_PATH.exists():
        logger.debug("[Bootstrap] Daha önce yapıldı, atlanıyor.")
        return False

    # Secrets dosyasını yükle
    secrets = _load_secrets()
    if secrets is None:
        logger.error("[Bootstrap] Secrets dosyası eksik — bootstrap atlanıyor.")
        return False

    logger.info("[Bootstrap] FPPRO fabrika ayarları yükleniyor...")
    errors: list[str] = []

    # ── 1. JSON dosyaları ────────────────────────────────────────────────────
    try:
        _bootstrap_db_config(secrets)
    except Exception as exc:
        errors.append(f"db_config: {exc}")
        logger.error("[Bootstrap] db_config hatası: %s", exc)

    try:
        _bootstrap_gsheets_config()
    except Exception as exc:
        errors.append(f"gsheets_config: {exc}")

    # ── 2. Veritabanı kayıtları ───────────────────────────────────────────────
    try:
        from db.database import get_connection
        conn = get_connection()
        try:
            _bootstrap_vomsis(conn, secrets)
        except Exception as exc:
            errors.append(f"vomsis: {exc}")

        try:
            _bootstrap_paytr(conn, secrets)
        except Exception as exc:
            errors.append(f"paytr: {exc}")

        try:
            _bootstrap_moy(conn, secrets)
        except Exception as exc:
            errors.append(f"moy: {exc}")

        try:
            _bootstrap_sirket(conn)
        except Exception as exc:
            errors.append(f"sirket: {exc}")

        conn.close()
    except Exception as exc:
        errors.append(f"db_connection: {exc}")
        logger.error("[Bootstrap] Veritabanı bağlantı hatası: %s", exc)

    # ── Sentinel yaz ─────────────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_json(_SENTINEL_PATH.with_suffix(".json"), {
        "bootstrapped_at": ts,
        "errors":          errors,
        "version":         "fppro-1.0",
    })
    _SENTINEL_PATH.touch()

    if errors:
        logger.warning("[Bootstrap] %d hata ile tamamlandı: %s", len(errors), errors)
    else:
        logger.info("[Bootstrap] ✅ Tüm ayarlar başarıyla yüklendi (%s).", ts)

    return True
