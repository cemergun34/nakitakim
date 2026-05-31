"""
Giriş ekranı — PHP index.php / login formunun PyQt6 karşılığı.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QRect, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QLinearGradient, QBrush, QPen
from PyQt6.QtWidgets import QApplication
from ui.theme import COLORS


class LoginWorker(QThread):
    """Authenticate işlemini arka thread'de çalıştırır (UI donmasını önler)."""
    finished = pyqtSignal(object)  # dict | None

    def __init__(self, username: str, password: str):
        super().__init__()
        self._username = username
        self._password = password

    def run(self):
        from services.auth_service import authenticate
        try:
            result = authenticate(self._username, self._password)
        except Exception:
            result = None
        self.finished.emit(result)


class LoginScreen(QWidget):
    """
    Giriş ekranı.
    login_success(user_dict) sinyali emit eder.
    """
    login_success = pyqtSignal(dict)

    _ANIM_FRAMES = [
        "●○○○  Sunucu veritabanına bağlanılıyor...",
        "○●○○  Sunucu veritabanına bağlanılıyor...",
        "○○●○  Sunucu veritabanına bağlanılıyor...",
        "○○○●  Sunucu veritabanına bağlanılıyor...",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim_frame = 0
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick_anim)
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
        title.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 22px; font-weight: 700;"
        )
        card_layout.addWidget(title)

        desc = QLabel("Hesabınıza giriş yapın")
        desc.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 13px; margin-bottom: 8px;"
        )
        card_layout.addWidget(desc)

        # Kullanıcı adı
        user_lbl = QLabel("Kullanıcı Adı")
        user_lbl.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: 600;"
        )
        card_layout.addWidget(user_lbl)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Kullanıcı adınızı girin")
        self.username_input.setFixedHeight(44)
        self.username_input.setStyleSheet(self._input_style())
        card_layout.addWidget(self.username_input)

        # Şifre
        pass_lbl = QLabel("Şifre")
        pass_lbl.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 12px; font-weight: 600;"
        )
        card_layout.addWidget(pass_lbl)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Şifrenizi girin")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedHeight(44)
        self.password_input.setStyleSheet(self._input_style())
        self.password_input.returnPressed.connect(self._try_login)
        card_layout.addWidget(self.password_input)

        # ── PG bekleme banneri ────────────────────────────────────────────────
        self._db_banner = QLabel("")
        self._db_banner.setWordWrap(True)
        self._db_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._db_banner.setFixedHeight(40)
        self._db_banner.setStyleSheet(
            "background:#1e3a8a;color:white;border-radius:8px;"
            "font-size:12px;font-weight:600;padding:0 12px;border:none;"
        )
        self._db_banner.hide()
        card_layout.addWidget(self._db_banner)

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

        # ── Çıkış butonu ──────────────────────────────────────────────────────
        card_layout.addSpacing(4)
        self.exit_btn = QPushButton("✕  Uygulamayı Kapat")
        self.exit_btn.setFixedHeight(42)
        self.exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_btn.setStyleSheet(f"""
            QPushButton {{
                background: #374151;
                color: white;
                font-size: 13px;
                font-weight: 600;
                border: none;
                border-radius: 12px;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background: #111827;
                color: white;
            }}
            QPushButton:pressed {{
                background: #000000;
            }}
        """)
        self.exit_btn.clicked.connect(self._on_exit)
        card_layout.addWidget(self.exit_btn)

        r_layout.addStretch()
        r_layout.addWidget(card)
        r_layout.addStretch()

        main.addWidget(right, 1)

    def keyPressEvent(self, event):
        """Gizli kısayol: Ctrl + Shift + Alt + S  →  Sistem Ayarları"""
        mods = event.modifiers()
        key  = event.key()
        if (
            mods == (Qt.KeyboardModifier.ControlModifier
                     | Qt.KeyboardModifier.ShiftModifier
                     | Qt.KeyboardModifier.AltModifier)
            and key == Qt.Key.Key_S
        ):
            self._open_superadmin()
        else:
            super().keyPressEvent(event)

    # ── DB bekleme banneri (PG modu) ─────────────────────────────────────────

    def set_db_loading(self, loading: bool, error: str = ""):
        if loading:
            self._db_banner.show()
            self._db_banner.setFixedHeight(40)
            self._db_banner.setStyleSheet(
                "background:#1e3a8a;color:white;border-radius:8px;"
                "font-size:12px;font-weight:600;padding:0 12px;border:none;"
            )
            self.login_btn.setEnabled(False)
            self.login_btn.setText("Bağlantı bekleniyor...")
            self._anim_frame = 0
            self._anim_timer.start(480)
            if hasattr(self, "_warp_btn"):
                self._warp_btn.hide()
            if hasattr(self, "_retry_btn"):
                self._retry_btn.hide()
        else:
            self._anim_timer.stop()
            if error:
                self._db_banner.setFixedHeight(52)
                self._db_banner.setText(
                    f"⚠  Sunucu bağlantısı kurulamadı.\n"
                    f"Port 5432 ve 6543 denendi — ikisi de başarısız.\n"
                    f"Cloudflare WARP'ı açık tutun veya VPN kullanın."
                )
                self._db_banner.setStyleSheet(
                    "background:#7f1d1d;color:#fecaca;border-radius:8px;"
                    "font-size:11px;font-weight:600;padding:6px 12px;border:none;"
                )
                self._db_banner.show()
                self.login_btn.setEnabled(True)
                self.login_btn.setText("GİRİŞ YAP")

                if not hasattr(self, "_warp_btn"):
                    from PyQt6.QtWidgets import QHBoxLayout
                    banner_parent_layout = self._db_banner.parentWidget().layout()
                    banner_idx = None
                    for i in range(banner_parent_layout.count()):
                        item = banner_parent_layout.itemAt(i)
                        if item and item.widget() == self._db_banner:
                            banner_idx = i
                            break

                    btn_row = QHBoxLayout()
                    btn_row.setSpacing(8)

                    self._warp_btn = QPushButton("☁  Cloudflare WARP İndir")
                    self._warp_btn.setFixedHeight(30)
                    self._warp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    self._warp_btn.setStyleSheet(
                        "QPushButton{background:#f97316;color:white;border:none;"
                        "border-radius:6px;font-size:11px;font-weight:700;}"
                        "QPushButton:hover{background:#ea580c;}"
                    )
                    self._warp_btn.clicked.connect(self._open_warp_download)
                    btn_row.addWidget(self._warp_btn)

                    self._retry_btn = QPushButton("🔄  Tekrar Dene")
                    self._retry_btn.setFixedHeight(30)
                    self._retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    self._retry_btn.setStyleSheet(
                        "QPushButton{background:#1e40af;color:white;border:none;"
                        "border-radius:6px;font-size:11px;font-weight:700;}"
                        "QPushButton:hover{background:#1d4ed8;}"
                    )
                    self._retry_btn.clicked.connect(self._retry_pg_connect)
                    btn_row.addWidget(self._retry_btn)
                    btn_row.addStretch()

                    if banner_idx is not None:
                        banner_parent_layout.insertLayout(banner_idx + 1, btn_row)
                    else:
                        banner_parent_layout.addLayout(btn_row)

                self._warp_btn.show()
                self._retry_btn.show()
            else:
                self._db_banner.setFixedHeight(40)
                self._db_banner.setText("✅  Sunucuya bağlandı — giriş yapabilirsiniz")
                self._db_banner.setStyleSheet(
                    "background:#14532d;color:#bbf7d0;border-radius:8px;"
                    "font-size:12px;font-weight:600;padding:0 12px;border:none;"
                )
                self._db_banner.show()
                self.login_btn.setEnabled(True)
                self.login_btn.setText("GİRİŞ YAP")
                if hasattr(self, "_warp_btn"):
                    self._warp_btn.hide()
                if hasattr(self, "_retry_btn"):
                    self._retry_btn.hide()
                QTimer.singleShot(3000, self._db_banner.hide)

    def _open_warp_download(self):
        import webbrowser, sys
        webbrowser.open("https://1.1.1.1/")

    def _retry_pg_connect(self):
        self.set_db_loading(True)
        from PyQt6.QtCore import QThread, pyqtSignal

        class _RetryThread(QThread):
            done = pyqtSignal(bool, str)
            def run(self_t):
                try:
                    from db.database import ensure_pg_ready
                    ok = ensure_pg_ready()
                    self_t.done.emit(ok, "")
                except Exception as exc:
                    self_t.done.emit(False, str(exc))

        self._retry_thread = _RetryThread()
        self._retry_thread.done.connect(
            lambda ok, msg: self.set_db_loading(False, error="" if ok else msg)
        )
        self._retry_thread.start()

    def _tick_anim(self):
        self._anim_frame = (self._anim_frame + 1) % len(self._ANIM_FRAMES)
        self._db_banner.setText(
            f"🔄  Lütfen bekleyiniz...  {self._ANIM_FRAMES[self._anim_frame]}"
        )

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

        try:
            from db.db_config import get_mode
            if get_mode() == "postgres":
                self.set_db_loading(True)
        except Exception:
            pass

        self._login_worker = LoginWorker(username, password)
        self._login_worker.finished.connect(self._on_login_result)
        self._login_worker.start()

    def _on_login_result(self, user):
        if user:
            self._anim_timer.stop()
            self._db_banner.hide()
            self.error_lbl.hide()
            self.login_success.emit(user)
        else:
            self._anim_timer.stop()
            self._db_banner.hide()
            self._show_error("Kullanıcı adı veya şifre hatalı.")
            self.login_btn.setEnabled(True)
            self.login_btn.setText("GİRİŞ YAP")

    def _show_error(self, msg: str):
        self.error_lbl.setText(f"⚠  {msg}")
        self.error_lbl.show()

    def _open_superadmin(self):
        from ui.screens.superadmin_dialog import SuperAdminDialog
        dlg = SuperAdminDialog(self)
        dlg.exec()

    def _on_exit(self):
        QApplication.quit()


