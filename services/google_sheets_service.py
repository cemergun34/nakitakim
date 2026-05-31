"""
google_sheets_service.py
────────────────────────────────────────────────────────────────
PHP: ajax/google_sheets_aktar.php  +  ajax/googleKasaisle.php

Kasa, Gider ve Genel Hesap Google Sheets verilerini CSV olarak
indirip genel_hesap_hareketleri tablosuna aktarır.

- gspread / API key GEREKMİYOR — sheet'ler "herkese açık" CSV URL
- Kaynak seçimi: 'kasa', 'gider', 'genelHesap' (veya hepsi)
- PostgreSQL: execute_values (toplu INSERT, ~10x hızlı)
- SQLite: executemany
────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import csv
import io
import re
import datetime
import urllib.request
import urllib.error
from typing import Callable, Optional

from db.database import get_connection


# ── Sheet URL'leri runtime'da config'den okunur ──────────────────────────────
# (Bkz. services/gsheets_config_service.py)

def _build_urls(cfg: dict) -> tuple[str, str, str]:
    """Config'deki sheet ID'lerinden CSV URL'lerini üretir."""
    kasa_id   = cfg.get("kasa_sheet_id", "")
    kasa_tab  = cfg.get("kasa_tab_name", "Kasa")
    gider_id  = cfg.get("gider_sheet_id", "")
    genel_id  = cfg.get("genel_hesap_sheet_id", "")

    kasa_url   = (f"https://docs.google.com/spreadsheets/d/{kasa_id}"
                  f"/gviz/tq?tqx=out:csv&sheet={kasa_tab}")
    gider_tpl  = (f"https://docs.google.com/spreadsheets/d/{gider_id}"
                  "/export?format=csv&sheet={year}")
    genel_url  = (f"https://docs.google.com/spreadsheets/d/{genel_id}"
                  "/export?format=csv")
    return kasa_url, gider_tpl, genel_url


# HTTP indirme zaman aşımı (saniye)
_TIMEOUT = 20


# ── Yardımcılar ──────────────────────────────────────────────────────────────

def _csv_download(url: str, label: str = "") -> str:
    """
    HTTP GET → CSV metin (BOM temizlenmiş).
    Arka plan QThread'i içinde çalışır — UI'yi bloke etmez.
    timeout=20s: Google yavaş yanıt verirse 20 sn bekler, sonra RuntimeError.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; NakitAkim/1.0)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        tag = f" [{label}]" if label else ""
        raise RuntimeError(f"HTTP {e.code}{tag} — Google Sheet indirilemedi.")
    except urllib.error.URLError as e:
        tag = f" [{label}]" if label else ""
        raise RuntimeError(f"Bağlantı hatası{tag}: {e.reason}")
    except Exception as e:
        raise RuntimeError(f"İndirme hatası: {e}")

    # Encoding tespiti
    for enc in ("utf-8-sig", "utf-8", "iso-8859-9"):
        try:
            return raw.decode(enc).lstrip("\ufeff")
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace").lstrip("\ufeff")


def _csv_parse(raw: str) -> list[list[str]]:
    """CSV metin → 2B liste (tamamen boş satırlar atılır)."""
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    reader = csv.reader(io.StringIO(raw))
    rows = []
    for row in reader:
        if any(c.strip() for c in row):
            rows.append(row)
    return rows


def _parse_float(val: str) -> float:
    """PHP parseFloat() karşılığı — Türkçe/Avrupa ve İngilizce sayı formatları."""
    val = val.strip().replace("TL", "").replace("₺", "").replace('"', "")
    val = val.replace("\xa0", "").replace("\u202f", "").strip()
    last_comma = val.rfind(",")
    last_dot   = val.rfind(".")
    if last_comma != -1 and (last_dot == -1 or last_comma > last_dot):
        val = val.replace(".", "").replace(",", ".")
    elif last_dot != -1 and (last_comma == -1 or last_dot > last_comma):
        val = val.replace(",", "")
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return 0.0


def _normalize_tarih(raw: str) -> Optional[datetime.date]:
    """DD.MM.YYYY, DD-MM-YYYY veya YYYY-MM-DD → date nesnesi."""
    raw = raw.strip()
    m = re.match(r'^(\d{1,2})[.\-](\d{1,2})[.\-](\d{4})$', raw)
    if m:
        return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.match(r'^(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})$', raw)
    if m:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _in_range(tarih_str: str, bas: datetime.date, bit: datetime.date) -> bool:
    d = _normalize_tarih(tarih_str)
    if d is None:
        return False
    return bas <= d <= bit


def _tarih_date(tarih: str) -> str:
    """tarih string → YYYY-MM-DD string (DB için)."""
    dt = _normalize_tarih(tarih)
    return dt.strftime("%Y-%m-%d") if dt else tarih


# ── Alt hesap kodu eşleştirme (önbellekli, thread-local safe) ─────────────────

_alt_hesap_cache: dict[str, Optional[int]] = {}


def _alt_hesap_id(conn, ack: str, userid: int) -> Optional[int]:
    ack = ack.strip()
    if not ack:
        return None
    key = f"{userid}:{ack}"
    if key in _alt_hesap_cache:
        return _alt_hesap_cache[key]
    try:
        row = conn.execute(
            "SELECT id FROM althesapkodu WHERE aciklama = ? AND userid = ? LIMIT 1",
            (ack, userid)
        ).fetchone()
        result = int(row["id"]) if row else None
    except Exception:
        result = None
    _alt_hesap_cache[key] = result
    return result


# ── INSERT SQL (ortak) ───────────────────────────────────────────────────────

_INSERT_SQL = """
    INSERT INTO genel_hesap_hareketleri
       (tarih, tarih_date, form_id, sube, kategori,
        teslim_sekli, teslim_sekli_id, aciklama, odeme_sekli,
        gelir, gider, nerden_geliyor,
        alt_hesap_kodu_id, userid, musteri_no, kayit_tarihi)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""


