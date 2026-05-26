"""
Vergi Muhtasar servisi — PyQt6 backend
PHP ayarlar.php → Eklentiler → Vergi Muhtasar bölümünün karşılığı.

PHP kaynak:
  ajax/ayarlar/vergiMuhtasarGetir.php
  ajax/dosya/vergiMuhtasarTopluYukle.php
"""
from __future__ import annotations
import csv
import io
import chardet
from typing import Optional

from db.database import get_connection


# ── Tablo adı (PHP ile birebir) ───────────────────────────────────────────────
TABLE = "VergiMuhtasar"


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı: Türkçe formatı float'a çevir (PHP parseDecimal() karşılığı)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_decimal(val: str) -> Optional[float]:
    """
    '1.234.567,89'  →  1234567.89
    ''  veya None   →  None
    """
    if val is None:
        return None
    val = val.strip()
    if val == "":
        return None
    # Noktalı binlik ayırıcıyı kaldır, virgülü noktaya çevir
    val = val.replace(".", "").replace(",", ".")
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Okuma  (PHP vergiMuhtasarGetir.php karşılığı)
# ─────────────────────────────────────────────────────────────────────────────

def get_vergi_muhtasar(userid: int, donem: str = "") -> dict:
    """
    Kullanıcıya ait Vergi Muhtasar kayıtlarını döndürür.

    PHP'deki davranışla birebir:
    - donem parametresi varsa filtrelenir
    - Distinct dönem listesi de döndürülür
    - Döndürülen sözlük: { 'success': bool, 'data': [...], 'donemler': [...] }
    """
    conn = get_connection()
    try:
        where  = "WHERE userid = ?"
        params: list = [userid]

        if donem:
            where  += " AND donem = ?"
            params.append(donem)

        sql  = (f"SELECT id, hesapkodu, ack, donem, gaytutar, vergkestutar "
                f"FROM {TABLE} {where} ORDER BY donem, hesapkodu")
        rows = conn.execute(sql, params).fetchall()
        data = [dict(r) for r in rows]

        # Distinct dönem listesi
        donemler = [
            r[0] for r in conn.execute(
                f"SELECT DISTINCT donem FROM {TABLE} WHERE userid=? ORDER BY donem",
                (userid,)
            ).fetchall()
        ]

        return {"success": True, "data": data, "donemler": donemler}
    except Exception as exc:
        return {"success": False, "message": str(exc), "data": [], "donemler": []}
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Güncelleme (inline düzenleme — PHP showAlert / pendingGuncelle karşılığı)
# ─────────────────────────────────────────────────────────────────────────────

def update_vergi_muhtasar_alan(
    userid: int,
    kayit_id: int,
    kolon: str,
    yeni_deger: float,
) -> dict:
    """
    Sadece 'gaytutar' veya 'vergkestutar' sütunlarını günceller.
    (PHP pendingGuncelle ile tetiklenen AJAX güncelleme mantığı)
    """
    if kolon not in ("gaytutar", "vergkestutar"):
        return {"success": False, "message": "Geçersiz sütun adı."}

    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE {TABLE} SET {kolon} = ? WHERE id = ? AND userid = ?",
            (yeni_deger, kayit_id, userid)
        )
        conn.commit()
        return {"success": True, "message": "Güncellendi."}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Silme (PHP pendingSilinecek / showAlert2 karşılığı)
# ─────────────────────────────────────────────────────────────────────────────

def delete_vergi_muhtasar(userid: int, kayit_id: int) -> dict:
    """Tek kaydı siler."""
    conn = get_connection()
    try:
        conn.execute(
            f"DELETE FROM {TABLE} WHERE id = ? AND userid = ?",
            (kayit_id, userid)
        )
        conn.commit()
        return {"success": True, "message": "Kayıt silindi."}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# CSV Toplu Yükleme (PHP vergiMuhtasarTopluYukle.php karşılığı)
# ─────────────────────────────────────────────────────────────────────────────

