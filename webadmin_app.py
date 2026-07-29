"""
webadmin-nakitakim Flask Uygulamasi
Port: 5050 (WEBADMIN_PORT env ile degistirilebilir)
"""
import os
import json
import hashlib
import logging
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Flask, request, jsonify, session,
    render_template_string, redirect, url_for
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('webadmin')


# ── DB Config: once db_config.json oku, yoksa env variable kullan ─────────────
def _load_pg_config() -> dict:
    """
    PostgreSQL parametrelerini su sirada arar:
    1. ~/NakitAkim/data/db_config.json  (nakitakim masaustu uygulamasi ile paylasilan config)
    2. Ortam degiskenleri (PG_HOST, PG_PASS vb.)
    3. Sabit varsayilan degerler
    """
    config_file = Path.home() / 'NakitAkim' / 'data' / 'db_config.json'
    cfg = {}
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            logger.info('DB config db_config.json dosyasindan yuklendi: %s', config_file)
        except Exception as e:
            logger.warning('db_config.json okunamadi, env variable kullanilacak: %s', e)

    return {
        'host':    os.environ.get('PG_HOST',    cfg.get('pg_host',   '127.0.0.1')),
        'port':    int(os.environ.get('PG_PORT', cfg.get('pg_port',   5432))),
        'dbname':  os.environ.get('PG_DB',      cfg.get('pg_db',     'neondb')),
        'user':    os.environ.get('PG_USER',     cfg.get('pg_user',   'postgres')),
        'password':os.environ.get('PG_PASS',     cfg.get('pg_pass',   '123')),
        'sslmode': os.environ.get('PG_SSLMODE',  cfg.get('pg_sslmode','prefer')),
    }


_PG_CFG = _load_pg_config()   # Uygulama baslarken bir kez yukle

# ── Config (ortam degiskenlerinden / db_config.json'dan) ─────────────────────
SECRET_KEY = os.environ.get('WEBADMIN_SECRET_KEY', 'fallback-secret-key-change-me')
DEBUG      = os.environ.get('WEBADMIN_DEBUG', 'false').lower() == 'true'
PORT       = int(os.environ.get('WEBADMIN_PORT', 5050))
HOST       = os.environ.get('WEBADMIN_HOST', '0.0.0.0')
API_KEY    = os.environ.get('WEBADMIN_API_KEY', 'nakit-akim-api-key-2024-secure')

# Geri uyumluluk icin (HTML template'lerinde kullaniliyor)
PG_HOST    = _PG_CFG['host']
PG_PORT    = _PG_CFG['port']
PG_DB      = _PG_CFG['dbname']
PG_USER    = _PG_CFG['user']
PG_PASS    = _PG_CFG['password']
PG_SSLMODE = _PG_CFG['sslmode']

# ── Flask App ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = SECRET_KEY


# ── DB Connection Pool ───────────────────────────────────────────────────────
# "Sifre degistirince duzeliyor" = PostgreSQL max_connections dolup tasyiyor.
# Her get_db() cagrisinda yeni baglanti acmak yerine havuzdan al/geri ver.
# Havuz max 10 baglanti — PostgreSQL'in varsayilan 100 limitinin cok altinda.
import threading as _threading
_pool      = None           # ThreadedConnectionPool — app baslarken olusturulur
_pool_lock = _threading.Lock()


def _build_dsn() -> dict:
    """psycopg2.connect() icin kwargs sozlugu."""
    cfg = _PG_CFG
    kw = dict(
        host=cfg['host'],
        port=cfg['port'],
        dbname=cfg['dbname'],
        user=cfg['user'],
        password=cfg['password'],
        sslmode=cfg['sslmode'],
        connect_timeout=15,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )
    # Neon SNI endpoint fix
    if 'neon.tech' in cfg['host']:
        endpoint_id = cfg['host'].split('.')[0]
        kw['options'] = f'project={endpoint_id}'
    return kw


