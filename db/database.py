"""
Veritabanı bağlantı yöneticisi — SQLite ve PostgreSQL otomatik routing.

Mod, ~/NakitAkim/data/db_config.json içinden okunur:
  mode = 'sqlite'   → SQLite (lokal, varsayılan)
  mode = 'postgres' → PostgreSQL (Supabase, sunucu)

_PgWrapper sayesinde psycopg2 bağlantısı sqlite3 gibi kullanılır:
  - conn.execute(sql, params)  → çalışır
  - conn.executemany(...)      → çalışır
  - conn.row_factory = ...     → DictCursor ile karşılanır
  - conn.lastrowid             → RETURNING ile desteklenir
  - ? parametreleri            → otomatik %s'e dönüştürülür

Servis kodları hiç değişmeden her iki modda çalışır.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from db.schema import SCHEMA_SQL

# ── SQLite yolu ───────────────────────────────────────────────────────────────
DB_DIR  = Path.home() / "NakitAkim" / "data"
DB_PATH = DB_DIR / "nakit_akim.db"


def get_db_path() -> Path:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    return DB_PATH


# ── sqlite3 ? → psycopg2 %s dönüşümü ────────────────────────────────────────

def _to_pg_sql(sql: str) -> str:
    """sqlite3'ün ? parametresini psycopg2'nin %s parametresine çevirir.

    Kurallar:
    1. String literalleri içindeki ? korunur.
    2. String literalleri içindeki % → %% (psycopg2 escape) olarak değiştirilir.
    3. String literalleri dışındaki ? → %s olarak değiştirilir.
    """
    result = []
    in_str = False
    str_char = None
    i = 0
    while i < len(sql):
        c = sql[i]
        if in_str:
            if c == '%':
                # psycopg2 için % → %% (string içinde wildcard korunur)
                result.append('%%')
            elif c == str_char:
                in_str = False
                result.append(c)
            else:
                result.append(c)
        elif c in ("'", '"'):
            in_str = True
            str_char = c
            result.append(c)
        elif c == '?':
            result.append('%s')
        else:
            result.append(c)
        i += 1
    return ''.join(result)


# ── PostgreSQL cursor wrapper (sqlite3.Cursor uyumlu) ────────────────────────

class _PgCursor:
    """psycopg2 cursor'ını sqlite3.Cursor gibi davranır hale getirir."""

    def __init__(self, pg_cur, pg_conn_raw):
        self._cur = pg_cur
        self._conn = pg_conn_raw
        self.lastrowid: int | None = None
        self.rowcount: int = -1

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur.fetchall())

    def keys(self):
        if self._cur.description:
            return [d[0] for d in self._cur.description]
        return []

    def close(self):
        self._cur.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ── PostgreSQL connection wrapper (sqlite3.Connection uyumlu) ─────────────────

class _PgWrapper:
    """
    psycopg2 bağlantısını sqlite3.Connection API'siyle uyumlu hale getirir.

    Servis kodları değişmeden her iki modda çalışır:
        conn = get_connection()
        row  = conn.execute("SELECT * FROM t WHERE id=?", (1,)).fetchone()
        conn.commit()
        conn.close()
    """

    # sqlite3 row_factory atamasını yut (DictCursor zaten aynı işi yapar)
    row_factory = None

    def __init__(self, pg_conn):
        self._conn = pg_conn

    # ── Temel API ────────────────────────────────────────────────────────────

    def execute(self, sql: str, params=()):
        import psycopg2.extras
        sql = _to_pg_sql(sql)
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute(sql, params or ())

        wrapper = _PgCursor(cur, self._conn)
        wrapper.rowcount = cur.rowcount

        # lastrowid: psycopg2'de RETURNING yok ise lastval() dene
        if sql.strip().upper().startswith("INSERT"):
            try:
                # Önce RETURNING id var mı bak
                if "RETURNING" in sql.upper():
                    row = cur.fetchone()
                    if row:
                        wrapper.lastrowid = row[0]
                else:
                    # SERIAL sütun varsa lastval() çalışır
                    lv_cur = self._conn.cursor()
                    lv_cur.execute("SELECT lastval()")
                    wrapper.lastrowid = lv_cur.fetchone()[0]
                    lv_cur.close()
            except Exception:
                wrapper.lastrowid = None

        return wrapper

    def executemany(self, sql: str, params_list):
        sql = _to_pg_sql(sql)
        cur = self._conn.cursor()
        cur.executemany(sql, params_list)
        cur.close()

    def executescript(self, script: str):
        """SQLite executescript → psycopg2'de ifade ifade çalıştır."""
        cur = self._conn.cursor()
        # Her ifadeyi ; ile böl ve çalıştır
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    cur.execute(stmt)
                except Exception:
                    pass
        cur.close()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        """Bağlantıyı KAPATMAZ — pool'da saklı kalır.
        (Commit, servis kodları tarafından açıkça yapılır.)
        """
        pass  # Bağlantı pool'da canlı kalır

    def cursor(self):
        import psycopg2.extras
        return self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # ── Pragma'ları yut (SQLite'a özgü) ─────────────────────────────────────

    def _noop(self, *_, **__):
        pass

    # ── Context manager ──────────────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        # close() çağrılmaz — bağlantı pool'da kalır
        return False


