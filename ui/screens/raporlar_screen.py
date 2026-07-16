"""
Raporlar ekranı — nakitGuncelTablo.php'nin PyQt6 karşılığı.
4 sekme: Gelir / Gider / Finansal Öngörüler / Gelir Gider
"""
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QScrollArea, QFrame, QComboBox, QSizePolicy,
    QSpacerItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from ui.theme import COLORS
from ui.components.monthly_table import MonthlyTable
from services import rapor_service


class RaporLoader(QThread):
    gelir_ready    = pyqtSignal(dict, dict, dict, dict)   # urun, tahsilat, sube, aylik
    gider_ready    = pyqtSignal(dict, dict)               # dagilim, odeme
    gg_ready       = pyqtSignal(list)                     # vadesi geçen
    error          = pyqtSignal(str)

    def __init__(self, userid: int, musterino: int, yil: int):
        super().__init__()
        self.userid = userid
        self.musterino = musterino
        self.yil = yil

    def run(self):
        try:
            # Gelir
            urun      = rapor_service.get_gelir_urun_hizmet_tablo(self.userid, self.musterino, self.yil)
            tahsilat  = rapor_service.get_gelir_tahsilat_turu_tablo(self.userid, self.musterino, self.yil)
            sube      = rapor_service.get_gelir_sube_bazli_tablo(self.userid, self.musterino, self.yil)
            aylik     = rapor_service.get_gelir_aylik_tutar_tablo(self.userid, self.musterino, self.yil)
            self.gelir_ready.emit(urun, tahsilat, sube, aylik)

            # Gider
            dagilim   = rapor_service.get_gider_dagilim_tablo(self.userid, self.musterino, self.yil)
            odeme     = rapor_service.get_gider_odeme_turu_tablo(self.userid, self.musterino, self.yil)
            self.gider_ready.emit(dagilim, odeme)

            # Gelir-Gider
            vadesi    = rapor_service.get_vadesi_gecen_tahsilatlar(self.userid, self.musterino)
            self.gg_ready.emit(vadesi)

        except Exception as e:
            self.error.emit(str(e))


