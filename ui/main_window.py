"""
Ana pencere — tüm ekranları barındıran shell.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from ui.theme import COLORS, SIDEBAR_WIDTH
from ui.components.sidebar import Sidebar
from ui.screens.dashboard_screen import DashboardScreen
from ui.screens.raporlar_screen import RaporlarScreen


class MainWindow(QMainWindow):
    """Ana uygulama penceresi."""

    def __init__(self, user: dict):
        super().__init__()
        self._user = user
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

        self.stack.setCurrentWidget(dash)

    def _navigate(self, page_id: str):
        if page_id == "exit":
            self.close()
            return

        if page_id in self._screens:
            self.stack.setCurrentWidget(self._screens[page_id])
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
