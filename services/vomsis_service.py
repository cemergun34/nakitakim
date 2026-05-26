"""
VOMSİS API Servisi — Python/requests
PHP test/vomsis.php  +  ajax/ayarlar/vomsisKaydet.php
                       +  ajax/ayarlar/vomsisBilgileriGetir.php
dosyalarının tam karşılığı.

Fonksiyonlar:
    get_vomsis_bilgileri(userid)  → dict
    save_vomsis_bilgileri(...)    → bool
    vomsis_authenticate(url, app_key, app_secret) → str | None
    vomsis_get_banks(url, token)  → list
    vomsis_get_accounts(url, token) → list
    vomsis_get_account_transactions(url, token, account_id, begin, end) → list
    vomsis_get_all_transactions(url, token, begin, end) → list
    vomsis_get_terminals(url, token) → list
    vomsis_get_terminal_transactions(url, token, terminal_id, begin, end) → list
    vomsis_get_all_transactions_chunked(url, token, start, end) → list
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from db.database import get_connection

logger = logging.getLogger(__name__)

# ── Varsayılan API adresi ───────────────────────────────────────────────────
DEFAULT_API_URL = "https://developers.vomsis.com/api/v2"


# ─────────────────────────────────────────────────────────────────────────────
# Veritabanı işlemleri  (vomsisKaydet.php + vomsisBilgileriGetir.php)
# ─────────────────────────────────────────────────────────────────────────────

def get_vomsis_bilgileri(userid: int) -> dict:
    """
    vomsisBilgileri tablosundan kullanıcıya ait kayıtları döndürür.
    Kayıt yoksa boş değerlerle dict döner.
    PHP: ajax/ayarlar/vomsisBilgileriGetir.php
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT appkey, seckey, url FROM vomsisBilgileri WHERE userid=? LIMIT 1",
            (userid,)
        ).fetchone()
        if row:
            return {
                "success": True,
                "appkey":  row["appkey"] or "",
                "seckey":  row["seckey"] or "",
                "url":     row["url"]    or DEFAULT_API_URL,
            }
        return {"success": True, "appkey": "", "seckey": "", "url": DEFAULT_API_URL}
    except Exception as e:
        logger.error("VOMSİS bilgileri getirme hatası: %s", e)
        return {"success": False, "appkey": "", "seckey": "", "url": DEFAULT_API_URL}
    finally:
        conn.close()


def save_vomsis_bilgileri(userid: int, appkey: str, seckey: str,
                          url: str = DEFAULT_API_URL) -> dict:
    """
    vomsisBilgileri tablosuna kayıt ekler veya günceller.
    PHP: ajax/ayarlar/vomsisKaydet.php
    Returns: {"success": bool, "message": str}
    """
    if not appkey or not seckey or not url:
        return {"success": False, "message": "Tüm alanları doldurunuz."}

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM vomsisBilgileri WHERE userid=? LIMIT 1",
            (userid,)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE vomsisBilgileri
                   SET appkey=?, seckey=?, url=?, guncelleme_tarihi=?
                   WHERE userid=?""",
                (appkey, seckey, url, now, userid)
            )
            message = "Vomsis bilgileri güncellendi."
        else:
            conn.execute(
                """INSERT INTO vomsisBilgileri (userid, appkey, seckey, url, kayit_tarihi, guncelleme_tarihi)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (userid, appkey, seckey, url, now, now)
            )
            message = "Vomsis bilgileri kaydedildi."

        conn.commit()
        return {"success": True, "message": message}
    except Exception as e:
        conn.rollback()
        logger.error("VOMSİS kaydetme hatası: %s", e)
        return {"success": False, "message": f"Hata: {e}"}
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# VOMSİS API İstekleri  (test/vomsis.php karşılığı)
# ─────────────────────────────────────────────────────────────────────────────

def _get_requests():
    """requests kütüphanesini geç yükle — kurulmamışsa ImportError."""
    try:
        import requests as _req
        return _req
    except ImportError as e:
        raise ImportError(
            "VOMSİS API için 'requests' kütüphanesi gerekli.\n"
            "Kurulum: pip install requests"
        ) from e


def vomsis_authenticate(api_url: str, app_key: str, app_secret: str,
                         timeout: int = 15) -> tuple[Optional[str], str]:
    """
    VOMSİS token alır.
    PHP: getVomsisToken($apiBase, $app_key, $app_secret)

    Returns:
        (token_str, "")          — başarılı durumda
        (None,  hata_mesajı)    — hata durumunda

    VOMSİS HTTP 200 döndürüp
        {"status":"error","message":"..."}
    formatında hata iletebilir (IP yasası, geçersiz key vb.)
    """
    req = _get_requests()
    url = api_url.rstrip("/") + "/authenticate"
    try:
        resp = req.post(
            url,
            json={"app_key": app_key, "app_secret": app_secret},
            headers={"Content-Type": "application/json"},
            timeout=timeout
        )
        resp.raise_for_status()
        data = resp.json()

        token = data.get("token")
        if token:
            return token, ""

        # VOMSİS hata mesajını al (IP yasası, key hatası vb.)
        api_msg = data.get("message") or data.get("error") or ""
        if not api_msg:
            api_msg = "API yanıtında token bulunamadı."
        logger.warning("VOMSİS token alınamadı: %s", api_msg)
        return None, api_msg

    except req.exceptions.Timeout:
        msg = "Bağlantı zaman aşımı (çevrimdışı mısınız?)."
        logger.error("VOMSİS timeout: %s", url)
        return None, msg
    except req.exceptions.ConnectionError:
        msg = "VOMSİS sunucusuna ulaşılamadı (İnternet bağlantısını kontrol edin)."
        logger.error("VOMSİS bağlantı hatası: %s", url)
        return None, msg
    except Exception as e:
        logger.error("VOMSİS authenticate hatası: %s", e)
        return None, str(e)