def _bulk_insert(conn, batch: list) -> None:
    """
    Toplu INSERT — PostgreSQL için psycopg2.extras.execute_values
    (tek seferde tüm satırları gönderir, ~10x hızlı).
    SQLite için standart executemany kullanılır.
    """
    if not batch:
        return
    try:
        # PostgreSQL modu: _PgWrapper._conn üzerinden execute_values
        from psycopg2.extras import execute_values as _ev
        from db.database import _to_pg_sql
        pg_sql = _to_pg_sql(_INSERT_SQL).strip()
        # execute_values VALUES kısmını tek seferde gönderir
        raw_conn = conn._conn          # gerçek psycopg2 bağlantısı
        cur = raw_conn.cursor()
        _ev(cur, pg_sql, batch, page_size=500)
        cur.close()
    except (AttributeError, ImportError, Exception):
        # SQLite veya psycopg2 yok — standart executemany
        conn.executemany(_INSERT_SQL, batch)


# ── Ana aktarım fonksiyonu ────────────────────────────────────────────────────

def google_sheets_aktar(
    userid: int,
    musterino: Optional[int],
    bas_tarih: datetime.date,
    bit_tarih: datetime.date,
    kaynaklar: Optional[list[str]] = None,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    PHP google_sheets_aktar.php'nin Python karşılığı.

    kaynaklar: ['kasa', 'gider', 'genelHesap'] — None ise hepsi işlenir.
    Döndürür: { success, message, eklenen, atlanan, hatalar }

    ⚠️  Bu fonksiyon bir QThread.run() içinden çağrılır.
        UI thread'ini bloke etmez.
    """
    if kaynaklar is None:
        kaynaklar = ["kasa", "gider", "genelHesap"]

    # ── Sheet URL'lerini config'den al ─────────────────────────────────────────
    from services.gsheets_config_service import load_config
    cfg = load_config()
    _KASA_URL, _GIDER_URL_TPL, _GENEL_URL = _build_urls(cfg)

    if not cfg.get("kasa_sheet_id") or not cfg.get("gider_sheet_id") or not cfg.get("genel_hesap_sheet_id"):
        return {"success": False,
                "message": "Google Sheets ID'leri tanımlanmamış. Lütfen Eklentiler → Google Sheets Ayarları bölümünden sheet bilgilerini girin.",
                "eklenen": 0, "atlanan": 0, "hatalar": []}

    def emit(msg: str):
        if progress_cb:
            progress_cb(msg)

    toplam_eklenen = 0
    hatalar: list[str] = []
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        # ── Eski kayıtları temizle ────────────────────────────────────────────
        if kaynaklar:
            placeholders = ",".join(["?" for _ in kaynaklar])
            conn.execute(
                f"""DELETE FROM genel_hesap_hareketleri
                    WHERE userid=? AND musteri_no=?
                    AND tarih_date >= ? AND tarih_date <= ?
                    AND nerden_geliyor IN ({placeholders})""",
                [userid, musterino,
                 bas_tarih.strftime("%Y-%m-%d"),
                 bit_tarih.strftime("%Y-%m-%d"),
                 *kaynaklar]
            )
            conn.commit()
            emit(f"🗑️  {bas_tarih} — {bit_tarih} aralığındaki eski kayıtlar temizlendi.")

        # ─────────────────────────────────────────────────────────────────────
        # 1) KASA
        # Şema: [0]Tarih [1]FormID [2]Şube [3]Kategori [4]Gelir [5]TeslimŞekli [6]İade
        # ─────────────────────────────────────────────────────────────────────
        if "kasa" in kaynaklar:
            emit("📥  KASA — Google Sheet indiriliyor...")
            try:
                csv_raw = _csv_download(_KASA_URL, "Kasa")
                rows    = _csv_parse(csv_raw)
                emit(f"📊  KASA — {len(rows)-1} satır okundu, filtreleniyor...")

                batch = []
                for row in rows[1:]:           # satır 0 başlık
                    tarih = (row[0] if len(row) > 0 else "").strip()
                    if not tarih or not _in_range(tarih, bas_tarih, bit_tarih):
                        continue
                    gelir_raw = (row[4] if len(row) > 4 else "").strip()
                    if not gelir_raw:
                        continue
                    gelir   = _parse_float(gelir_raw) or None
                    iade_r  = (row[6] if len(row) > 6 else "").strip()
                    gider   = _parse_float(iade_r) or None
                    form_id = (row[1] if len(row) > 1 else "").strip()
                    kat     = (row[3] if len(row) > 3 else "").strip()
                    batch.append((
                        tarih, _tarih_date(tarih), form_id, "Merkez", kat,
                        None, None, None, "Nakit",
                        gelir, gider, "kasa",
                        None, userid, musterino, now_str
                    ))

                if batch:
                    _bulk_insert(conn, batch)
                    conn.commit()
                toplam_eklenen += len(batch)
                emit(f"✅  KASA: {len(batch)} kayıt eklendi.")
            except Exception as exc:
                hatalar.append(f"KASA: {exc}")
                emit(f"❌  KASA hatası: {exc}")

        # ─────────────────────────────────────────────────────────────────────
        # 2) GİDER
        # Şema: [0]Tarih [1]? [2]OdemeSekli [3]Tutar [4]Açıklama [5]FormID
        # Tab adı = yıl (örn: "2025")
        # ─────────────────────────────────────────────────────────────────────
        if "gider" in kaynaklar:
            yillar = list(range(bas_tarih.year, bit_tarih.year + 1))
            for yil in yillar:
                emit(f"📥  GİDER {yil} — Google Sheet indiriliyor...")
                try:
                    url     = _GIDER_URL_TPL.format(year=yil)
                    csv_raw = _csv_download(url, f"Gider-{yil}")
                    rows    = _csv_parse(csv_raw)
                    emit(f"📊  GİDER {yil} — {len(rows)-1} satır okundu, filtreleniyor...")

                    batch = []
                    for row in rows[1:]:
                        tarih = (row[0] if len(row) > 0 else "").strip()
                        if not tarih or not _in_range(tarih, bas_tarih, bit_tarih):
                            continue
                        gider_raw = (row[3] if len(row) > 3 else "").strip()
                        if not gider_raw:
                            continue
                        gider_val = _parse_float(gider_raw) or None
                        ack       = (row[4] if len(row) > 4 else "").strip()
                        form_id   = (row[5] if len(row) > 5 else "").strip()
                        odeme_raw = (row[2] if len(row) > 2 else "").strip()
                        odeme     = "Nakit" if (not odeme_raw or odeme_raw == "Nakit") else "Kredi Kartı"
                        alt_id    = _alt_hesap_id(conn, ack, userid)
                        batch.append((
                            tarih, _tarih_date(tarih), form_id, "Merkez", None,
                            None, None, ack, odeme,
                            None, gider_val, "gider",
                            alt_id, userid, musterino, now_str
                        ))

                    if batch:
                        _bulk_insert(conn, batch)
                        conn.commit()
                    toplam_eklenen += len(batch)
                    emit(f"✅  GİDER {yil}: {len(batch)} kayıt eklendi.")
                except Exception as exc:
                    hatalar.append(f"GİDER({yil}): {exc}")
                    emit(f"❌  GİDER({yil}) hatası: {exc}")

        # ─────────────────────────────────────────────────────────────────────
        # 3) GENEL HESAP
        # Dinamik başlıklar: "Alınan Tutar"=gelir, "Tutar"=gider
        # ─────────────────────────────────────────────────────────────────────
        if "genelHesap" in kaynaklar:
            emit("📥  GENEL HESAP — Google Sheet indiriliyor...")
            try:
                csv_raw = _csv_download(_GENEL_URL, "GenelHesap")
                rows    = _csv_parse(csv_raw)

                if not rows:
                    raise RuntimeError("Genel Hesap sheet boş geldi.")

                emit(f"📊  GENEL HESAP — {len(rows)-1} satır okundu, başlıklar analiz ediliyor...")

                # Başlıkları dinamik bul
                headers      = rows[0]
                alinan_cols: list[int] = []
                gider_col    = -1
                teslim_col   = -1

                for c, h in enumerate(headers):
                    h = h.strip()
                    if "Alınan Tutar" in h or "alinan tutar" in h.lower():
                        alinan_cols.append(c)
                    elif h.lower() == "tutar":
                        gider_col = c
                    elif "teslim" in h.lower() and "şekl" in h.lower():
                        teslim_col = c

                batch = []
                for row in rows[1:]:
                    tarih = (row[0] if len(row) > 0 else "").strip()
                    if (not tarih
                            or tarih.lower() == "tarih"
                            or tarih == "Toplam"
                            or not _in_range(tarih, bas_tarih, bit_tarih)):
                        continue

                    form_id = (row[1] if len(row) > 1 else "").strip()
                    sube    = (row[2] if len(row) > 2 else "").strip()
                    kat     = (row[3] if len(row) > 3 else "").strip()
                    ack     = (row[4] if len(row) > 4 else "").strip()
                    teslim  = (row[teslim_col] if teslim_col != -1 and len(row) > teslim_col else "").strip()
                    alt_id  = _alt_hesap_id(conn, ack, userid) or _alt_hesap_id(conn, kat, userid)
                    td      = _tarih_date(tarih)

                    # Gelir satırları
                    for col in alinan_cols:
                        gelir_val = _parse_float((row[col] if len(row) > col else "").strip())
                        if gelir_val <= 0:
                            continue
                        odeme = (row[col - 1] if col > 0 and len(row) > col - 1 else "").strip()
                        batch.append((
                            tarih, td, form_id, sube, kat,
                            teslim or None, None, ack, odeme,
                            gelir_val, None, "genelHesap",
                            alt_id, userid, musterino, now_str
                        ))

                    # Gider satırı
                    if gider_col != -1:
                        gider_val = _parse_float((row[gider_col] if len(row) > gider_col else "").strip())
                        if gider_val > 0:
                            odeme = (row[gider_col + 1] if len(row) > gider_col + 1 else "").strip()
                            batch.append((
                                tarih, td, form_id, sube, kat,
                                teslim or None, None, ack, odeme,
                                None, gider_val, "genelHesap",
                                alt_id, userid, musterino, now_str
                            ))

                if batch:
                    emit(f"⏳  GENEL HESAP — {len(batch)} kayıt veritabanına yazılıyor...")
                    _bulk_insert(conn, batch)
                    conn.commit()
                toplam_eklenen += len(batch)
                emit(f"✅  GENEL HESAP: {len(batch)} kayıt eklendi.")
            except Exception as exc:
                hatalar.append(f"GENEL HESAP: {exc}")
                emit(f"❌  GENEL HESAP hatası: {exc}")

    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "message": str(exc), "eklenen": 0, "atlanan": 0, "hatalar": [str(exc)]}
    finally:
        try:
            conn.close()
        except Exception:
            pass

    msg = (f"İşlem tamamlandı. {toplam_eklenen} kayıt eklendi.")
    if hatalar:
        msg += f" ({len(hatalar)} hata oluştu)"

    return {
        "success": True,
        "message": msg,
        "eklenen": toplam_eklenen,
        "atlanan": 0,
        "hatalar": hatalar,
    }
