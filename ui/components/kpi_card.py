"""
KPI kart bileşeni — PHP admin panelindeki renkli kartların PyQt6 karşılığı.
"""
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QBrush, QLinearGradient, QPen, QFont
from ui.theme import COLORS, FONTS, CARD_RADIUS


class KPICard(QFrame):
    """
    Renkli gradient arka planlı KPI kart bileşeni.
    Hover animasyonu ve tıklanabilirlik desteği.
    """

    def __init__(
        self,
        title: str,
        value: str,
        subtitle: str = "",
        color: str = COLORS["green"],
        color2: str = "",
        click_cb=None,
        parent=None,
    ):
        super().__init__(parent)
        self._base_color = color
        self._color2 = color2 or self._darken(color)
        self._click_cb = click_cb
        self._hovered = False
        self._elevation = 0.0

        self.setFixedHeight(145)
        self.setMinimumWidth(190)
        self.setCursor(Qt.CursorShape.PointingHandCursor if click_cb else Qt.CursorShape.ArrowCursor)
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(
            f"color: rgba(255,255,255,0.88); font-size: 12px; font-weight: 500; background: transparent;"
        )
        self.title_lbl.setWordWrap(True)

        self.value_lbl = QLabel(value)
        self.value_lbl.setStyleSheet(
            "color: white; font-size: 22px; font-weight: 700; background: transparent; letter-spacing: -0.5px;"
        )
        self.value_lbl.setWordWrap(True)

        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setStyleSheet(
            "color: rgba(255,255,255,0.70); font-size: 10px; background: transparent;"
        )
        self.sub_lbl.setWordWrap(True)

        layout.addWidget(self.title_lbl)
        layout.addWidget(self.value_lbl)
        layout.addStretch()
        if subtitle:
            layout.addWidget(self.sub_lbl)

    def set_value(self, value: str, subtitle: str = ""):
        self.value_lbl.setText(value)
        if subtitle:
            self.sub_lbl.setText(subtitle)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        # Gölge efekti
        if self._hovered:
            shadow_rect = rect.adjusted(4, 4, -4, -4)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 40))
            painter.drawRoundedRect(shadow_rect.adjusted(-2, 2, 2, 2), CARD_RADIUS, CARD_RADIUS)

        # Gradient arka plan
        gradient = QLinearGradient(0, 0, rect.width(), rect.height())
        gradient.setColorAt(0.0, QColor(self._base_color))
        gradient.setColorAt(1.0, QColor(self._color2))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        draw_rect = rect.adjusted(0, 0, 0, 0) if not self._hovered else rect.adjusted(0, -3, 0, 0)
        painter.drawRoundedRect(draw_rect, CARD_RADIUS, CARD_RADIUS)

        # Dekoratif daire
        painter.setBrush(QColor(255, 255, 255, 20))
        painter.drawEllipse(rect.right() - 60, rect.bottom() - 60, 90, 90)
        painter.setBrush(QColor(255, 255, 255, 12))
        painter.drawEllipse(rect.right() - 30, rect.top() - 30, 70, 70)

        painter.end()
        super().paintEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self._click_cb and event.button() == Qt.MouseButton.LeftButton:
            self._click_cb()
        super().mousePressEvent(event)

    @staticmethod
    def _darken(hex_color: str, factor: float = 0.75) -> str:
        try:
            c = QColor(hex_color)
            r = int(c.red() * factor)
            g = int(c.green() * factor)
            b = int(c.blue() * factor)
            return QColor(r, g, b).name()
        except Exception:
            return hex_color
