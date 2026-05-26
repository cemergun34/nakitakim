"""
Giriş ekranı — PHP index.php / login formunun PyQt6 karşılığı.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor, QPainter, QLinearGradient, QBrush, QPixmap
from ui.theme import COLORS
from services.auth_service import authenticate


class LoginScreen(QWidget):
    """
    Giriş ekranı.
    login_success(user_dict) sinyali emit eder.
    """
    login_success = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── Sol: Gradient panel ────────────────────────────────────────────────
        left = GradientPanel()
        left.setMinimumWidth(480)
        main.addWidget(left, 1)

        # ── Sağ: Giriş formu ──────────────────────────────────────────────────
        right = QWidget()
        right.setStyleSheet(f"background: {COLORS['bg']};")
        right.setMinimumWidth(440)
        r_layout = QVBoxLayout(right)
        r_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        r_layout.setContentsMargins(60, 60, 60, 60)
        r_layout.setSpacing(0)

        # Logo metin
        logo_lbl = QLabel("IQ Finans")
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl.setStyleSheet(f"""
            color: {COLORS['btn_primary']};
            font-size: 32px;
            font-weight: 800;
            letter-spacing: 2px;
        """)
        r_layout.addWidget(logo_lbl)

        subtitle = QLabel("Nakit Akış Yönetimi")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px; margin-bottom: 40px;")
        r_layout.addWidget(subtitle)
        r_layout.addSpacing(40)

        # Kart
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: white;
                border-radius: 20px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 36, 36, 36)
        card_layout.setSpacing(16)

        title = QLabel("Giriş Yap")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 22px; font-weight: 700;")
        card_layout.addWidget(title)

        desc = QLabel("Hesabınıza giriş yapın")
        desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px; margin-bottom: 8px;")
        card_layout.addWidget(desc)

        # Kullanıcı adı
        user_lbl = QLabel("Kullanıcı Adı")
        user_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: 600;")
        card_layout.addWidget(user_lbl)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Kullanıcı adınızı girin")
        self.username_input.setFixedHeight(44)
        self.username_input.setStyleSheet(self._input_style())
        card_layout.addWidget(self.username_input)

        # Şifre
        pass_lbl = QLabel("Şifre")
        pass_lbl.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: 600;")
        card_layout.addWidget(pass_lbl)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Şifrenizi girin")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedHeight(44)
        self.password_input.setStyleSheet(self._input_style())
        self.password_input.returnPressed.connect(self._try_login)
        card_layout.addWidget(self.password_input)

        # Hata mesajı
        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet(f"color: {COLORS['red']}; font-size: 12px;")
        self.error_lbl.hide()
        card_layout.addWidget(self.error_lbl)

        # Giriş butonu
        card_layout.addSpacing(8)
        self.login_btn = QPushButton("GİRİŞ YAP")
        self.login_btn.setFixedHeight(48)
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['btn_primary']};
                color: white;
                font-size: 14px;
                font-weight: 700;
                border: none;
                border-radius: 12px;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background: #2563EB;
            }}
            QPushButton:pressed {{
                background: #1D4ED8;
            }}
        """)
        self.login_btn.clicked.connect(self._try_login)
        card_layout.addWidget(self.login_btn)

        r_layout.addWidget(card)
        r_layout.addStretch()

        main.addWidget(right, 1)

    def _input_style(self) -> str:
        return f"""
            QLineEdit {{
                background: {COLORS['bg']};
                border: 1.5px solid {COLORS['border']};
                border-radius: 10px;
                padding: 0 14px;
                font-size: 13px;
                color: {COLORS['text_primary']};
            }}
            QLineEdit:focus {{
                border-color: {COLORS['btn_primary']};
                background: white;
            }}
        """

    def _try_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            self._show_error("Lütfen tüm alanları doldurun.")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("Giriş yapılıyor...")

        user = authenticate(username, password)
        if user:
            self.error_lbl.hide()
            self.login_success.emit(user)
        else:
            self._show_error("Kullanıcı adı veya şifre hatalı.")
            self.login_btn.setEnabled(True)
            self.login_btn.setText("GİRİŞ YAP")

    def _show_error(self, msg: str):
        self.error_lbl.setText(f"⚠  {msg}")
        self.error_lbl.show()


class GradientPanel(QWidget):
    """Giriş ekranının sol tarafındaki gradient dekoratif panel."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        grad = QLinearGradient(0, 0, rect.width(), rect.height())
        grad.setColorAt(0.0, QColor("#1E3A5F"))
        grad.setColorAt(0.5, QColor("#2563EB"))
        grad.setColorAt(1.0, QColor("#7C3AED"))

        painter.fillRect(rect, QBrush(grad))

        # Dekoratif daireler
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 15))
        painter.drawEllipse(-80, -80, 320, 320)
        painter.setBrush(QColor(255, 255, 255, 10))
        painter.drawEllipse(rect.width() - 200, rect.height() - 200, 320, 320)
        painter.setBrush(QColor(255, 255, 255, 8))
        painter.drawEllipse(rect.width() // 2 - 100, rect.height() // 2 - 100, 200, 200)

        # Metin
        painter.setPen(QColor(255, 255, 255))
        font = QFont(".AppleSystemUIFont", 28, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect.adjusted(40, 0, -40, 0),
                         Qt.AlignmentFlag.AlignCenter,
                         "IQ Finans\nNakit Akış Yönetimi")

        sub_font = QFont(".AppleSystemUIFont", 13)
        painter.setFont(sub_font)
        painter.setPen(QColor(255, 255, 255, 180))
        painter.drawText(rect.adjusted(40, 80, -40, 0),
                         Qt.AlignmentFlag.AlignCenter,
                         "Finansal verilerinizi\ngüvenle yönetin")
        painter.end()
