# -*- coding: utf-8 -*-
"""
Kredi Kartı Servisi — PyQt6 backend
PHP ayarlar.php → Eklentiler → Kredi Kartı bölümünün karşılığı.

PHP kaynaklar:
  ajax/nakit/nocache.php                    → get_kart_listesi()
  ajax/dosya/krediKartVeriAktar.php         → yukle_csv_yapıkredi()
  ajax/dosya/krediKartVeriAktarPdf.php      → yukle_pdf_isbank()
  ajax/dosya/krediKartVeriAktarPdfYK.php    → yukle_pdf_yapıkredi()

DB Tabloları:
  key_kartlari   — kart tanımları (kullanıcıya ait kayıtlı kartlar)
  kredikartidata — aktarılan banka ekstreleri
"""
from __future__ import annotations

import csv
import io
import os
import re
import secrets
import string
import sys
from pathlib import Path
from typing import Optional

import chardet

from db.database import get_connection

# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı: random anahtar (PHP generateRandomString karşılığı)
# ─────────────────────────────────────────────────────────────────────────────

def _random_key(length: int = 12) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length)) + "kart"


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı: Türkçe tutar string'ini float'a çevir
# ─────────────────────────────────────────────────────────────────────────────

def _tr_float(val: str) -> Optional[float]:
    """'1.250,50' → 1250.50  |  '-300,00' → -300.0"""
    if not val:
        return None
    val = str(val).strip().replace("−", "-").replace("\u2212", "-").replace("+", "")
    val = val.replace(".", "").replace(",", ".")
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Kart Listesi (PHP nocache.php → SELECT * FROM key_kartlari)
# ─────────────────────────────────────────────────────────────────────────────