def _get_pool():
    """Havuzu singleton olarak olusturur (thread-safe)."""
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            import psycopg2.pool
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,   # max 10 esz. baglanti — server catlamasin
                **_build_dsn()
            )
            logger.info('DB baglanti havuzu olusturuldu (min=1, max=10)')
    return _pool


class _PooledConn:
    """
    Context manager: 'with get_db() as conn:' seklinde kullanilir.
    Blok bitince veya exception olursa baglanti havuza iade edilir — ASLA sizmiyor.
    """
    def __init__(self):
        self._conn = None

    def __enter__(self):
        try:
            pool = _get_pool()
            self._conn = pool.getconn()
            # Kapali/broken baglantilari otomatik yenile
            if self._conn.closed:
                pool.putconn(self._conn, close=True)
                self._conn = pool.getconn()
        except Exception:
            # Havuz dolu/hatali ise dogrudan yeni baglanti ac (fallback)
            import psycopg2
            self._conn = psycopg2.connect(**_build_dsn())
            self._conn._direct = True   # havuzdan degil, dogrudan acildi
        return self._conn

    def __exit__(self, exc_type, *_):
        if self._conn is None:
            return
        try:
            if exc_type:                 # exception olduysa rollback yap
                try:
                    self._conn.rollback()
                except Exception:
                    pass
            if getattr(self._conn, '_direct', False):
                self._conn.close()       # dogrudan acilmissa kapat
            else:
                _get_pool().putconn(self._conn)  # havuza geri ver
        except Exception as _pe:
            logger.warning('DB havuz iade hatasi: %s', _pe)
        self._conn = None


def get_db():
    """
    Geriye donuk uyumluluk icin korunuyor.
    Yeni kodlarda 'with get_db_ctx() as conn:' kullanin.
    Context manager destekler: 'with get_db() as conn:'
    """
    return _PooledConn()


# ── Dekoratörler ─────────────────────────────────────────────────────────────
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-API-Key')
        if key != API_KEY:
            return jsonify({'success': False, 'error': 'Unauthorized - Gecersiz API Key'}), 401
        return f(*args, **kwargs)
    return decorated


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ── HTML Sablonlar ────────────────────────────────────────────────────────────
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IQ Finans - Webadmin Giris</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%);
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh;
}
.card {
    background: #16213e;
    border: 1px solid #0f3460;
    border-radius: 16px;
    padding: 44px 40px;
    width: 400px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}
