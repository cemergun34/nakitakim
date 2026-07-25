"""
E-Fatura Import Servisi
PHP ajax/dosya/efatura.php  +  ajax/ayarlar/faturaTopluisle.php
dosyalarının Python/SQLite karşılığı.

Fonksiyonlar:
    import_xml(xml_path, mod, userid) → dict
    toplu_isle(fatura_ids, hesap_kodu_id, cari_str, mod, userid) → dict
    get_faturalar(userid, mod) → list[dict]
    get_alt_hesap_kodlari(userid) → list[dict]
    get_cari_hesaplar(userid) → list[dict]

Mükerrer Kayıt Koruması (3 katman):
    1. Uygulama katmanı — hash kontrolü (SELECT önceki kayıt)
    2. Uygulama katmanı — faturano + userid + mod kombinasyon kontrolü
    3. Veritabanı katmanı — UNIQUE INDEX (hash, userid) ve
       UNIQUE INDEX (faturano, userid, gelirgidermod) ihlali yakalanırsa
       "skipped" olarak döner (race condition koruması)
"""

from __future__ import annotations
import json
import shutil
import os
from datetime import datetime
from typing import Optional

from db.database import get_connection
from db.efatura_parser import parse_invoice_xml

# Yüklenen XML dosyaları için kalıcı klasör (realpath ile normalize edildi)
UPLOAD_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "faturalar")
)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _is_unique_violation(exc: Exception) -> bool:
    """
    PostgreSQL veya SQLite unique constraint ihlali mi kontrol eder.
    psycopg2: pgcode 23505 (unique_violation)
    sqlite3:  'UNIQUE constraint failed' mesajı
    """
    msg = str(exc).lower()
    # psycopg2
    if hasattr(exc, 'pgcode') and getattr(exc, 'pgcode', '') == '23505':
        return True
    # psycopg2 — pgcode bazen wrapped exception içinde
    cause = getattr(exc, '__cause__', None) or getattr(exc, '__context__', None)
    if cause and hasattr(cause, 'pgcode') and getattr(cause, 'pgcode', '') == '23505':
        return True
    # SQLite
    if 'unique constraint failed' in msg:
        return True
    # Genel fallback
    if 'unique' in msg and ('violation' in msg or 'constraint' in msg or 'duplicate' in msg):
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı fonksiyonlar
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_cari_hesap(conn, unvan: str, vergi_no: str, vergi_daire: str,
                        tc: str, userid: int) -> int:
    """
    carihesaplar tablosunu kontrol eder, yoksa ekler, id döndürür.
    PHP efatura.php'deki dinamik SELECT + INSERT bloğunun karşılığı.
    """
    logtarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if vergi_no:
        row = conn.execute(
            "SELECT id FROM carihesaplar WHERE userid=? AND vergiNo=? LIMIT 1",
            (userid, vergi_no)
        ).fetchone()
    elif tc:
        row = conn.execute(
            "SELECT id FROM carihesaplar WHERE userid=? AND tcno=? LIMIT 1",
            (userid, tc)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM carihesaplar WHERE userid=? AND unvan=? LIMIT 1",
            (userid, unvan)
        ).fetchone()

    if row:
        return row[0]

    cur = conn.execute(
        """INSERT INTO carihesaplar (unvan, vergiDaire, vergiNo, tcno, userid, logtarih)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (unvan, vergi_daire, vergi_no, tc, userid, logtarih)
    )
    return cur.lastrowid


# ─────────────────────────────────────────────────────────────────────────────
# Ana servis fonksiyonları
# ─────────────────────────────────────────────────────────────────────────────

def import_xml(xml_path: str, userid: int, mod: str = None,
               izin_verilen_tipler: tuple[str, ...] | None = None) -> dict:
    """
    Tek UBL-TR XML dosyasını parse edip veritabanına kaydeder.
    mod verilmezse VKN karsilastirmasi ile otomatik tespit edilir.

    Args:
        xml_path:             Diskteki XML dosyasinin tam yolu
        userid:               Oturumdaki kullanici ID
        mod:                  'gelir' | 'gider' (verilmezse otomatik tespit)
        izin_verilen_tipler:  İzin verilen InvoiceTypeCode değerleri.
                              None veya boş ise varsayılan olarak yalnızca
                              ("", "380") — yani SATIŞ faturaları — kabul edilir.
                              Örn: ("380",) sadece satış
                                   ("380", "381") satış + iade
                                   ("380", "381", "389") hepsi

    Returns:
        {'success': bool, 'message': str, 'meta': dict | None}
        Atlandıysa ek olarak: {'skipped': True, 'skip_reason': 'tip_filtresi'}
    """
    from services.sirket_service import detect_fatura_mod

    # Varsayılan: sadece SATIŞ (380) ve TypeCode'u boş/tanımsız olanlar
    if not izin_verilen_tipler:
        izin_verilen_tipler = ("", "380")

    # 1 - XML parse
    parsed = parse_invoice_xml(xml_path)
    if not parsed.success:
        return {"success": False, "message": parsed.message}

    # 2 - Fatura tipi filtresi — İPTAL (389) / İADE (381) kontrolü
    if parsed.fatura_tipi not in izin_verilen_tipler:
        tip_adi = parsed.fatura_tipi_adi  # "İPTAL", "İADE", vb.
        return {
            "success": True,
            "skipped": True,
            "skip_reason": "tip_filtresi",
            "message": (
                f"{tip_adi} faturası atlandı (Fatura No: {parsed.fatura_no}). "
                f"Yalnızca SATIŞ faturaları aktarılır."
            ),
        }

    # 3 - Mod otomatik tespit
    if mod not in ("gelir", "gider"):
        mod = detect_fatura_mod(
            xml_supplier_vkn=parsed.vergi_no       or "",
            xml_supplier_tc =parsed.tc              or "",
            xml_customer_vkn=parsed.alici_vergi_no  or "",
            xml_customer_tc =parsed.alici_tc        or "",
            userid=userid,
        )
        if mod is None:
            return {
                "success": False,
                "no_match": True,
                "message": (
                    f"VKN eslesmesi bulunamadi - fatura atlandi: "
                    f"{parsed.fatura_no} | "
                    f"Tedarikci VKN: {parsed.vergi_no or parsed.tc} | "
                    f"Alici VKN: {parsed.alici_vergi_no or parsed.alici_tc}"
                )
            }

    # 3 - meta olustur
    meta_dict = parsed.meta_dict(mod)
    meta_json = json.dumps(meta_dict, ensure_ascii=False)

    unvan       = meta_dict.get("unvan", "")
    vergi_no    = meta_dict.get("vergiNo", "")
    vergi_daire = meta_dict.get("vergiDairesi", "")
    tc          = meta_dict.get("tc", "")
    tarih       = meta_dict.get("tarih", "")
    toplam      = meta_dict.get("genel_toplam", "")
    fatura_no   = meta_dict.get("faturaNo", "")

    # 4 - Hash hesapla
    fatura_hash = parsed.compute_hash(mod)
    gruplama = "|".join([fatura_no, unvan, vergi_no, tc, vergi_daire])

    conn = get_connection()
    try:
        # 5a - Birincil duplicate kontrolu: hash
        row = conn.execute(
            "SELECT id FROM faturalar WHERE hash=? AND userid=? LIMIT 1",
            (fatura_hash, userid)
        ).fetchone()
        if row:
            return {
                "success": True,
                "skipped": True,
                "message": "Bu fatura zaten mevcut (hash), atlandi.",
                "meta": meta_dict
            }

        # 5b - İkincil duplicate kontrolu: faturano + mod kombinasyonu
        # (farklı hash ama aynı fatura no ile yeniden import senaryosu)
        if fatura_no:
            row2 = conn.execute(
                "SELECT id FROM faturalar "
                "WHERE faturano=? AND userid=? AND gelirgidermod=? LIMIT 1",
                (fatura_no, userid, mod)
            ).fetchone()
            if row2:
                return {
                    "success": True,
                    "skipped": True,
                    "message": f"Bu fatura numarası zaten mevcut ({fatura_no}), atlandi.",
                    "meta": meta_dict
                }

        # 6 - XML kopyala
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        dest_name = f"fatura_{ts}_{os.path.basename(xml_path)}"
        dest_path = os.path.join(UPLOAD_DIR, dest_name)
        shutil.copy2(xml_path, dest_path)

        try:
            from services.webadmin_client import WebAdminClient, get_webadmin_config
            cfg = get_webadmin_config(userid)
            if cfg.get("enabled") and cfg.get("base_url"):
                musterino = 1
                try:
                    from db.db_config import get_pg_params
                    import psycopg2
                    pg_conn = psycopg2.connect(**get_pg_params())
                    pg_cur = pg_conn.cursor()
                    pg_cur.execute(
                        "SELECT musterino FROM sirket_profili WHERE userid=%s LIMIT 1",
                        (userid,)
                    )
                    row = pg_cur.fetchone()
                    pg_cur.close(); pg_conn.close()
                    if row and row[0]:
                        musterino = int(row[0])
                except Exception:
                    pass
                sirket_klasor = str(musterino).zfill(4)
                client = WebAdminClient(base_url=cfg["base_url"], api_key=cfg["api_key"])
                res = client.upload_fatura_xml(dest_path, sirket=sirket_klasor)
                if not res.get("success"):
                    import logging
                    logging.getLogger(__name__).warning("Fatura XML sunucuya yüklenemedi: %s", res.get("error"))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Fatura XML sunucuya yüklenirken hata oluştu: %s", e)

        # 6b - GHH'dan formno ve sube bul (unvan eşleşmesiyle)
        # XML'den gelen fatura unvanı, GHH.aciklama ile ILIKE eşleşirse
        # o kaydın form_id'sini formno olarak, sube'sini kayıda yazarız.
        found_formno = None
        found_sube   = None
        if unvan:
            try:
                ghh_row = conn.execute(
                    """SELECT form_id, sube
                       FROM genel_hesap_hareketleri
                       WHERE userid = ?
                         AND musteri_no = 1
                         AND LOWER(TRIM(aciklama)) = LOWER(TRIM(?))
                         AND form_id IS NOT NULL AND form_id != ''
                       ORDER BY id DESC
                       LIMIT 1""",
                    (userid, unvan)
                ).fetchone()
                if ghh_row:
                    found_formno = ghh_row[0]
                    found_sube   = ghh_row[1]
            except Exception:
                pass  # GHH eşleşmesi olmasa da import devam etsin

        # 7 - INSERT (ON CONFLICT DO NOTHING — DB unique index ihlali race condition koruması)
        cur = conn.execute(
            """INSERT INTO faturalar
               (userid, unvan, vergino, vergiDairesi, toplam, fatura,
                tarih, hash, gruplama, gelirGiderMod, faturano, kaynak, xml_dosya, musterino,
                formNo)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
               ON CONFLICT DO NOTHING""",
            (userid, unvan, vergi_no, vergi_daire, toplam, meta_json,
             tarih, fatura_hash, gruplama, mod, fatura_no, "xml", dest_path,
             found_formno)
        )
        fatura_id = cur.lastrowid

        # ON CONFLICT DO NOTHING tetiklendiyse lastrowid None/0 olur
        if not fatura_id:
            conn.rollback()
            return {
                "success": True,
                "skipped": True,
                "message": "Bu fatura zaten mevcut (DB constraint), atlandi.",
                "meta": meta_dict
            }

        # 8 - carihesaplar
        _ensure_cari_hesap(conn, unvan, vergi_no, vergi_daire, tc, userid)

        conn.commit()
        return {
            "success": True,
            "message": "Fatura basariyla iceri aktarildi.",
            "fatura_id": fatura_id,
            "meta": meta_dict
        }

    except Exception as e:
        conn.rollback()
        # DB unique constraint ihlali → mükerrer kayıt girişimi
        if _is_unique_violation(e):
            return {
                "success": True,
                "skipped": True,
                "message": "Bu fatura zaten mevcut (unique ihlali), atlandi.",
                "meta": meta_dict
            }
        return {"success": False, "message": f"Veritabani hatasi: {e}"}
    finally:
        conn.close()


def toplu_isle(fatura_ids: list[int], hesap_kodu_id: int,
               cari_str: str, mod: str, userid: int) -> dict:
    """
    Seçilen faturaları hareketler tablosuna toplu olarak işler.
    PHP ajax/ayarlar/faturaTopluisle.php'nin karşılığı.

    cari_str formatı: "unvan*-*vergiNo*-*tc*-*vergiDaire"  (PHP ile aynı)

    Args:
        fatura_ids:     İşlenecek fatura ID listesi
        hesap_kodu_id:  althesapkodu tablosundaki ID
        cari_str:       *-* ile ayrılmış cari hesap bilgisi
        mod:            'gelir' | 'gider'
        userid:         Kullanıcı ID

    Returns:
        {'success': bool, 'message': str, 'count': int}
    """
    if not fatura_ids:
        return {"success": False, "message": "İşlenecek fatura seçilmedi."}

    # cari_str ayrıştır
    parts = [p.strip() for p in cari_str.split("*-*")]
    while len(parts) < 4:
        parts.append("")
    cari_unvan, cari_vergi_no, cari_tc, cari_vergi_daire = parts[:4]

    conn = get_connection()
    try:
        # 1 — carihesaplar'dan cari_id bul
        if cari_vergi_no:
            cari_row = conn.execute(
                "SELECT id FROM carihesaplar WHERE userid=? AND vergiNo=? LIMIT 1",
                (userid, cari_vergi_no)
            ).fetchone()
        elif cari_tc:
            cari_row = conn.execute(
                "SELECT id FROM carihesaplar WHERE userid=? AND tcno=? LIMIT 1",
                (userid, cari_tc)
            ).fetchone()
        else:
            cari_row = conn.execute(
                "SELECT id FROM carihesaplar WHERE userid=? AND unvan=? LIMIT 1",
                (userid, cari_unvan)
            ).fetchone()

        if not cari_row:
            return {"success": False, "message": "Cari hesap bulunamadı."}
        cari_id = cari_row[0]

        # 2 — althesapkodu'ndan hesap kodu al
        hesap_row = conn.execute(
            "SELECT kod, gelirGider FROM althesapkodu WHERE id=? AND userid=? LIMIT 1",
            (hesap_kodu_id, userid)
        ).fetchone()
        if not hesap_row:
            return {"success": False, "message": "Hesap kodu bulunamadı."}
        hesap_kodu_gercek = hesap_row[0]

        # 3 — Fatura kayıtlarını çek
        placeholders = ",".join("?" * len(fatura_ids))
        fatura_rows = conn.execute(
            f"SELECT id, unvan, toplam, tarih, faturano, fatura FROM faturalar "
            f"WHERE userid=? AND id IN ({placeholders})",
            [userid] + fatura_ids
        ).fetchall()

        if not fatura_rows:
            return {"success": False, "message": "Seçilen faturalar bulunamadı."}

        insert_count = 0
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 4 — Her fatura için hareketler INSERT
        for row in fatura_rows:
            fat_id, fat_unvan, fat_toplam, fat_tarih, fat_no, fat_json = row

            # Meta JSON'dan tarih al (daha güvenilir)
            try:
                meta = json.loads(fat_json or "{}")
                tarih_str = meta.get("tarih", fat_tarih or "")
            except Exception:
                tarih_str = fat_tarih or ""

            # Tarihi gün.ay.yıl formatına çevir (PHP ile uyumlu)
            try:
                if "-" in tarih_str:
                    dt = datetime.strptime(tarih_str, "%Y-%m-%d")
                    tarih_fmt = dt.strftime("%d.%m.%Y")
                else:
                    tarih_fmt = tarih_str
            except Exception:
                tarih_fmt = tarih_str

            try:
                tutar = float(str(fat_toplam).replace(",", ".")) if fat_toplam else 0.0
            except ValueError:
                tutar = 0.0

            # mod'a göre borç/alacak yönü (PHP ile aynı)
            if mod == "gelir":
                borc  = tutar
                alacak = 0.0
            else:  # gider
                borc  = 0.0
                alacak = tutar

            try:
                conn.execute(
                    """INSERT INTO hareketler
                       (tarih, hesapKodu, aciklama, gelirGider, kategori_id,
                        kaynak, carihesapId, faturaNo, faturaUnvan,
                        alinan_tutar1, musteriNo)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (tarih_fmt, hesap_kodu_gercek,
                     fat_unvan or cari_unvan,
                     mod, 0,
                     "fatura", cari_id,
                     fat_no or "",
                     fat_unvan or cari_unvan,
                     tutar, userid)
                )

                # faturalar tablosunu güncelle — işlenmiş olarak işaretle
                conn.execute(
                    "UPDATE faturalar SET gelirGiderMod=?, faturaMod='islendi' WHERE id=? AND userid=?",
                    (mod, fat_id, userid)
                )
                insert_count += 1
            except Exception:
                continue  # Tek satır hatası tüm işlemi durdurmasın

        conn.commit()
        return {
            "success": True,
            "message": f"{insert_count} fatura hareketlere aktarıldı.",
            "count": insert_count
        }

    except Exception as e:
        conn.rollback()
        return {"success": False, "message": f"İşlem hatası: {e}"}
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# UI için yardımcı sorgular
# ─────────────────────────────────────────────────────────────────────────────

