"""
KPI Detay Diyaloğu — kartlara tıklandığında açılır.
İki katmanlı:
  1. Şube / kategori bazlı özet kartları
  2. Seçilen şube / kategorinin işlem listesi (tablo)
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QGridLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QSizePolicy, QStackedWidget,
    QApplication, QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QBrush, QPainter, QLinearGradient

from ui.theme import COLORS, CARD_RADIUS
from utils.format import fmt_para


# ─── KPI DETAY KARTI ──────────────────────────────────────────────────────────

class DetayKarti(QFrame):
    """Şube özet kartı (gradient, tıklanabilir)."""
    clicked = pyqtSignal(dict)  # row dict emit eder

    RENK_PALETI = [
        ("#10B981", "#059669"),
        ("#3B82F6", "#1D4ED8"),
        ("#8B5CF6", "#6D28D9"),
        ("#EC4899", "#DB2777"),
        ("#F59E0B", "#D97706"),
        ("#6B7280", "#4B5563"),
        ("#EA580C", "#C2410C"),
        ("#0EA5E9", "#0284C7"),
    ]

    def __init__(self, row: dict, index: int, gelir_field="toplam_gelir",
                 gider_field="toplam_gider", tutar_field=None, parent=None):
        super().__init__(parent)
        self._row = row
        self._hovered = False
        c1, c2 = self.RENK_PALETI[index % len(self.RENK_PALETI)]
        self._c1, self._c2 = c1, c2
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(240, 120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        sube = str(row.get("sube_adi", "Bilinmeyen"))
        lbl_name = QLabel(sube)
        lbl_name.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 12px; font-weight: 600; background: transparent;")
        lbl_name.setWordWrap(True)
        layout.addWidget(lbl_name)

        # Tutar
        if tutar_field and row.get(tutar_field) is not None:
            tutar = float(row.get(tutar_field) or 0)
            lbl_tutar = QLabel(fmt_para(tutar))
        else:
            gelir = float(row.get(gelir_field) or 0)
            gider = float(row.get(gider_field) or 0)
            net = gelir - gider
            sign = "+" if net >= 0 else "-"
            color = "white" if net >= 0 else "#FCA5A5"
            lbl_tutar = QLabel(f"{sign}{fmt_para(abs(net))}")
            lbl_tutar.setStyleSheet(f"color: {color}; font-size: 19px; font-weight: 700; background: transparent;")
            layout.addWidget(lbl_tutar)

            kayit = row.get("kayit_sayisi", 0)
            lbl_sub = QLabel(f"{kayit} işlem  •  Tıkla → detay")
            lbl_sub.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 10px; background: transparent;")
            layout.addWidget(lbl_sub)
            layout.addStretch()
            return

        lbl_tutar.setStyleSheet("color: white; font-size: 19px; font-weight: 700; background: transparent;")
        layout.addWidget(lbl_tutar)
        kayit = row.get("kayit_sayisi", 0)
        lbl_sub = QLabel(f"{kayit} kayıt  •  Tıkla → detay")
        lbl_sub.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 10px; background: transparent;")
        layout.addWidget(lbl_sub)
        layout.addStretch()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        g = QLinearGradient(0, 0, rect.width(), rect.height())
        g.setColorAt(0, QColor(self._c1))
        g.setColorAt(1, QColor(self._c2))
        p.setBrush(QBrush(g))
        p.setPen(Qt.PenStyle.NoPen)
        r = rect.adjusted(0, -3, 0, 0) if self._hovered else rect
        p.drawRoundedRect(r, CARD_RADIUS, CARD_RADIUS)
        # dekoratif daire
        p.setBrush(QColor(255, 255, 255, 20))
        p.drawEllipse(rect.right() - 50, rect.bottom() - 50, 80, 80)
        p.end()
        super().paintEvent(event)

    def enterEvent(self, e):
        self._hovered = True; self.update()
    def leaveEvent(self, e):
        self._hovered = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._row)


# ─── İŞLEM TABLOSU ────────────────────────────────────────────────────────────

class IslemTablosu(QTableWidget):
    """Tüm kart tipleri için ortak işlem listesi tablosu."""

    KOLON_SETLERI = {
        "hareketler": [
            ("Tarih", "tarih"), ("Açıklama", "aciklama"),
            ("Şube", "sube_adi"), ("Tutar", "tutar"),
            ("Gelir/Gider", "gelirGider"), ("Teslim Şekli", "teslim_sekli"),
            ("Fatura No", "faturaNo"),
        ],
        "genel_hesap": [
            ("Tarih", "tarih"), ("Açıklama", "aciklama"),
            ("Şube", "sube_adi"), ("Gelir", "gelir"), ("Gider", "gider"),
            ("Teslim Şekli", "teslim_sekli"), ("Ödeme Şekli", "odeme_sekli"),
            ("Kategori", "kategori"),
        ],
        "faturalar": [
            ("Tarih", "tarih"), ("Ünvan", "unvan"),
            ("Fatura No", "faturano"), ("Vergi No", "vergino"),
            ("Tutar", "toplam"), ("Fatura Modu", "faturaMod"),
            ("Form No", "formNo"), ("Kaynak", "kaynak"),
        ],
    }

    def __init__(self, tablo_tipi: str = "hareketler", parent=None):
        super().__init__(parent)
        self._tablo_tipi = tablo_tipi
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        self.setStyleSheet(f"""
            QTableWidget {{
                background: white;
                alternate-background-color: #F8FAFF;
                gridline-color: {COLORS['border']};
                font-size: 11px;
                border: 1.5px solid {COLORS['border']};
                border-radius: 8px;
            }}
            QTableWidget::item {{ padding: 5px 8px; color: {COLORS['text_primary']}; }}
            QTableWidget::item:selected {{ background: #DBEAFE; color: #1E40AF; }}
            QHeaderView::section {{
                background: {COLORS['table_header']};
                color: {COLORS['text_secondary']};
                font-size: 10px; font-weight: 600;
                padding: 6px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)
        cols = self.KOLON_SETLERI.get(tablo_tipi, self.KOLON_SETLERI["hareketler"])
        self.setColumnCount(len(cols))
        self.setHorizontalHeaderLabels([c[0] for c in cols])

    def load_rows(self, rows: list[dict]):
        cols = self.KOLON_SETLERI.get(self._tablo_tipi, self.KOLON_SETLERI["hareketler"])
        self.setRowCount(len(rows))
        PARA_COLS = {"tutar", "gelir", "gider", "toplam"}
        for r_idx, row in enumerate(rows):
            for c_idx, (_, key) in enumerate(cols):
                val = row.get(key)
                if key in PARA_COLS and val is not None:
                    try:
                        text = fmt_para(float(val))
                    except Exception:
                        text = str(val) if val is not None else "-"
                else:
                    text = str(val) if val is not None else "-"
                item = QTableWidgetItem(text)
                if key in PARA_COLS:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if key in ("gelir", "tutar") and val and float(val) > 0:
                        item.setForeground(QBrush(QColor("#059669")))
                    elif key == "gider" and val and float(val) > 0:
                        item.setForeground(QBrush(QColor("#DC2626")))
                self.setItem(r_idx, c_idx, item)
        self.resizeRowsToContents()


# ─── ANA DETAY DİYALOĞU ──────────────────────────────────────────────────────

class DetayDialog(QDialog):
    """
    2 aşamalı diyalog:
    Sayfa 0 → Şube özet kartları
    Sayfa 1 → Seçilen şubenin işlem listesi
    """

    def __init__(self, baslik: str, ozet_rows: list[dict],
                 detay_fn,          # callable(sube_adi) → list[dict]
                 tablo_tipi: str = "hareketler",
                 gelir_field="toplam_gelir", gider_field="toplam_gider",
                 tutar_field=None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(baslik)
        self.setStyleSheet(f"background: {COLORS['bg']};")

        self._detay_fn = detay_fn
        self._tablo_tipi = tablo_tipi
        self._baslik = baslik

        # Kutucukların tam kapladığı pencere boyutunu dinamik hesapla
        cols_per_row = 4
        card_w, card_h = 240, 120
        spacing = 16
        margin_x, margin_y = 24, 20
        header_h = 56

        num_cards = len(ozet_rows)
        actual_cols = min(num_cards, cols_per_row) if num_cards > 0 else 1
        actual_rows = (num_cards + cols_per_row - 1) // cols_per_row if num_cards > 0 else 1

        self._ozet_width = actual_cols * card_w + (actual_cols - 1) * spacing + margin_x * 2
        self._ozet_height = header_h + actual_rows * card_h + (actual_rows - 1) * spacing + margin_y * 2
        self.resize(self._ozet_width, self._ozet_height)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(56)
        header.setStyleSheet(f"""
            QFrame {{ background: {COLORS['btn_primary']}; }}
        """)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)

        self._back_btn = QPushButton("← Geri")
        self._back_btn.setFixedHeight(34)
        self._back_btn.setFixedWidth(90)
        self._back_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.2);
                color: white; border: none;
                border-radius: 8px; font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.35); }}
        """)
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.hide()
        self._back_btn.clicked.connect(self._show_ozet)
        hl.addWidget(self._back_btn)

        self._title_lbl = QLabel(baslik)
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setStyleSheet("color: white; font-size: 16px; font-weight: 700;")
        hl.addWidget(self._title_lbl, 1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(34, 34)
        close_btn.setStyleSheet("""
            QPushButton { background: rgba(255,255,255,0.2); color: white;
                          border: none; border-radius: 8px; font-size: 16px; }
            QPushButton:hover { background: rgba(255,255,255,0.4); }
        """)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        hl.addWidget(close_btn)
        root.addWidget(header)

        # ── Stacked ───────────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        # ── Sayfa 0: Özet kartlar ─────────────────────────────────────────────
        ozet_page = QScrollArea()
        ozet_page.setWidgetResizable(True)
        ozet_page.setFrameShape(QFrame.Shape.NoFrame)
        ozet_page.setStyleSheet("background: transparent;")

        ozet_inner = QWidget()
        ozet_inner.setStyleSheet("background: transparent;")
        ozet_grid = QGridLayout(ozet_inner)
        ozet_grid.setContentsMargins(24, 20, 24, 20)
        ozet_grid.setSpacing(16)

        cols_per_row = 4
        for idx, row in enumerate(ozet_rows):
            kart = DetayKarti(row, idx,
                              gelir_field=gelir_field,
                              gider_field=gider_field,
                              tutar_field=tutar_field)
            kart.clicked.connect(self._on_kart_clicked)
            r, c = divmod(idx, cols_per_row)
            ozet_grid.addWidget(kart, r, c)

        # Eğer boş sütunlar varsa, doldurucu ekle
        remainder = len(ozet_rows) % cols_per_row
        if remainder:
            for i in range(cols_per_row - remainder):
                spacer = QWidget()
                spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                r_last = len(ozet_rows) // cols_per_row
                ozet_grid.addWidget(spacer, r_last, remainder + i)

        ozet_page.setWidget(ozet_inner)
        self._stack.addWidget(ozet_page)

        # ── Sayfa 1: İşlem listesi ────────────────────────────────────────────
        detay_page = QWidget()
        detay_page.setStyleSheet("background: transparent;")
        dp_layout = QVBoxLayout(detay_page)
        dp_layout.setContentsMargins(16, 12, 16, 12)
        dp_layout.setSpacing(8)

        # Bilgi Barları (Pills) Üst Bölüm
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        
        # 1. Başlık ve Şube Adı
        self._detay_sube_lbl = QLabel("")
        self._detay_sube_lbl.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: 13px;
            font-weight: 700;
            padding: 8px 12px;
            background: #EFF6FF;
            border-radius: 8px;
            border: 1px solid #BFDBFE;
        """)
        top_row.addWidget(self._detay_sube_lbl)
        
        # 2. Gelir Pill
        self._detay_gelir_lbl = QLabel("")
        self._detay_gelir_lbl.setStyleSheet(f"""
            color: #047857;
            font-size: 13px;
            font-weight: 700;
            padding: 8px 12px;
            background: #D1FAE5;
            border-radius: 8px;
            border: 1px solid #A7F3D0;
        """)
        top_row.addWidget(self._detay_gelir_lbl)
        
        # 3. Gider Pill
        self._detay_gider_lbl = QLabel("")
        self._detay_gider_lbl.setStyleSheet(f"""
            color: #B91C1C;
            font-size: 13px;
            font-weight: 700;
            padding: 8px 12px;
            background: #FEE2E2;
            border-radius: 8px;
            border: 1px solid #FCA5A5;
        """)
        top_row.addWidget(self._detay_gider_lbl)
        
        # 4. Net Pill
        self._detay_net_lbl = QLabel("")
        top_row.addWidget(self._detay_net_lbl)
        top_row.addStretch()

        self._excel_btn = QPushButton("📥 Excel İndir")
        self._excel_btn.setFixedHeight(38)
        self._excel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._excel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['btn_excel'] if 'btn_excel' in COLORS else '#059669'};
                color: white;
                font-size: 12px;
                font-weight: 700;
                border: none;
                border-radius: 8px;
                padding: 0 16px;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{ background: #047857; }}
        """)
        self._excel_btn.clicked.connect(self._export_excel)
        top_row.addWidget(self._excel_btn)
        dp_layout.addLayout(top_row)

        # Ay ve Yıl Bazında Filtreleme Layout
        date_filter_row = QHBoxLayout()
        date_filter_row.setSpacing(10)
        
        lbl_date_filter = QLabel("📅 Ay/Yıl Filtresi:")
        lbl_date_filter.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; font-weight: 600;")
        date_filter_row.addWidget(lbl_date_filter)
        
        # Ay ComboBox
        self.combo_ay = QComboBox()
        self.combo_ay.setFixedHeight(28)
        self.combo_ay.setFixedWidth(120)
        self.combo_ay.setStyleSheet(self._combo_style())
        self.combo_ay.addItem("Tüm Aylar", None)
        aylar = [
            ("Ocak", 1), ("Şubat", 2), ("Mart", 3), ("Nisan", 4),
            ("Mayıs", 5), ("Haziran", 6), ("Temmuz", 7), ("Ağustos", 8),
            ("Eylül", 9), ("Ekim", 10), ("Kasım", 11), ("Aralık", 12)
        ]
        for name, code in aylar:
            self.combo_ay.addItem(name, code)
        self.combo_ay.currentIndexChanged.connect(self._apply_filters)
        date_filter_row.addWidget(self.combo_ay)
        
        # Yıl ComboBox
        self.combo_yil = QComboBox()
        self.combo_yil.setFixedHeight(28)
        self.combo_yil.setFixedWidth(120)
        self.combo_yil.setStyleSheet(self._combo_style())
        self.combo_yil.addItem("Tüm Yıllar", None)
        
        import datetime
        current_year = datetime.datetime.now().year
        for y in range(current_year + 1, current_year - 5, -1):
            self.combo_yil.addItem(str(y), int(y))
        self.combo_yil.currentIndexChanged.connect(self._apply_filters)
        date_filter_row.addWidget(self.combo_yil)
        
        date_filter_row.addStretch()
        dp_layout.addLayout(date_filter_row)

        # Kolon Filtreleri Satırı
        self._filter_container = QWidget()
        filter_layout = QHBoxLayout(self._filter_container)
        filter_layout.setContentsMargins(0, 4, 0, 4)
        filter_layout.setSpacing(8)
        
        self.filters = []
        cols = IslemTablosu.KOLON_SETLERI.get(tablo_tipi, [])
        for c_name, _ in cols:
            le = QLineEdit()
            le.setPlaceholderText(f"🔍 {c_name}...")
            le.setFixedHeight(28)
            le.setStyleSheet(f"""
                QLineEdit {{
                    background: white;
                    border: 1px solid {COLORS['border']};
                    border-radius: 6px;
                    padding: 0 8px;
                    font-size: 11px;
                    color: {COLORS['text_primary']};
                }}
                QLineEdit:focus {{ border-color: {COLORS['btn_primary']}; }}
            """)
            le.textChanged.connect(self._apply_filters)
            filter_layout.addWidget(le)
            self.filters.append(le)
            
        dp_layout.addWidget(self._filter_container)

        self._tablo = IslemTablosu(tablo_tipi)
        dp_layout.addWidget(self._tablo, 1)

        self._stack.addWidget(detay_page)

    def _combo_style(self) -> str:
        return f"""
            QComboBox {{
                background: white;
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 0 8px;
                font-size: 11px;
                font-weight: 600;
                color: #1F2937;
            }}
            QComboBox:focus {{ border-color: {COLORS['btn_primary']}; }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background-color: white;
                color: #1F2937;
                selection-background-color: #DBEAFE;
                selection-color: #1E40AF;
                border: 1px solid {COLORS['border']};
            }}
        """

    def _parse_date(self, date_str: str):
        date_str = date_str.strip()
        if not date_str or date_str == "-":
            return None, None
        try:
            # Format 1: DD.MM.YYYY
            if "." in date_str:
                parts = date_str.split(".")
                if len(parts) == 3:
                    return int(parts[1]), int(parts[2])
            # Format 2: YYYY-MM-DD
            if "-" in date_str:
                parts = date_str.split("-")
                if len(parts) >= 3:
                    if len(parts[0]) == 4:
                        return int(parts[1]), int(parts[0])
                    else:
                        return int(parts[1]), int(parts[2])
        except Exception:
            pass
        return None, None

    def _on_kart_clicked(self, row: dict):
        sube_adi = row.get("sube_adi", "")
        kayit = row.get("kayit_sayisi", 0)
        gelir = float(row.get("toplam_gelir") or row.get("toplam_tutar") or row.get("toplam_gider") or 0)
        gider = float(row.get("toplam_gider") or 0)
        net = gelir - gider

        self._detay_sube_lbl.setText(f"📍 {sube_adi}  ({kayit} kayıt)")
        self._detay_gelir_lbl.setText(f"🟢 Gelir: {fmt_para(gelir)}")
        self._detay_gider_lbl.setText(f"🔴 Gider: {fmt_para(gider)}")
        
        if net >= 0:
            self._detay_net_lbl.setText(f"💎 Net: +{fmt_para(net)}")
            self._detay_net_lbl.setStyleSheet(f"""
                color: #1E40AF;
                font-size: 13px;
                font-weight: 700;
                padding: 8px 12px;
                background: #DBEAFE;
                border-radius: 8px;
                border: 1px solid #BFDBFE;
            """)
        else:
            self._detay_net_lbl.setText(f"⚠️ Net: -{fmt_para(abs(net))}")
            self._detay_net_lbl.setStyleSheet(f"""
                color: #B91C1C;
                font-size: 13px;
                font-weight: 700;
                padding: 8px 12px;
                background: #FEE2E2;
                border-radius: 8px;
                border: 1px solid #FCA5A5;
            """)

        # Filtreleri temizle
        for le in self.filters:
            le.blockSignals(True)
            le.clear()
            le.blockSignals(False)

        # Ay/Yıl filtrelerini sıfırla
        self.combo_ay.blockSignals(True)
        self.combo_ay.setCurrentIndex(0)
        self.combo_ay.blockSignals(False)

        self.combo_yil.blockSignals(True)
        self.combo_yil.setCurrentIndex(0)
        self.combo_yil.blockSignals(False)

        # Veriyi yükle
        try:
            rows = self._detay_fn(sube_adi)
        except Exception as e:
            rows = []
            self._detay_info.setText(f"Hata: {e}")

        self._tablo.load_rows(rows)
        self._back_btn.show()
        self._title_lbl.setText(f"{self._baslik}  →  {sube_adi}")
        self._stack.setCurrentIndex(1)
        self.resize(1100, 680)

    def _show_ozet(self):
        self._back_btn.hide()
        self._title_lbl.setText(self._baslik)
        self._stack.setCurrentIndex(0)
        self.resize(self._ozet_width, self._ozet_height)

    def _apply_filters(self):
        selected_ay = self.combo_ay.currentData()       # int or None
        selected_yil = self.combo_yil.currentData()     # int or None

        for row_idx in range(self._tablo.rowCount()):
            match = True
            
            # 1. Ay ve Yıl Seçimi ile Tarih Filtresi (Tarih kolonu her zaman 0. kolondur)
            if (selected_ay is not None) or (selected_yil is not None):
                tarih_item = self._tablo.item(row_idx, 0)
                if tarih_item:
                    ay, yil = self._parse_date(tarih_item.text())
                    if selected_ay is not None and ay != selected_ay:
                        match = False
                    if selected_yil is not None and yil != selected_yil:
                        match = False
                else:
                    match = False

            # 2. Kolon Bazlı Metin Aramaları
            if match:
                for col_idx, le in enumerate(self.filters):
                    txt = le.text().strip().lower()
                    if not txt:
                        continue
                    item = self._tablo.item(row_idx, col_idx)
                    cell_txt = item.text().lower() if item else ""
                    if txt not in cell_txt:
                        match = False
                        break
                        
            self._tablo.setRowHidden(row_idx, not match)

    def _export_excel(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        import re
        import datetime
        
        # Dosya adını temizle (özel karakterleri ve ok işaretini kaldır)
        title_text = self._title_lbl.text()
        clean_title = re.sub(r'[^\w\s\-]', '_', title_text)
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel Olarak Kaydet", f"{clean_title}.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return
            
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Detay Listesi"
            
            # Excel Stylings
            font_title = Font(name="Segoe UI", size=14, bold=True, color="1E3A8A")
            font_subtitle = Font(name="Segoe UI", size=9, italic=True, color="4B5563")
            font_header = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
            font_data = Font(name="Segoe UI", size=10, color="1F2937")
            font_total = Font(name="Segoe UI", size=11, bold=True, color="1E3A8A")
            
            fill_header = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid") # Soft Blue
            fill_total = PatternFill(start_color="EFF6FF", end_color="EFF6FF", fill_type="solid")  # Extremely Soft Blue
            
            border_thin = Border(
                left=Side(style="thin", color="E5E7EB"),
                right=Side(style="thin", color="E5E7EB"),
                top=Side(style="thin", color="E5E7EB"),
                bottom=Side(style="thin", color="E5E7EB")
            )
            border_total = Border(
                top=Side(style="thin", color="93C5FD"),
                bottom=Side(style="double", color="1E3A8A")
            )
            
            # 1. Rapor Başlık Bloğu
            ws.append([title_text])
            ws.cell(row=1, column=1).font = font_title
            
            rapor_tarih = f"Raporlama Tarihi: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
            ws.append([rapor_tarih])
            ws.cell(row=2, column=1).font = font_subtitle
            
            ws.append([]) # Boşluk
            
            # Headers
            headers = []
            for col in range(self._tablo.columnCount()):
                item = self._tablo.horizontalHeaderItem(col)
                headers.append(item.text() if item else f"Kolon {col+1}")
            ws.append(headers)
            
            header_row_idx = 4
            for col_idx in range(len(headers)):
                cell = ws.cell(row=header_row_idx, column=col_idx+1)
                cell.font = font_header
                cell.fill = fill_header
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = border_thin
            
            # Helper to clean financial strings to pure float
            def clean_amount(val_str: str):
                if not val_str or val_str.strip() in ("-", ""):
                    return 0.0
                s = val_str.replace("₺", "").replace("TL", "").replace("$", "").replace("€", "").replace("+", "").strip()
                s = s.replace(".", "").replace(",", ".")
                try:
                    return float(s)
                except ValueError:
                    return 0.0
            
            # Sum tracker for columns
            column_sums = {col: 0.0 for col in range(self._tablo.columnCount())}
            
            # Rows writing
            current_row_idx = 5
            for row in range(self._tablo.rowCount()):
                if self._tablo.isRowHidden(row):
                    continue
                
                row_data = []
                for col in range(self._tablo.columnCount()):
                    header_text = headers[col]
                    item = self._tablo.item(row, col)
                    cell_text = item.text() if item else ""
                    
                    if header_text in ("Tutar", "Gelir", "Gider"):
                        val_num = clean_amount(cell_text)
                        row_data.append(val_num)
                        column_sums[col] += val_num
                    else:
                        row_data.append(cell_text)
                        
                ws.append(row_data)
                
                # Style active data row
                for col in range(len(row_data)):
                    cell = ws.cell(row=current_row_idx, column=col+1)
                    cell.font = font_data
                    cell.border = border_thin
                    
                    if headers[col] in ("Tutar", "Gelir", "Gider"):
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                        cell.number_format = '#,##0.00'
                    elif headers[col] == "Tarih":
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    else:
                        cell.alignment = Alignment(horizontal="left", vertical="center")
                        
                current_row_idx += 1
            
            # 2. Dynamic GENEL TOPLAM Row
            summary_row = []
            for col in range(self._tablo.columnCount()):
                if col == 0:
                    summary_row.append("GENEL TOPLAM")
                elif headers[col] in ("Tutar", "Gelir", "Gider"):
                    summary_row.append(column_sums[col])
                else:
                    summary_row.append("")
                    
            ws.append(summary_row)
            
            # Style summary row
            for col in range(len(summary_row)):
                cell = ws.cell(row=current_row_idx, column=col+1)
                cell.font = font_total
                cell.fill = fill_total
                cell.border = border_total
                
                if col == 0:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                elif headers[col] in ("Tutar", "Gelir", "Gider"):
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    cell.number_format = '#,##0.00'
            
            # 3. Auto Width Adjustment
            for col in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    if cell.row in (1, 2, 3): # Skip title headers for width
                        continue
                    if cell.value is not None:
                        # If it is float formatted, round to string format
                        if isinstance(cell.value, float):
                            val_str = f"{cell.value:,.2f}"
                        else:
                            val_str = str(cell.value)
                        max_len = max(max_len, len(val_str))
                ws.column_dimensions[col_letter].width = max(max_len + 4, 12)
                
            # Set gridlines visible
            ws.views.sheetView[0].showGridLines = True
            
            wb.save(path)
            
            # Premium styled success popup
            msg = QMessageBox(self)
            msg.setWindowTitle("Başarılı")
            msg.setText("Excel raporu ve genel toplamlar başarıyla şekillendirilip kaydedildi!")
            msg.setStyleSheet("""
                QMessageBox { background-color: white; }
                QLabel { color: #1F2937; font-size: 13px; font-weight: 600; min-width: 280px; min-height: 40px; }
                QPushButton { background-color: #2563EB; color: white; border: none; border-radius: 6px; padding: 6px 18px; font-size: 11px; font-weight: bold; }
                QPushButton:hover { background-color: #1D4ED8; }
            """)
            msg.exec()
            
        except Exception as e:
            import traceback
            err_msg = f"Excel kaydedilirken hata oluştu:\n{e}\n\nDetay:\n{traceback.format_exc()}"
            print(err_msg)
            
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Hata")
            msg.setText(f"Excel raporu oluşturulurken beklenmedik hata oluştu:\n{e}")
            msg.setStyleSheet("""
                QMessageBox { background-color: white; }
                QLabel { color: #DC2626; font-size: 12px; font-weight: 600; min-width: 240px; }
                QPushButton { background-color: #DC2626; color: white; border: none; border-radius: 6px; padding: 6px 16px; }
            """)
            msg.exec()