.logo { color: #e94560; font-size: 26px; font-weight: 700; margin-bottom: 4px; }
.sub  { color: #6677aa; font-size: 13px; margin-bottom: 32px; }
label { display: block; color: #9999bb; font-size: 12px; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
input {
    width: 100%; padding: 12px 16px;
    background: #0a1628; border: 1px solid #1e3a5f;
    border-radius: 8px; color: #fff; font-size: 14px;
    margin-bottom: 20px; outline: none; transition: border 0.2s;
}
input:focus { border-color: #e94560; }
button {
    width: 100%; padding: 13px;
    background: #e94560; border: none; border-radius: 8px;
    color: #fff; font-size: 15px; font-weight: 700;
    cursor: pointer; transition: background 0.2s; letter-spacing: 0.5px;
}
button:hover { background: #c73652; }
.error {
    background: rgba(233,69,96,0.15);
    border: 1px solid #e94560;
    border-radius: 8px; padding: 12px 16px;
    color: #e94560; font-size: 13px; margin-bottom: 20px;
}
</style>
</head>
<body>
<div class="card">
  <div class="logo">IQ Finans</div>
  <div class="sub">Webadmin Yonetim Paneli</div>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
  <form method="post" autocomplete="off">
    <label>Kullanici Adi</label>
    <input type="text" name="username" placeholder="kullanici adi veya e-posta" autofocus required>
    <label>Sifre</label>
    <input type="password" name="password" placeholder="sifreniz" required>
    <button type="submit">GIRIS YAP</button>
  </form>
</div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>IQ Finans - Webadmin</title>
<style>
body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #eee; padding: 40px; }
h1   { color: #e94560; margin-bottom: 20px; }
.box { background: #16213e; border: 1px solid #0f3460; border-radius: 10px; padding: 24px; margin-bottom: 16px; }
.key { color: #6677aa; font-size: 12px; }
.val { color: #fff; font-size: 14px; font-weight: 600; margin-top: 2px; }
a    { color: #e94560; text-decoration: none; }
a:hover { text-decoration: underline; }
</style>
</head>
<body>
<h1>Webadmin Paneli</h1>
<div class="box">
  <div class="key">Hosgeldiniz</div>
  <div class="val">{{ username }}</div>
</div>
<div class="box">
  <div class="key">Sunucu</div>
  <div class="val">http://{{ host }}:{{ port }}</div>
  <div class="key" style="margin-top:12px">Veritabani</div>
  <div class="val">{{ pg_db }} @ {{ pg_host }}</div>
  <div class="key" style="margin-top:12px">API Endpoint</div>
  <div class="val">POST /api/womsis/sync</div>
</div>
<a href="/logout">Cikis Yap</a>
</body>
</html>
"""


# ── Web Route'lari ────────────────────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = (request.form.get('password') or '').strip()
        user = _authenticate(username, password)
        if user:
            session['user_id']   = user['id']
            session['username']  = user['kullanici_adi']
            session['musterino'] = user.get('musterino', 1)
            logger.info('Giris basarili: %s', username)
            return redirect(url_for('dashboard'))
        error = 'Kullanici adi veya sifre yanlis.'
        logger.warning('Basarisiz giris denemesi: %s', username)
    return render_template_string(LOGIN_HTML, error=error)


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template_string(
        DASHBOARD_HTML,
        username=session.get('username', ''),
        host=PG_HOST, port=PORT,
        pg_db=PG_DB, pg_host=PG_HOST
    )


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ── API Route'lari ────────────────────────────────────────────────────────────
@app.route('/api/womsis/sync', methods=['POST'])
@require_api_key
def api_womsis_sync():
    try:
        data      = request.get_json() or {}
        userid    = int(data.get('userid', 1))
        musterino = int(data.get('musterino', 1))
        start     = data.get('start_date') or (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        end       = data.get('end_date')   or datetime.now().strftime('%Y-%m-%d')

        creds = _get_womsis_creds(userid)
        if not creds:
            return jsonify({
                'success': False,
                'error_code': 'no_sirket_profili',
                'error': 'Bu kullanici icin Womsis bilgisi tanimli degil.'
            })

        start_dt = datetime.strptime(start, '%Y-%m-%d')
        end_dt   = datetime.strptime(end,   '%Y-%m-%d').replace(hour=23, minute=59, second=59)

        transactions = _fetch_womsis_transactions(
            creds['url'], creds['appkey'], creds['seckey'],
            start_dt, end_dt
        )

        # ── DB'ye kaydet (womsis_banka) ──────────────────────────────────────
        saved, skipped = _save_womsis_to_db(transactions, userid=userid, musterino=musterino)
        logger.info('womsis/sync: %d cekildi, %d kaydedildi, %d atlandı (userid=%d, musterino=%d)',
                    len(transactions), saved, skipped, userid, musterino)

        return jsonify({
            'success':      True,
            'count':        len(transactions),
            'saved':        saved,
            'skipped':      skipped,
            'timestamp':    datetime.now().isoformat(),
            'period':       {'start': start, 'end': end}
        })

    except Exception as e:
        logger.error('womsis/sync hatasi: %s', e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/womsis/pos-sync', methods=['POST'])
@require_api_key
def api_womsis_pos_sync():
    """
    Womsis API'den fiziksel POS (womsiPos) verilerini cekip womsi_pos tablosuna kaydeder.
    Banka hareketi sync (/api/womsis/sync) ile birebir ayni mimari.
    """
    try:
        data      = request.get_json() or {}
        userid    = int(data.get('userid', 1))
        musterino = int(data.get('musterino', 1))
        start     = data.get('start_date') or (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        end       = data.get('end_date')   or datetime.now().strftime('%Y-%m-%d')

        creds = _get_womsis_creds(userid)
        if not creds:
            return jsonify({
                'success': False,
                'error_code': 'no_sirket_profili',
                'error': 'Bu kullanici icin Womsis bilgisi tanimli degil.'
            })

        start_dt = datetime.strptime(start, '%Y-%m-%d')
        end_dt   = datetime.strptime(end,   '%Y-%m-%d').replace(hour=23, minute=59, second=59)

        transactions = _fetch_womsis_pos_transactions(
            creds['url'], creds['appkey'], creds['seckey'],
            start_dt, end_dt
        )

        saved, skipped = _save_womsis_pos_to_db(transactions, userid=userid, musterino=musterino)
        logger.info('womsis/pos-sync: %d cekildi, %d kaydedildi, %d atlandi (userid=%d, musterino=%d)',
                    len(transactions), saved, skipped, userid, musterino)

        return jsonify({
            'success':   True,
            'count':     len(transactions),
            'saved':     saved,
            'skipped':   skipped,
            'timestamp': datetime.now().isoformat(),
            'period':    {'start': start, 'end': end}
        })

    except Exception as e:
        logger.error('womsis/pos-sync hatasi: %s', e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/womsis/test', methods=['POST'])
@require_api_key
def api_womsis_test():
    try:
        data   = request.get_json() or {}
        userid = int(data.get('userid', 1))
        creds  = _get_womsis_creds(userid)
        if not creds:
            return jsonify({'success': False, 'error': 'Womsis bilgisi tanimli degil.'})

        import requests as req
        url  = creds['url'].rstrip('/') + '/authenticate'
        resp = req.post(
            url,
            json={'app_key': creds['appkey'], 'app_secret': creds['seckey']},
            timeout=15
        )
        token = resp.json().get('token')
        if token:
            return jsonify({'success': True, 'message': 'Womsis baglantisi basarili.'})
        return jsonify({'success': False, 'error': 'Token alinamadi.'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/womsis/status', methods=['GET'])
@require_api_key
def api_womsis_status():
    return jsonify({
        'success':   True,
        'status':    'ok',
        'timestamp': datetime.now().isoformat(),
        'server':    f'{HOST}:{PORT}'
    })


@app.route('/api/womsis/accounts', methods=['GET'])
@require_api_key
def api_womsis_accounts():
    try:
        userid = int(request.args.get('userid', 1))
        creds  = _get_womsis_creds(userid)
        if not creds:
            return jsonify({'success': False, 'error': 'Womsis bilgisi tanimli degil.'})

        import requests as req
        auth_url = creds['url'].rstrip('/') + '/authenticate'
        resp  = req.post(auth_url, json={'app_key': creds['appkey'], 'app_secret': creds['seckey']}, timeout=15)
        token = resp.json().get('token')
        if not token:
            return jsonify({'success': False, 'error': 'Token alinamadi.'})

        acc_url  = creds['url'].rstrip('/') + '/accounts'
        aresp    = req.get(acc_url, headers={'Authorization': f'Bearer {token}'}, timeout=20)
        accounts = aresp.json().get('accounts', [])
        return jsonify({'success': True, 'accounts': accounts})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Yardimci Fonksiyonlar ─────────────────────────────────────────────────────
def _authenticate(username: str, password: str):
    """uyelik tablosundan kullanici dogrula — duz metin / MD5 / bcrypt."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT id, kullanici_adi, sifre, musterino
                   FROM uyelik
                   WHERE kullanici_adi = %s OR eposta = %s
                   LIMIT 1""",
                (username, username)
            )
            row = cur.fetchone()
            cur.close()

            if not row:
                return None

            uid, uname, stored, musterino = row
            stored = stored or ''

            # 1. Duz metin
            if stored == password:
                return {'id': uid, 'kullanici_adi': uname, 'musterino': musterino or 1}

            # 2. MD5
            if stored == hashlib.md5(password.encode()).hexdigest():
                return {'id': uid, 'kullanici_adi': uname, 'musterino': musterino or 1}

            # 3. Bcrypt ($2y$ PHP uyumu)
            try:
                import bcrypt
                check = stored.replace('$2y$', '$2b$', 1).encode()
                if bcrypt.checkpw(password.encode(), check):
                    return {'id': uid, 'kullanici_adi': uname, 'musterino': musterino or 1}
            except Exception:
                pass

            return None
    except Exception as e:
        logger.error('Kimlik dogrulama DB hatasi: %s', e)
        return None


def _get_womsis_creds(userid: int):
    """vomsisbilgileri tablosundan Womsis bilgilerini getir."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT appkey, seckey, url FROM vomsisbilgileri WHERE userid = %s LIMIT 1",
                (userid,)
            )
            row = cur.fetchone()
            cur.close()
            if row:
                return {
                    'appkey': row[0] or '',
                    'seckey': row[1] or '',
                    'url':    row[2] or 'https://developers.vomsis.com/api/v2'
                }
            return None
    except Exception as e:
        logger.error('Womsis creds DB hatasi: %s', e)
        return None


def _fetch_womsis_transactions(api_url, app_key, app_secret, start_dt, end_dt):
    """Womsis API'den 7 gunluk parcalar halinde tum islemleri cek."""
    import requests as req
    from urllib.parse import urlencode

    # Token al
    auth_url = api_url.rstrip('/') + '/authenticate'
    resp  = req.post(auth_url, json={'app_key': app_key, 'app_secret': app_secret}, timeout=15)
    token = resp.json().get('token')
    if not token:
        raise ValueError('Womsis token alinamadi: ' + str(resp.json()))

    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
    results = []
    current = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)

    while current < end_dt:
        chunk_end = min(current + timedelta(days=6), end_dt).replace(hour=23, minute=59, second=59)
        params    = urlencode({
            'beginDate': current.strftime('%d-%m-%Y %H:%M:%S'),
            'endDate':   chunk_end.strftime('%d-%m-%Y %H:%M:%S')
        })
        tx_url = f"{api_url.rstrip('/')}/transactions?{params}"
        try:
            r = req.get(tx_url, headers=headers, timeout=30)
            results.extend(r.json().get('transactions', []))
        except Exception as ce:
            logger.warning('Chunk [%s] hatasi: %s', current.date(), ce)
        current = (current + timedelta(days=7)).replace(hour=0, minute=0, second=0)

    return results


def _fetch_womsis_pos_transactions(api_url, app_key, app_secret, start_dt, end_dt):
    """
    Womsis API'den fiziksel POS islemlerini cek.
    PHP: womsisPosIsle.php mantigi — once terminal listesi al,
    sonra her terminal icin /pos-rapor/stations/{id}/transactions endpoint'ini
    14 gunluk parcalar halinde sorgula.
    """
    import requests as req
    from urllib.parse import urlencode

    CHUNK_DAYS = 14  # PHP: $CHUNK_DAYS = 14

    # ── 1. Token al (PHP: vomsisReq authenticate) ────────────────────────────
    auth_url = api_url.rstrip('/') + '/authenticate'
    resp  = req.post(auth_url, json={'app_key': app_key, 'app_secret': app_secret}, timeout=15)
    token = resp.json().get('token')
    if not token:
        raise ValueError('Womsis token alinamadi (pos-sync): ' + str(resp.json()))

    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}

    # ── 2. Terminal (station) listesi al (PHP: /pos-rapor/stations) ──────────
    stations_url  = api_url.rstrip('/') + '/pos-rapor/stations'
    stations_resp = req.get(stations_url, headers=headers, timeout=20)
    stations      = stations_resp.json().get('data', [])

    if not stations:
        logger.info('pos-sync: Sistemde kayitli fiziksel POS terminali bulunamadi.')
        return []

    # ── 3. 14 gunluk chunk'lar olustur (PHP: $CHUNK_DAYS = 14) ───────────────
    chunks  = []
    current = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    while current <= end_dt:
        chunk_end = min(current + timedelta(days=CHUNK_DAYS - 1), end_dt)
        chunks.append({
            'begin': current.strftime('%d-%m-%Y'),
            'end':   chunk_end.strftime('%d-%m-%Y'),
        })
        current = chunk_end + timedelta(days=1)
        current = current.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── 4. Her terminal x her chunk icin islemleri cek ────────────────────────
    results = []
    for station in stations:
        station_id   = station.get('id')
        station_no   = station.get('station_no') or station.get('id') or ''
        workplace_no = station.get('workplace_no') or ''
        bank_title   = station.get('bank_title') or station.get('bank_name') or ''

        if not station_id:
            continue

        for chunk in chunks:
            tx_url = (
                f"{api_url.rstrip('/')}/pos-rapor/stations/{station_id}/transactions?"
                + urlencode({'beginDate': chunk['begin'], 'endDate': chunk['end']})
            )
            try:
                r    = req.get(tx_url, headers=headers, timeout=30)
                data = r.json()
                txs  = data.get('transactions', [])
                # Her islem kaydina terminal bilgisini ekle (alan esleme icin)
                for tx in txs:
                    tx.setdefault('_station_no',   str(station_no))
                    tx.setdefault('_workplace_no', str(workplace_no))
                    tx.setdefault('_bank_title',   str(bank_title))
                results.extend(txs)
                logger.info('pos-sync terminal=%s chunk [%s → %s]: %d kayit',
                            station_id, chunk['begin'], chunk['end'], len(txs))
            except Exception as ce:
                logger.warning('POS terminal=%s chunk [%s] hatasi: %s',
                               station_id, chunk['begin'], ce)

    return results


def _save_womsis_pos_to_db(transactions: list, userid: int = 1, musterino: int = 1) -> tuple:
    """
    Womsis API'den gelen POS islemlerini womsi_pos tablosuna kaydeder.
    Mukerrer onleme: isyeriNo + islemTarihi + islemTutari + kartNo kombinasyonu.
    Returns: (kaydedilen, atlanan)
    """
    if not transactions:
        return 0, 0

    saved   = 0
    skipped = 0
    now     = datetime.now()

    try:
        with get_db() as conn:
            cur = conn.cursor()

            # womsi_pos tablosunu olustur (yoksa)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS womsi_pos (
                    id                   SERIAL PRIMARY KEY,
                    userid               INTEGER NOT NULL DEFAULT 0,
                    musterino            INTEGER NOT NULL DEFAULT 1,
                    isyerino             TEXT    DEFAULT '',
                    carihesap            TEXT    DEFAULT '',
                    hesabagecistarihi    TEXT    DEFAULT '',
                    islemtutari          NUMERIC DEFAULT 0,
                    islemtarihi          TEXT    DEFAULT '',
                    posno                TEXT    DEFAULT '',
                    isyeriucretitutar    NUMERIC DEFAULT 0,
                    nettutar             NUMERIC DEFAULT 0,
                    brand                TEXT    DEFAULT '',
                    kartno               TEXT    DEFAULT '',
                    islemtipi            TEXT    DEFAULT '',
                    aciklama             TEXT    DEFAULT '',
                    islemtarih           TEXT    DEFAULT '',
                    kayittarihi          TEXT    DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

            for tx in transactions:
                # ── Alan eslemeleri — PHP womsisPosIsle.php ile birebir esleme ──
                isyerino          = str(
                    tx.get('_workplace_no') or tx.get('workplace')  or
                    tx.get('isyeriNo')      or tx.get('merchantNo') or tx.get('shopCode') or ''
                )
                carihesap         = str(
                    tx.get('_bank_title') or tx.get('cariHesap') or
                    tx.get('accountNo')   or tx.get('account')    or ''
                )
                hesabagecistarihi = str(
                    tx.get('valor')                    or tx.get('transfer_to_account_date') or
                    tx.get('settlementDate')            or tx.get('hesabaGecisTarihi') or
                    tx.get('valueDate')                 or ''
                )
                islemtarihi       = str(
                    tx.get('date') or tx.get('transactionDate') or tx.get('islemTarihi') or ''
                )
                posno             = str(
                    tx.get('station')    or tx.get('_station_no') or tx.get('terminalId') or
                    tx.get('posNo')      or tx.get('terminal')    or ''
                )
                brand             = str(
                    tx.get('sub_card_type') or tx.get('card_type') or tx.get('cardBrand') or
                    tx.get('brand')         or tx.get('scheme')    or ''
                )
                kartno            = str(
                    tx.get('card_number') or tx.get('maskedCardNo') or
                    tx.get('kartNo')      or tx.get('cardNo')       or ''
                )
                islemtipi         = str(
                    tx.get('transaction_type') or tx.get('transactionType') or
                    tx.get('islemTipi')        or tx.get('type') or ''
                )
                aciklama   = str(tx.get('description') or tx.get('aciklama') or '')[:255]
                islemtarih = now.strftime('%d/%m/%Y')  # PHP: date('d/m/Y')

                try:
                    islemtutari       = round(abs(float(
                        tx.get('gross_amount') or tx.get('amount') or tx.get('islemTutari') or 0
                    )), 2)
                    isyeriucretitutar = round(abs(float(
                        tx.get('commission') or tx.get('commissionAmount') or
                        tx.get('isyeriUcretiTutar') or tx.get('fee') or 0
                    )), 2)
                    nettutar = round(abs(float(
                        tx.get('net_amount') or tx.get('netAmount') or
                        tx.get('netTutar')   or tx.get('net') or 0
                    )), 2)
                except (ValueError, TypeError):
                    islemtutari = isyeriucretitutar = nettutar = 0.0

                # ── Mukerrer kontrolu ──
                cur.execute(
                    'SELECT id FROM womsi_pos '
                    'WHERE userid=%s AND isyerino=%s AND islemtarihi=%s '
                    'AND islemtutari=%s AND kartno=%s LIMIT 1',
                    (userid, isyerino, islemtarihi, islemtutari, kartno)
                )
                if cur.fetchone():
                    skipped += 1
                    continue

                cur.execute("""
                    INSERT INTO womsi_pos
                        (userid, musterino, isyerino, carihesap, hesabagecistarihi,
                         islemtutari, islemtarihi, posno,
                         isyeriucretitutar, nettutar, brand,
                         kartno, islemtipi, aciklama, islemtarih, kayittarihi)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    userid, musterino, isyerino, carihesap, hesabagecistarihi,
                    islemtutari, islemtarihi, posno,
                    isyeriucretitutar, nettutar, brand,
                    kartno, islemtipi, aciklama, islemtarih,
                    now.strftime('%Y-%m-%d %H:%M:%S')
                ))
                saved += 1

            conn.commit()
            cur.close()
    except Exception as e:
        logger.error('womsi_pos DB kayit hatasi: %s', e, exc_info=True)

    return saved, skipped


def _save_womsis_to_db(transactions: list, userid: int = 1, musterino: int = 1) -> tuple[int, int]:
    """
    Womsis API'den gelen islemleri womsis_banka tablosuna kaydeder.
    Ayni womsiskey varsa atlar (mukerrer kayit onleme).
    Returns: (kaydedilen, atlanan)
    """
    if not transactions:
        return 0, 0

    saved   = 0
    skipped = 0
    now     = datetime.now()

    try:
        with get_db() as conn:
            cur = conn.cursor()

            for tx in transactions:
                account_id = str(tx.get('accountId') or tx.get('account_id') or '')
                tx_id      = str(tx.get('id') or tx.get('transactionId') or '')
                womsiskey  = f"{account_id}_{tx_id}" if account_id and tx_id else ''

                raw_tarih = str(tx.get('date') or tx.get('transactionDate') or tx.get('valueDate') or '')
                tarih_iso = None
                for fmt in ('%Y-%m-%d', '%d-%m-%Y %H:%M:%S', '%d-%m-%Y', '%Y-%m-%dT%H:%M:%S'):
                    try:
                        tarih_iso = datetime.strptime(raw_tarih[:len(fmt)], fmt).strftime('%Y-%m-%d')
                        break
                    except Exception:
                        continue
                if not tarih_iso:
                    tarih_iso = now.strftime('%Y-%m-%d')

                tutar_raw  = tx.get('amount') or tx.get('tutar') or 0
                tutar      = abs(float(tutar_raw))
                debit      = float(tx.get('debit')  or 0)
                credit     = float(tx.get('credit') or 0)
                if credit > 0 and debit == 0:
                    gelirgider = 'gelir'
                elif debit > 0 and credit == 0:
                    gelirgider = 'gider'
                else:
                    gelirgider = 'gelir' if float(tutar_raw) >= 0 else 'gider'

                aciklama   = str(tx.get('description') or tx.get('aciklama') or '')[:255]
                sube       = str(tx.get('accountName') or tx.get('bankName') or tx.get('sube') or '')
                iban       = str(tx.get('iban') or '')
                bakiye     = float(tx.get('balance') or tx.get('bakiye') or 0)
                hesap_turu = str(tx.get('currency') or tx.get('hesap_turu') or 'TL')
                dekont_no  = str(tx.get('referenceNo') or tx.get('dekont_no') or '')

                if womsiskey:
                    cur.execute(
                        'SELECT id FROM womsis_banka WHERE womsiskey = %s AND userid = %s LIMIT 1',
                        (womsiskey, userid)
                    )
                    if cur.fetchone():
                        skipped += 1
                        continue

                cur.execute("""
                    INSERT INTO womsis_banka
                        (userid, musterino, tarih, aciklama, gelirgider, tutar,
                         sube, faturaunvan, womsiskey, kaynak,
                         created_at, bakiye, iban, hesap_turu, dekont_no)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    userid, musterino, tarih_iso, aciklama, gelirgider, tutar,
                    sube, '-', womsiskey, 'womsis_scheduler',
                    now, bakiye, iban, hesap_turu, dekont_no
                ))
                saved += 1

            conn.commit()
            cur.close()
    except Exception as e:
        logger.error('womsis DB kayit hatasi: %s', e, exc_info=True)

    return saved, skipped


# ── Hata Yoneticileri ─────────────────────────────────────────────────────────
@app.errorhandler(500)
def handle_500(e):
    logger.error('500 hatasi: %s', e, exc_info=True)
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Sunucu hatasi: ' + str(e)}), 500
    return f'<h2>Sunucu Hatasi</h2><pre>{e}</pre>', 500


@app.errorhandler(404)
def handle_404(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Endpoint bulunamadi.'}), 404
    return redirect(url_for('login'))


# ── Baslat ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    logger.info('=' * 50)
    logger.info('webadmin-nakitakim basliyor')
    logger.info('Adres  : http://%s:%s', HOST, PORT)
    logger.info('DB     : %s@%s:%s/%s (ssl=%s)', PG_USER, PG_HOST, PG_PORT, PG_DB, PG_SSLMODE)
    logger.info('Debug  : %s', DEBUG)
    logger.info('=' * 50)
    # threaded=True: zamanlayici ile UI istekleri birbirini bloklamasin
    app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True)
