"""
IQ Finans — Nakit Akış Masaüstü Uygulaması
Giriş noktası.
"""
import sys
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from db.database import initialize_db, db_exists
from ui.screens.login_screen import LoginScreen
from ui.screens.setup_dialog import SetupDialog
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("IQ Finans")
    app.setOrganizationName("FPPRO")

    # Varsayılan font
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    # Yüksek DPI desteği (PyQt6'da otomatik)

    # Veritabanını başlat
    initialize_db()

    # İlk kurulum gerekli mi?
    if not db_exists():
        setup = SetupDialog()
        if setup.exec() != SetupDialog.DialogCode.Accepted:
            sys.exit(0)

    # Global durum
    _state = {"user": None, "main_win": None}

    # Giriş ekranı
    login_screen = LoginScreen()
    login_screen.setWindowTitle("IQ Finans — Giriş")
    login_screen.resize(1100, 700)
    login_screen.show()

    def _on_login(user: dict):
        _state["user"] = user
        
        # Uygulamanın login kapanınca tamamen kapanmasını engelle
        app.setQuitOnLastWindowClosed(False)
        login_screen.hide()

        def _after_setup():
            win = MainWindow(user)
            _state["main_win"] = win
            win.show()
            # Ana pencere açılınca normal davranışa geri dön
            app.setQuitOnLastWindowClosed(True)
            login_screen.close()

        # Artık her girişte sormayacak. İlk kurulum zaten girişte yapılıyor.
        _after_setup()

    login_screen.login_success.connect(_on_login)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
