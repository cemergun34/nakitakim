# -*- coding: utf-8 -*-
"""
Migration: 6 tabloya musterino alanı ekle
==========================================
Hedef tablolar:
  - odemesekli
  - sirket_profili
  - subeler
  - vomsisbilgileri
  - webadmin_sirket_config
  - womsi_banka

Strateji:
  - PostgreSQL: ALTER TABLE ... ADD COLUMN IF NOT EXISTS (sıfır kesinti)
  - SQLite: tablo var mı / kolon var mı kontrol et, yoksa ALTER TABLE ekle
  - Mevcut NULL kayıtları UPDATE ile musterino=1 yapılır
  - İdempotent: defalarca çalıştırılabilir
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

# Eklenecek (tablo_adı, varsayılan) çiftleri
TARGET_TABLES = [
    "odemesekli",
    "sirket_profili",
    "subeler",
    "vomsisbilgileri",
    "webadmin_sirket_config",
    "womsis_banka",   # Gerçek tablo adı
    # "womsi_banka",  # Eski/alternatif ad — yoksa zaten atlanır
]


def run_migration(verbose: bool = True) -> dict:
    """
    Tüm hedef tablolara musterino INTEGER DEFAULT 1 sütunu ekler.

    Returns:
        {"success": bool, "results": {tablo: "added"|"exists"|"error"}, "message": str}
    """
    results: dict[str, str] = {}

    try:
        from db.database import get_connection
        from db.db_config import get_mode
    except ImportError as e:
        return {"success": False, "results": {}, "message": f"Import hatası: {e}"}

    mode = get_mode()
    conn = get_connection()

    try:
        if mode == "postgres":
            results = _run_pg(conn, verbose)
        else:
            results = _run_sqlite(conn, verbose)
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error("Migration hatası: %s", exc)
        return {"success": False, "results": results, "message": str(exc)}
    finally:
        try:
            conn.close()
        except Exception:
            pass

    errors = [t for t, s in results.items() if s == "error"]
    added  = [t for t, s in results.items() if s == "added"]
    exists = [t for t, s in results.items() if s == "exists"]

    msg_parts = []
    if added:
        msg_parts.append(f"{len(added)} tabloya musterino eklendi: {', '.join(added)}")
    if exists:
        msg_parts.append(f"{len(exists)} tabloda zaten vardı: {', '.join(exists)}")
    if errors:
        msg_parts.append(f"Hata ({len(errors)} tablo): {', '.join(errors)}")

    return {
        "success": len(errors) == 0,
        "results": results,
        "message": " | ".join(msg_parts) or "Tamamlandı.",
    }


# ── PostgreSQL yolu ───────────────────────────────────────────────────────────

def _run_pg(conn, verbose: bool) -> dict[str, str]:
    results: dict[str, str] = {}

    for tablo in TARGET_TABLES:
        try:
            # 1. Kolon var mı?
            exists_row = conn.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = ? AND column_name = 'musterino'
                """,
                (tablo,)
            ).fetchone()

            if exists_row:
                results[tablo] = "exists"
                if verbose:
                    print(f"[Migration] {tablo}.musterino zaten var — atlandı")
                continue

            # 2. Kolon ekle
            conn.execute(
                f"ALTER TABLE {tablo} ADD COLUMN musterino INTEGER DEFAULT 1"
            )

            # 3. Mevcut NULL kayıtları güncelle
            conn.execute(
                f"UPDATE {tablo} SET musterino = 1 WHERE musterino IS NULL"
            )

            results[tablo] = "added"
            if verbose:
                print(f"[Migration] ✅ {tablo}.musterino eklendi (DEFAULT 1)")

        except Exception as exc:
            logger.warning("PG migration hatası [%s]: %s", tablo, exc)
            results[tablo] = "error"
            if verbose:
                print(f"[Migration] ❌ {tablo}: {exc}")
            # Devam et — diğer tablolara bak
            try:
                conn.execute("ROLLBACK TO SAVEPOINT _mig_sp")
                conn.execute("RELEASE SAVEPOINT _mig_sp")
            except Exception:
                pass

    return results


# ── SQLite yolu ───────────────────────────────────────────────────────────────

def _run_sqlite(conn, verbose: bool) -> dict[str, str]:
    results: dict[str, str] = {}

    for tablo in TARGET_TABLES:
        try:
            # Tablo var mı?
            tbl_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (tablo,)
            ).fetchone()
            if not tbl_exists:
                results[tablo] = "exists"  # Tablo yok → atla
                if verbose:
                    print(f"[Migration] {tablo} tablosu bulunamadı — atlandı")
                continue

            # Kolon var mı?
            cols = conn.execute(f"PRAGMA table_info({tablo})").fetchall()
            col_names = [c[1].lower() for c in cols]
            if "musterino" in col_names:
                results[tablo] = "exists"
                if verbose:
                    print(f"[Migration] {tablo}.musterino zaten var — atlandı")
                continue

            # Kolon ekle
            conn.execute(
                f"ALTER TABLE {tablo} ADD COLUMN musterino INTEGER DEFAULT 1"
            )
            conn.execute(
                f"UPDATE {tablo} SET musterino = 1 WHERE musterino IS NULL"
            )
            results[tablo] = "added"
            if verbose:
                print(f"[Migration] ✅ {tablo}.musterino eklendi (DEFAULT 1)")

        except Exception as exc:
            logger.warning("SQLite migration hatası [%s]: %s", tablo, exc)
            results[tablo] = "error"
            if verbose:
                print(f"[Migration] ❌ {tablo}: {exc}")

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

    print("=" * 60)
    print("Migration: musterino alanı ekleme")
    print("=" * 60)
    result = run_migration(verbose=True)
    print()
    if result["success"]:
        print(f"✅ Migration tamamlandı: {result['message']}")
    else:
        print(f"❌ Migration hatası: {result['message']}")