def get_kart_listesi(userid: int, musterino: int = 1) -> dict:
    """
    Kullanıcıya ait kayıtlı kredi kartı tanımlarını döndürür.
    PHP: ajax/nakit/nocache.php → SELECT * FROM key_kartlari
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, banka, no, tag, hesapkodu, bankaadi, iban "
            "FROM key_kartlari WHERE userid = %s AND (musterino = %s OR musterino IS NULL) ORDER BY bankaadi, banka",
            (userid, musterino)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # camelCase aliasları da ekle (UI uyumu için)
            d["hesapKodu"] = d.get("hesapkodu", "")
            d["bankaAdi"]  = d.get("bankaadi", "")
            d["tag"]       = d.get("tag", "")
            result.append(d)
        return {"success": True, "data": result}
    except Exception as exc:
        return {"success": False, "message": str(exc), "data": []}
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# CSV — YapıKredi Formatı (PHP krediKartVeriAktar.php)
# ─────────────────────────────────────────────────────────────────────────────

def yukle_csv_yapıkredi(
    userid: int,
    musterino: int,
    dosya_yolu: str,
    hesap_kodu: str,
    banka_adi: str,
) -> dict:
    """
    YapıKredi CSV formatındaki banka ekstresini parse ederek
    kredikartidata tablosuna kaydeder.

    CSV sütun sırası (PHP ile birebir):
        İşlem Tarihi(0) | İşlemler(1) | Sektör(2) | Tutar(3) | Kart No(4) | ...

    Mükerrer kontrolü: (userid, tarih, aciklama, alinan_tutar1) üçlüsüne göre.
    """
    try:
        with open(dosya_yolu, "rb") as f:
            raw = f.read()
    except Exception as exc:
        return {"success": False, "errors": f"Dosya okunamadı: {exc}", "added": 0, "skipped": 0}

    # Encoding tespiti (PHP mb_convert_encoding karşılığı)
    detected = chardet.detect(raw)
    enc = detected.get("encoding") or "utf-8"
    try:
        content = raw.decode(enc)
    except Exception:
        try:
            content = raw.decode("windows-1254")
        except Exception:
            content = raw.decode("utf-8", errors="replace")

    # BOM temizle
    content = content.lstrip("\ufeff")

    lines = content.splitlines()
    if not lines:
        return {"success": False, "errors": "Dosya boş.", "added": 0, "skipped": 0}

    # Ayırıcı tespiti (PHP ile aynı mantık)
    limit = min(15, len(lines))
    sc_count = sum(l.count(";") for l in lines[:limit])
    cm_count = sum(l.count(",") for l in lines[:limit])
    sep = ";" if sc_count > cm_count else ","

    baslik_bulundu = False
    basarili = mukerrer = hatali = 0

    conn = get_connection()
    try:
        insert_sql = (
            "INSERT INTO kredikartidata "
            "(userid, musterino, tarih, aciklama, tutar, hesapkodu, alinan_tutar1, banka) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        )
        check_sql = (
            "SELECT COUNT(*) FROM kredikartidata "
            "WHERE userid=%s AND musterino=%s AND tarih=%s AND aciklama=%s AND alinan_tutar1=%s"
        )

        for line in lines:
            # BOM (ilk satır olabilir)
            if line.startswith("\xef\xbb\xbf"):
                line = line[3:]

            data = line.split(sep)

            # Başlık satırını tespit et (PHP: strpos($satirMetni, 'tarih') && 'tutar')
            if not baslik_bulundu:
                joined = sep.join(data).lower()
                if "tarih" in joined and "tutar" in joined:
                    baslik_bulundu = True
                continue  # başlık satırı eklenmez

            if len(data) < 4:
                continue

            islem_tarihi = data[0].strip()
            if not islem_tarihi:
                continue

            islemler = data[1].strip()[:250] if len(data) > 1 else ""

            # PHP: Önceki Dönem / Hesap Özeti / Borcu → atla
            if ("önceki dönem" in islemler.lower()
                    and "hesap özeti" in islemler.lower()
                    and "borcu" in islemler.lower()):
                continue

            tutar_str = data[3].strip().replace("TL", "").replace("tl", "").strip() if len(data) > 3 else ""
            tutar_float = _tr_float(tutar_str) or 0.0
            tutar_str_duzenli = str(tutar_float).replace(".", ",")

            # Mükerrer kontrolü
            mukerrer_sayisi = conn.execute(
                check_sql, (str(userid), str(musterino), islem_tarihi, islemler, tutar_float)
            ).fetchone()[0]
            if mukerrer_sayisi > 0:
                mukerrer += 1
                continue

            try:
                conn.execute(insert_sql, (
                    str(userid), str(musterino),
                    islem_tarihi, islemler,
                    tutar_str_duzenli, hesap_kodu, tutar_float, banka_adi
                ))
                basarili += 1
            except Exception:
                hatali += 1

        if not baslik_bulundu:
            conn.rollback()
            return {
                "success": False,
                "errors": "Dosyada beklenen başlık satırı (İşlem Tarihi, İşlemler vb.) bulunamadı.",
                "added": 0, "skipped": 0,
            }

        conn.commit()
        return {
            "success": True,
            "message": (
                f"YapıKredi CSV: {basarili} kayıt eklendi, "
                f"{mukerrer} mükerrer atlandı"
                + (f", {hatali} hatalı." if hatali else ".")
            ),
            "added": basarili, "skipped": mukerrer,
        }
    except Exception as exc:
        conn.rollback()
        return {"success": False, "errors": f"DB hatası: {exc}", "added": 0, "skipped": 0}
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# PDF — İş Bankası (PHP krediKartVeriAktarPdf.php + isbank_isle.py)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_pdf_isbank(dosya_yolu: str) -> list[dict]:
    """
    isbank_isle.py parse motorunu doğrudan Python olarak çağırır.
    PHP'de exec() ile çalıştırılan scriptin PyQt6 karşılığı.

    Döndürülen liste: [{islem_tarihi, aciklama, tutar_str, tutar, kaynak_dosya}, ...]
    """
    # İş Bankası parse motorunu import et
    sys.path.insert(0, "/Applications/XAMPP/xamppfiles/htdocs/moyTr/dev")
    try:
        import isbank_isle as ib
        import importlib
        importlib.reload(ib)   # Stale cache'e karşı
    except ImportError:
        # PHP'deki gibi fallback: pdfplumber ile basit okuma
        return _parse_pdf_fallback(dosya_yolu, banka="isbank")
    finally:
        if sys.path[0] == "/Applications/XAMPP/xamppfiles/htdocs/moyTr/dev":
            sys.path.pop(0)

    try:
        df = ib.process_pdf(dosya_yolu)
        if df.empty:
            return []
        return df[["islem_tarihi", "aciklama", "tutar_str", "tutar", "kaynak_dosya"]].to_dict(orient="records")
    except Exception:
        return []


def _parse_pdf_yapıkredi(dosya_yolu: str) -> list[dict]:
    """
    yapi_kredi_isle.py parse motorunu doğrudan Python olarak çağırır.
    """
    sys.path.insert(0, "/Applications/XAMPP/xamppfiles/htdocs/moyTr/dev")
    try:
        import yapi_kredi_isle as yk
        import importlib
        importlib.reload(yk)
    except ImportError:
        return _parse_pdf_fallback(dosya_yolu, banka="yapıkredi")
    finally:
        if sys.path[0] == "/Applications/XAMPP/xamppfiles/htdocs/moyTr/dev":
            sys.path.pop(0)

    try:
        data = yk.parse_pdf(dosya_yolu)
        # yapi_kredi_isle returns {tarih, aciklama, tutar_str, tutar, kaynak_dosya}
        # PHP alanları ile eşleştir:
        result = []
        for d in data:
            result.append({
                "islem_tarihi": d.get("tarih", ""),
                "aciklama":     d.get("aciklama", ""),
                "tutar_str":    d.get("tutar_str", ""),
                "tutar":        d.get("tutar", 0.0),
                "kaynak_dosya": d.get("kaynak_dosya", ""),
            })
        return result
    except Exception:
        return []


def _parse_pdf_fallback(dosya_yolu: str, banka: str = "") -> list[dict]:
    """pdfplumber ile basit metin okuma üzerinden parse etmeye çalışır."""
    islemler = []
    try:
        import pdfplumber
        import os
        import re

        kaynak_dosya = os.path.basename(dosya_yolu)

        if banka == "isbank":
            isbank_pattern = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(.+?)\s*(-?\d{1,3}(?:\.\d{3})*(?:,\d+))(?:\s|$)")
            isbank_start_pattern = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(.+?)(?:\s*(-?\d{1,3}(?:\.\d{3})*(?:,\d+))(?:\s|$))?$")

            with pdfplumber.open(dosya_yolu) as pdf:
                pending_date = None
                pending_desc = None

                for page in pdf.pages:
                    text = page.extract_text()
                    if not text:
                        continue

                    for line in text.split('\n'):
                        line = line.strip()
                        if not line:
                            continue

                        if pending_date:
                            amt_match = re.match(r"^(-?\d{1,3}(?:\.\d{3})*(?:,\d+))$", line)
                            if amt_match:
                                tutar_str = amt_match.group(1)
                                tutar = tutar_str.replace('.', '').replace(',', '.')
                                islemler.append({
                                    "islem_tarihi": pending_date,
                                    "aciklama": pending_desc.strip(),
                                    "tutar_str": tutar_str,
                                    "tutar": float(tutar),
                                    "kaynak_dosya": kaynak_dosya
                                })
                                pending_date = pending_desc = None
                                continue
                            else:
                                pending_date = pending_desc = None

                        match = isbank_pattern.search(line)
                        if match:
                            tarih = match.group(1)
                            aciklama = match.group(3).strip()
                            tutar_str = match.group(4)
                            tutar = tutar_str.replace('.', '').replace(',', '.')
                            islemler.append({
                                "islem_tarihi": tarih,
                                "aciklama": aciklama,
                                "tutar_str": tutar_str,
                                "tutar": float(tutar),
                                "kaynak_dosya": kaynak_dosya
                            })
                        else:
                            match_start = isbank_start_pattern.search(line)
                            if match_start and not match_start.group(4):
                                pending_date = match_start.group(1)
                                pending_desc = match_start.group(3)

        elif banka == "yapıkredi":
            # YapıKredi: "17 Aralık 2025  AÇIKLAMA  1.234,56"
            TR_AYLAR = {
                "Ocak": "01", "Şubat": "02", "Mart": "03", "Nisan": "04",
                "Mayıs": "05", "Haziran": "06", "Temmuz": "07", "Ağustos": "08",
                "Eylül": "09", "Ekim": "10", "Kasım": "11", "Aralık": "12",
            }

            def _tr_tarih_cevir(gun: str, ay_str: str, yil: str) -> str:
                ay = TR_AYLAR.get(ay_str, "00")
                return f"{gun.zfill(2)}/{ay}/{yil}"

            # Başlık satırını ve özet satırlarını atlamak için
            SKIP_PATTERNS = re.compile(
                r"(İşlem Tarihi|ÖNCEKI DÖNEM|ÖNCEKİ DÖNEM|DÖNEM BORCU|TOPLAM|PUAN ÖZETİ|"
                r"Alışveriş.*Aylık|Akdi Faiz|Gecikme Faiz|Devreden|Kalan TL|"
                r"Dijital Kart|ABNO|FTNO|İşlem Tutarı|taksidi|TRY|USD Karşılığı)",
                re.IGNORECASE
            )

            # "17 Aralık 2025  AÇIKLAMA  1.234,56  [opsiyonel taksit bilgisi] [opsiyonel puan]"
            yk_pattern = re.compile(
                r"^(\d{1,2})\s+(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+(\d{4})"
                r"\s+(.+?)\s+(\+?-?\d{1,3}(?:\.\d{3})*,\d+)"
                r"(?:\s+[\d.,/]+)*(?:\s+\d+)?$"
            )

            with pdfplumber.open(dosya_yolu) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if not text:
                        continue

                    for line in text.split('\n'):
                        line = line.strip()
                        if not line or SKIP_PATTERNS.search(line):
                            continue

                        match = yk_pattern.match(line)
                        if match:
                            gun, ay_str, yil, aciklama, tutar_raw = match.groups()
                            tarih = _tr_tarih_cevir(gun, ay_str, yil)

                            is_odeme = tutar_raw.startswith("+")
                            tutar_str = tutar_raw.replace('+', '').strip()
                            tutar = tutar_str.replace('.', '').replace(',', '.')
                            try:
                                tutar_float = float(tutar)
                                if is_odeme:
                                    tutar_float = -tutar_float
                            except ValueError:
                                continue

                            islemler.append({
                                "islem_tarihi": tarih,
                                "aciklama": aciklama.strip(),
                                "tutar_str": tutar_str,
                                "tutar": tutar_float,
                                "kaynak_dosya": kaynak_dosya
                            })

    except Exception as e:
        import logging
        logging.error("Fallback parse hatası: %s", e)

    return islemler


def _yukle_pdf_ortak(
    userid: int,
    musterino: int,
    dosya_yolları: list[str],
    hesap_kodu: str,
    banka_adi: str,
    banka_adi_liste: list[str],  # Her dosya için özel banka adı
    is_yapıkredi: bool,
) -> dict:
    """
    Birden fazla PDF dosyasını parse ederek DB'ye kaydeder.
    PHP krediKartVeriAktarPdf.php + krediKartVeriAktarPdfYK.php mantığının birleşimi.
    """
    toplam_basarili = toplam_mukerrer = toplam_hatali = islenen = 0
    hatalar: list[str] = []

    conn = get_connection()
    try:
        insert_sql = (
            "INSERT INTO kredikartidata "
            "(userid, musterino, tarih, aciklama, tutar, alinan_tutar1, hesapkodu, womsiskey, banka) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        check_sql = (
            "SELECT COUNT(*) FROM kredikartidata "
            "WHERE userid=%s AND musterino=%s AND tarih=%s AND alinan_tutar1=%s AND aciklama LIKE %s"
        )

        for idx, dosya_yolu in enumerate(dosya_yolları):
            # İlgili parser ile işlem listesini al
            if is_yapıkredi:
                islemler = _parse_pdf_yapıkredi(dosya_yolu)
            else:
                islemler = _parse_pdf_isbank(dosya_yolu)

            if not islemler:
                hatalar.append(f"{os.path.basename(dosya_yolu)}: İşlem çıkarılamadı.")
                continue

            islenen += 1
            # Dosya için kullanılacak banka adı (PHP bankaAdiList[i] karşılığı)
            dosya_banka_adi = (
                banka_adi_liste[idx] if idx < len(banka_adi_liste) else banka_adi
            ) or banka_adi

            basarili = mukerrer = hatali = 0

            for ism in islemler:
                islem_tarihi  = ism.get("islem_tarihi", "")
                aciklama_orj  = ism.get("aciklama", "")
                kaynak_dosya  = ism.get("kaynak_dosya", "")
                tutar_str     = ism.get("tutar_str", "")
                tutar_float   = float(ism.get("tutar", 0) or 0)

                # Açıklama = kaynak_dosya + aciklama (PHP: $aciklamaBirlesik)
                aciklama_birlesik = f"{kaynak_dosya} {aciklama_orj}".strip()[:250]

                # Tutar string düzenleme: binlik noktaları kaldır
                tutar_str_duzenli = tutar_str.replace(".", "") if tutar_str else str(tutar_float)

                # Mükerrer kontrolü (PHP checkStmt karşılığı)
                mukerrer_sayisi = conn.execute(
                    check_sql,
                    (str(userid), str(musterino), islem_tarihi, tutar_float, f"%{aciklama_orj}%")
                ).fetchone()[0]
                if mukerrer_sayisi > 0:
                    mukerrer += 1
                    continue

                womsiskey = _random_key()

                try:
                    conn.execute("SAVEPOINT sp_insert")
                    conn.execute(insert_sql, (
                        str(userid), str(musterino),
                        islem_tarihi, aciklama_birlesik,
                        tutar_str_duzenli, tutar_float,
                        hesap_kodu, womsiskey, dosya_banka_adi
                    ))
                    conn.execute("RELEASE SAVEPOINT sp_insert")
                    basarili += 1
                except Exception as exc:
                    conn.execute("ROLLBACK TO SAVEPOINT sp_insert")
                    hatali += 1
                    import sys
                    print(f"DB INSERT HATA: {exc}", file=sys.stderr)
                    hatalar.append(f"{os.path.basename(dosya_yolu)}: {exc}")

            toplam_basarili += basarili
            toplam_mukerrer += mukerrer
            toplam_hatali   += hatali

        conn.commit()

        if islenen > 0 or toplam_basarili > 0:
            banka_tip = "Yapı Kredi PDF" if is_yapıkredi else "İş Bankası PDF"
            msg = (
                f"{banka_tip}: {islenen} dosyadan {toplam_basarili} kayıt eklendi, "
                f"{toplam_mukerrer} mükerrer atlandı"
                + (f", {toplam_hatali} hatalı." if toplam_hatali else ".")
            )
            return {"success": True, "message": msg, "added": toplam_basarili, "skipped": toplam_mukerrer}
        else:
            return {
                "success": False,
                "errors": " | ".join(hatalar) if hatalar else "Hiçbir dosya işlenemedi.",
                "added": 0, "skipped": 0,
            }

    except Exception as exc:
        conn.rollback()
        return {"success": False, "errors": f"DB hatası: {exc}", "added": 0, "skipped": 0}
    finally:
        conn.close()


def yukle_pdf_isbank(
    userid: int,
    musterino: int,
    dosya_yolları: list[str],
    hesap_kodu: str,
    banka_adi: str,
    banka_adi_liste: list[str] | None = None,
) -> dict:
    """PHP krediKartVeriAktarPdf.php karşılığı — İş Bankası PDF."""
    return _yukle_pdf_ortak(
        userid, musterino, dosya_yolları, hesap_kodu, banka_adi,
        banka_adi_liste or [], is_yapıkredi=False
    )


def yukle_pdf_yapıkredi(
    userid: int,
    musterino: int,
    dosya_yolları: list[str],
    hesap_kodu: str,
    banka_adi: str,
    banka_adi_liste: list[str] | None = None,
) -> dict:
    """PHP krediKartVeriAktarPdfYK.php karşılığı — Yapı Kredi PDF."""
    return _yukle_pdf_ortak(
        userid, musterino, dosya_yolları, hesap_kodu, banka_adi,
        banka_adi_liste or [], is_yapıkredi=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tek giriş noktası: dosya türü + banka adına göre uygun parser'ı seç
# PHP JS: targetUrl belirleme mantığının karşılığı
# ─────────────────────────────────────────────────────────────────────────────

def yukle_dosyalar(
    userid: int,
    musterino: int,
    dosya_yolları: list[str],
    hesap_kodu: str,
    banka_adi: str,
    dosya_turu: str,  # 'csv' | 'pdf' | 'xlsx'
    banka_adi_liste: list[str] | None = None,
) -> dict:
    """
    PHP JS'teki targetUrl belirleme mantığının Python karşılığı:
      - dosyaTuru === 'pdf' + YapıKredi → yukle_pdf_yapıkredi
      - dosyaTuru === 'pdf' + diğer     → yukle_pdf_isbank
      - dosyaTuru === 'csv'             → yukle_csv_yapıkredi (ilk dosya)
      - dosyaTuru === 'xlsx'            → ileride eklenebilir
    """
    turu = (dosya_turu or "").lower().strip()
    banka_norm = banka_adi.replace(" ", "").lower()
    is_yapıkredi = "yapıkredi" in banka_norm or "yapikredi" in banka_norm

    if turu == "pdf":
        if is_yapıkredi:
            return yukle_pdf_yapıkredi(userid, musterino, dosya_yolları, hesap_kodu, banka_adi, banka_adi_liste)
        else:
            return yukle_pdf_isbank(userid, musterino, dosya_yolları, hesap_kodu, banka_adi, banka_adi_liste)

    elif turu == "csv":
        # CSV için ilk dosyayı al (PHP tekli dosya destekler)
        if not dosya_yolları:
            return {"success": False, "errors": "Dosya seçilmedi.", "added": 0, "skipped": 0}
        return yukle_csv_yapıkredi(userid, musterino, dosya_yolları[0], hesap_kodu, banka_adi)

    elif turu == "xlsx":
        return {"success": False, "errors": "XLSX desteği henüz eklenmedi.", "added": 0, "skipped": 0}

    else:
        return {"success": False, "errors": f"Desteklenmeyen dosya türü: {dosya_turu}", "added": 0, "skipped": 0}


def ekle_kredi_kart(
    userid: int,
    banka: str,
    no: str,
    hesap_kodu: str,
    banka_adi: str,
    iban: str
) -> dict:
    """Yeni bir kredi kartını key_kartlari tablosuna ekler."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO key_kartlari (banka, no, userid, hesapkodu, bankaadi, iban) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (banka, no, str(userid), hesap_kodu, banka_adi, iban)
        )
        conn.commit()
        return {"success": True}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


def sil_kredi_kart(userid: int, card_id: int) -> dict:
    """Kredi kartını key_kartlari tablosundan siler."""
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM key_kartlari WHERE id = %s AND userid = %s",
            (card_id, str(userid))
        )
        conn.commit()
        return {"success": True}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()
