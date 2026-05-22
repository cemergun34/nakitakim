"""
Aylık tablo bileşeni — Gelir/Gider raporlarındaki pivot tablolar için.
12 ay sütunu + Yıllık Toplam sütunu ile DataTable benzeri görünüm.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
    QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont
from ui.theme import COLORS, FONTS
from utils.format import fmt_para


AYLAR_KISA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz",
               "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


class MonthlyTable(QWidget):
    """
    Kategori × 12 Ay × Yıllık Toplam pivot tablosu.
    Veri formatı: services.rapor_service._pivot_to_monthly_table() çıktısı.
    """

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._data = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Başlık çubuğu
        header = QFrame()
        header.setFixedHeight(44)
        header.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['btn_primary']};
                border-radius: 10px 10px 0 0;
            }}
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 0, 16, 0)

        lbl = QLabel(f"⊞  {self._title}")
        lbl.setStyleSheet("color: white; font-weight: 600; font-size: 13px; background: transparent;")
        h_layout.addWidget(lbl)
        h_layout.addStretch()

        layout.addWidget(header)

        # Tablo
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setGridStyle(Qt.PenStyle.SolidLine)

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: white;
                alternate-background-color: {COLORS['row_alt']};
                gridline-color: {COLORS['border']};
                font-size: 11px;
                border: 1px solid {COLORS['border']};
                border-radius: 0 0 10px 10px;
            }}
            QTableWidget::item {{
                padding: 5px 8px;
                color: {COLORS['text_primary']};
            }}
            QTableWidget::item:selected {{
                background: {COLORS['table_hover']};
                color: {COLORS['text_primary']};
            }}
            QHeaderView::section {{
                background: {COLORS['table_header']};
                color: {COLORS['text_secondary']};
                font-size: 10px;
                font-weight: 600;
                padding: 6px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)

        layout.addWidget(self.table)

    def load_data(self, data: dict):
        """
        data = {"aylar": [...12...], "satirlar": [...], "genel_toplam": float}
        """
        self._data = data
        if not data or not data.get("satirlar"):
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        cols = ["Kategori"] + AYLAR_KISA + ["Yıllık Toplam"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)

        satirlar = data["satirlar"]
        self.table.setRowCount(len(satirlar))

        for row_idx, satir in enumerate(satirlar):
            is_total = satir.get("is_total", False)

            # Kategori
            item = QTableWidgetItem(satir["kategori"])
            if is_total:
                item.setFont(QFont(FONTS["primary"], 9, QFont.Weight.Bold))
                item.setForeground(QBrush(QColor(COLORS["table_total_fg"])))
            else:
                item.setFont(QFont(FONTS["primary"], 9))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 0, item)

            # Aylık değerler
            for col_idx, val in enumerate(satir["aylik"]):
                text = fmt_para(float(val)) if float(val) != 0 else "-"
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if is_total:
                    item.setFont(QFont(FONTS["primary"], 9, QFont.Weight.Bold))
                    item.setForeground(QBrush(QColor(COLORS["table_total_fg"])))
                    item.setBackground(QBrush(QColor(COLORS["table_total_bg"])))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, col_idx + 1, item)

            # Yıllık toplam
            yillik = float(satir.get("yillik_toplam", 0))
            item = QTableWidgetItem(fmt_para(yillik))
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            font = QFont(FONTS["primary"], 9, QFont.Weight.Bold)
            item.setFont(font)
            if is_total:
                item.setForeground(QBrush(QColor(COLORS["table_total_fg"])))
                item.setBackground(QBrush(QColor(COLORS["table_total_bg"])))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, len(AYLAR_KISA) + 1, item)

        self.table.resizeRowsToContents()
