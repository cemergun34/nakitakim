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
from db.db_config import get_mode


def _fix_pg_sequence(conn) -> None:
    """
    PostgreSQL modunda SERIAL sequence'ı tablodaki MAX(id) ile senkronize eder.
    SQLite→PG migration'da explicit ID'ler girildiğinde sequence geride kalabilir;
    bu fonksiyon INSERT öncesi çağrılarak 'duplicate key' hatasını önler.
    """
    if get_mode() != "postgres":
        return
    try:
        conn.execute(
            "SELECT setval('\"VergiMuhtasar_id_seq\"', "
            "COALESCE((SELECT MAX(id) FROM vergimuhtasar), 0) + 1, false)"
        )
    except Exception:
        pass  # sequence adı farklıysa veya hata oluşursa sessizce devam et


def _mno_col() -> str:
    """PostgreSQL: musteri_no, SQLite: musterino"""
    return "musteri_no" if get_mode() == "postgres" else "musterino"


# ── Tablo adı (PHP ile birebir) ───────────────────────────────────────────────
TABLE = "vergimuhtasar"


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

def get_vergi_muhtasar(userid: int, musterino: str = None, donem: str = "", yil: int = None, ilk_tarih: str = None, son_tarih: str = None) -> dict:
    """
    Kullanıcıya ait Vergi Muhtasar kayıtlarını döndürür.

    PHP'deki davranışla birebir:
    - donem parametresi varsa filtrelenir
    - yil parametresi varsa o yıla ait kayıtlar filtrelenir
    - ilk_tarih/son_tarih varsa döneme göre (Python'da) filtrelenir
    - Distinct dönem listesi de döndürülür
    - Her satır için fark = gaytutar - vergkestutar hesaplanır
    - Döndürülen sözlük: { 'success': bool, 'data': [...], 'donemler': [...] }
    """
    conn = get_connection()
    try:
        where  = "WHERE userid = ?"
        params: list = [userid]

        if musterino is not None:
            where += f" AND {_mno_col()} = ?"
            # PostgreSQL musteri_no sütunu INTEGER; string geçilmemeli
            try:
                params.append(int(musterino))
            except (ValueError, TypeError):
                params.append(musterino)

        if donem:
            where  += " AND donem = ?"
            params.append(donem)

        if yil and not donem:
            # donem örn: 'Oca.25', 'Ara.26' — son 2 hane yılın son 2 rakamı
            yil_suffix = str(yil)[-2:]
            where += " AND donem LIKE ?"
            params.append(f"%.{yil_suffix}")
        elif ilk_tarih and not donem and not yil:
            # fetch for the year from ilk_tarih to be safe
            yil_suffix = ilk_tarih[2:4]
            where += " AND donem LIKE ?"
            params.append(f"%.{yil_suffix}")

        sql  = (f"SELECT id, hesapkodu, ack, donem, gaytutar, vergkestutar "
                f"FROM {TABLE} {where} ORDER BY donem, hesapkodu")
        rows = conn.execute(sql, params).fetchall()

        gay_toplam  = 0.0
        verg_toplam = 0.0
        fark_toplam = 0.0
        data = []
        
        ay_map = {"Oca": 1, "Şub": 2, "Mar": 3, "Nis": 4, "May": 5, "Haz": 6, 
                  "Tem": 7, "Ağu": 8, "Eyl": 9, "Eki": 10, "Kas": 11, "Ara": 12}
                  
        for r in rows:
            if ilk_tarih and son_tarih and not donem:
                d_str = r["donem"]
                try:
                    a_str, y_str = d_str.split('.')
                    d_ay = ay_map.get(a_str, 1)
                    d_yil = 2000 + int(y_str)
                    d_cmp = f"{d_yil}-{d_ay:02d}"
                    i_cmp = ilk_tarih[:7]
                    s_cmp = son_tarih[:7]
                    if not (i_cmp <= d_cmp <= s_cmp):
                        continue
                except Exception:
                    pass
                    
            gay  = float(r["gaytutar"]     or 0)
            verg = float(r["vergkestutar"] or 0)
            fark = gay - verg
            gay_toplam  += gay
            verg_toplam += verg
            fark_toplam += abs(fark)   # PHP: Math.abs(gay - verg)
            d = dict(r)  # _CIRow'dan plain dict oluştur (fark eklemek için)
            d["fark"] = fark
            data.append(d)

        # Distinct dönem listesi
        donemler = [
            r[0] for r in conn.execute(
                f"SELECT DISTINCT donem FROM {TABLE} WHERE userid=? ORDER BY donem",
                (userid,)
            ).fetchall()
        ]

        def _fmt(v: float, sign=False) -> str:
            s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return (f"+{s} ₺" if sign else f"₺{s}")

        return {
            "success": True,
            "data": data,
            "donemler": donemler,
            "gay_toplam":      gay_toplam,
            "gay_toplam_fmt":  _fmt(gay_toplam),
            "verg_toplam":     verg_toplam,
            "verg_toplam_fmt": _fmt(verg_toplam),
            "fark_toplam":     fark_toplam,
            "fark_toplam_fmt": _fmt(fark_toplam, sign=True),
            "kayit_sayisi":    len(data),
        }
    except Exception as exc:
        return {"success": False, "message": str(exc), "data": [], "donemler": []}
    finally:
        conn.close()


def get_dashboard_toplam(userid: int, musterino: str = None, yil: int = None, ilk_tarih: str = None, son_tarih: str = None) -> dict:
    """
    PHP: initMaasKiraSmmmCard() → #dashMaasKiraSmmmToplam
    Formül: farkToplam += Math.abs(gay - verg)  (her satır için, NULL→0)
    """
    r = get_vergi_muhtasar(userid, musterino=musterino, yil=yil, ilk_tarih=ilk_tarih, son_tarih=son_tarih)
    if not r.get("success"):
        return {"success": False, "fark_toplam": 0.0, "fark_toplam_fmt": "₺0,00"}

    def _fmt_kart(v: float) -> str:
        """PHP: farkToplam.toLocaleString('tr-TR') + ' ₺'  (kart stili)"""
        s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{s} ₺"

    return {
        "success":      True,
        "fark_toplam":      r["fark_toplam"],
        "fark_toplam_fmt":  _fmt_kart(r["fark_toplam"]),   # '10.853.717,00 ₺'
        "gay_toplam":       r["gay_toplam"],
        "verg_toplam":      r["verg_toplam"],
        "kayit_sayisi":     r["kayit_sayisi"],
    }



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
    CSV dosyasını okur, parse eder ve vergimuhtasar tablosuna UPSERT yapar.

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
        # PostgreSQL sequence senkronizasyonu: migration'dan gelen explicit ID'ler
        # sequence'ı geri bırakabilir; INSERT öncesi düzelt.
        _fix_pg_sequence(conn)

        # PostgreSQL'de musteri_no sütun adı farklı olabilir
        mno_col = _mno_col()

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
                    f"(userid, {mno_col}, hesapkodu, ack, donem, gaytutar, vergkestutar) "
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
