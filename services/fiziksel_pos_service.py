# -*- coding: utf-8 -*-
"""
Fiziksel POS (Womsis) Servisi — PyQt6 backend
===============================================
PHP kaynaklar:
  ajax/get_fiziksel_pos_hareketleri.php  → get_fiziksel_pos_hareketleri()
  admin_dashboard.js                      → fpHareketleriYukle(), womsisSonGuncellemeGoster()

DB Tablosu (SQLite karşılığı):
  womsi_pos  — Womsis fiziksel POS işlem dökümü

Tablo sütunları (PHP womsiPos MySQL):
  isyeriNo | cariHesap | hesabaGecisTarihi | islemTutari |
  islemTarihi | posNo | isyeriUcretiTutar | netTutar | brand |
  kartNo | islemTipi | aciklama
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional

from db.database import get_connection


# ---------------------------------------------------------------------------
# 0. Tablo oluşturma
# ---------------------------------------------------------------------------

_WOMSI_POS_SQL = """
CREATE TABLE IF NOT EXISTS womsi_pos (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    userid               INTEGER NOT NULL DEFAULT 0,
    musterino            INTEGER NOT NULL DEFAULT 1,
    isyeriNo             TEXT    DEFAULT '',
    cariHesap            TEXT    DEFAULT '',
    hesabaGecisTarihi    TEXT    DEFAULT '',
    islemTutari          REAL    DEFAULT 0.0,
    islemTarihi          TEXT    DEFAULT '',
    posNo                TEXT    DEFAULT '',
    isyeriUcretiTutar    REAL    DEFAULT 0.0,
    netTutar             REAL    DEFAULT 0.0,
    brand                TEXT    DEFAULT '',
    kartNo               TEXT    DEFAULT '',
    islemTipi            TEXT    DEFAULT '',
    aciklama             TEXT    DEFAULT '',
    islemTarih           TEXT    DEFAULT '',
    kayitTarihi          TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_womsi_pos_userid      ON womsi_pos(userid);
CREATE INDEX IF NOT EXISTS idx_womsi_pos_islemtarihi ON womsi_pos(userid, islemTarihi);
"""


def ensure_tables() -> None:
    """womsi_pos tablosunu oluşturur (yoksa). SQLite ve PostgreSQL uyumlu."""
    conn = get_connection()
    try:
        # SQLite → executescript; PostgreSQL → tek tek execute
        try:
            conn.executescript(_WOMSI_POS_SQL)
            conn.commit()
        except AttributeError:
            # PostgreSQL wrapper'ı — executescript yok, satır satır çalıştır
            for stmt in _WOMSI_POS_SQL.split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        conn.execute(stmt + ";")
                    except Exception:
                        pass
            conn.commit()
    except Exception:
        pass
    finally:
        conn.close()



# ---------------------------------------------------------------------------
# 1. Yardımcı: Türkçe tutar formatı
# ---------------------------------------------------------------------------

def _fmt_tl(val: float) -> str:
    """float → '₺1.234,56'"""
    fmt = f"{abs(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"₺{fmt}"


def _norm_date(val: str) -> Optional[str]:
    """
    DD.MM.YYYY veya DD.MM.YYYY HH:MM → YYYY-MM-DD karşılaştırma için.
    PHP'deki STR_TO_DATE(islemTarihi, '%d.%m.%Y') karşılığı.
    """
    if not val:
        return None
    s = str(val).strip()
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# 2. Dashboard KPI özeti
#    PHP: womsisSonGuncellemeGoster() → #womsisDashIslem, #womsisDashOdeme, #womsisToplamBadge
# ---------------------------------------------------------------------------

def get_dashboard_ozet(userid: int, musterino: int) -> dict:
    """
    womsi_pos tablosundan toplam İşlem ve Net Tutar değerlerini döndürür.
    PHP: womsisSonGuncellemeGoster() → res.toplam_islem_fmt, res.toplam_net_fmt
    """
    ensure_tables()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT "
            "  COALESCE(SUM(islemtutari), 0)       AS toplam_islem, "
            "  COALESCE(SUM(isyeriucretitutar), 0) AS toplam_isyeri, "
            "  COALESCE(SUM(nettutar), 0)           AS toplam_net, "
            "  COUNT(*) AS kayit_sayisi "
            "FROM womsi_pos WHERE musterino = ? ",
            (musterino,)
        ).fetchone()
        islem  = float(row[0] or 0)
        isyeri = float(row[1] or 0)
        net    = float(row[2] or 0)
        kayit  = int(row[3] or 0)
        return {
            "success":          True,
            "toplam_islem":     islem,
            "toplam_isyeri":    isyeri,
            "toplam_net":       net,
            "toplam_islem_fmt": _fmt_tl(islem),
            "toplam_isyeri_fmt":_fmt_tl(isyeri),
            "toplam_net_fmt":   _fmt_tl(net),
            "kayit_sayisi":     kayit,
        }
    except Exception as exc:
        return {
            "success": False, "message": str(exc),
            "toplam_islem": 0.0, "toplam_net": 0.0,
            "toplam_islem_fmt": "₺0,00", "toplam_net_fmt": "₺0,00",
            "kayit_sayisi": 0,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 3. Hareket listesi (modal DataTable)
#    PHP: get_fiziksel_pos_hareketleri.php → $allTransactions
# ---------------------------------------------------------------------------

def get_hareketler(
    userid:    int,
    musterino: int,
    ilk_tarih: str,   # 'YYYY-MM-DD'
    son_tarih: str,   # 'YYYY-MM-DD'
) -> dict:
    """
    womsi_pos tablosundan tarih aralığına göre hareketleri getirir.
    Kolon adları lowercase — hem SQLite hem PostgreSQL uyumlu.

    Returns:
        {
            'success': bool,
            'data': [dict, ...],
            'toplam_islem':      float,
            'toplam_isyeri':     float,
            'toplam_net':        float,
            'toplam_islem_fmt':  '₺...',
            'toplam_isyeri_fmt': '₺...',
            'toplam_net_fmt':    '₺...',
            'kayit_sayisi':      int
        }
    """
    ensure_tables()

    try:
        ilk_dt = datetime.strptime(ilk_tarih, "%Y-%m-%d")
        son_dt = datetime.strptime(son_tarih, "%Y-%m-%d")
    except ValueError as exc:
        return {"success": False, "message": f"Tarih formatı hatalı: {exc}"}

    conn = get_connection()
    try:
        # Lowercase kolon adları — hem SQLite hem PG uyumlu
        rows_all = conn.execute(
            "SELECT isyerino, carihesap, hesabagecistarihi, "
            "       islemtutari, islemtarihi, posno, "
            "       isyeriucretitutar, nettutar, brand, "
            "       kartno, islemtipi, aciklama "
            "FROM womsi_pos WHERE musterino = ?",
            (musterino,)
        ).fetchall()

        toplam_islem  = 0.0
        toplam_isyeri = 0.0
        toplam_net    = 0.0
        data: list[dict] = []

        for r in rows_all:
            # _CIRow case-insensitive dict — key ile doğrudan eriş
            islemtarihi_v       = r["islemtarihi"]
            isyerino_v          = r["isyerino"]
            carihesap_v         = r["carihesap"]
            hesabagecistarihi_v = r["hesabagecistarihi"]
            islemtutari_v       = r["islemtutari"]
            posno_v             = r["posno"]
            isyeriucret_v       = r["isyeriucretitutar"]
            nettutar_v          = r["nettutar"]
            brand_v             = r["brand"]
            kartno_v            = r["kartno"]
            islemtipi_v         = r["islemtipi"]
            aciklama_v          = r["aciklama"]

            norm = _norm_date(str(islemtarihi_v or ""))
            if not norm:
                continue
            if norm < ilk_tarih or norm > son_tarih:
                continue

            gross = float(islemtutari_v or 0)
            comm  = float(isyeriucret_v or 0)
            net   = float(nettutar_v    or 0)

            toplam_islem  += gross
            toplam_isyeri += comm
            toplam_net    += net

            data.append({
                "isyerino":          str(isyerino_v          or ""),
                "carihesap":         str(carihesap_v         or ""),
                "hesabagecistarihi": str(hesabagecistarihi_v or ""),
                "islemtutari":       gross,
                "islemtarihi":       str(islemtarihi_v       or ""),
                "posno":             str(posno_v             or ""),
                "isyeritutar":       comm,
                "nettutar":          net,
                "brand":             str(brand_v             or ""),
                "kartno":            str(kartno_v            or ""),
                "islemtipi":         str(islemtipi_v         or ""),
                "aciklama":          str(aciklama_v          or ""),
            })


        # PHP: ORDER BY STR_TO_DATE(islemTarihi,'%d.%m.%Y') DESC
        data.sort(
            key=lambda x: _norm_date(x.get("islemtarihi", "")) or "",
            reverse=True
        )

        return {
            "success":           True,
            "data":              data,
            "toplam_islem":      toplam_islem,
            "toplam_isyeri":     toplam_isyeri,
            "toplam_net":        toplam_net,
            "toplam_islem_fmt":  _fmt_tl(toplam_islem),
            "toplam_isyeri_fmt": _fmt_tl(toplam_isyeri),
            "toplam_net_fmt":    _fmt_tl(toplam_net),
            "kayit_sayisi":      len(data),
        }

    except Exception as exc:
        return {"success": False, "message": f"Veritabanı hatası: {exc}"}
    finally:
        conn.close()