class RaporlarScreen(QWidget):
    """Raporlar ana ekranı — 4 sekmeli tablo yapısı."""

    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self._user = user
        self._userid = user.get("GercekUserId", user.get("Kayitno", 1))
        self._musterino = user.get("musterino", user.get("GercekUserId", 1))
        self._yil = datetime.now().year
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # Başlık + Yıl seçimi
        header = QHBoxLayout()
        self.title_lbl = QLabel(f"Raporlar ( {self._yil} )")
        self.title_lbl.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: 22px;
            font-weight: 700;
        """)
        header.addWidget(self.title_lbl)
        header.addStretch()

        self.yil_combo = QComboBox()
        current_year = datetime.now().year
        for y in range(current_year + 1, current_year - 6, -1):
            self.yil_combo.addItem(str(y), y)
        self.yil_combo.setCurrentText(str(current_year))
        self.yil_combo.setFixedHeight(34)
        self.yil_combo.setFixedWidth(100)
        self.yil_combo.setStyleSheet(f"""
            QComboBox {{
                background: white;
                border: 1.5px solid {COLORS['border']};
                border-radius: 8px;
                padding: 0 10px;
                font-size: 13px;
                font-weight: 600;
                color: {COLORS['text_primary']};
            }}
            QComboBox:focus {{
                border-color: {COLORS['btn_primary']};
            }}
            QComboBox::drop-down {{ border: none; }}
        """)
        self.yil_combo.currentIndexChanged.connect(self._on_yil_changed)
        header.addWidget(self.yil_combo)

        excel_btn = QPushButton("📥 EXCEL")
        excel_btn.setFixedHeight(34)
        excel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        excel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['btn_excel']};
                color: white;
                font-size: 12px;
                font-weight: 700;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
            }}
            QPushButton:hover {{ background: #047857; }}
        """)
        header.addWidget(excel_btn)
        root.addLayout(header)

        sub_title = QLabel("Yıllık Hesap Özeti")
        sub_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 16px; font-weight: 600;")
        root.addWidget(sub_title)

        # ── Tab Widget ──────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: transparent;
            }}
            QTabBar::tab {{
                background: {COLORS['bg']};
                color: {COLORS['text_secondary']};
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 600;
                border: none;
                border-bottom: 2px solid transparent;
                margin-right: 4px;
                letter-spacing: 1px;
                text-transform: uppercase;
            }}
            QTabBar::tab:selected {{
                color: {COLORS['btn_primary']};
                background: white;
                border-bottom: 2px solid {COLORS['btn_primary']};
            }}
            QTabBar::tab:hover:!selected {{
                background: white;
                color: {COLORS['text_primary']};
            }}
        """)

        # Gelir Sekmesi
        self.gelir_tab = self._make_scroll_tab()
        gelir_inner = self.gelir_tab.widget()
        gelir_layout = gelir_inner.layout()

        self.tbl_urun     = MonthlyTable("Ürün Hizmet Tablosu")
        self.tbl_tahsilat = MonthlyTable("Tahsilat Türü Tablosu")
        self.tbl_sube_g   = MonthlyTable("Şube Bazlı Tablo")
        self.tbl_aylik    = MonthlyTable("Aylık Tutar Tablosu")

        for tbl in [self.tbl_urun, self.tbl_tahsilat, self.tbl_sube_g, self.tbl_aylik]:
            tbl.setMinimumHeight(220)
            gelir_layout.addWidget(tbl)

        gelir_layout.addStretch()
        self.tabs.addTab(self.gelir_tab, "GELİR")

        # Gider Sekmesi
        self.gider_tab = self._make_scroll_tab()
        gider_inner = self.gider_tab.widget()
        gider_layout = gider_inner.layout()

        self.tbl_dagilim = MonthlyTable("Gider Dağılım Tablosu")
        self.tbl_odeme   = MonthlyTable("Ödeme Türü Tablosu")

        for tbl in [self.tbl_dagilim, self.tbl_odeme]:
            tbl.setMinimumHeight(220)
            gider_layout.addWidget(tbl)

        gider_layout.addStretch()
        self.tabs.addTab(self.gider_tab, "GİDER")

        # Finansal Öngörüler Sekmesi
        self.ongoru_tab = self._make_scroll_tab()
        ongoru_inner = self.ongoru_tab.widget()
        ongoru_layout = ongoru_inner.layout()

        self.tbl_ongoru = MonthlyTable("Öngörü Gelir Tablosu")
        self.tbl_ongoru.setMinimumHeight(220)
        ongoru_layout.addWidget(self.tbl_ongoru)
        ongoru_layout.addStretch()
        self.tabs.addTab(self.ongoru_tab, "FİNANSAL ÖNGÖRÜLER")

        # Gelir Gider Sekmesi
        self.gg_tab = self._make_scroll_tab()
        gg_inner = self.gg_tab.widget()
        gg_layout = gg_inner.layout()

        gg_lbl = QLabel("Günlük Mali Durum, Alacaklı Cariler ve Vadesi Geçen Tahsilatlar")
        gg_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; padding: 10px;")
        gg_layout.addWidget(gg_lbl)
        gg_layout.addStretch()
        self.tabs.addTab(self.gg_tab, "GELİR GİDER")

        root.addWidget(self.tabs)

    def _make_scroll_tab(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(16)

        scroll.setWidget(inner)
        return scroll

    def _on_yil_changed(self):
        self._yil = self.yil_combo.currentData()
        self.title_lbl.setText(f"Raporlar ( {self._yil} )")
        self._load_data()

    def _load_data(self):
        self._loader = RaporLoader(self._userid, self._musterino, self._yil)
        self._loader.gelir_ready.connect(self._on_gelir_ready)
        self._loader.gider_ready.connect(self._on_gider_ready)
        self._loader.error.connect(lambda e: print(f"[Rapor] Hata: {e}"))
        self._loader.start()

    def _on_gelir_ready(self, urun, tahsilat, sube, aylik):
        self.tbl_urun.load_data(urun)
        self.tbl_tahsilat.load_data(tahsilat)
        self.tbl_sube_g.load_data(sube)
        self.tbl_aylik.load_data(aylik)

    def _on_gider_ready(self, dagilim, odeme):
        self.tbl_dagilim.load_data(dagilim)
        self.tbl_odeme.load_data(odeme)
