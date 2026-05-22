"""
Veri aktarım ekranı — uygulama ilk açılışında MySQL → SQLite aktarımı için.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from ui.theme import COLORS
from db.importer import run_import


class ImportThread(QThread):
    progress = pyqtSignal(str, int)   # (tablo_adı, kayıt_sayısı)
    finished = pyqtSignal(int, list)  # (toplam, hatalar)

    def run(self):
        try:
            total, errors = run_import(
                progress_cb=lambda tbl, cnt: self.progress.emit(tbl, cnt)
            )
            self.finished.emit(total, errors)
        except Exception as e:
            self.finished.emit(0, [str(e)])


class SetupDialog(QDialog):
    """
    İlk kurulum / veri güncelleme diyaloğu.
    MySQL'den SQLite'a veri aktarımını başlatır.
    """
    setup_complete = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IQ Finans — Veri Kurulumu")
        self.setFixedSize(520, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._thread = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        # Başlık
        title = QLabel("📥  Veri Kurulumu")
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {COLORS['text_primary']};")
        layout.addWidget(title)

        desc = QLabel(
            "MySQL veritabanınızdaki (iqdev21Nisan) veriler yerel SQLite "
            "veritabanına aktarılacak. Bu işlem birkaç dakika sürebilir."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        layout.addWidget(desc)

        # İlerleme çubuğu
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Belirsiz mod
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {COLORS['border']};
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {COLORS['btn_primary']};
                border-radius: 4px;
            }}
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Log alanı
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(220)
        self.log_area.setStyleSheet(f"""
            QTextEdit {{
                background: {COLORS['text_primary']};
                color: #A3E635;
                font-family: Consolas, monospace;
                font-size: 11px;
                border-radius: 10px;
                padding: 10px;
                border: none;
            }}
        """)
        self.log_area.hide()
        layout.addWidget(self.log_area)

        # Durum etiketi
        self.status_lbl = QLabel("MySQL bağlantısı kontrol ediliyor...")
        self.status_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        self.status_lbl.hide()
        layout.addWidget(self.status_lbl)

        layout.addStretch()

        # Butonlar
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.skip_btn = QPushButton("Şimdi Değil")
        self.skip_btn.setFixedHeight(40)
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg']};
                color: {COLORS['text_secondary']};
                border: 1.5px solid {COLORS['border']};
                border-radius: 10px;
                padding: 0 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{ background: {COLORS['border']}; }}
        """)
        self.skip_btn.clicked.connect(self._on_skip)
        btn_row.addWidget(self.skip_btn)

        self.start_btn = QPushButton("🔄  Aktarımı Başlat")
        self.start_btn.setFixedHeight(40)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['btn_primary']};
                color: white;
                border: none;
                border-radius: 10px;
                padding: 0 24px;
                font-size: 13px;
                font-weight: 700;
                margin-left: 10px;
            }}
            QPushButton:hover {{ background: #2563EB; }}
        """)
        self.start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self.start_btn)

        layout.addLayout(btn_row)

    def _on_skip(self):
        self.setup_complete.emit()
        self.accept()

    def _on_start(self):
        self.start_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.start_btn.setText("Aktarılıyor...")
        self.progress_bar.show()
        self.log_area.show()
        self.status_lbl.show()
        self.log_area.clear()
        self._append_log("Aktarım başlatıldı...")

        self._thread = ImportThread()
        self._thread.progress.connect(self._on_progress)
        self._thread.finished.connect(self._on_finished)
        self._thread.start()

    def _on_progress(self, table: str, count: int):
        if count == -1:
            self._append_log(f"⚠  {table}: MySQL'de bulunamadı")
        elif count == -2:
            self._append_log(f"✗  {table}: Hata oluştu")
        else:
            self._append_log(f"✔  {table}: {count:,} kayıt aktarıldı")
        self.status_lbl.setText(f"İşleniyor: {table}")

    def _on_finished(self, total: int, errors: list):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)

        if errors:
            self._append_log(f"\n⚠  Hatalar:")
            for e in errors:
                self._append_log(f"   - {e}")

        self._append_log(f"\n✅  Tamamlandı! Toplam {total:,} kayıt aktarıldı.")
        self.status_lbl.setText(f"✅  {total:,} kayıt aktarıldı.")
        self.start_btn.setText("✓  Tamam")
        self.start_btn.setEnabled(True)
        self.start_btn.clicked.disconnect()
        self.start_btn.clicked.connect(self._on_done)

    def _on_done(self):
        self.setup_complete.emit()
        self.accept()

    def _append_log(self, text: str):
        self.log_area.append(text)
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )
