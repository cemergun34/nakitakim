# -*- coding: utf-8 -*-
"""
webadmin-nakitAkim REST API İstemcisi
=======================================
nakitAkim uygulamasından webadmin'in REST API'sini çağırmak için kullanılır.

Kullanım (herhangi bir yerden):

    from services.webadmin_client import WebAdminClient

    client = WebAdminClient()                    # config'den otomatik yükler
    result = client.sync_womsis(userid=1)        # POST /api/womsis/sync
    if result["success"]:
        print(result["count"], "işlem çekildi")
        transactions = result["transactions"]

Ya da QThread içinde (UI donmaz):

    from services.webadmin_client import WebAdminSyncWorker
    # ... (aşağıda örnek)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Config: PostgreSQL webadmin_sirket_config tablosundan ──────────────────────

def get_webadmin_config(userid: int) -> dict:
    """
    Şirket bazlı webadmin bağlantı ayarlarını PostgreSQL'den okur.
    webadmin_sirket_config tablosunda userid eşleşen satırı döner.
    Bulunamazsa güvenli varsayılanları döner.
    """
    defaults = {
        "base_url": _DEFAULT_BASE_URL,
        "api_key":  _DEFAULT_API_KEY,
        "timeout":  60,
        "enabled":  False,   # DB'de tanımlı değilse pasif
        "firmaadi": "",
    }
    try:
        from db.database import get_connection
        conn = get_connection()
        if conn is None:
            return defaults
        cur = conn.cursor()
        cur.execute(
            """
            SELECT webadmin_url, api_key, aktif, firmaadi
            FROM webadmin_sirket_config
            WHERE userid = %s
            LIMIT 1
            """,
            (userid,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            defaults["base_url"] = (row[0] or _DEFAULT_BASE_URL).rstrip("/")
            defaults["api_key"]  = row[1] or _DEFAULT_API_KEY
            defaults["enabled"]  = bool(row[2])
            defaults["firmaadi"] = row[3] or ""
    except Exception as e:
        logger.warning("webadmin_sirket_config okunamadı: %s", e)
    return defaults


# Geriye dönük uyumluluk — eski çağrılar için
def _load_client_config() -> dict:
    return {
        "base_url": _DEFAULT_BASE_URL,
        "api_key":  _DEFAULT_API_KEY,
        "timeout":  60,
        "enabled":  True,
    }


class WebAdminClient:
    """
    webadmin-nakitAkim REST API istemcisi.

    Tüm metodlar senkron çalışır — QThread içinde veya arka planda kullanın.

    API Key kullanımı:
      - nakitAkim her istekte X-API-Key header'ı ile gönderir
      - webadmin bu key'i config.py'deki WEBADMIN_API_KEY ile karşılaştırır
      - Eşleşmezse HTTP 401 döner
      - Key, webadmin_sirket_config tablosunda şirket bazında saklanır
    """

    def __init__(self,
                 userid:   Optional[int] = None,
                 base_url: Optional[str] = None,
                 api_key:  Optional[str] = None,
                 timeout:  int = 60):
        # Dışarıdan geçirilmişse direkt kullan
        # Geçirilmemişse DB'den şirket bazlı oku
        if base_url and api_key:
            self.base_url = base_url.rstrip("/")
            self.api_key  = api_key
        elif userid is not None:
            cfg = get_webadmin_config(userid)
            self.base_url = (base_url or cfg["base_url"]).rstrip("/")
            self.api_key  = api_key  or cfg["api_key"]
        else:
            # Fallback: eski varsayılanlar
            cfg = _load_client_config()
            self.base_url = (base_url or cfg["base_url"]).rstrip("/")
            self.api_key  = api_key  or cfg["api_key"]
        self.timeout = timeout

    # ── Ortak istek yardımcısı ────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {
            "X-API-Key":    self.api_key,
            "Content-Type": "application/json",
            "Accept":       "application/json",
        }

    def _post(self, endpoint: str, body: dict) -> dict:
        import requests
        url = f"{self.base_url}{endpoint}"
        try:
            resp = requests.post(url, json=body, headers=self._headers(), timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": f"webadmin sunucusuna bağlanılamadı ({self.base_url}). Sunucunun çalıştığından emin olun."}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "İstek zaman aşımına uğradı."}
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                return {"success": False, "error": "Geçersiz API Key. webadmin config.py dosyasını kontrol edin."}
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error("webadmin POST hatası [%s]: %s", endpoint, e)
            return {"success": False, "error": str(e)}

    def _get(self, endpoint: str, params: dict = None) -> dict:
        import requests
        url = f"{self.base_url}{endpoint}"
        try:
            resp = requests.get(url, params=params, headers=self._headers(), timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": f"webadmin sunucusuna bağlanılamadı ({self.base_url})."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Ana metodlar ──────────────────────────────────────────────────────────

    def sync_womsis(self,
                    userid:     int  = 1,
                    start_date: Optional[str] = None,
                    end_date:   Optional[str] = None) -> dict:
        """
        webadmin'e POST /api/womsis/sync isteği gönderir.
        webadmin Womsis API'den tüm hareketleri çekip JSON olarak döner.

        Parametreler:
            userid:     nakitAkim kullanıcı ID (default: 1)
            start_date: "YYYY-MM-DD" formatında, default: 30 gün önce
            end_date:   "YYYY-MM-DD" formatında, default: bugün

        Dönüş:
            {
              "success": True,
              "count": 42,
              "transactions": [...],
              "timestamp": "2024-06-09T12:00:00",
              "period": {"start": "...", "end": "..."}
            }
        """
        body: dict = {"userid": userid}
        if start_date:
            body["start_date"] = start_date
        if end_date:
            body["end_date"] = end_date
        return self._post("/api/womsis/sync", body)

    def test_connection(self, userid: int = 1) -> dict:
        """
        webadmin aracılığıyla Womsis bağlantısını test eder.
        POST /api/womsis/test
        """
        return self._post("/api/womsis/test", {"userid": userid})

    def get_sync_status(self) -> dict:
        """
        Son sync durumunu getirir (veri yok, sadece meta).
        GET /api/womsis/status
        """
        return self._get("/api/womsis/status")

    def get_accounts(self, userid: int = 1) -> dict:
        """
        Womsis hesap listesini getirir.
        GET /api/womsis/accounts
        """
        return self._get("/api/womsis/accounts", {"userid": userid})

    def ping(self) -> bool:
        """webadmin sunucusunun erişilebilir olduğunu kontrol eder."""
        try:
            import requests
            resp = requests.get(f"{self.base_url}/", timeout=5)
            return resp.status_code in (200, 302, 404)
        except Exception:
            return False


# ── PyQt6 QThread Worker ──────────────────────────────────────────────────────

try:
    from PyQt6.QtCore import QThread, pyqtSignal

    class WebAdminSyncWorker(QThread):
        """
        nakitAkim'deki diğer Worker sınıflarıyla uyumlu QThread.
        UI'yi bloklamadan webadmin REST API'yi çağırır.

        Kullanım örneği (ayarlar_screen.py veya herhangi bir ekrandan):

            self._webadmin_worker = WebAdminSyncWorker(
                userid=self.userid,
                start_date="2024-01-01",
                end_date="2024-12-31"
            )
            self._webadmin_worker.progress.connect(self._on_progress)
            self._webadmin_worker.finished.connect(self._on_done)
            self._webadmin_worker.start()
        """
        progress = pyqtSignal(str)   # durum mesajı
        finished = pyqtSignal(dict)  # {'success': bool, 'count': int, 'transactions': [...]}

        def __init__(self,
                     userid:     int  = 1,
                     start_date: Optional[str] = None,
                     end_date:   Optional[str] = None,
                     base_url:   Optional[str] = None,
                     api_key:    Optional[str] = None):
            super().__init__()
            self._userid     = userid
            self._start_date = start_date
            self._end_date   = end_date
            self._base_url   = base_url
            self._api_key    = api_key

        def run(self):
            # ── Şirket bazlı config'i DB'den oku ────────────────────────────
            cfg = get_webadmin_config(self._userid)

            # Dışarıdan geçirilen base_url/api_key varsa onları kullan (override)
            base_url = self._base_url or cfg.get("base_url")
            api_key  = self._api_key  or cfg.get("api_key")

            if not cfg.get("enabled") and not self._base_url:
                self.finished.emit({
                    "success":      False,
                    "error_code":   "webadmin_not_configured",
                    "error":        "Bu şirket için webadmin bağlantısı tanımlanmamış.\n"
                                    "Yöneticinizle iletişime geçin.",
                    "count":        0,
                    "inserted":     0,
                    "skipped":      0,
                    "transactions": []
                })
                return

            client = WebAdminClient(base_url=base_url, api_key=api_key)
            firma = cfg.get("firmaadi") or f"userid={self._userid}"
            self.progress.emit(f"🌐  [{firma}] webadmin sunucusuna bağlanılıyor...")

            if not client.ping():
                self.finished.emit({
                    "success": False,
                    "error": f"webadmin sunucusuna ulaşılamadı ({client.base_url}).\n"
                             "Lütfen 'python3 app.py' ile webadmin'i başlatın.",
                    "count": 0,
                    "inserted": 0,
                    "skipped": 0,
                    "transactions": []
                })
                return

            # ── 1. webadmin REST API'den Womsis verilerini çek ────────────────
            self.progress.emit("📡  Womsis verileri webadmin üzerinden çekiliyor...")
            result = client.sync_womsis(
                userid=self._userid,
                start_date=self._start_date,
                end_date=self._end_date
            )

            if not result.get("success"):
                # ── Şirket profili kontrolü ───────────────────────────────────
                if result.get("error_code") == "no_sirket_profili":
                    self.finished.emit({
                        "success":      False,
                        "error_code":   "no_sirket_profili",
                        "error":        "Önce iqDenetim üzerinden kullanıcı tanımının yapılması gerekir.\n"
                                        "Şirket profili tanımlanmadan Womsis verisi çekilemez.",
                        "count":        0,
                        "inserted":     0,
                        "skipped":      0,
                        "transactions": []
                    })
                    return

                err = result.get("error") or result.get("message") or "Bilinmeyen hata"
                self.finished.emit({
                    "success":      False,
                    "error":        err,
                    "count":        0,
                    "inserted":     0,
                    "skipped":      0,
                    "transactions": []
                })
                return

            transactions = result.get("transactions", [])
            fetched = len(transactions)
            self.progress.emit(f"✅  {fetched} işlem çekildi. Veritabanı kontrol ediliyor...")

            # ── 2. nakitAkim DB'ye yaz — womsiskey ile mükerrer kontrol ───────
            from db.database import get_connection

            inserted = 0
            skipped  = 0
            conn = get_connection()
            try:
                for tx in transactions:
                    # Alan eşlemeleri (VomsisIsleWorker ile birebir aynı)
                    tarih_raw  = tx.get("date") or tx.get("processDate") or ""
                    aciklama   = tx.get("description") or tx.get("explanation") or ""
                    tutar_raw  = tx.get("amount") or tx.get("tryAmount") or 0
                    try:
                        tutar = float(str(tutar_raw).replace(",", "."))
                    except (ValueError, TypeError):
                        tutar = 0.0
                    yon         = tx.get("direction") or tx.get("transactionDirection") or ""
                    gelir_gider = "gelir" if str(yon).upper() in ("CREDIT", "ALACAK", "+") else "gider"
                    vomsis_key  = str(tx.get("id") or tx.get("transactionId") or "").strip()

                    # ── Mükerrer kayıt kontrolü ──────────────────────────────
                    if vomsis_key:
                        exists = conn.execute(
                            "SELECT id FROM hareketler WHERE womsiskey=? AND userid=? LIMIT 1",
                            (vomsis_key, self._userid)
                        ).fetchone()
                        if exists:
                            skipped += 1
                            continue   # Zaten var → atla

                    # ── DB'ye ekle ────────────────────────────────────────────
                    conn.execute(
                        """INSERT INTO hareketler
                           (tarih, aciklama, gelirgider, alinan_tutar1, kaynak, womsiskey, userid)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (tarih_raw, aciklama, gelir_gider, tutar,
                         "vomsis_webadmin", vomsis_key, self._userid)
                    )
                    inserted += 1

                    if inserted % 20 == 0:
                        self.progress.emit(f"💾  {inserted} kayıt eklendi, {skipped} atlandı...")

                conn.commit()
            except Exception as exc:
                conn.rollback()
                self.finished.emit({
                    "success": False,
                    "error": f"DB yazma hatası: {exc}",
                    "count": fetched,
                    "inserted": inserted,
                    "skipped": skipped,
                    "transactions": transactions
                })
                return
            finally:
                conn.close()

            msg = f"{inserted} yeni kayıt eklendi"
            if skipped:
                msg += f", {skipped} mevcut kayıt atlandı"
            msg += f" (webadmin, toplam {fetched} çekildi)"

            self.finished.emit({
                "success":      True,
                "message":      msg,
                "count":        fetched,
                "inserted":     inserted,
                "skipped":      skipped,
                "transactions": transactions
            })

except ImportError:
    # PyQt6 yoksa (örn. test ortamında) Worker sınıfı tanımlanmaz
    pass
