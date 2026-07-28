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
import ssl
import urllib.request
import urllib.error
from typing import Callable, Optional


def _ssl_context() -> ssl.SSLContext:
    """
    macOS'ta Python'un varsayılan CA deposu boş olabilir (cafile=None).
    certifi kütüphanesi varsa onun CA paketini kullan; yoksa doğrulama kapalı fallback.
    """
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
        return ctx
    except ImportError:
        pass
    except Exception:
        pass
    # Fallback: sertifika doğrulamasını kapat (certifi yoksa)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

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
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_ssl_context()) as resp:
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
    Toplu INSERT — PostgreSQL icin psycopg2.extras.execute_values
    (tek seferde tum satirlari gonderir, ~10x hizli).
    SQLite icin standart executemany kullanilir.

    NOT: Mukerrer engeli 'sil+yeniden yukle' yontemiyle saglanir:
    google_sheets_aktar() once DELETE ile aralik temizler, sonra INSERT yapar.
    Tabloda unique constraint olmadigi icin ON CONFLICT DO NOTHING etkisizdir.
    """
    if not batch:
        return

    # execute_values, VALUES kisminda tek bir %s placeholder bekler.
    _EV_SQL = (
        "INSERT INTO genel_hesap_hareketleri "
        "(tarih, tarih_date, form_id, sube, kategori, "
        "teslim_sekli, teslim_sekli_id, aciklama, odeme_sekli, "
        "gelir, gider, nerden_geliyor, "
        "alt_hesap_kodu_id, userid, musteri_no, kayit_tarihi) "
        "VALUES %s"
    )

    try:
        from psycopg2.extras import execute_values as _ev
        raw_conn = conn._conn          # gercek psycopg2 baglantisi
        cur = raw_conn.cursor()
        _ev(cur, _EV_SQL, batch, page_size=500)
        cur.close()
    except (AttributeError, ImportError):
        # SQLite modu — standart executemany
        conn.executemany(_INSERT_SQL, batch)
    except Exception:
        # psycopg2 execute_values basarisiz → satir satir fallback
        try:
            raw_conn = conn._conn
            cur = raw_conn.cursor()
            pg_sql = (
                "INSERT INTO genel_hesap_hareketleri "
                "(tarih, tarih_date, form_id, sube, kategori, "
                "teslim_sekli, teslim_sekli_id, aciklama, odeme_sekli, "
                "gelir, gider, nerden_geliyor, "
                "alt_hesap_kodu_id, userid, musteri_no, kayit_tarihi) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            )
            cur.executemany(pg_sql, batch)
            cur.close()
        except Exception:
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
        # ── Eski kayıtları temizle (sil+yeniden yükle yöntemi) ───────────────
        # Tabloda unique constraint olmadığından mükerrer engeli DELETE ile sağlanır:
        # seçili tarih aralığı + kaynak türlerine göre eski kayıtlar silindi,
        # ardından Google Sheets'ten taze veri eklenir.
        if kaynaklar:
            placeholders = ",".join(["?" for _ in kaynaklar])
            del_result = conn.execute(
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
            silinen = getattr(del_result, 'rowcount', '?')
            emit(f"🗑️  {bas_tarih} — {bit_tarih} aralığındaki {silinen} eski kayıt temizlendi.")

        # ─────────────────────────────────────────────────────────────────────
        # 1) KASA
        # Google Sheet şeması: [0]Tarih [1]FormID [2]Şube [3]Kategori [4]Gelir(₺) [5]TeslimŞekli [6]İade(₺)
        # Satır 0: başlık (boş/özet), Satır 1: toplam özeti satırı → ikisi atlanır (rows[2:])
        # ─────────────────────────────────────────────────────────────────────
        if "kasa" in kaynaklar:
            emit("📥  KASA — Google Sheet indiriliyor...")
            try:
                csv_raw = _csv_download(_KASA_URL, "Kasa")
                rows    = _csv_parse(csv_raw)
                emit(f"📊  KASA — {len(rows)-2} satır okundu, filtreleniyor...")

                batch = []
                for row in rows[2:]:           # satır 0=başlık, satır 1=toplam özeti → atla
                    tarih = (row[0] if len(row) > 0 else "").strip()
                    if not tarih or not _in_range(tarih, bas_tarih, bit_tarih):
                        continue
                    gelir_raw = (row[4] if len(row) > 4 else "").strip()
                    iade_r    = (row[6] if len(row) > 6 else "").strip()

                    gelir = _parse_float(gelir_raw) or None
                    gider = _parse_float(iade_r) or None

                    # En az biri değer içermeli — ikisi de boşsa bu satır atla
                    if not gelir and not gider:
                        continue

                    # form_id: boş / '-' / sadece tire-noise → None kaydet
                    form_raw = (row[1] if len(row) > 1 else "").strip()
                    if form_raw in ("", "-", "—", "None", "nan", "null"):
                        form_id = None
                    else:
                        form_id = form_raw

                    # Şube: sheet'ten oku, yoksa 'Merkez'
                    sube_raw = (row[2] if len(row) > 2 else "").strip()
                    sube = sube_raw if sube_raw and sube_raw not in ("-", "—") else "Merkez"

                    # Kategori
                    kat = (row[3] if len(row) > 3 else "").strip() or None

                    # Teslim şekli: sheet'ten oku (kolon 5)
                    teslim_raw = (row[5] if len(row) > 5 else "").strip()
                    teslim = teslim_raw if teslim_raw and teslim_raw not in ("-", "—") else None



                    batch.append((
                        tarih, _tarih_date(tarih), form_id, sube, kat,
                        teslim, None, None, "Nakit",
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
        # Kolon haritası (Excel/Sheets yapısı):
        #   0:Tarih  1:Form  2:Şube  3:Kategori  4:Açıklama
        #   5:Ödeme Şekli 1  6:Alınan Tutar  7:Ödeme Şekli 2  8:Alınan Tutar
        #   9:Ödeme Şekli 3  10:Alınan Tutar  11:TOPLAM
        #   12:Teslim Şekli  13:Tutar (gider)  14:Ödeme Şekli (gider için)
        #
        # Gelir: alinan_cols (6, 8, 10) → nerden_geliyor='genelHesap'
        # Gider: gider_col (13 "Tutar") → nerden_geliyor='genelHesap'
        #         tüm teslim şekli türleri için (Parça Alımı, Cihaz Alımı, iade vb.)
        # ─────────────────────────────────────────────────────────────────────
        if "genelHesap" in kaynaklar:
            emit("📥  GENEL HESAP — Google Sheet indiriliyor...")
            try:
                csv_raw = _csv_download(_GENEL_URL, "GenelHesap")
                rows    = _csv_parse(csv_raw)

                if not rows:
                    raise RuntimeError("Genel Hesap sheet boş geldi.")

                emit(f"📊  GENEL HESAP — {len(rows)-1} satır okundu, başlıklar analiz ediliyor...")

                # ── Başlıkları dinamik bul ────────────────────────────────────
                headers      = rows[0]
                alinan_cols: list[int] = []
                gider_col    = -1
                teslim_col   = -1
                odeme_sekli_col = -1   # gider satırı için Ödeme Şekli kolonu

                for c, h in enumerate(headers):
                    hn = h.strip().lower()
                    # Alınan Tutar: "alınan tutar" veya "alinan tutar"
                    if "alınan tutar" in hn or "alinan tutar" in hn:
                        alinan_cols.append(c)
                    # Tutar (gider): başlık tam "tutar" (küçük harf)
                    elif hn in ("tutar",):
                        gider_col = c
                        # Sağ komşu Ödeme Şekli ise onu işaretle
                        if c + 1 < len(headers):
                            nxt = headers[c + 1].strip().lower()
                            if "ödeme" in nxt or "odeme" in nxt:
                                odeme_sekli_col = c + 1
                    # Teslim Şekli: hem "teslim" hem "ekl" içermeli,
                    # "ödeme"/"odeme" içermemeli (Ödeme Şekli ile karışmasın)
                    elif ("teslim" in hn and ("şekl" in hn or "sekl" in hn)
                          and "ödeme" not in hn and "odeme" not in hn):
                        teslim_col = c

                emit(
                    f"   Başlıklar → alinan_cols={alinan_cols}, "
                    f"gider_col={gider_col}, teslim_col={teslim_col}, "
                    f"odeme_sekli_col={odeme_sekli_col}"
                )

                batch = []
                for row in rows[1:]:
                    tarih = (row[0] if len(row) > 0 else "").strip()
                    if (not tarih
                            or tarih.lower() == "tarih"
                            or tarih == "Toplam"
                            or not _in_range(tarih, bas_tarih, bit_tarih)):
                        continue

                    # form_id: float → int → str (veya string olduğu gibi)
                    form_raw = (row[1] if len(row) > 1 else "").strip()
                    if not form_raw or form_raw in ("-", "—", "None", "nan"):
                        form_id = None
                    else:
                        try:
                            form_id = str(int(float(form_raw)))
                        except (ValueError, TypeError):
                            form_id = form_raw

                    sube   = (row[2] if len(row) > 2 else "").strip() or "Merkez"
                    kat    = (row[3] if len(row) > 3 else "").strip() or None
                    ack    = (row[4] if len(row) > 4 else "").strip() or None
                    teslim = (row[teslim_col] if teslim_col != -1 and len(row) > teslim_col
                              else "").strip() or None
                    alt_id = _alt_hesap_id(conn, ack or "", userid) or _alt_hesap_id(conn, kat or "", userid)
                    td     = _tarih_date(tarih)

                    # ── Gelir satırları (Alınan Tutar kolonları) ──────────────
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

                    # ── Gider satırı (Tutar kolonu) ───────────────────────────
                    if gider_col != -1:
                        gider_val = _parse_float((row[gider_col] if len(row) > gider_col else "").strip())
                        if gider_val > 0:
                            if odeme_sekli_col != -1 and len(row) > odeme_sekli_col:
                                odeme_g = (row[odeme_sekli_col] or "").strip() or None
                            elif len(row) > gider_col + 1:
                                odeme_g = (row[gider_col + 1] or "").strip() or None
                            else:
                                odeme_g = None
                            batch.append((
                                tarih, td, form_id, sube, kat,
                                teslim, None, ack, odeme_g,
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
