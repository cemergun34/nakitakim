"""
Yıllık Gelir-Gider Karşılaştırma Grafiği.
Custom QPainter ile çizilmiş, premium ve yüksek performanslı bar grafiği.
"""
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont, QBrush, QPen, QLinearGradient
from utils.format import fmt_para


class GelirGiderChart(QWidget):
    """Modern custom bar chart widget comparing income vs expenses by month."""

    MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(240)
        self._data: list[dict] = []
        self._max_value = 1.0

    def load_data(self, monthly_data: list[dict]):
        """
        Loads database values.
        monthly_data is a list of dicts like: [{'ay': '01', 'toplam_gelir': 123.4, 'toplam_gider': 99.2}]
        """
        # Initialize 12 months with zeros
        self._data = [{"gelir": 0.0, "gider": 0.0} for _ in range(12)]
        
        for row in monthly_data:
            try:
                idx = int(row.get("ay", 1)) - 1
                if 0 <= idx < 12:
                    self._data[idx]["gelir"] = float(row.get("toplam_gelir") or 0.0)
                    self._data[idx]["gider"] = float(row.get("toplam_gider") or 0.0)
            except Exception:
                pass

        # Calculate max value for scaling
        max_val = 0.0
        for m in self._data:
            max_val = max(max_val, m["gelir"], m["gider"])
        self._max_value = max_val if max_val > 0 else 1.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Dimensions
        w = self.width()
        h = self.height()
        
        # Background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(0, 0, w, h, 12, 12)

        # Padding
        pad_top = 40
        pad_bottom = 35
        pad_left = 65
        pad_right = 20
        
        chart_w = w - pad_left - pad_right
        chart_h = h - pad_top - pad_bottom

        if not self._data:
            p.setPen(QColor("#6B7280"))
            p.setFont(QFont("Inter", 11, QFont.Weight.Medium))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Grafik verisi yükleniyor...")
            p.end()
            return

        # ── Grid Lines and Y-Axis Labels ──────────────────────────────────────
        steps = 4
        p.setFont(QFont("Inter", 8))
        grid_pen = QPen(QColor("#E5E7EB"), 1, Qt.PenStyle.DashLine)
        
        for i in range(steps + 1):
            val = (self._max_value / steps) * i
            y = pad_top + chart_h - (chart_h / steps) * i
            
            # Grid line
            p.setPen(grid_pen)
            p.drawLine(int(pad_left), int(y), int(w - pad_right), int(y))
            
            # Y label
            p.setPen(QColor("#6B7280"))
            p.drawText(QRectF(5, y - 8, pad_left - 12, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, fmt_para(val))

        # ── Legend ────────────────────────────────────────────────────────────
        p.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        # Gelir Indicator
        p.setBrush(QColor("#10B981"))
        p.drawRoundedRect(pad_left, 15, 12, 12, 3, 3)
        p.setPen(QColor("#1F2937"))
        p.drawText(pad_left + 18, 25, "GELİR")

        # Gider Indicator
        p.setBrush(QColor("#EF4444"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(pad_left + 80, 15, 12, 12, 3, 3)
        p.setPen(QColor("#1F2937"))
        p.drawText(pad_left + 98, 25, "GİDER")

        # ── Bars and X-Axis Labels ────────────────────────────────────────────
        col_w = chart_w / 12
        bar_gap = 4
        bar_w = (col_w - 20) / 2
        
        for i in range(12):
            col_x = pad_left + col_w * i
            
            # Values
            gelir = self._data[i]["gelir"]
            gider = self._data[i]["gider"]
            
            # Normalized Heights
            h_gelir = (gelir / self._max_value) * chart_h
            h_gider = (gider / self._max_value) * chart_h
            
            # Coordinates
            y_base = pad_top + chart_h
            
            # Draw Gelir Bar
            if h_gelir > 0:
                g_gradient = QLinearGradient(col_x, y_base - h_gelir, col_x, y_base)
                g_gradient.setColorAt(0, QColor("#34D399"))
                g_gradient.setColorAt(1, QColor("#10B981"))
                p.setBrush(QBrush(g_gradient))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(QRectF(col_x, y_base - h_gelir, bar_w, h_gelir), 3, 3)
            
            # Draw Gider Bar
            if h_gider > 0:
                r_gradient = QLinearGradient(col_x + bar_w + bar_gap, y_base - h_gider, col_x + bar_w + bar_gap, y_base)
                r_gradient.setColorAt(0, QColor("#F87171"))
                r_gradient.setColorAt(1, QColor("#EF4444"))
                p.setBrush(QBrush(r_gradient))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(QRectF(col_x + bar_w + bar_gap, y_base - h_gider, bar_w, h_gider), 3, 3)
            
            # Draw X Month Label
            p.setFont(QFont("Inter", 8, QFont.Weight.Medium))
            p.setPen(QColor("#4B5563"))
            p.drawText(QRectF(col_x, y_base + 6, col_w, 20), Qt.AlignmentFlag.AlignCenter, self.MONTHS[i])
            
        p.end()