def get_faturalar(userid: int, mod: Optional[str] = None) -> list[dict]:
    """
    Kullanıcıya ait fatura listesini döndürür.
    mod: 'gelir' | 'gider' | None (hepsi)
    """
    conn = get_connection()
    try:
        if mod:
            rows = conn.execute(
                """SELECT id, unvan, vergino, vergiDairesi, toplam, tarih,
                          faturano, gelirGiderMod, faturaMod, yuklenmeTarihi
                   FROM faturalar WHERE userid=? AND gelirGiderMod=?
                   ORDER BY id DESC""",
                (userid, mod)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, unvan, vergino, vergiDairesi, toplam, tarih,
                          faturano, gelirGiderMod, faturaMod, yuklenmeTarihi
                   FROM faturalar WHERE userid=?
                   ORDER BY id DESC""",
                (userid,)
            ).fetchall()

        cols = ["id", "unvan", "vergino", "vergiDairesi", "toplam", "tarih",
                "faturano", "gelirGiderMod", "faturaMod", "yuklenmeTarihi"]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def get_alt_hesap_kodlari(userid: int) -> list[dict]:
    """Açılır liste için althesapkodu tablosunu döndürür."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, kod, aciklama, gelirGider FROM althesapkodu WHERE userid=? ORDER BY kod",
            (userid,)
        ).fetchall()
        return [{"id": r[0], "kod": r[1], "aciklama": r[2], "gelirGider": r[3]} for r in rows]
    finally:
        conn.close()


def get_cari_hesaplar(userid: int) -> list[dict]:
    """Açılır liste için carihesaplar tablosunu döndürür."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT id, unvan, vergiNo, tcno, vergiDaire
               FROM carihesaplar WHERE userid=? ORDER BY unvan""",
            (userid,)
        ).fetchall()
        result = []
        for r in rows:
            cari_id, unvan, vergi_no, tc, vergi_daire = r
            # PHP ile uyumlu *-* formatı
            cari_str = f"{unvan}*-*{vergi_no or ''}*-*{tc or ''}*-*{vergi_daire or ''}"
            result.append({
                "id": cari_id,
                "unvan": unvan,
                "vergiNo": vergi_no,
                "tcno": tc,
                "vergiDaire": vergi_daire,
                "cari_str": cari_str,
            })
        return result
    finally:
        conn.close()