def _vomsis_get(api_url: str, token: str, timeout: int = 20) -> dict:
    """
    Genel GET isteği.
    PHP: vomsisGetRequest($url, $token)
    """
    req = _get_requests()
    try:
        resp = req.get(
            api_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            },
            timeout=timeout
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("VOMSİS GET hatası [%s]: %s", api_url, e)
        return {}


def vomsis_get_banks(api_base: str, token: str) -> list:
    """PHP: getBanks($apiBase, $token)"""
    data = _vomsis_get(f"{api_base.rstrip('/')}/banks", token)
    return data.get("banks", [])


def vomsis_get_accounts(api_base: str, token: str) -> list:
    """PHP: getAccounts($apiBase, $token)"""
    data = _vomsis_get(f"{api_base.rstrip('/')}/accounts", token)
    return data.get("accounts", [])


def vomsis_get_account_detail(api_base: str, token: str, account_id) -> dict:
    """PHP: getAccountDetail($apiBase, $token, $accountId)"""
    return _vomsis_get(f"{api_base.rstrip('/')}/accounts/{account_id}", token)


def vomsis_get_account_transactions(api_base: str, token: str,
                                     account_id, begin_date: str,
                                     end_date: str) -> list:
    """
    PHP: getAccountTransactions($apiBase, $token, $accountId, $beginDate, $endDate)
    Tarih formatı: "dd-MM-YYYY HH:mm:ss"
    """
    from urllib.parse import urlencode
    params = urlencode({"beginDate": begin_date, "endDate": end_date})
    url = f"{api_base.rstrip('/')}/accounts/{account_id}/transactions?{params}"
    data = _vomsis_get(url, token)
    return data.get("transactions", [])


def vomsis_get_all_transactions(api_base: str, token: str,
                                 begin_date: str, end_date: str,
                                 bank_name: str = None) -> list:
    """
    PHP: getAllTransactions($apiBase, $token, $beginDate, $endDate, $bankName)
    """
    from urllib.parse import urlencode
    params = {"beginDate": begin_date, "endDate": end_date}
    if bank_name:
        params["bankName"] = bank_name
    url = f"{api_base.rstrip('/')}/transactions?{urlencode(params)}"
    data = _vomsis_get(url, token)
    return data.get("transactions", [])


def vomsis_get_all_transactions_chunked(api_base: str, token: str,
                                         start_dt: datetime,
                                         end_dt: datetime) -> list:
    """
    7 günlük parçalara bölerek tüm banka hareketlerini çeker.
    PHP: getAllTransactionsByRange($apiBase, $token, $startDate, $endDate)
    """
    all_results = []
    current = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    while current < end_dt:
        chunk_end = min(current + timedelta(days=6), end_dt)
        chunk_end = chunk_end.replace(hour=23, minute=59, second=59)

        begin_str = current.strftime("%d-%m-%Y %H:%M:%S")
        end_str   = chunk_end.strftime("%d-%m-%Y %H:%M:%S")

        txs = vomsis_get_all_transactions(api_base, token, begin_str, end_str)
        all_results.extend(txs)

        current = current + timedelta(days=7)
        current = current.replace(hour=0, minute=0, second=0, microsecond=0)

    return all_results


def vomsis_get_terminals(api_base: str, token: str) -> list:
    """PHP: getTerminals($apiBase, $token)"""
    data = _vomsis_get(f"{api_base.rstrip('/')}/pos-rapor/stations", token)
    return data.get("data", [])


def vomsis_get_terminal_transactions(api_base: str, token: str,
                                      terminal_id, begin_date: str,
                                      end_date: str) -> list:
    """PHP: getTerminalTransactions($apiBase, $token, $terminalId, $beginDate, $endDate)"""
    from urllib.parse import urlencode
    params = urlencode({"beginDate": begin_date, "endDate": end_date})
    url = f"{api_base.rstrip('/')}/pos-rapor/stations/{terminal_id}/transactions?{params}"
    data = _vomsis_get(url, token)
    return data.get("transactions", [])


# ─────────────────────────────────────────────────────────────────────────────
# Test / hızlı kontrol yardımcısı
# ─────────────────────────────────────────────────────────────────────────────

def vomsis_test_connection(api_base: str, app_key: str,
                            app_secret: str) -> dict:
    """
    Bağlantıyı test eder; token alabiliyorsa hesap listesini döner.
    UI'daki 'Kontrol Et' butonuna karşılık gelir.
    """
    token, err_msg = vomsis_authenticate(api_base, app_key, app_secret)
    if not token:
        return {
            "success": False,
            "message": err_msg or "Token alınamadı. API bilgilerini kontrol edin."
        }

    accounts = vomsis_get_accounts(api_base, token)
    return {
        "success": True,
        "message": f"Bağlantı başarılı! {len(accounts)} hesap bulundu.",
        "token":    token,
        "accounts": accounts,
    }