# ── Ana bağlantı fonksiyonu (akıllı routing) ─────────────────────────────────

def get_connection():
    """
    Aktif moda göre bağlantı döndürür.

    SQLite modu  → sqlite3.Connection  (row_factory=sqlite3.Row ile)
    Postgres modu → _PgWrapper          (sqlite3 uyumlu psycopg2 sarmalayıcı)

    Her çağrıda yeni bağlantı açılır (thread-safe).
    """
    from db.db_config import get_mode
    if get_mode() == "postgres":
        return _get_pg_connection()
    return _get_sqlite_connection()


def _get_sqlite_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


# ── PostgreSQL Bağlantı Havuzu (Thread-Local Persistent) ───────────────────────
# Her thread bir kez bağlanır, sonraki çağrılarda aynı bağlantıyı kullanır.
# Bağlantı kesildiğinde otomatik yeniden bağlanır.

_pg_local = threading.local()   # her thread için ayrı alan


def _try_pg_connect(params: dict):
    """
    Tek bir psycopg2.connect() denemesi.
    Bağlantı kurulamazsa anlamlı hata mesajıyla RuntimeError fırlatır.
    """
    import psycopg2
    try:
        raw = psycopg2.connect(**params)
        raw.autocommit = False
        return raw
    except psycopg2.OperationalError as exc:
        msg = str(exc).lower()
        if "connection refused" in msg or "timeout" in msg or "could not connect" in msg:
            raise RuntimeError(
                f"Sunucuya bağlanılamadı ({params['host']}:{params['port']}).\n"
                "Olası nedenler:\n"
                "  • İnternet bağlantısı yok\n"
                "  • Cloudflare WARP / VPN çalışmıyor\n"
                "  • Port güvenlik duvarı tarafından engellendi\n"
                f"Hata detayı: {exc}"
            ) from exc
        raise RuntimeError(str(exc)) from exc


def _get_pg_connection() -> _PgWrapper:
    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError(
            "psycopg2 yüklü değil.\n"
            "Terminal'de: pip install psycopg2-binary"
        ) from exc

    from db.db_config import get_pg_params

    # Mevcut bağlantı varsa sağlık kontrolü yap
    raw = getattr(_pg_local, "conn", None)
    if raw is not None and not raw.closed:
        try:
            raw.rollback()
            return _PgWrapper(raw)
        except Exception:
            try:
                raw.close()
            except Exception:
                pass
            _pg_local.conn = None

    params = get_pg_params()

    # ── Port fallback: 5432 → 6543 (Supabase transaction mode) ──────────────
    # Supabase hem 5432 (session mode) hem 6543 (transaction mode) destekler.
    # Bazı ağlar / ISP'ler 5432'yi engeller; 6543 genellikle açıktır.
    primary_port   = int(params.get("port", 5432))
    fallback_ports = [primary_port]
    if primary_port == 5432:
        fallback_ports.append(6543)   # Supabase Supavisor transaction port
    elif primary_port == 6543:
        fallback_ports.append(5432)

    last_exc: Exception | None = None
    for port in fallback_ports:
        attempt_params = dict(params)
        attempt_params["port"] = port
        # İlk port için normal timeout, fallback için biraz daha fazla ver
        attempt_params["connect_timeout"] = 10 if port == primary_port else 15
        try:
            print(f"[DB] PG bağlantısı deneniyor: {attempt_params['host']}:{port} ...")
            new_raw = _try_pg_connect(attempt_params)
            _pg_local.conn = new_raw
            if port != primary_port:
                print(f"[DB] Fallback port {port} ile bağlantı kuruldu ✅")
                # Başarılı portu config'e yaz (bir sonraki çalıştırmada direkt doğru port)
                try:
                    from db.db_config import load_config, save_config
                    cfg = load_config()
                    cfg["pg_port"] = port
                    save_config(cfg)
                    print(f"[DB] db_config.json güncellendi: port={port}")
                except Exception:
                    pass
            else:
                print(f"[DB] PG bağlantısı kuruldu ✅ (port {port})")
            return _PgWrapper(new_raw)
        except RuntimeError as exc:
            last_exc = exc
            print(f"[DB] Port {port} başarısız: {exc}")
            continue

    # Her iki port da başarısız
    raise last_exc or RuntimeError("PostgreSQL bağlantısı kurulamadı.")



