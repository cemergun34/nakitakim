# -*- coding: utf-8 -*-
"""
SQLite → PostgreSQL Migrasyon Aracı (Hızlı Mod)
================================================
Her tablo için:
  1. TRUNCATE → mevcut verileri temizle
  2. Tüm satırları tek seferde toplu INSERT
  3. Tek commit → minimum network round-trip

ON CONFLICT DO NOTHING yerine TRUNCATE + bulk insert kullanıldığı için
çok daha hızlı çalışır.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Generator

from db.pg_schema import PG_TABLES, PG_INDEXES, SKIP_TABLES

# SQLite kaynak
SQLITE_PATH = Path.home() / "NakitAkim" / "data" / "nakit_akim.db"

# Batch büyüklüğü — progress güncellemesi için (toplu insertta)
BATCH_SIZE = 2000


@dataclass
class MigrasyonSonuc:
    tablo:     str
    toplam:    int  = 0
    aktarilan: int  = 0
    hata:      str  = ""
    ara:       bool = False
    bitti:     bool = False


def _get_pg_conn():
    """db_config.py'dan PostgreSQL bağlantısı açar."""
    import psycopg2
    from db.db_config import get_pg_params
    conn = psycopg2.connect(**get_pg_params())
    conn.autocommit = False
    return conn


def _get_sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _create_pg_schema(pg_conn) -> None:
    """PostgreSQL'de tüm tabloları ve indeksleri oluşturur."""
    cur = pg_conn.cursor()
    for _tablo_adi, ddl in PG_TABLES:
        cur.execute(ddl)
    for idx_sql in PG_INDEXES:
        try:
            cur.execute(idx_sql)
        except Exception:
            pass
    pg_conn.commit()
    cur.close()


def _get_sqlite_tables(sq_conn: sqlite3.Connection) -> list[str]:
    rows = sq_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows if r[0] not in SKIP_TABLES]


def _pg_tablo_adi(sqlite_tablo: str) -> str:
    """SQLite tablo adını PostgreSQL'deki küçük harfli karşılığına çevirir."""
    return sqlite_tablo.lower()


def migrate_all(batch_size: int = BATCH_SIZE) -> Generator[MigrasyonSonuc, None, None]:
    """
    Generator: İlerleme için MigrasyonSonuc üretir.

    Her tablo için:
      - Önce TRUNCATE (temizle)
      - Sonra tümünü toplu INSERT (tek commit)
      - ara=True  → Batch ilerleme (büyük tablolarda)
      - ara=False → Tablo tamamlandı
      - bitti=True → Tüm migrasyon bitti
    """
    sq_conn = _get_sqlite_conn()
    pg_conn = _get_pg_conn()

    try:
        # 1. Şemayı oluştur
        _create_pg_schema(pg_conn)

        tablolar = _get_sqlite_tables(sq_conn)

        for tablo in tablolar:
            pg_tablo = _pg_tablo_adi(tablo)

            # Satır sayısını al
            try:
                toplam = sq_conn.execute(
                    f'SELECT COUNT(*) FROM "{tablo}"'
                ).fetchone()[0]
            except Exception as exc:
                yield MigrasyonSonuc(tablo=tablo, hata=str(exc))
                continue

            if toplam == 0:
                yield MigrasyonSonuc(tablo=tablo, toplam=0, aktarilan=0)
                continue

            # Sütun adlarını al
            try:
                ornek = sq_conn.execute(
                    f'SELECT * FROM "{tablo}" LIMIT 1'
                ).fetchone()
                if ornek is None:
                    yield MigrasyonSonuc(tablo=tablo, toplam=0, aktarilan=0)
                    continue
                # Kolon adları küçük harfe çevrilir (PG uyumu)
                kolonlar = [k.lower() for k in ornek.keys()]
            except Exception as exc:
                yield MigrasyonSonuc(tablo=tablo, hata=str(exc))
                continue

            quoted_cols  = ", ".join(kolonlar)          # tırnaksız — hepsi küçük
            placeholders = ", ".join(["%s"] * len(kolonlar))
            insert_sql   = (
                f'INSERT INTO {pg_tablo} ({quoted_cols}) '
                f'VALUES ({placeholders})'
            )

            aktarilan = 0
            cur = pg_conn.cursor()

            try:
                # ── 1. Temizle ────────────────────────────────────────────────
                cur.execute(f'TRUNCATE TABLE {pg_tablo} RESTART IDENTITY CASCADE')
                pg_conn.commit()

                # ── 2. Tüm satırları oku ve batch'ler hâlinde gönder ──────────
                rows_iter = sq_conn.execute(f'SELECT * FROM "{tablo}"')
                batch: list = []

                for row in rows_iter:
                    batch.append(tuple(row))

                    if len(batch) >= batch_size:
                        cur.executemany(insert_sql, batch)
                        pg_conn.commit()
                        aktarilan += len(batch)
                        batch = []

                        yield MigrasyonSonuc(
                            tablo=tablo,
                            toplam=toplam,
                            aktarilan=aktarilan,
                            ara=True
                        )

                # Son batch — tek commit
                if batch:
                    cur.executemany(insert_sql, batch)
                    pg_conn.commit()
                    aktarilan += len(batch)

                # Reset sequence (identity) to match max ID
                pk_col = "kayitno" if pg_tablo == "tanim_kullanici" else "id"
                try:
                    cur.execute(f"SELECT setval(pg_get_serial_sequence('{pg_tablo}', '{pk_col}'), COALESCE(MAX({pk_col}), 1)) FROM {pg_tablo}")
                    pg_conn.commit()
                except Exception:
                    pass

                yield MigrasyonSonuc(
                    tablo=tablo,
                    toplam=toplam,
                    aktarilan=aktarilan,
                    ara=False
                )

            except Exception as exc:
                pg_conn.rollback()
                yield MigrasyonSonuc(
                    tablo=tablo,
                    toplam=toplam,
                    aktarilan=aktarilan,
                    hata=str(exc)
                )
            finally:
                cur.close()

        yield MigrasyonSonuc(tablo="", bitti=True)

    finally:
        sq_conn.close()
        pg_conn.close()
