"""
Sol kenar çubuğu (Sidebar) — PHP blurMenu.js benzeri ikon tabanlı menü.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush
from ui.theme import COLORS, SIDEBAR_WIDTH


class SidebarButton(QPushButton):
    """İkon + tooltip tabanlı kenar çubuğu butonu."""

    def __init__(self, icon_text: str, tooltip: str, page_id: str, parent=None):
        super().__init__(parent)
        self._page_id = page_id
        self._active = False

        self.setFixedSize(SIDEBAR_WIDTH, SIDEBAR_WIDTH)
        self.setText(icon_text)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()

    @property
    def page_id(self):
        return self._page_id

    def set_active(self, active: bool):
        self._active = active
        self._update_style()

    def _update_style(self):
        if self._active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['btn_primary']};
                    color: white;
                    border: none;
                    border-radius: 14px;
                    font-size: 20px;
                    margin: 6px;
                }}
                QPushButton:hover {{
                    background: #2563EB;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS['text_secondary']};
                    border: none;
                    border-radius: 14px;
                    font-size: 20px;
                    margin: 6px;
                }}
                QPushButton:hover {{
                    background: {COLORS['border']};
                    color: {COLORS['btn_primary']};
                }}
            """)


class Sidebar(QFrame):
    """
    Sol kenar çubuğu.
    page_changed sinyali emit eder: page_id str.
    """
    page_changed = pyqtSignal(str)

    MENU_ITEMS = [
        ("🏠", "Dashboard",   "dashboard"),
        ("📊", "Raporlar",    "raporlar"),
        ("⚙️",  "Ayarlar",    "ayarlar"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['sidebar_bg']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Logo
        logo = QLabel("IQ")
        logo.setFixedSize(SIDEBAR_WIDTH, SIDEBAR_WIDTH)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(f"""
            QLabel {{
                background: {COLORS['btn_primary']};
                color: white;
                font-size: 18px;
                font-weight: 800;
                border-radius: 0;
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        layout.addWidget(logo)
        layout.addSpacing(8)

        self._buttons: list[SidebarButton] = []
        for icon, tip, pid in self.MENU_ITEMS:
            btn = SidebarButton(icon, tip, pid)
            btn.clicked.connect(lambda checked, p=pid: self._on_click(p))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()

        # Çıkış butonu
        exit_btn = SidebarButton("🚪", "Çıkış", "exit")
        exit_btn.clicked.connect(lambda: self.page_changed.emit("exit"))
        layout.addWidget(exit_btn)
        layout.addSpacing(8)

        # İlk sekmeyi aktif et
        if self._buttons:
            self._buttons[0].set_active(True)

    def _on_click(self, page_id: str):
        for btn in self._buttons:
            btn.set_active(btn.page_id == page_id)
        self.page_changed.emit(page_id)

    def set_active_page(self, page_id: str):
        for btn in self._buttons:
            btn.set_active(btn.page_id == page_id)