def close_pg_pool():
    """Thread'in bağlantısını kapat (uygulama kapanırken çağrılır)."""
    raw = getattr(_pg_local, "conn", None)
    if raw:
        try:
            raw.close()
        except Exception:
            pass
        _pg_local.conn = None



# ── Şema yönetimi ─────────────────────────────────────────────────────────────

def initialize_db():
    """SQLite şemasını oluşturur ve uyelik tablosu boşsa superadmin/123 ekler.
    IF NOT EXISTS — güvenli tekrar çalıştırma.
    """
    conn = _get_sqlite_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        # uyelik tablosu boşsa superadmin/123 otomatik ekle
        count = conn.execute("SELECT COUNT(*) FROM uyelik").fetchone()[0]
        if count == 0:
            conn.execute("""
                INSERT OR IGNORE INTO uyelik
                    (kullanici_adi, sifre, yetki, firmaAdi,
                     hesapTuru, bagli_hesap, altKullaniciSayisi)
                VALUES ('superadmin', '123', 'superadmin', 'IQ Finans', 0, -1, 0)
            """)
            conn.commit()
            print("[DB] SQLite: superadmin kullanıcısı oluşturuldu.")

        print(f"[DB] SQLite hazır: {DB_PATH}")
    finally:
        conn.close()



def initialize_pg_schema():
    """
    PostgreSQL şemasını oluşturur (IF NOT EXISTS).
    Startup'ta arka planda çağırılır; bağlantı yoksa sessizce atlanır.
    """
    try:
        from db.pg_schema import PG_TABLES, PG_INDEXES
        raw_conn = _get_pg_connection()
        cur = raw_conn.cursor()
        for _name, ddl in PG_TABLES:
            cur.execute(ddl)
        for idx_sql in PG_INDEXES:
            try:
                cur.execute(idx_sql)
            except Exception:
                pass
        raw_conn.commit()
        cur.close()
        raw_conn.close()
        print("[DB] PostgreSQL şema hazır.")
    except Exception as exc:
        print(f"[DB] PostgreSQL şema oluşturulamadı: {exc}")


def ensure_pg_ready() -> bool:
    """
    PostgreSQL modunda sıfırdan kurulum sağlar:
    1. şema yoksa oluşturur.
    2. uyelik tablosu boşsa superadmin / 123 kullanıcısını ekler.

    Returns:
        True  — başarılı (uygulama çalışabilir)
        False — PG bağlantısı kurulamadı
    """
    try:
        from db.pg_schema import PG_TABLES, PG_INDEXES
        conn = _get_pg_connection()
        cur = conn._conn.cursor()

        # 1. Tablo şemasını oluştur
        for _name, ddl in PG_TABLES:
            cur.execute(ddl)
        for idx_sql in PG_INDEXES:
            try:
                cur.execute(idx_sql)
            except Exception:
                pass
        conn.commit()

        # 2. uyelik tablosu boşsa superadmin ekle
        cur.execute("SELECT COUNT(*) FROM uyelik")
        count = cur.fetchone()[0]
        if count == 0:
            cur.execute("""
                INSERT INTO uyelik
                    (kullanici_adi, sifre, yetki, firmaAdi,
                     hesapTuru, bagli_hesap, altKullaniciSayisi)
                VALUES ('superadmin', '123', 'superadmin', 'IQ Finans', 0, -1, 0)
                ON CONFLICT DO NOTHING
            """)
            conn.commit()
            print("[DB] PostgreSQL: superadmin kullanıcısı oluşturuldu.")

        cur.close()
        conn.close()
        print("[DB] PostgreSQL hazır.")
        return True
    except Exception as exc:
        print(f"[DB] ensure_pg_ready hata: {exc}")
        return False



def db_exists() -> bool:
    """Veritabanında kayıt olup olmadığını kontrol eder."""
    from db.db_config import get_mode
    if get_mode() == "postgres":
        try:
            conn = _get_pg_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT EXISTS("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_name='uyelik'"
                ")"
            )
            exists = cur.fetchone()[0]
            cur.close()
            conn.close()
            return bool(exists)
        except Exception:
            return False
    # SQLite modu
    if not DB_PATH.exists():
        return False
    conn = _get_sqlite_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='table' AND name='hareketler'"
        ).fetchone()[0]
        return count > 0
    finally:
        conn.close()