# ── Animasyonlu Gradient Panel ────────────────────────────────────────────────

class GradientPanel(QWidget):
    """
    Giriş ekranının sol tarafındaki gradient dekoratif panel.
    Baloncuklar rastgele hareket eder, duvarlardan sekip geri döner — 30fps.
    """

    _BUBBLE_COUNT = 9

    _LABELS = [
        "Nakit Akış", "Gelir", "Gider",
        "Bankalar", "Kredi Kartları",
        "Nakit Akış", "Gelir", "Gider", "Bankalar",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        import random
        self._rng = random.Random()

        # Her baloncuk: [x, y, radius, vx, vy, alpha, label]
        self._bubbles: list[list] = []
        for i in range(self._BUBBLE_COUNT):
            r   = self._rng.uniform(28, 90)
            vx  = self._rng.uniform(0.35, 1.1) * self._rng.choice([-1, 1])
            vy  = self._rng.uniform(0.35, 1.1) * self._rng.choice([-1, 1])
            a   = self._rng.uniform(12, 32)
            lbl = self._LABELS[i % len(self._LABELS)]
            self._bubbles.append([
                self._rng.uniform(50, 430),
                self._rng.uniform(50, 550),
                r, vx, vy, a, lbl
            ])

        self._timer = QTimer(self)
        self._timer.setInterval(33)   # ~30fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        """Her frame'de baloncukları hareket ettir, sınırlardan sekir."""
        w = max(self.width(), 1)
        h = max(self.height(), 1)
        for b in self._bubbles:
            x, y, r, vx, vy = b[0], b[1], b[2], b[3], b[4]
            x += vx
            y += vy
            if x - r < 0:
                x = r;  vx = abs(vx)
            elif x + r > w:
                x = w - r;  vx = -abs(vx)
            if y - r < 0:
                y = r;  vy = abs(vy)
            elif y + r > h:
                y = h - r;  vy = -abs(vy)
            b[0], b[1], b[3], b[4] = x, y, vx, vy
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        for b in self._bubbles:
            r = b[2]
            if b[0] < r or b[0] > w - r:
                b[0] = self._rng.uniform(r, max(r + 1, w - r))
            if b[1] < r or b[1] > h - r:
                b[1] = self._rng.uniform(r, max(r + 1, h - r))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # ── Gradient arka plan ──────────────────────────────────────────────────
        grad = QLinearGradient(0, 0, rect.width(), rect.height())
        grad.setColorAt(0.0, QColor("#1E3A5F"))
        grad.setColorAt(0.5, QColor("#2563EB"))
        grad.setColorAt(1.0, QColor("#7C3AED"))
        painter.fillRect(rect, QBrush(grad))

        # ── Animasyonlu baloncuklar ─────────────────────────────────────────────
        painter.setPen(Qt.PenStyle.NoPen)
        for b in self._bubbles:
            x, y, r, _, _, a, label = b[0], b[1], b[2], b[3], b[4], b[5], b[6]
            ai = int(a)
            # İç saydam daire
            painter.setBrush(QColor(255, 255, 255, ai))
            painter.drawEllipse(int(x - r), int(y - r), int(r * 2), int(r * 2))
            # Kenar halkası
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, min(255, int(ai * 2.5))), 1.5))
            painter.drawEllipse(int(x - r), int(y - r), int(r * 2), int(r * 2))

            # ── Baloncuk içi silik etiket ─────────────────────────────────────
            font_size = max(7, int(r * 0.28))   # Yarıçapa göre ölçekli font
            lbl_font = QFont(".AppleSystemUIFont", font_size)
            painter.setFont(lbl_font)
            # Opaklık: baloncuğun kenara göre biraz daha belirgin ama hâlâ silik
            painter.setPen(QColor(255, 255, 255, min(255, int(ai * 3.2))))
            from PyQt6.QtCore import QRectF
            painter.drawText(
                QRectF(x - r, y - r, r * 2, r * 2),
                Qt.AlignmentFlag.AlignCenter,
                label
            )
            painter.setPen(Qt.PenStyle.NoPen)

        # ── Merkez metin ────────────────────────────────────────────────────────
        painter.setPen(QColor(255, 255, 255))
        font = QFont(".AppleSystemUIFont", 28, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            rect.adjusted(40, 0, -40, 0),
            Qt.AlignmentFlag.AlignCenter,
            "IQ Finans\nNakit Akış Yönetimi"
        )

        # ── Veritabanı Bilgi Rozeti (alt sol köşe) ─────────────────────────────
        try:
            from db.db_config import get_mode
            mode = get_mode()
            if mode == "postgres":
                db_text = "🌐  Sunucu (PostgreSQL) veritabanınızda açılıyorsunuz."
                bg_color = QColor("#1D4ED8")
            else:
                db_text = "💻  Lokal (SQLite) veritabanınızda açılıyorsunuz."
                bg_color = QColor("#2563EB")

            badge_font = QFont(".AppleSystemUIFont", 11, QFont.Weight.Bold)
            painter.setFont(badge_font)
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(db_text)
            text_h = fm.height()
            pad_x, pad_y = 18, 9
            b_w = text_w + pad_x * 2
            b_h = text_h + pad_y * 2
            badge_rect = QRect(24, rect.height() - b_h - 24, b_w, b_h)
            painter.setBrush(QBrush(bg_color))
            painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
            painter.drawRoundedRect(badge_rect, 8, 8)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, db_text)
        except Exception:
            pass

        painter.end()
