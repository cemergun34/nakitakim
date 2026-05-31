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
        r_layout.setContentsMargins(60, 60, 60, 20)
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
        subtitle.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 14px; margin-bottom: 40px;"
        )
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

        r_layout.addWidget(card)
        r_layout.addStretch()
        r_layout.addSpacing(12)

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
        """
        loading=True  : animasyonlu bekleme göster, login butonunu kilitle
        loading=False : banneri gizle (veya hata/başarı mesajı göster)
        """
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
            # WARP butonunu gizle
            if hasattr(self, "_warp_btn"):
                self._warp_btn.hide()
            if hasattr(self, "_retry_btn"):
                self._retry_btn.hide()
        else:
            self._anim_timer.stop()
            if error:
                # ── Hata banneri ──────────────────────────────────────────────
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

                # ── Cloudflare WARP & Tekrar Dene butonları ───────────────────
                if not hasattr(self, "_warp_btn"):
                    import os
                    from PyQt6.QtWidgets import QHBoxLayout
                    # Buton layout — banner'ın parent layout'unu bul
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
                # ── Başarı banneri ────────────────────────────────────────────
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
        """Cloudflare WARP indirme sayfasını tarayıcıda açar."""
        import webbrowser
        import sys
        if sys.platform == "darwin":
            webbrowser.open("https://1.1.1.1/")   # Mac: App Store + web
        elif sys.platform == "win32":
            webbrowser.open("https://1.1.1.1/")
        else:
            webbrowser.open("https://1.1.1.1/")

    def _retry_pg_connect(self):
        """PostgreSQL bağlantısını tekrar dener."""
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
        """Her timer tick'inde animasyon karesini günceller."""
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

        # PG modunda bekleme bannerı göster
        try:
            from db.db_config import get_mode
            if get_mode() == "postgres":
                self.set_db_loading(True)
        except Exception:
            pass

        # Arka thread'de çalıştır — PostgreSQL modunda UI donmasını önler
        self._login_worker = LoginWorker(username, password)
        self._login_worker.finished.connect(self._on_login_result)
        self._login_worker.start()

    def _on_login_result(self, user):
        if user:
            # Başarı: banner'i gizle, ana pencereye geç
            self._anim_timer.stop()
            self._db_banner.hide()
            self.error_lbl.hide()
            self.login_success.emit(user)
        else:
            # Hata: banner'i kaldır, hata mesajı göster
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
        """Uygulamayı kapatır."""
        QApplication.quit()


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
        painter.drawEllipse(
            rect.width() // 2 - 100, rect.height() // 2 - 100, 200, 200
        )

        # Metin
        painter.setPen(QColor(255, 255, 255))
        font = QFont(".AppleSystemUIFont", 28, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            rect.adjusted(40, 0, -40, 0),
            Qt.AlignmentFlag.AlignCenter,
            "IQ Finans\nNakit Akış Yönetimi"
        )

        sub_font = QFont(".AppleSystemUIFont", 13)
        painter.setFont(sub_font)
        painter.setPen(QColor(255, 255, 255, 180))
        painter.drawText(
            rect.adjusted(40, 80, -40, 0),
            Qt.AlignmentFlag.AlignCenter,
            "Finansal verilerinizi\ngüvenle yönetin"
        )

        # ── Veritabanı Bilgi Rozeti (Bottom-Left Badge) ────────────────────────
        try:
            from db.db_config import get_mode
            mode = get_mode()
            if mode == "postgres":
                db_text = "🌐  Sunucu (PostgreSQL) veritabanınızda açılıyorsunuz."
                bg_color = QColor("#1D4ED8")  # Premium koyu mavi
            else:
                db_text = "💻  Lokal (SQLite) veritabanınızda açılıyorsunuz."
                bg_color = QColor("#2563EB")  # Premium canlı mavi

            badge_font = QFont(".AppleSystemUIFont", 11, QFont.Weight.Bold)
            painter.setFont(badge_font)

            # Metin genişliği/yüksekliğini hesapla
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(db_text)
            text_h = fm.height()

            # Rozet konum ve ölçüleri
            pad_x = 18
            pad_y = 9
            b_w = text_w + pad_x * 2
            b_h = text_h + pad_y * 2
            b_x = 24
            b_y = rect.height() - b_h - 24

            badge_rect = QRect(b_x, b_y, b_w, b_h)

            # Arka plan çiz
            painter.setBrush(QBrush(bg_color))
            # İnce şık sınır çizgisi
            painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
            painter.drawRoundedRect(badge_rect, 8, 8)

            # Metni çiz
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, db_text)
        except Exception:
            pass

        painter.end()
