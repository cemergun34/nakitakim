from __future__ import annotations
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ayarlar_screen_patch.py
=======================
Veritabanı sekmesini (VeriTabaniCard, MigrasyonDialog, tab) 
ayarlar_screen.py'a güvenli şekilde ekler.
"""
import re, sys
from pathlib import Path

SRC = Path("ui/screens/ayarlar_screen.py")
text = SRC.read_text(encoding="utf-8")

# ──────────────────────────────────────────────────────────────────────────────
# 1. Dosyanın SONUNA worker + card + dialog sınıflarını ekle
# ──────────────────────────────────────────────────────────────────────────────
APPEND_CODE = '''

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  VERİTABANI AYARLARI  —  eklendi: db_config tabanlı SQLite/PostgreSQL       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# ── SweetConfirmDialog (yardımcı dialog) ──────────────────────────────────────

class SweetConfirmDialog(QDialog):
    """Minimal onay diyaloğu (SweetAlert tarzı)."""

    def __init__(self, parent=None, title="", text="",
                 confirm_text="Evet", cancel_text="İptal", is_danger=False):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._result = False
        self._build(title, text, confirm_text, cancel_text, is_danger)

    def _build(self, title, text, confirm_text, cancel_text, is_danger):
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        from PyQt6.QtGui import QColor
        master = QVBoxLayout(self)
        master.setContentsMargins(12, 12, 12, 12)
        box = QFrame()
        box.setObjectName("scd_box")
        box.setStyleSheet(
            "QFrame#scd_box{background:#ffffff;border:1.5px solid #e2e8f0;border-radius:16px;}"
        )
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(20); sh.setColor(QColor(0,0,0,40)); sh.setOffset(0,4)
        box.setGraphicsEffect(sh)
        master.addWidget(box)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(24,24,24,20); lay.setSpacing(12)
        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet("font-size:15px;font-weight:700;color:#1e293b;background:transparent;border:none;")
        lay.addWidget(t)
        d = QLabel(text)
        d.setWordWrap(True); d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d.setStyleSheet("font-size:12px;color:#475569;background:transparent;border:none;")
        lay.addWidget(d)
        lay.addSpacing(4)
        brow = QHBoxLayout(); brow.setSpacing(8)
        if cancel_text:
            cb = QPushButton(cancel_text)
            cb.setFixedHeight(36)
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setStyleSheet(
                "QPushButton{background:#f1f5f9;color:#475569;border:none;border-radius:8px;font-size:12px;font-weight:600;padding:0 16px;}"
                "QPushButton:hover{background:#e2e8f0;}")
            cb.clicked.connect(self.reject)
            brow.addWidget(cb)
        ok_color = "#ef4444" if is_danger else "#6366f1"
        ob = QPushButton(confirm_text)
        ob.setFixedHeight(36)
        ob.setCursor(Qt.CursorShape.PointingHandCursor)
        ob.setStyleSheet(
            f"QPushButton{{background:{ok_color};color:white;border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:{'#dc2626' if is_danger else '#4f46e5'}}}")
        ob.clicked.connect(self.accept)
        brow.addWidget(ob)
        lay.addLayout(brow)

    @classmethod
    def confirm(cls, parent, title, text, confirm_text="Evet",
                cancel_text="İptal", is_danger=False):
        dlg = cls(parent, title, text, confirm_text, cancel_text, is_danger)
        return dlg.exec() == QDialog.DialogCode.Accepted


# ── PostgreSQL bağlantı test worker ──────────────────────────────────────────

class VeriTabaniTestWorker(QThread):
    islendi = pyqtSignal(dict)

    def __init__(self, host, port, dbname, user, password, sslmode):
        super().__init__()
        self._h, self._port, self._db = host, port, dbname
        self._user, self._pw, self._ssl = user, password, sslmode

    def run(self):
        try:
            import psycopg2
        except ImportError:
            self.islendi.emit({"success": False,
                "message": "psycopg2 yüklü değil.\npip install psycopg2-binary", "ver": ""})
            return
        params = dict(host=self._h, port=self._port, dbname=self._db,
                      user=self._user, sslmode=self._ssl, connect_timeout=8)
        if self._pw:
            params["password"] = self._pw
        try:
            conn = psycopg2.connect(**params)
            v = conn.server_version
            conn.close()
            self.islendi.emit({"success": True, "message": "Bağlantı başarılı!",
                "ver": f"PostgreSQL {v//10000}.{(v%10000)//100}"})
        except Exception as e:
            self.islendi.emit({"success": False, "message": str(e), "ver": ""})


# ── SQLite → PostgreSQL migrasyon worker ─────────────────────────────────────

class MigrasyonWorker(QThread):
    ilerleme = pyqtSignal(str, int, int, bool)
    islendi  = pyqtSignal(bool, str)

    def __init__(self, batch_size: int = 250):
        super().__init__()
        self._batch_size = batch_size

    def run(self):
        from db.sqlite_to_pg import migrate_all
        toplam = 0
        hatalar: list[str] = []
        try:
            for s in migrate_all(batch_size=self._batch_size):
                if s.bitti:
                    break
                if s.hata:
                    hatalar.append(f"{s.tablo}: {s.hata}")
                if not s.ara:
                    toplam += s.aktarilan
                self.ilerleme.emit(s.tablo, s.aktarilan, s.toplam, s.ara)
            if hatalar:
                self.islendi.emit(False,
                    f"Tamamlandı — {toplam:,} kayıt aktarıldı.\\nHatalar:\\n" + "\\n".join(hatalar[:5]))
            else:
                self.islendi.emit(True, f"✅  Tüm veriler aktarıldı!\\n{toplam:,} kayıt PostgreSQL\'e taşındı.")
        except Exception as e:
            self.islendi.emit(False, f"Hata: {e}")


# ── Migrasyon ilerleme diyaloğu ───────────────────────────────────────────────

class MigrasyonDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(640)
        self.setModal(True)
        self._worker: MigrasyonWorker | None = None
        self._tablo_sayisi = 0
        self._satir_lbl_map: dict[str, tuple] = {}
        self._satir_map: dict[str, bool] = {}
        self._toplam_aktarilan = 0
        self._build()

    def _build(self):
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QScrollArea
        from PyQt6.QtGui import QColor
        master = QVBoxLayout(self)
        master.setContentsMargins(16, 16, 16, 16)
        # Dış çerçeve
        box = QFrame()
        box.setObjectName("mgr_box")
        box.setStyleSheet(
            "QFrame#mgr_box{background:#ffffff;border:1.5px solid #e2e8f0;border-radius:18px;}")
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(28); sh.setColor(QColor(0,0,0,45)); sh.setOffset(0,6)
        box.setGraphicsEffect(sh)
        master.addWidget(box)
        root = QVBoxLayout(box)
        root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        # Header
        hdr = QFrame()
        hdr.setFixedHeight(64)
        hdr.setStyleSheet(
            "QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6366f1,stop:1 #8b5cf6);"
            "border-top-left-radius:17px;border-top-right-radius:17px;}")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(22,0,22,0)
        hl.addWidget(_lbl("🚚", "font-size:24px;background:transparent;border:none;"))
        hl.addWidget(_lbl("Veri Taşıma  —  SQLite → PostgreSQL",
            "font-size:15px;font-weight:700;color:#ffffff;background:transparent;border:none;letter-spacing:.4px;"))
        hl.addStretch()
        root.addWidget(hdr)
        # Body
        body = QFrame()
        body.setStyleSheet("QFrame{background:transparent;border:none;}")
        bl = QVBoxLayout(body); bl.setContentsMargins(22,18,22,18); bl.setSpacing(14)
        bl.addWidget(_lbl(
            "SQLite veritabanındaki tüm kayıtlar PostgreSQL\'e aktarılıyor.\\n"
            "İnternet bağlantı hızınıza göre birkaç dakika sürebilir.",
            "font-size:12px;color:#000000;background:transparent;border:none;"))
        # Durum + sayaç
        sr = QHBoxLayout()
        self._durum_lbl = _lbl("⏳  Başlatılıyor...",
            "font-size:12px;font-weight:700;color:#6366f1;background:transparent;border:none;")
        sr.addWidget(self._durum_lbl)
        sr.addStretch()
        self._sayac_lbl = _lbl("0 kayıt aktarıldı",
            "font-size:12px;font-weight:600;color:#000000;background:transparent;border:none;")
        sr.addWidget(self._sayac_lbl)
        bl.addLayout(sr)
        # Progress
        self._prog = QProgressBar()
        self._prog.setRange(0,1000); self._prog.setValue(0)
        self._prog.setFixedHeight(10); self._prog.setTextVisible(False)
        self._prog.setStyleSheet(
            "QProgressBar{background:#e2e8f0;border-radius:5px;border:none;}"
            "QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6366f1,stop:1 #8b5cf6);border-radius:5px;}")
        bl.addWidget(self._prog)
        # Tablo başlığı
        hf = QFrame(); hf.setFixedHeight(30)
        hf.setStyleSheet("QFrame{background:#f1f5f9;border-radius:8px 8px 0 0;border:none;}")
        hfl = QHBoxLayout(hf); hfl.setContentsMargins(10,0,10,0)
        for txt, s in [("Tablo",3),("Aktarılan",2),("Toplam",2),("Durum",1)]:
            hfl.addWidget(_lbl(txt,
                "font-size:11px;font-weight:700;color:#000000;background:transparent;border:none;"), s)
        bl.addWidget(hf)
        # Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea{background:white;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;}")
        scroll.setMinimumHeight(240); scroll.setMaximumHeight(320)
        self._tablo_widget = QWidget()
        self._tablo_widget.setStyleSheet("background:white;")
        self._tablo_lay = QVBoxLayout(self._tablo_widget)
        self._tablo_lay.setContentsMargins(0,0,0,0); self._tablo_lay.setSpacing(0)
        self._tablo_lay.addStretch()
        scroll.setWidget(self._tablo_widget)
        bl.addWidget(scroll)
        self._scroll = scroll
        # Sonuç
        self._sonuc_frame = QFrame()
        self._sonuc_frame.setStyleSheet(
            "QFrame{background:#f0fdf4;border:1.5px solid #bbf7d0;border-radius:10px;}")
        sfl = QHBoxLayout(self._sonuc_frame); sfl.setContentsMargins(14,10,14,10)
        self._sonuc_ic = _lbl("✅","font-size:20px;background:transparent;border:none;")
        sfl.addWidget(self._sonuc_ic)
        self._sonuc_lbl = QLabel("")
        self._sonuc_lbl.setWordWrap(True)
        self._sonuc_lbl.setStyleSheet("font-size:12px;color:#000000;background:transparent;border:none;")
        sfl.addWidget(self._sonuc_lbl,1)
        self._sonuc_frame.hide()
        bl.addWidget(self._sonuc_frame)
        # Kapat
        br = QHBoxLayout(); br.addStretch()
        self._kapat_btn = QPushButton("  Kapat  ")
        self._kapat_btn.setEnabled(False); self._kapat_btn.setFixedHeight(38)
        self._kapat_btn.setMinimumWidth(120)
        self._kapat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._kapat_btn.setStyleSheet(
            "QPushButton{background:#6366f1;color:#ffffff;border:none;border-radius:9px;font-size:13px;font-weight:700;}"
            "QPushButton:hover{background:#4f46e5;}"
            "QPushButton:disabled{background:#e2e8f0;color:#94a3b8;}")
        self._kapat_btn.clicked.connect(self.accept)
        br.addWidget(self._kapat_btn)
        bl.addLayout(br)
        root.addWidget(body)

    def _add_row(self, tablo):
        idx = len(self._satir_map)
        satir = QFrame()
        satir.setStyleSheet(
            f"QFrame{{background:{'#f8fafc' if idx%2==0 else '#ffffff'};"
            "border:none;border-bottom:1px solid #f1f5f9;}}")
        satir.setFixedHeight(36)
        lay = QHBoxLayout(satir); lay.setContentsMargins(10,0,10,0); lay.setSpacing(0)
        for txt, s in [(tablo,3),("0",2),("0",2),("⏳",1)]:
            lay.addWidget(_lbl(txt,"font-size:12px;color:#000000;background:transparent;border:none;"),s)
        lbls = satir.findChildren(QLabel)
        self._tablo_lay.insertWidget(self._tablo_lay.count()-1, satir)
        return lbls[1], lbls[2], lbls[3]  # akt, top, dur

    def start(self, batch_size: int = 250):
        self._worker = MigrasyonWorker(batch_size)
        self._worker.ilerleme.connect(self._on_ilerleme)
        self._worker.islendi.connect(self._on_islendi)
        self._worker.start()

    def _on_ilerleme(self, tablo, aktarilan, toplam, ara):
        self._durum_lbl.setText(f"⏳  {tablo} aktarılıyor...")
        if tablo not in self._satir_map:
            lbls = self._add_row(tablo)
            self._satir_map[tablo] = True
            self._satir_lbl_map[tablo] = lbls
        a, t, d = self._satir_lbl_map[tablo]
        a.setText(f"{aktarilan:,}"); t.setText(f"{toplam:,}")
        if ara:
            d.setText("⏳"); d.setStyleSheet("font-size:12px;color:#6366f1;background:transparent;border:none;")
        else:
            self._tablo_sayisi += 1
            if aktarilan >= toplam:
                d.setText("✅"); d.setStyleSheet("font-size:12px;color:#059669;background:transparent;border:none;")
                self._toplam_aktarilan += aktarilan
            else:
                d.setText("⚠️"); d.setStyleSheet("font-size:12px;color:#d97706;background:transparent;border:none;")
        self._sayac_lbl.setText(f"{self._toplam_aktarilan:,} kayıt aktarıldı")
        vb = self._scroll.verticalScrollBar(); vb.setValue(vb.maximum())
        tp = int(self._tablo_sayisi*(960/24))
        ip = int(aktarilan/toplam*(960/24)) if toplam>0 else 0
        self._prog.setValue(min(990, tp+ip))

    def _on_islendi(self, ok, msg):
        self._prog.setValue(1000)
        self._durum_lbl.setText("✅  Tamamlandı!" if ok else "❌  Hatalar oluştu")
        self._durum_lbl.setStyleSheet(
            f"font-size:12px;font-weight:700;color:{'#059669' if ok else '#dc2626'};"
            "background:transparent;border:none;")
        self._sonuc_lbl.setText(msg)
        if not ok:
            self._sonuc_ic.setText("❌")
            self._sonuc_frame.setStyleSheet(
                "QFrame{background:#fef2f2;border:1.5px solid #fecaca;border-radius:10px;}")
        self._sonuc_frame.show()
        self._kapat_btn.setEnabled(True)


# ── Yardımcı ─────────────────────────────────────────────────────────────────

def _lbl(text, style=""):
    l = QLabel(text)
    if style:
        l.setStyleSheet(style)
    return l


# ── Veritabanı Ayarları Kartı ─────────────────────────────────────────────────

class VeriTabaniCard(QFrame):
    """
    Ayarlar → Veritabanı sekmesi.
    Mod: SQLite (lokal) veya PostgreSQL (sunucu/Supabase).
    Migrasyon: SQLite → PostgreSQL veri aktarımı.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._test_worker: VeriTabaniTestWorker | None = None
        self.setStyleSheet(
            "QFrame{background:white;border:1.5px solid #c7d2fe;border-radius:14px;}")
        self._build()
        self._load()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24,22,24,22); root.setSpacing(18)

        # Başlık
        h = QHBoxLayout()
        h.addWidget(_lbl("🗄️","font-size:22px;"))
        h.addWidget(_lbl("Veritabanı Bağlantısı",
            "font-size:14px;font-weight:700;color:#000000;letter-spacing:.5px;"))
        h.addStretch(); root.addLayout(h)

        # Bilgi
        root.addWidget(_lbl(
            "💡  Lokal mod tek kullanıcı içindir. Birden fazla kişi aynı anda "
            "aynı verileri kullanacaksa PostgreSQL sunucu modunu seçin. "
            "Mod değiştirdikten sonra uygulamayı yeniden başlatın.",
            "background:#eef2ff;color:#3730a3;border-radius:8px;"
            "padding:10px 14px;font-size:12px;border:none;"))

        # Mod seçimi
        mf = QFrame()
        mf.setStyleSheet("QFrame{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;}")
        ml = QVBoxLayout(mf); ml.setContentsMargins(16,14,16,14); ml.setSpacing(10)
        ml.addWidget(_lbl("Bağlantı Modu","font-size:12px;font-weight:600;color:#64748b;"))
        br = QHBoxLayout(); br.setSpacing(10)
        self._sqlite_btn = QPushButton("💻  Lokal (SQLite)")
        self._sqlite_btn.setCheckable(True); self._sqlite_btn.setFixedHeight(44)
        self._sqlite_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sqlite_btn.clicked.connect(lambda: self._on_mod("sqlite"))
        br.addWidget(self._sqlite_btn)
        self._pg_btn = QPushButton("🌐  Sunucu (PostgreSQL)")
        self._pg_btn.setCheckable(True); self._pg_btn.setFixedHeight(44)
        self._pg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pg_btn.clicked.connect(lambda: self._on_mod("postgres"))
        br.addWidget(self._pg_btn)
        ml.addLayout(br)
        self._mod_hint = QLabel("Mevcut mod: Lokal (SQLite)")
        self._mod_hint.setStyleSheet("font-size:11px;color:#94a3b8;")
        ml.addWidget(self._mod_hint)
        root.addWidget(mf)

        # PostgreSQL alanları
        self._pg_frame = QFrame()
        self._pg_frame.setStyleSheet(
            "QFrame{background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;}")
        pgl = QVBoxLayout(self._pg_frame); pgl.setContentsMargins(18,16,18,16); pgl.setSpacing(12)
        pgl.addWidget(_lbl("🌐  PostgreSQL Sunucu Bilgileri",
            "font-size:13px;font-weight:700;color:#0c4a6e;"))
        pgl.addWidget(_lbl(
            "Supabase, Railway veya kendi sunucunuzun bilgilerini girin.\n"
            "Supabase için: Settings → Database → Connection pooling → Session mode",
            "font-size:11px;color:#0369a1;"))

        INP = ("QLineEdit{background:white;border:1.5px solid #bae6fd;border-radius:8px;"
               "padding:0 10px;font-size:13px;color:#000000;height:34px;}"
               "QLineEdit:focus{border-color:#0ea5e9;}")
        LBL = "font-size:11px;font-weight:600;color:#000000;"

        # Host + Port
        r1 = QHBoxLayout(); r1.setSpacing(10)
        hc = QVBoxLayout()
        hc.addWidget(_lbl("Sunucu (Host)", LBL))
        self._host_inp = QLineEdit()
        self._host_inp.setFixedHeight(36)
        self._host_inp.setPlaceholderText("aws-0-eu-central-1.pooler.supabase.com")
        self._host_inp.setStyleSheet(INP)
        hc.addWidget(self._host_inp)
        r1.addLayout(hc, 3)
        pc = QVBoxLayout()
        pc.addWidget(_lbl("Port", LBL))
        self._port_inp = QLineEdit()
        self._port_inp.setFixedHeight(36)
        self._port_inp.setPlaceholderText("5432")
        self._port_inp.setStyleSheet(INP)
        pc.addWidget(self._port_inp)
        r1.addLayout(pc, 1)
        pgl.addLayout(r1)

        # DB + User
        r2 = QHBoxLayout(); r2.setSpacing(10)
        dc = QVBoxLayout()
        dc.addWidget(_lbl("Veritabanı Adı", LBL))
        self._db_inp = QLineEdit()
        self._db_inp.setFixedHeight(36)
        self._db_inp.setPlaceholderText("postgres")
        self._db_inp.setStyleSheet(INP)
        dc.addWidget(self._db_inp)
        r2.addLayout(dc)
        uc = QVBoxLayout()
        uc.addWidget(_lbl("Kullanıcı Adı", LBL))
        self._user_inp = QLineEdit()
        self._user_inp.setFixedHeight(36)
        self._user_inp.setPlaceholderText("postgres.proje-id")
        self._user_inp.setStyleSheet(INP)
        uc.addWidget(self._user_inp)
        r2.addLayout(uc)
        pgl.addLayout(r2)

        # Pass + SSL
        r3 = QHBoxLayout(); r3.setSpacing(10)
        pasc = QVBoxLayout()
        pasc.addWidget(_lbl("Şifre", LBL))
        self._pass_inp = QLineEdit()
        self._pass_inp.setFixedHeight(36)
        self._pass_inp.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_inp.setPlaceholderText("••••••••••••")
        self._pass_inp.setStyleSheet(INP)
        pasc.addWidget(self._pass_inp)
        r3.addLayout(pasc, 3)
        sslc = QVBoxLayout()
        sslc.addWidget(_lbl("SSL Modu", LBL))
        self._ssl_combo = QComboBox()
        self._ssl_combo.addItems(["require", "prefer", "disable"])
        self._ssl_combo.setFixedHeight(36)
        self._ssl_combo.setStyleSheet(
            "QComboBox{background:white;border:1.5px solid #bae6fd;"
            "border-radius:8px;padding:0 8px;font-size:13px;color:#000000;}"
            "QComboBox:focus{border-color:#0ea5e9;}")
        sslc.addWidget(self._ssl_combo)
        r3.addLayout(sslc, 1)
        pgl.addLayout(r3)

        # Test
        tr = QHBoxLayout(); tr.setSpacing(10)
        self._test_btn = QPushButton("🔌  Bağlantıyı Test Et")
        self._test_btn.setFixedHeight(36)
        self._test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_btn.setStyleSheet(
            "QPushButton{background:#0ea5e9;color:white;border:none;"
            "border-radius:8px;font-size:13px;font-weight:600;padding:0 16px;}"
            "QPushButton:hover{background:#0284c7;}"
            "QPushButton:disabled{background:#cbd5e1;color:#94a3b8;}")
        self._test_btn.clicked.connect(self._on_test)
        tr.addWidget(self._test_btn)
        self._test_result = QLabel("")
        self._test_result.setWordWrap(True)
        self._test_result.setStyleSheet("font-size:12px;color:#000000;")
        tr.addWidget(self._test_result, 1)
        pgl.addLayout(tr)
        root.addWidget(self._pg_frame)

        # Kaydet
        kr = QHBoxLayout(); kr.setSpacing(10)
        self._kaydet_btn = QPushButton("💾  Kaydet")
        self._kaydet_btn.setFixedHeight(40); self._kaydet_btn.setMinimumWidth(140)
        self._kaydet_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._kaydet_btn.setStyleSheet(
            "QPushButton{background:#6366f1;color:white;border:none;"
            "border-radius:10px;font-size:13px;font-weight:700;letter-spacing:.5px;}"
            "QPushButton:hover{background:#4f46e5;}")
        self._kaydet_btn.clicked.connect(self._on_kaydet)
        kr.addWidget(self._kaydet_btn)
        self._kaydet_durum = QLabel("")
        self._kaydet_durum.setStyleSheet("font-size:12px;color:#000000;")
        kr.addWidget(self._kaydet_durum, 1)
        root.addLayout(kr)

        # Ayırıcı
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#e2e8f0;"); root.addWidget(sep)

        # Migrasyon bölümü
        tf = QFrame()
        tf.setStyleSheet(
            "QFrame{background:#fefce8;border:1px solid #fde68a;border-radius:10px;}")
        tl = QVBoxLayout(tf); tl.setContentsMargins(18,14,18,14); tl.setSpacing(10)
        tl.addWidget(_lbl("🚚  Mevcut Veriyi PostgreSQL\'e Taşı",
            "font-size:13px;font-weight:700;color:#92400e;"))
        tl.addWidget(_lbl(
            "SQLite\'daki tüm kayıtları PostgreSQL\'e kopyalar. Önce bağlantıyı "
            "kaydedin ve test edin.  Mevcut veriler kaybolmaz — sadece kopyalanır. "
            "Yeniden başlatmada tekrar taşınsa da duplicate oluşmaz (ON CONFLICT DO NOTHING).",
            "font-size:11px;color:#78350f;"))

        # Paket boyutu
        pr = QHBoxLayout(); pr.setSpacing(8)
        pr.addWidget(_lbl("📦  Paket boyutu:", "font-size:12px;font-weight:600;color:#92400e;"))
        self._batch_combo = QComboBox()
        self._batch_combo.addItems([
            "50  (Çok yavaş bağlantı / Supabase free tier)",
            "100  (Yavaş bağlantı)",
            "250  (Normal — varsayılan)",
            "500  (Hızlı bağlantı)",
            "1000  (Çok hızlı / LAN)"
        ])
        self._batch_combo.setCurrentIndex(2)
        self._batch_combo.setFixedHeight(32)
        self._batch_combo.setStyleSheet(
            "QComboBox{background:white;border:1.5px solid #fde68a;"
            "border-radius:7px;padding:0 8px;font-size:12px;color:#000000;}"
            "QComboBox:focus{border-color:#d97706;}")
        pr.addWidget(self._batch_combo); pr.addStretch()
        tl.addLayout(pr)

        self._tasima_btn = QPushButton("🚀  Veriyi PostgreSQL\'e Taşı")
        self._tasima_btn.setFixedHeight(40)
        self._tasima_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tasima_btn.setStyleSheet(
            "QPushButton{background:#d97706;color:white;border:none;"
            "border-radius:9px;font-size:13px;font-weight:700;}"
            "QPushButton:hover{background:#b45309;}")
        self._tasima_btn.clicked.connect(self._on_tasima)
        tl.addWidget(self._tasima_btn)
        root.addWidget(tf)

        self._update_mod("sqlite")

    def _update_mod(self, mod):
        self._current_mod = mod
        ACT = ("QPushButton{background:#6366f1;color:white;border:none;"
               "border-radius:9px;font-size:13px;font-weight:700;}")
        IDL = ("QPushButton{background:#f1f5f9;color:#475569;border:1.5px solid #e2e8f0;"
               "border-radius:9px;font-size:13px;font-weight:600;}"
               "QPushButton:hover{background:#e2e8f0;}")
        if mod == "sqlite":
            self._sqlite_btn.setStyleSheet(ACT); self._sqlite_btn.setChecked(True)
            self._pg_btn.setStyleSheet(IDL);     self._pg_btn.setChecked(False)
            if hasattr(self, "_mod_hint"):
                self._mod_hint.setText("Mevcut mod: Lokal (SQLite) — yalnızca bu bilgisayar")
        else:
            self._pg_btn.setStyleSheet(ACT);      self._pg_btn.setChecked(True)
            self._sqlite_btn.setStyleSheet(IDL);  self._sqlite_btn.setChecked(False)
            if hasattr(self, "_mod_hint"):
                self._mod_hint.setText("Mevcut mod: Sunucu (PostgreSQL) — çok kullanıcılı")
        if hasattr(self, "_pg_frame"):
            self._pg_frame.setVisible(mod == "postgres")

    def _load(self):
        from db.db_config import load_config
        cfg = load_config()
        self._update_mod(cfg.get("mode", "sqlite"))
        self._host_inp.setText(cfg.get("pg_host", ""))
        self._port_inp.setText(str(cfg.get("pg_port", 5432)))
        self._db_inp.setText(cfg.get("pg_db", "postgres"))
        self._user_inp.setText(cfg.get("pg_user", "postgres"))
        self._pass_inp.setText(cfg.get("pg_pass", ""))
        idx = self._ssl_combo.findText(cfg.get("pg_sslmode", "require"))
        if idx >= 0:
            self._ssl_combo.setCurrentIndex(idx)

    def _on_mod(self, mod):
        self._update_mod(mod)

    def _on_test(self):
        h = self._host_inp.text().strip()
        db = self._db_inp.text().strip()
        u = self._user_inp.text().strip()
        if not h or not db or not u:
            self._test_result.setText("❌  Host, DB ve Kullanıcı zorunludur.")
            return
        try:
            port = int(self._port_inp.text().strip() or "5432")
        except ValueError:
            self._test_result.setText("❌  Port sayı olmalıdır.")
            return
        self._test_btn.setEnabled(False)
        self._test_result.setText("⏳  Bağlanılıyor...")
        self._test_result.setStyleSheet("font-size:12px;color:#6366f1;")
        self._test_worker = VeriTabaniTestWorker(
            h, port, db, u, self._pass_inp.text(), self._ssl_combo.currentText())
        self._test_worker.islendi.connect(self._on_test_done)
        self._test_worker.start()

    def _on_test_done(self, res):
        self._test_btn.setEnabled(True)
        if res.get("success"):
            self._test_result.setText(f"✅  {res[\'message\']}  ({res[\'ver\']})")
            self._test_result.setStyleSheet("font-size:12px;color:#059669;font-weight:600;")
        else:
            self._test_result.setText(f"❌  {res[\'message\']}")
            self._test_result.setStyleSheet("font-size:12px;color:#dc2626;")

    def _on_kaydet(self):
        from db.db_config import load_config, save_config
        mod = getattr(self, "_current_mod", "sqlite")
        cfg = load_config()
        old = cfg.get("mode", "sqlite")
        cfg.update({
            "mode": mod,
            "pg_host": self._host_inp.text().strip(),
            "pg_port": int(self._port_inp.text().strip() or "5432"),
            "pg_db":   self._db_inp.text().strip(),
            "pg_user": self._user_inp.text().strip(),
            "pg_pass": self._pass_inp.text(),
            "pg_sslmode": self._ssl_combo.currentText(),
        })
        save_config(cfg)
        if old != mod:
            ok = SweetConfirmDialog.confirm(
                self, "Mod Değiştirildi",
                f"Veritabanı modu değiştirildi:\\n  {old.upper()} → {mod.upper()}\\n\\n"
                "Değişikliğin geçerli olması için uygulamayı yeniden başlatın.\\n"
                "Şimdi kapatılsın mı?",
                confirm_text="Evet, Kapat", cancel_text="Sonra", is_danger=False)
            if ok:
                from PyQt6.QtWidgets import QApplication
                QApplication.quit()
            else:
                self._kaydet_durum.setText("✅  Kaydedildi — yeniden başlatınca aktif olur.")
                self._kaydet_durum.setStyleSheet("font-size:12px;color:#d97706;font-weight:600;")
        else:
            self._kaydet_durum.setText("✅  Kaydedildi.")
            self._kaydet_durum.setStyleSheet("font-size:12px;color:#059669;font-weight:600;")

    def _on_tasima(self):
        from db.db_config import load_config
        cfg = load_config()
        if cfg.get("mode") != "postgres" or not cfg.get("pg_host"):
            SweetConfirmDialog.confirm(self, "Önce Bağlantı Gerekli",
                "PostgreSQL bağlantı bilgilerini girin,\\nbağlantıyı test edin ve kaydedin.",
                confirm_text="Tamam", cancel_text="", is_danger=False)
            return
        _MAP = {0:50, 1:100, 2:250, 3:500, 4:1000}
        bs = _MAP.get(self._batch_combo.currentIndex(), 250)
        if not SweetConfirmDialog.confirm(self, "Veri Taşıma",
            f"SQLite\'daki tüm kayıtlar PostgreSQL\'e kopyalanacak.\\n\\n"
            f"📦  Paket boyutu: {bs} satır\\n"
            "Bu işlem birkaç dakika sürebilir.",
            confirm_text="Evet, Taşı", cancel_text="Vazgeç", is_danger=False):
            return
        dlg = MigrasyonDialog(self)
        dlg.show()
        dlg.start(batch_size=bs)

    def refresh(self):
        self._load()
'''

# Guard: zaten eklenmiş mi?
if "class VeriTabaniCard" in text:
    print("SKIP: VeriTabaniCard zaten mevcut.")
    sys.exit(0)

text += APPEND_CODE
SRC.write_text(text, encoding="utf-8")
print(f"APPEND OK — {SRC} ({len(text.splitlines())} satır)")
