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
    """womsi_pos tablosunu oluşturur (yoksa)."""
    conn = get_connection()
    try:
        conn.executescript(_WOMSI_POS_SQL)
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

def get_dashboard_ozet(userid: int) -> dict:
    """
    womsi_pos tablosundan toplam İşlem ve Net Tutar değerlerini döndürür.
    PHP: womsisSonGuncellemeGoster() → res.toplam_islem_fmt, res.toplam_net_fmt

    Returns:
        {
            'success': bool,
            'toplam_islem': float,   → #womsisDashIslem
            'toplam_net':   float,   → #womsisDashOdeme / #womsisToplamBadge
            'toplam_islem_fmt': '₺...',
            'toplam_net_fmt':   '₺...',
            'kayit_sayisi': int
        }
    """
    ensure_tables()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT "
            "  COALESCE(SUM(islemTutari), 0)       AS toplam_islem, "
            "  COALESCE(SUM(isyeriUcretiTutar), 0) AS toplam_isyeri, "
            "  COALESCE(SUM(netTutar), 0)           AS toplam_net, "
            "  COUNT(*) AS kayit_sayisi "
            "FROM womsi_pos WHERE userid = ?",
            (userid,)
        ).fetchone()
        islem  = float(row["toplam_islem"]  or 0)
        isyeri = float(row["toplam_isyeri"] or 0)
        net    = float(row["toplam_net"]    or 0)
        kayit  = int(row["kayit_sayisi"]    or 0)
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
    ilk_tarih: str,   # 'YYYY-MM-DD'
    son_tarih: str,   # 'YYYY-MM-DD'
) -> dict:
    """
    womsi_pos tablosundan tarih aralığına göre hareketleri getirir.
    PHP: ajax/get_fiziksel_pos_hareketleri.php → SELECT ... WHERE STR_TO_DATE(islemTarihi,'%d.%m.%Y') BETWEEN

    Returns:
        {
            'success': bool,
            'data': [dict, ...],          ← 9 sütun
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
        rows_all = conn.execute(
            "SELECT isyeriNo, cariHesap, hesabaGecisTarihi, "
            "       islemTutari, islemTarihi, posNo, "
            "       isyeriUcretiTutar, netTutar, brand, "
            "       kartNo, islemTipi, aciklama "
            "FROM womsi_pos WHERE userid = ?",
            (userid,)
        ).fetchall()

        toplam_islem  = 0.0
        toplam_isyeri = 0.0
        toplam_net    = 0.0
        data: list[dict] = []

        for r in rows_all:
            r = dict(r)
            norm = _norm_date(r.get("islemTarihi", ""))
            if not norm:
                continue
            if norm < ilk_tarih or norm > son_tarih:
                continue

            gross  = float(r.get("islemTutari")       or 0)
            comm   = float(r.get("isyeriUcretiTutar") or 0)
            net    = float(r.get("netTutar")           or 0)

            toplam_islem  += gross
            toplam_isyeri += comm
            toplam_net    += net

            data.append({
                "isyerino":          r.get("isyeriNo",          ""),
                "carihesap":         r.get("cariHesap",         ""),
                "hesabagecistarihi": r.get("hesabaGecisTarihi", ""),
                "islemtutari":       gross,
                "islemtarihi":       r.get("islemTarihi",       ""),
                "posno":             r.get("posNo",             ""),
                "isyeritutar":       comm,
                "nettutar":          net,
                "brand":             r.get("brand",             ""),
                "kartno":            r.get("kartNo",            ""),
                "islemtipi":         r.get("islemTipi",        ""),
                "aciklama":          r.get("aciklama",          ""),
            })

        # PHP: ORDER BY STR_TO_DATE(islemTarihi,'%d.%m.%Y') DESC
        data.sort(key=lambda x: _norm_date(x.get("islemtarihi", "")) or "", reverse=True)

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
