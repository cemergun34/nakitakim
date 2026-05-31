"""
Ana pencere — tüm ekranları barındıran shell.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon

from ui.theme import COLORS, SIDEBAR_WIDTH
from ui.components.sidebar import Sidebar
from ui.screens.dashboard_screen import DashboardScreen
from ui.screens.raporlar_screen import RaporlarScreen
from ui.screens.ayarlar_screen import AyarlarScreen


class MainWindow(QMainWindow):
    """Ana uygulama penceresi."""
    logout_requested = pyqtSignal()   # Çıkış → login ekranına dön

    def __init__(self, user: dict):
        super().__init__()
        self._user = user
        self._is_logging_out = False
        self.setWindowTitle("IQ Finans — Nakit Akış Yönetimi")
        self.setMinimumSize(1280, 780)
        self.resize(1440, 860)
        self._setup_ui()
        self._center()

    def _setup_ui(self):
        central = QWidget()
        central.setStyleSheet(f"background: {COLORS['bg']};")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.page_changed.connect(self._navigate)
        root.addWidget(self.sidebar)

        # İçerik alanı
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {COLORS['bg']};")
        root.addWidget(self.stack, 1)

        # Ekranları oluştur
        self._screens = {}

        dash = DashboardScreen(self._user)
        self.stack.addWidget(dash)
        self._screens["dashboard"] = dash

        rapor = RaporlarScreen(self._user)
        self.stack.addWidget(rapor)
        self._screens["raporlar"] = rapor

        ayarlar = AyarlarScreen(self._user)
        self.stack.addWidget(ayarlar)
        self._screens["ayarlar"] = ayarlar

        # Moy'dan veri çekilince dashboard'u otomatik yenile
        if hasattr(ayarlar, "_moy_card"):
            ayarlar._moy_card.data_changed.connect(dash.refresh)

        self.stack.setCurrentWidget(dash)

    def _navigate(self, page_id: str):
        if page_id == "exit":
            self._is_logging_out = True
            self.logout_requested.emit()
            return

        if page_id in self._screens:
            screen = self._screens[page_id]
            self.stack.setCurrentWidget(screen)
            # Sayfanın refresh() methodu varsa çağır (canlı güncelleme)
            if hasattr(screen, "refresh") and callable(screen.refresh):
                screen.refresh()
        else:
            # Henüz implement edilmemiş sayfalar
            from PyQt6.QtWidgets import QLabel
            placeholder = QLabel(f"🚧  {page_id.upper()} ekranı yakında eklenecek")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 18px;")
            self.stack.addWidget(placeholder)
            self._screens[page_id] = placeholder
            self.stack.setCurrentWidget(placeholder)

    def _center(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            w, h = self.width(), self.height()
            self.move((geo.width() - w) // 2, (geo.height() - h) // 2)

    def closeEvent(self, event):
        if not self._is_logging_out:
            event.ignore()
            self._is_logging_out = True
            self.logout_requested.emit()
        else:
            event.accept()
