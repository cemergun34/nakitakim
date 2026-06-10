"""
IQ Finans — Nakit Akış Masaüstü Uygulaması
Giriş noktası.
"""
import sys
import warnings

# macOS LibreSSL / urllib3 uyumsuzluk uyarısını bastır (sadece uyarı, hata değil)
warnings.filterwarnings("ignore", message=".*LibreSSL.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")
try:
    from urllib3.exceptions import NotOpenSSLWarning
    warnings.filterwarnings("ignore", category=NotOpenSSLWarning)
except ImportError:
    pass

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

# QWebEngineView macOS'ta QApplication'dan ÖNCE initialize edilmeli
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    import PyQt6.QtWebEngineCore                         # noqa: F401
except ImportError:
    pass


# ── PostgreSQL sıfırdan kurulum thread'i ──────────────────────────────────────

class _PgSetupThread(QThread):
    """
    PostgreSQL modunda arka planda:
     - Şema oluşturur (IF NOT EXISTS)
     - uyelik tablosu boşsa superadmin/123 ekler
    UI donmaz.
    """
    done = pyqtSignal(bool, str)   # (başarılı, mesaj)

    def run(self):
        try:
            from db.database import ensure_pg_ready
            ok = ensure_pg_ready()
            self.done.emit(ok, "")
        except Exception as exc:
            self.done.emit(False, str(exc))


def main():
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    app = QApplication(sys.argv)
    app.setApplicationName("IQ Finans")
    app.setOrganizationName("FPPRO")

    # Sistem fontunu seç
    if sys.platform == "darwin":
        font = QFont(".AppleSystemUIFont", 13)
    elif sys.platform == "win32":
        font = QFont("Segoe UI", 9)
    else:
        font = QFont("Ubuntu", 10)
    app.setFont(font)

    # ── Veritabanını başlat ────────────────────────────────────────────
    from db.db_config import get_mode
    from db.database import initialize_db

    # ── FPPRO fabrika ayarları (ilk kurulumda bir kez çalışır) ─────────────
    try:
        from bootstrap_fppro import run_bootstrap
        run_bootstrap(force=False)   # sentinel varsa otomatik atlanır
    except Exception as _bs_exc:
        print(f"[Bootstrap] Uyarı: {_bs_exc}")

    mode = get_mode()

    # SQLite şeması her zaman hazırlanır (hızlı, yerel, fallback için gerekli)
    initialize_db()

    # ── SQLite modu: DB yoksa sessizce oluştur ────────────────────────────
    if mode != "postgres":
        import sqlite3 as _sqlite3
        from db.database import DB_PATH as _DB_PATH

        def _sqlite_has_data() -> bool:
            """uyelik tablosu var ve dolu mu?"""
            if not _DB_PATH.exists():
                return False
            try:
                conn = _sqlite3.connect(str(_DB_PATH))
                count = conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master "
                    "WHERE type='table' AND name='uyelik'"
                ).fetchone()[0]
                conn.close()
                return count > 0
            except Exception:
                return False

        if not _sqlite_has_data():
            # Yeni makine / ilk çalıştırma — sessizce şema oluştur
            # initialize_db() zaten superadmin/123 ekliyor (uyelik boşsa)
            print("[DB] Yeni kurulum: veritabanı ve superadmin kullanıcısı oluşturuluyor...")
            from db.database import initialize_db as _reinit
            _reinit()
            print("[DB] Sessiz kurulum tamamlandı — superadmin / 123 ile giriş yapabilirsiniz.")

    # ── Giriş ekranı ─────────────────────────────────────────────────
    from ui.screens.login_screen import LoginScreen
    from ui.main_window import MainWindow

    _state = {"user": None, "main_win": None}

    login_screen = LoginScreen()
    login_screen.setWindowTitle("IQ Finans — Giriş")
    login_screen.resize(1100, 700)
    login_screen.show()

    # ── PostgreSQL modu: arka planda şema + superadmin kur ────────────
    if mode == "postgres":
        _pg_setup = _PgSetupThread()

        def _on_pg_setup_done(ok: bool, msg: str):
            # Arka planda sessizce çalışır — banner login butonuna basılınca gösterilir
            if not ok:
                print(f"[DB] PG setup hata: {msg}")
            else:
                print("[DB] PostgreSQL hazır.")

        _pg_setup.done.connect(_on_pg_setup_done)
        _pg_setup.start()
        app._pg_setup = _pg_setup  # GC'den korunmak için referans sakla

    def _on_login(user: dict):
        _state["user"] = user
        app.setQuitOnLastWindowClosed(False)
        login_screen.hide()

        win = MainWindow(user)
        _state["main_win"] = win

        def _on_logout():
            app.setQuitOnLastWindowClosed(False)
            win.close()
            _state["main_win"] = None
            # Login alanlarını temizle
            login_screen.username_input.clear()
            login_screen.password_input.clear()
            login_screen.error_lbl.hide()
            login_screen.login_btn.setEnabled(True)
            login_screen.login_btn.setText("GİRİŞ YAP")
            login_screen.show()
            app.setQuitOnLastWindowClosed(True)

        win.logout_requested.connect(_on_logout)
        win.show()
        app.setQuitOnLastWindowClosed(True)
        login_screen.hide()

        # ── Otomatik webadmin Sync ────────────────────────────────────────────
        # Login sonrası, DB'de webadmin yapılandırması varsa otomatik çek.
        # Kullanıcı hiçbir butona basmak zorunda kalmaz.
        def _auto_webadmin_sync():
            userid = user.get("id") or user.get("userid")
            if not userid:
                return
            try:
                from services.webadmin_client import get_webadmin_config
                cfg = get_webadmin_config(userid)
                if not cfg.get("enabled"):
                    return   # Bu kullanıcı için webadmin tanımlı değil

                from datetime import datetime, timedelta
                from ui.screens.ayarlar_screen import WebAdminSyncDialog
                start_str = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
                end_str   = datetime.now().strftime("%Y-%m-%d")

                dlg = WebAdminSyncDialog(
                    userid=userid,
                    start_str=start_str,
                    end_str=end_str,
                    parent=win,
                )
                dlg.setWindowTitle(
                    f"🌐  Hoş geldiniz! Verileriniz güncelleniyor…"
                    f"  ({cfg.get('firmaadi') or 'webadmin'})"
                )
                dlg.exec()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Otomatik webadmin sync hatası: %s", e)

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(800, _auto_webadmin_sync)   # pencere tamamen açıldıktan sonra

    login_screen.login_success.connect(_on_login)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