def toplu_yukle_csv(
    userid: int,
    dosya_yolu: str,
    musteri_no: Optional[int] = None,
) -> dict:
    """
    CSV dosyasını okur, parse eder ve VergiMuhtasar tablosuna UPSERT yapar.

    CSV formatı (noktalı virgül ayrımlı, opsiyonel BOM):
        hesapkodu;ack;donem;gaytutar;vergkestutar[;gaytutar_temiz;vergkestutar_temiz]

    Aynı (userid, hesapkodu, donem) var ise günceller, yoksa ekler.
    Döndürülen sözlük: { 'success', 'message', 'added', 'updated', 'skipped' }
    """
    # ── 1. Dosyayı oku + encoding tespiti ────────────────────────────────────
    try:
        with open(dosya_yolu, "rb") as f:
            raw = f.read()
    except Exception as exc:
        return {"success": False, "message": f"Dosya okunamadı: {exc}", "added": 0, "updated": 0, "skipped": 0}

    # Boyut kontrolü (2 MB — PHP ile aynı)
    if len(raw) > 2 * 1024 * 1024:
        return {"success": False, "message": "Dosya boyutu 2 MB'den büyük olamaz.",
                "added": 0, "updated": 0, "skipped": 0}

    # Encoding tespiti (chardet ile) — PHP mb_convert_encoding karşılığı
    detected = chardet.detect(raw)
    enc = detected.get("encoding") or "utf-8"
    try:
        content = raw.decode(enc)
    except (UnicodeDecodeError, LookupError):
        try:
            content = raw.decode("iso-8859-9")
        except Exception:
            content = raw.decode("utf-8", errors="replace")

    # BOM temizle (PHP ltrim BOM karşılığı)
    content = content.lstrip("\ufeff")

    # ── 2. CSV satır-satır parse ──────────────────────────────────────────────
    insert_values: list[dict] = []
    hatali_satir  = 0

    reader = csv.reader(io.StringIO(content), delimiter=";")
    for row_idx, row in enumerate(reader, start=1):
        if not any(cell.strip() for cell in row):
            continue  # Boş satır atla

        # Başlık satırını atla (PHP: stripos($line, 'hesapkodu') !== false)
        if row_idx == 1 and row and "hesapkodu" in row[0].lower():
            continue

        # En az 4 alan zorunlu
        if len(row) < 4:
            hatali_satir += 1
            continue

        hesapkodu    = row[0].strip()
        ack          = row[1].strip() if len(row) > 1 else ""
        donem        = row[2].strip() if len(row) > 2 else ""
        gaytutar     = _parse_decimal(row[3]) if len(row) > 3 else None
        vergkestutar = _parse_decimal(row[4]) if len(row) > 4 else None

        if not hesapkodu or not donem:
            hatali_satir += 1
            continue

        insert_values.append({
            "userid":       userid,
            "musteri_no":   musteri_no,
            "hesapkodu":    hesapkodu,
            "ack":          ack,
            "donem":        donem,
            "gaytutar":     gaytutar,
            "vergkestutar": vergkestutar,
        })

    if not insert_values:
        return {
            "success": False,
            "message": "Geçerli veri bulunamadı.",
            "added": 0, "updated": 0, "skipped": hatali_satir,
        }

    # ── 3. UPSERT: mevcut → UPDATE, yoksa → INSERT (PHP ile birebir) ──────────
    eklenen   = 0
    guncellen = 0
    conn = get_connection()
    try:
        for val in insert_values:
            # Mevcut kaydı kontrol et
            existing = conn.execute(
                f"SELECT id FROM {TABLE} "
                f"WHERE userid=? AND hesapkodu=? AND donem=? LIMIT 1",
                (val["userid"], val["hesapkodu"], val["donem"])
            ).fetchone()

            if existing:
                conn.execute(
                    f"UPDATE {TABLE} SET ack=?, gaytutar=?, vergkestutar=? "
                    f"WHERE id=? AND userid=?",
                    (val["ack"], val["gaytutar"], val["vergkestutar"],
                     existing[0], val["userid"])
                )
                guncellen += 1
            else:
                conn.execute(
                    f"INSERT INTO {TABLE} "
                    f"(userid, musteri_no, hesapkodu, ack, donem, gaytutar, vergkestutar) "
                    f"VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (val["userid"], val["musteri_no"], val["hesapkodu"],
                     val["ack"], val["donem"], val["gaytutar"], val["vergkestutar"])
                )
                eklenen += 1

        conn.commit()
        return {
            "success": True,
            "message": (
                f"{eklenen} yeni kayıt eklendi, "
                f"{guncellen} kayıt güncellendi, "
                f"{hatali_satir} satır atlandı."
            ),
            "added":   eklenen,
            "updated": guncellen,
            "skipped": hatali_satir,
        }
    except Exception as exc:
        conn.rollback()
        return {
            "success": False,
            "message": f"Veritabanı hatası: {exc}",
            "added": 0, "updated": 0, "skipped": hatali_satir,
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Şema CSV içeriği (PHP vmSemaIndir karşılığı)
# ─────────────────────────────────────────────────────────────────────────────

SEMA_CSV_ICERIK = (
    "hesapkodu;ack;donem;gaytutar;vergkestutar;gaytutar_temiz;vergkestutar_temiz\r\n"
    "11;asgari ücret;Ara.25;77.149,65;;77149.65;0.0\r\n"
)

SEMA_CSV_DOSYA_ADI = "muhtasarVergi_ornek.csv"
