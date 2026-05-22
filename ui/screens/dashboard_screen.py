"""
Dashboard ekranı — PHP admin_panel.php / admin.php'nin PyQt6 karşılığı.
12 KPI kartı + Yıllık Gelir-Gider grafik.
"""
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QGridLayout, QFrame, QPushButton, QComboBox, QSizePolicy,
    QDateEdit, QSpacerItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont

from ui.theme import COLORS, FONTS
from ui.components.kpi_card import KPICard
from ui.components.detay_dialog import DetayDialog
from ui.components.gelir_gider_chart import GelirGiderChart
from services.dashboard_service import get_all_dashboard_data
from services import detay_service
from utils.format import fmt_para, fmt_signed


class DashboardLoader(QThread):
    """Arka planda veri yükler — UI donmaması için."""
    data_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, userid: int, musterino: int, yil: int):
        super().__init__()
        self.userid = userid
        self.musterino = musterino
        self.yil = yil

    def run(self):
        try:
            data = get_all_dashboard_data(self.userid, self.musterino, self.yil)
            self.data_ready.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class DashboardScreen(QWidget):
    """
    Ana dashboard ekranı.
    12 KPI kartını 2 satır × 6 sütun grid içinde gösterir.
    """

    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self._user = user
        self._userid = user.get("GercekUserId", user.get("Kayitno", 1))
        self._musterino = user.get("GercekUserId", user.get("Kayitno", 1))
        self._yil = datetime.now().year
        self._loader = None
        self._cards: dict[str, KPICard] = {}
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(20)

        # ── Başlık çubuğu ──────────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: 24px;
            font-weight: 700;
            letter-spacing: 1px;
        """)
        header.addWidget(title)
        header.addStretch()
        # Şirket / kullanıcı
        sirket = self._user.get("Kurum_Durumu", "IQ Finans")
        kullanici = self._user.get("Adi", "")
        profil = QLabel(f"🏢 {sirket}  •  👤 {kullanici}")
        profil.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; margin-right: 15px;")
        header.addWidget(profil)

        root.addLayout(header)

        # ── Bilgi banner ────────────────────────────────────────────────────────
        self.banner = QLabel("FİNANS DURUM BİLGİSİ")
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner.setFixedHeight(38)
        self.banner.setStyleSheet(f"""
            background: {COLORS['text_primary']};
            color: white;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 3px;
            border-radius: 10px;
            padding: 0 20px;
        """)
        root.addWidget(self.banner)

        # Banner altı araç çubuğu (Yıl Seçimi sağda)
        banner_sub = QHBoxLayout()
        banner_sub.addStretch()

        self.yil_combo = QComboBox()
        current_year = datetime.now().year
        for y in range(current_year + 1, current_year - 6, -1):
            self.yil_combo.addItem(str(y), y)
        self.yil_combo.setCurrentText(str(self._yil))
        self.yil_combo.setFixedHeight(32)
        self.yil_combo.setFixedWidth(120)
        self.yil_combo.setStyleSheet(f"""
            QComboBox {{
                background: white;
                border: 1.5px solid {COLORS['border']};
                border-radius: 8px;
                padding: 0 10px;
                font-size: 12px;
                font-weight: 600;
                color: {COLORS['text_primary']};
            }}
            QComboBox:focus {{
                border-color: {COLORS['btn_primary']};
            }}
            QComboBox::drop-down {{ border: none; }}
        """)
        self.yil_combo.currentIndexChanged.connect(self._on_yil_changed)
        banner_sub.addWidget(self.yil_combo)
        root.addLayout(banner_sub)

        # ── Scroll alan ─────────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(20)

        # ── KPI Grid (2 × 6) ───────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(16)

        KPI_DEFS = [
            # (key,              başlık,              renk1,                renk2,        satır, sütun)
            ("nakit_kasa_gelir", "Nakit Kasa Gelir",  COLORS["green"],      "#059669",    0, 0),
            ("nakit_kasa_odeme", "Nakit Kasa Ödeme",  COLORS["teal"],       "#0284C7",    0, 1),
            ("kesilen_fatura",   "Kesilen Fatura",     COLORS["purple"],     "#6D28D9",    0, 2),
            ("gelen_fatura",     "Gelen Fatura",       COLORS["pink"],       "#DB2777",    0, 3),
            ("gider_pusulasi",   "Gider Pusulası",     "#16A34A",            "#15803D",    0, 4),
            ("kurum_odemeleri",  "Kurum Ödemeleri",    COLORS["dark_blue"],  "#162C47",    0, 5),
            ("maas_kira_smm",    "Maaş Kira SMM",      "#374151",            "#1F2937",    1, 0),
            ("bankalar_bakiye",  "Bankalar Bakiye",    COLORS["grey"],       "#4B5563",    1, 1),
            ("sanal_pos",        "Sanal Pos",          "#111827",            "#030712",    1, 2),
            ("fiziksel_pos",     "Fiziksel Pos",       "#1F2937",            "#111827",    1, 3),
            ("kredi_karti",      "Kredi Kartları",     "#D97706",            "#B45309",    1, 4),
            ("genel_hesap",      "Genel Hesap Tablosu","#EA580C",            "#C2410C",    1, 5),
        ]

        for key, title, c1, c2, row, col in KPI_DEFS:
            card = KPICard(
                title=title,
                value="Yükleniyor...",
                color=c1,
                color2=c2,
                click_cb=lambda k=key: self._on_card_click(k),
            )
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._cards[key] = card
            grid.addWidget(card, row, col)

        vbox.addLayout(grid)

        # ── Tarih filtresi + Excel ──────────────────────────────────────────────
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        ilk_lbl = QLabel("İlk Tarih:")
        ilk_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        filter_bar.addWidget(ilk_lbl)

        self.ilk_tarih = QDateEdit()
        self.ilk_tarih.setCalendarPopup(True)
        self.ilk_tarih.setDate(QDate(self._yil, 1, 1))
        self.ilk_tarih.setFixedHeight(34)
        self.ilk_tarih.setStyleSheet(self._input_style())
        filter_bar.addWidget(self.ilk_tarih)

        son_lbl = QLabel("Son Tarih:")
        son_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        filter_bar.addWidget(son_lbl)

        self.son_tarih = QDateEdit()
        self.son_tarih.setCalendarPopup(True)
        self.son_tarih.setDate(QDate.currentDate())
        self.son_tarih.setFixedHeight(34)
        self.son_tarih.setStyleSheet(self._input_style())
        filter_bar.addWidget(self.son_tarih)

        filter_bar.addStretch()

        self.excel_btn = QPushButton("📥 EXCEL İNDİR")
        self.excel_btn.setFixedHeight(34)
        self.excel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.excel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['btn_excel']};
                color: white;
                font-size: 12px;
                font-weight: 700;
                border: none;
                border-radius: 8px;
                padding: 0 18px;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{ background: #047857; }}
        """)
        filter_bar.addWidget(self.excel_btn)

        vbox.addLayout(filter_bar)

        # ── Grafik ─────────────────────────────────────────────────────────────
        self.chart = GelirGiderChart()
        vbox.addWidget(self.chart)

        scroll.setWidget(container)
        root.addWidget(scroll)

    def _input_style(self) -> str:
        return f"""
            QDateEdit {{
                background: white;
                border: 1.5px solid {COLORS['border']};
                border-radius: 8px;
                padding: 0 10px;
                font-size: 12px;
                color: {COLORS['text_primary']};
            }}
        """

    def _load_data(self):
        if self._loader and self._loader.isRunning():
            return

        self._loader = DashboardLoader(self._userid, self._musterino, self._yil)
        self._loader.data_ready.connect(self._on_data_ready)
        self._loader.error.connect(self._on_error)
        self._loader.start()

    def _on_data_ready(self, data: dict):
        c = self._cards
        
        # Grafik verilerini güncelle
        self.chart.load_data(data.get("monthly_chart", []))

        # Nakit Kasa Gelir
        kasa = data.get("nakit_kasa", {})
        c["nakit_kasa_gelir"].set_value(
            fmt_para(kasa.get("gelir", 0)),
            f"Gelir: {fmt_para(kasa.get('gelir', 0))}  Gider: {fmt_para(kasa.get('gider', 0))}"
        )

        # Nakit Kasa Ödeme
        gider = data.get("gider", {})
        c["nakit_kasa_odeme"].set_value(
            fmt_para(gider.get("gider", 0)),
            "genel_hesap_hareketleri · gider"
        )

        # Kesilen / Gelen Fatura
        fat = data.get("faturalar", {})
        c["kesilen_fatura"].set_value(
            fmt_para(fat.get("kesilen", 0)),
            "Detaylar için tıklayın..."
        )
        c["gelen_fatura"].set_value(
            fmt_para(fat.get("gelen", 0)),
            "Detaylar için tıklayın..."
        )

        # Gider Pusulası
        gp = data.get("gider_pusulasi", {})
        c["gider_pusulasi"].set_value(
            fmt_para(gp.get("gider", 0)),
            "Parça Alımı (Cihaz)"
        )

        # Kurum Ödemeleri
        kurum = data.get("kurum_odemeleri", {})
        c["kurum_odemeleri"].set_value(
            fmt_para(kurum.get("toplam", 0)),
            "Vergi ödeme detayları"
        )

        # Maaş Kira SMM
        mks = data.get("maas_kira_smm", {})
        c["maas_kira_smm"].set_value(
            fmt_para(mks.get("toplam", 0)),
            "Personel, Kira ve Müşavirlik Giderleri"
        )

        # Bankalar Bakiye
        c["bankalar_bakiye"].set_value("₺0,00", "Detaylar için tıklayın...")

        # Sanal Pos
        pos = data.get("sanal_pos", {})
        c["sanal_pos"].set_value(
            fmt_para(pos.get("islem", 0)),
            f"İşlem: {fmt_para(pos.get('islem', 0))}  Ödeme: {fmt_para(pos.get('odeme', 0))}"
        )

        # Fiziksel Pos
        c["fiziksel_pos"].set_value("₺0,00", "Yerel tablodan anlık veriler")

        # Kredi Kartları
        kk = data.get("kredi_karti", {})
        c["kredi_karti"].set_value(
            fmt_para(kk.get("borc", 0)),
            f"Borç: {fmt_para(kk.get('borc', 0))}  Ödeme: {fmt_para(kk.get('odeme', 0))}"
        )

        # Genel Hesap
        gh = data.get("genel_hesap", {})
        c["genel_hesap"].set_value(
            fmt_para(gh.get("net", 0)),
            "genel_hesap_hareketleri · genelHesap"
        )

    def _on_error(self, msg: str):
        self.banner.setText(f"⚠  Hata: {msg}")
        self.banner.setStyleSheet(f"""
            background: {COLORS['red']};
            color: white;
            font-size: 12px;
            font-weight: 600;
            border-radius: 10px;
            padding: 0 20px;
        """)
        for card in self._cards.values():
            card.set_value("Hata")

    # ─── KART TIKLAMA ────────────────────────────────────────────────────────

    def _on_card_click(self, key: str):
        """KPI kartına tıklandığında ilgili detay diyaloğunu açar."""
        uid = self._userid
        mno = self._musterino
        yil = self._yil

        if key in ("nakit_kasa_gelir", "nakit_kasa_odeme"):
            ozet = detay_service.get_nakit_kasa_sube_ozet(uid, mno, yil)
            def detay_fn(sube_adi):
                # sube id'sini bul
                sube_id = None
                for r in ozet:
                    if r.get("sube_adi") == sube_adi:
                        sube_id = r.get("sube_id")
                        break
                return detay_service.get_hareketler_detay(uid, mno, yil, sube_id=sube_id)
            dlg = DetayDialog(
                baslik="Nakit Kasa — Şube Özeti",
                ozet_rows=ozet,
                detay_fn=detay_fn,
                tablo_tipi="hareketler",
                parent=self,
            )

        elif key in ("genel_hesap",):
            ozet = detay_service.get_genel_hesap_sube_ozet(uid, mno, yil)
            def detay_fn(sube_adi):
                return detay_service.get_genel_hesap_detay(uid, mno, yil, sube_adi=sube_adi)
            dlg = DetayDialog(
                baslik="Genel Hesap Tablosu — Şube Özeti",
                ozet_rows=ozet,
                detay_fn=detay_fn,
                tablo_tipi="genel_hesap",
                parent=self,
            )

        elif key == "kesilen_fatura":
            ozet = detay_service.get_fatura_sube_ozet(uid, yil, "gelir")
            def detay_fn(sube_adi):
                return detay_service.get_fatura_detay(uid, yil, "gelir", unvan=sube_adi)
            dlg = DetayDialog(
                baslik="Kesilen Faturalar — Ünvan Özeti",
                ozet_rows=ozet,
                detay_fn=detay_fn,
                tablo_tipi="faturalar",
                gelir_field="toplam_tutar",
                gider_field="toplam_tutar",
                tutar_field="toplam_tutar",
                parent=self,
            )

        elif key == "gelen_fatura":
            ozet = detay_service.get_fatura_sube_ozet(uid, yil, "gider")
            def detay_fn(sube_adi):
                return detay_service.get_fatura_detay(uid, yil, "gider", unvan=sube_adi)
            dlg = DetayDialog(
                baslik="Gelen Faturalar — Ünvan Özeti",
                ozet_rows=ozet,
                detay_fn=detay_fn,
                tablo_tipi="faturalar",
                gelir_field="toplam_tutar",
                gider_field="toplam_tutar",
                tutar_field="toplam_tutar",
                parent=self,
            )

        elif key in ("gider_pusulasi", "kurum_odemeleri", "maas_kira_smm"):
            ozet = detay_service.get_gider_sube_ozet(uid, mno, yil)
            def detay_fn(sube_adi):
                return detay_service.get_genel_hesap_detay(uid, mno, yil, sube_adi=sube_adi)
            dlg = DetayDialog(
                baslik="Gider Detayı — Kategori Özeti",
                ozet_rows=ozet,
                detay_fn=detay_fn,
                tablo_tipi="genel_hesap",
                gelir_field="toplam_gelir",
                gider_field="toplam_gider",
                parent=self,
            )

        else:
            # Henüz uygulanmamış kartlar için basit mesaj
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, key,
                f"'{key}' kartı için detay görünümü yakında eklenecek."
            )
            return

        dlg.exec()

    def _on_yil_changed(self):
        self._yil = self.yil_combo.currentData()
        self.banner.setText(f"FİNANS DURUM BİLGİSİ ( {self._yil} )")
        # Kartları yükleniyor moduna al
        for card in self._cards.values():
            card.set_value("Yükleniyor...")
        self._load_data()
