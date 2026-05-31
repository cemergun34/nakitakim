
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  VERİTABANI AYARLARI — SweetAlert tasarımı, batch migration, local/PG mod  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝


def _mk_lbl(text, style=""):
    l = QLabel(text)
    if style:
        l.setStyleSheet(style)
    return l


class SweetConfirmDialog(QDialog):
    """Minimal onay diyaloğu — SweetAlert tarzı, frameless."""

    def __init__(self, parent=None, title="", text="",
                 confirm_text="Evet", cancel_text="İptal", is_danger=False):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
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
        sh.setBlurRadius(20)
        sh.setColor(QColor(0, 0, 0, 40))
        sh.setOffset(0, 4)
        box.setGraphicsEffect(sh)
        master.addWidget(box)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(24, 24, 24, 20)
        lay.setSpacing(12)
        t = QLabel(title)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet(
            "font-size:15px;font-weight:700;color:#1e293b;"
            "background:transparent;border:none;"
        )
        lay.addWidget(t)
        d = QLabel(text)
        d.setWordWrap(True)
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d.setStyleSheet(
            "font-size:12px;color:#475569;background:transparent;border:none;"
        )
        lay.addWidget(d)
        lay.addSpacing(4)
        brow = QHBoxLayout()
        brow.setSpacing(8)
        if cancel_text:
            cb = QPushButton(cancel_text)
            cb.setFixedHeight(36)
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.setStyleSheet(
                "QPushButton{background:#f1f5f9;color:#475569;border:none;"
                "border-radius:8px;font-size:12px;font-weight:600;padding:0 16px;}"
                "QPushButton:hover{background:#e2e8f0;}"
            )
            cb.clicked.connect(self.reject)
            brow.addWidget(cb)
        ok_bg = "#ef4444" if is_danger else "#6366f1"
        ok_hv = "#dc2626" if is_danger else "#4f46e5"
        ob = QPushButton(confirm_text)
        ob.setFixedHeight(36)
        ob.setCursor(Qt.CursorShape.PointingHandCursor)
        ob.setStyleSheet(
            f"QPushButton{{background:{ok_bg};color:white;border:none;"
            f"border-radius:8px;font-size:12px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:{ok_hv};}}"
        )
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
        self._host = host
        self._port = port
        self._db = dbname
        self._user = user
        self._pw = password
        self._ssl = sslmode

    def run(self):
        try:
            import psycopg2
        except ImportError:
            self.islendi.emit({
                "success": False,
                "message": "psycopg2 yüklü değil.\npip install psycopg2-binary",
                "ver": ""
            })
            return
        params = dict(
            host=self._host, port=self._port, dbname=self._db,
            user=self._user, sslmode=self._ssl, connect_timeout=8
        )
        if self._pw:
            params["password"] = self._pw
        try:
            conn = psycopg2.connect(**params)
            v = conn.server_version
            conn.close()
            self.islendi.emit({
                "success": True,
                "message": "Bağlantı başarılı!",
                "ver": f"PostgreSQL {v//10000}.{(v % 10000)//100}"
            })
        except Exception as exc:
            self.islendi.emit({"success": False, "message": str(exc), "ver": ""})


# ── SQLite → PostgreSQL migrasyon worker ─────────────────────────────────────

class MigrasyonWorker(QThread):
    ilerleme = pyqtSignal(str, int, int, bool)  # tablo, aktarilan, toplam, ara
    islendi  = pyqtSignal(bool, str)

    def __init__(self, batch_size: int = 250):
        super().__init__()
        self._batch_size = batch_size

    def run(self):
        from db.sqlite_to_pg import migrate_all
        toplam_aktarilan = 0
        hatalar: list[str] = []
        try:
            for s in migrate_all(batch_size=self._batch_size):
                if s.bitti:
                    break
                if s.hata:
                    hatalar.append(f"{s.tablo}: {s.hata}")
                if not s.ara:
                    toplam_aktarilan += s.aktarilan
                self.ilerleme.emit(s.tablo, s.aktarilan, s.toplam, s.ara)
            if hatalar:
                ozet = (
                    f"Tamamlandı — {toplam_aktarilan:,} kayıt aktarıldı.\n"
                    "Hatalar:\n" + "\n".join(hatalar[:5])
                )
                self.islendi.emit(False, ozet)
            else:
                self.islendi.emit(
                    True,
                    f"✅  Tüm veriler aktarıldı!\n{toplam_aktarilan:,} kayıt PostgreSQL'e taşındı."
                )
        except Exception as exc:
            self.islendi.emit(False, f"Hata: {exc}")


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
        self._satir_map: dict[str, bool] = {}
        self._satir_lbl_map: dict[str, tuple] = {}
        self._toplam_aktarilan = 0
        self._build()

    def _build(self):
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QScrollArea
        from PyQt6.QtGui import QColor

        master = QVBoxLayout(self)
        master.setContentsMargins(16, 16, 16, 16)

        box = QFrame()
        box.setObjectName("mgr_box")
        box.setStyleSheet(
            "QFrame#mgr_box{background:#ffffff;border:1.5px solid #e2e8f0;border-radius:18px;}"
        )
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(28)
        sh.setColor(QColor(0, 0, 0, 45))
        sh.setOffset(0, 6)
        box.setGraphicsEffect(sh)
        master.addWidget(box)

        root = QVBoxLayout(box)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Mor gradient başlık
        hdr = QFrame()
        hdr.setFixedHeight(64)
        hdr.setStyleSheet(
            "QFrame{"
            "  background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6366f1,stop:1 #8b5cf6);"
            "  border-top-left-radius:17px;border-top-right-radius:17px;"
            "}"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(22, 0, 22, 0)
        hl.addWidget(_mk_lbl("🚚", "font-size:24px;background:transparent;border:none;"))
        hl.addWidget(_mk_lbl(
            "Veri Taşıma  —  SQLite → PostgreSQL",
            "font-size:15px;font-weight:700;color:#ffffff;"
            "background:transparent;border:none;letter-spacing:.4px;"
        ))
        hl.addStretch()
        root.addWidget(hdr)

        # Gövde
        body = QFrame()
        body.setStyleSheet("QFrame{background:transparent;border:none;}")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(22, 18, 22, 18)
        bl.setSpacing(14)

        bl.addWidget(_mk_lbl(
            "SQLite veritabanındaki tüm kayıtlar PostgreSQL'e aktarılıyor.\n"
            "İnternet bağlantı hızınıza göre birkaç dakika sürebilir.",
            "font-size:12px;color:#000000;background:transparent;border:none;"
        ))

        sr = QHBoxLayout()
        self._durum_lbl = _mk_lbl(
            "⏳  Başlatılıyor...",
            "font-size:12px;font-weight:700;color:#6366f1;"
            "background:transparent;border:none;"
        )
        sr.addWidget(self._durum_lbl)
        sr.addStretch()
        self._sayac_lbl = _mk_lbl(
            "0 kayıt aktarıldı",
            "font-size:12px;font-weight:600;color:#000000;"
            "background:transparent;border:none;"
        )
        sr.addWidget(self._sayac_lbl)
        bl.addLayout(sr)

        self._prog = QProgressBar()
        self._prog.setRange(0, 1000)
        self._prog.setValue(0)
        self._prog.setFixedHeight(10)
        self._prog.setTextVisible(False)
        self._prog.setStyleSheet(
            "QProgressBar{background:#e2e8f0;border-radius:5px;border:none;}"
            "QProgressBar::chunk{"
            "  background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6366f1,stop:1 #8b5cf6);"
            "  border-radius:5px;"
            "}"
        )
        bl.addWidget(self._prog)

        # Tablo başlık şeridi
        hf = QFrame()
        hf.setFixedHeight(30)
        hf.setStyleSheet("QFrame{background:#f1f5f9;border-radius:8px 8px 0 0;border:none;}")
        hfl = QHBoxLayout(hf)
        hfl.setContentsMargins(10, 0, 10, 0)
        for col_txt, col_stretch in [("Tablo", 3), ("Aktarılan", 2), ("Toplam", 2), ("Durum", 1)]:
            hfl.addWidget(_mk_lbl(
                col_txt,
                "font-size:11px;font-weight:700;color:#000000;background:transparent;border:none;"
            ), col_stretch)
        bl.addWidget(hf)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea{background:white;border:1px solid #e2e8f0;"
            "border-top:none;border-radius:0 0 8px 8px;}"
        )
        scroll.setMinimumHeight(240)
        scroll.setMaximumHeight(320)
        self._tablo_widget = QWidget()
        self._tablo_widget.setStyleSheet("background:white;")
        self._tablo_lay = QVBoxLayout(self._tablo_widget)
        self._tablo_lay.setContentsMargins(0, 0, 0, 0)
        self._tablo_lay.setSpacing(0)
        self._tablo_lay.addStretch()
        scroll.setWidget(self._tablo_widget)
        bl.addWidget(scroll)
        self._scroll = scroll

        self._sonuc_frame = QFrame()
        self._sonuc_frame.setStyleSheet(
            "QFrame{background:#f0fdf4;border:1.5px solid #bbf7d0;border-radius:10px;}"
        )
        sfl = QHBoxLayout(self._sonuc_frame)
        sfl.setContentsMargins(14, 10, 14, 10)
        self._sonuc_ic = _mk_lbl("✅", "font-size:20px;background:transparent;border:none;")
        sfl.addWidget(self._sonuc_ic)
        self._sonuc_lbl = QLabel("")
        self._sonuc_lbl.setWordWrap(True)
        self._sonuc_lbl.setStyleSheet(
            "font-size:12px;color:#000000;background:transparent;border:none;"
        )
        sfl.addWidget(self._sonuc_lbl, 1)
        self._sonuc_frame.hide()
        bl.addWidget(self._sonuc_frame)

        br = QHBoxLayout()
        br.addStretch()
        self._kapat_btn = QPushButton("  Kapat  ")
        self._kapat_btn.setEnabled(False)
        self._kapat_btn.setFixedHeight(38)
        self._kapat_btn.setMinimumWidth(120)
        self._kapat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._kapat_btn.setStyleSheet(
            "QPushButton{background:#6366f1;color:#ffffff;border:none;"
            "border-radius:9px;font-size:13px;font-weight:700;}"
            "QPushButton:hover{background:#4f46e5;}"
            "QPushButton:disabled{background:#e2e8f0;color:#94a3b8;}"
        )
        self._kapat_btn.clicked.connect(self.accept)
        br.addWidget(self._kapat_btn)
        bl.addLayout(br)
        root.addWidget(body)

    def _add_row(self, tablo):
        idx = len(self._satir_map)
        satir = QFrame()
        bg = "#f8fafc" if idx % 2 == 0 else "#ffffff"
        satir.setStyleSheet(
            f"QFrame{{background:{bg};border:none;border-bottom:1px solid #f1f5f9;}}"
        )
        satir.setFixedHeight(36)
        lay = QHBoxLayout(satir)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(0)
        nm = _mk_lbl(tablo, "font-size:12px;color:#000000;background:transparent;border:none;")
        ak = _mk_lbl("0", "font-size:12px;font-weight:600;color:#000000;background:transparent;border:none;")
        tp = _mk_lbl("0", "font-size:12px;color:#000000;background:transparent;border:none;")
        du = _mk_lbl("⏳", "font-size:12px;color:#6366f1;background:transparent;border:none;")
        lay.addWidget(nm, 3)
        lay.addWidget(ak, 2)
        lay.addWidget(tp, 2)
        lay.addWidget(du, 1)
        self._tablo_lay.insertWidget(self._tablo_lay.count() - 1, satir)
        return ak, tp, du

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
        a_lbl, t_lbl, d_lbl = self._satir_lbl_map[tablo]
        a_lbl.setText(f"{aktarilan:,}")
        t_lbl.setText(f"{toplam:,}")
        if ara:
            d_lbl.setText("⏳")
            d_lbl.setStyleSheet(
                "font-size:12px;color:#6366f1;background:transparent;border:none;"
            )
        else:
            self._tablo_sayisi += 1
            if aktarilan >= toplam:
                d_lbl.setText("✅")
                d_lbl.setStyleSheet(
                    "font-size:12px;color:#059669;background:transparent;border:none;"
                )
                self._toplam_aktarilan += aktarilan
            else:
                d_lbl.setText("⚠️")
                d_lbl.setStyleSheet(
                    "font-size:12px;color:#d97706;background:transparent;border:none;"
                )
        self._sayac_lbl.setText(f"{self._toplam_aktarilan:,} kayıt aktarıldı")
        vb = self._scroll.verticalScrollBar()
        vb.setValue(vb.maximum())
        tp_val = int(self._tablo_sayisi * (960 / 24))
        ic_val = int(aktarilan / toplam * (960 / 24)) if toplam > 0 else 0
        self._prog.setValue(min(990, tp_val + ic_val))

    def _on_islendi(self, ok, msg):
        self._prog.setValue(1000)
        self._durum_lbl.setText("✅  Tamamlandı!" if ok else "❌  Hatalar oluştu")
        self._durum_lbl.setStyleSheet(
            f"font-size:12px;font-weight:700;"
            f"color:{'#059669' if ok else '#dc2626'};"
            "background:transparent;border:none;"
        )
        self._sonuc_lbl.setText(msg)
        if not ok:
            self._sonuc_ic.setText("❌")
            self._sonuc_frame.setStyleSheet(
                "QFrame{background:#fef2f2;border:1.5px solid #fecaca;border-radius:10px;}"
            )
        self._sonuc_frame.show()
        self._kapat_btn.setEnabled(True)


# ── Veritabanı Ayarları Kartı ─────────────────────────────────────────────────

class VeriTabaniCard(QFrame):
    """
    Ayarlar → 🗄️ Veritabanı sekmesi.
    Mod: SQLite (lokal) veya PostgreSQL (sunucu / Supabase).
    Migration: SQLite → PostgreSQL, paket boyutu seçilebilir.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._test_worker: VeriTabaniTestWorker | None = None
        self._current_mod = "sqlite"
        self.setStyleSheet(
            "QFrame{background:white;border:1.5px solid #c7d2fe;border-radius:14px;}"
        )
        self._build()
        self._load()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)

        # ── Başlık ──────────────────────────────────────────────────────────
        h = QHBoxLayout()
        h.addWidget(_mk_lbl("🗄️", "font-size:22px;"))
        h.addWidget(_mk_lbl(
            "Veritabanı Bağlantısı",
            "font-size:14px;font-weight:700;color:#000000;letter-spacing:.5px;"
        ))
        h.addStretch()
        root.addLayout(h)

        root.addWidget(_mk_lbl(
            "💡  Lokal mod tek kullanıcı içindir. Birden fazla kişi aynı verileri "
            "kullanacaksa PostgreSQL sunucu modunu seçin. "
            "Mod değiştirdikten sonra uygulamayı yeniden başlatın.",
            "background:#eef2ff;color:#3730a3;border-radius:8px;"
            "padding:10px 14px;font-size:12px;border:none;"
        ))

        # ── Mod Seçimi ──────────────────────────────────────────────────────
        mf = QFrame()
        mf.setStyleSheet(
            "QFrame{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;}"
        )
        ml = QVBoxLayout(mf)
        ml.setContentsMargins(16, 14, 16, 14)
        ml.setSpacing(10)
        ml.addWidget(_mk_lbl(
            "Bağlantı Modu",
            "font-size:12px;font-weight:600;color:#64748b;"
        ))
        br2 = QHBoxLayout()
        br2.setSpacing(10)
        self._sqlite_btn = QPushButton("💻  Lokal (SQLite)")
        self._sqlite_btn.setCheckable(True)
        self._sqlite_btn.setFixedHeight(44)
        self._sqlite_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sqlite_btn.clicked.connect(lambda: self._on_mod("sqlite"))
        br2.addWidget(self._sqlite_btn)
        self._pg_btn = QPushButton("🌐  Sunucu (PostgreSQL)")
        self._pg_btn.setCheckable(True)
        self._pg_btn.setFixedHeight(44)
        self._pg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pg_btn.clicked.connect(lambda: self._on_mod("postgres"))
        br2.addWidget(self._pg_btn)
        ml.addLayout(br2)
        self._mod_hint = QLabel("Mevcut mod: Lokal (SQLite)")
        self._mod_hint.setStyleSheet("font-size:11px;color:#94a3b8;")
        ml.addWidget(self._mod_hint)
        root.addWidget(mf)

        # ── PostgreSQL Alanları ─────────────────────────────────────────────
        self._pg_frame = QFrame()
        self._pg_frame.setStyleSheet(
            "QFrame{background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;}"
        )
        pgl = QVBoxLayout(self._pg_frame)
        pgl.setContentsMargins(18, 16, 18, 16)
        pgl.setSpacing(12)

        pgl.addWidget(_mk_lbl(
            "🌐  PostgreSQL Sunucu Bilgileri",
            "font-size:13px;font-weight:700;color:#0c4a6e;"
        ))
        pgl.addWidget(_mk_lbl(
            "Supabase kullanıyorsanız: Settings → Database → Connection pooling → Session mode\n"
            "Host: aws-0-eu-central-1.pooler.supabase.com  |  Port: 5432  "
            "|  User: postgres.[proje-id]",
            "font-size:11px;color:#0369a1;"
        ))

        _INP = (
            "QLineEdit{background:white;border:1.5px solid #bae6fd;border-radius:8px;"
            "padding:0 10px;font-size:13px;color:#000000;}"
            "QLineEdit:focus{border-color:#0ea5e9;}"
        )
        _LBL = "font-size:11px;font-weight:600;color:#000000;"

        # Host + Port
        r1 = QHBoxLayout()
        r1.setSpacing(10)
        hc = QVBoxLayout()
        hc.addWidget(_mk_lbl("Sunucu (Host)", _LBL))
        self._host_inp = QLineEdit()
        self._host_inp.setFixedHeight(36)
        self._host_inp.setPlaceholderText("aws-0-eu-central-1.pooler.supabase.com")
        self._host_inp.setStyleSheet(_INP)
        hc.addWidget(self._host_inp)
        r1.addLayout(hc, 3)
        pc = QVBoxLayout()
        pc.addWidget(_mk_lbl("Port", _LBL))
        self._port_inp = QLineEdit()
        self._port_inp.setFixedHeight(36)
        self._port_inp.setPlaceholderText("5432")
        self._port_inp.setStyleSheet(_INP)
        pc.addWidget(self._port_inp)
        r1.addLayout(pc, 1)
        pgl.addLayout(r1)

        # DB + User
        r2 = QHBoxLayout()
        r2.setSpacing(10)
        dc = QVBoxLayout()
        dc.addWidget(_mk_lbl("Veritabanı Adı", _LBL))
        self._db_inp = QLineEdit()
        self._db_inp.setFixedHeight(36)
        self._db_inp.setPlaceholderText("postgres")
        self._db_inp.setStyleSheet(_INP)
        dc.addWidget(self._db_inp)
        r2.addLayout(dc)
        uc = QVBoxLayout()
        uc.addWidget(_mk_lbl("Kullanıcı Adı", _LBL))
        self._user_inp = QLineEdit()
        self._user_inp.setFixedHeight(36)
        self._user_inp.setPlaceholderText("postgres.proje-id")
        self._user_inp.setStyleSheet(_INP)
        uc.addWidget(self._user_inp)
        r2.addLayout(uc)
        pgl.addLayout(r2)

        # Şifre + SSL
        r3 = QHBoxLayout()
        r3.setSpacing(10)
        pasc = QVBoxLayout()
        pasc.addWidget(_mk_lbl("Şifre", _LBL))
        self._pass_inp = QLineEdit()
        self._pass_inp.setFixedHeight(36)
        self._pass_inp.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_inp.setPlaceholderText("••••••••••••")
        self._pass_inp.setStyleSheet(_INP)
        pasc.addWidget(self._pass_inp)
        r3.addLayout(pasc, 3)
        sslc = QVBoxLayout()
        sslc.addWidget(_mk_lbl("SSL Modu", _LBL))
        self._ssl_combo = QComboBox()
        self._ssl_combo.addItems(["require", "prefer", "disable"])
        self._ssl_combo.setFixedHeight(36)
        self._ssl_combo.setStyleSheet(
            "QComboBox{background:white;border:1.5px solid #bae6fd;"
            "border-radius:8px;padding:0 8px;font-size:13px;color:#000000;}"
            "QComboBox:focus{border-color:#0ea5e9;}"
        )
        sslc.addWidget(self._ssl_combo)
        r3.addLayout(sslc, 1)
        pgl.addLayout(r3)

        # Test butonu + sonuç
        tr = QHBoxLayout()
        tr.setSpacing(10)
        self._test_btn = QPushButton("🔌  Bağlantıyı Test Et")
        self._test_btn.setFixedHeight(36)
        self._test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_btn.setStyleSheet(
            "QPushButton{background:#0ea5e9;color:white;border:none;"
            "border-radius:8px;font-size:13px;font-weight:600;padding:0 16px;}"
            "QPushButton:hover{background:#0284c7;}"
            "QPushButton:disabled{background:#cbd5e1;color:#94a3b8;}"
        )
        self._test_btn.clicked.connect(self._on_test)
        tr.addWidget(self._test_btn)
        self._test_result = QLabel("")
        self._test_result.setWordWrap(True)
        self._test_result.setStyleSheet("font-size:12px;color:#000000;")
        tr.addWidget(self._test_result, 1)
        pgl.addLayout(tr)

        root.addWidget(self._pg_frame)

        # ── Kaydet ──────────────────────────────────────────────────────────
        kr = QHBoxLayout()
        kr.setSpacing(10)
        self._kaydet_btn = QPushButton("💾  Kaydet")
        self._kaydet_btn.setFixedHeight(40)
        self._kaydet_btn.setMinimumWidth(140)
        self._kaydet_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._kaydet_btn.setStyleSheet(
            "QPushButton{background:#6366f1;color:white;border:none;"
            "border-radius:10px;font-size:13px;font-weight:700;letter-spacing:.5px;}"
            "QPushButton:hover{background:#4f46e5;}"
        )
        self._kaydet_btn.clicked.connect(self._on_kaydet)
        kr.addWidget(self._kaydet_btn)
        self._kaydet_durum = QLabel("")
        self._kaydet_durum.setStyleSheet("font-size:12px;color:#000000;")
        kr.addWidget(self._kaydet_durum, 1)
        root.addLayout(kr)

        # Ayırıcı çizgi
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#e2e8f0;")
        root.addWidget(sep)

        # ── Migrasyon Bölümü ────────────────────────────────────────────────
        tf = QFrame()
        tf.setStyleSheet(
            "QFrame{background:#fefce8;border:1px solid #fde68a;border-radius:10px;}"
        )
        tl = QVBoxLayout(tf)
        tl.setContentsMargins(18, 14, 18, 14)
        tl.setSpacing(10)
        tl.addWidget(_mk_lbl(
            "🚚  Mevcut Veriyi PostgreSQL'e Taşı",
            "font-size:13px;font-weight:700;color:#92400e;"
        ))
        tl.addWidget(_mk_lbl(
            "SQLite'daki tüm kayıtları PostgreSQL'e kopyalar.  Önce bağlantıyı "
            "kaydedin ve test edin.  Mevcut veriler kaybolmaz — sadece kopyalanır.  "
            "Yeniden taşıma yapılsa bile duplicate oluşmaz (ON CONFLICT DO NOTHING).",
            "font-size:11px;color:#78350f;"
        ))

        pr = QHBoxLayout()
        pr.setSpacing(8)
        pr.addWidget(_mk_lbl(
            "📦  Paket boyutu:",
            "font-size:12px;font-weight:600;color:#92400e;"
        ))
        self._batch_combo = QComboBox()
        self._batch_combo.addItems([
            "50  (Çok yavaş bağlantı / Supabase free)",
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
            "QComboBox:focus{border-color:#d97706;}"
        )
        pr.addWidget(self._batch_combo)
        pr.addStretch()
        tl.addLayout(pr)

        self._tasima_btn = QPushButton("🚀  Veriyi PostgreSQL'e Taşı")
        self._tasima_btn.setFixedHeight(40)
        self._tasima_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tasima_btn.setStyleSheet(
            "QPushButton{background:#d97706;color:white;border:none;"
            "border-radius:9px;font-size:13px;font-weight:700;}"
            "QPushButton:hover{background:#b45309;}"
        )
        self._tasima_btn.clicked.connect(self._on_tasima)
        tl.addWidget(self._tasima_btn)
        root.addWidget(tf)

        self._update_mod_ui("sqlite")

    # ── Yardımcı metodlar ────────────────────────────────────────────────────

    def _update_mod_ui(self, mod):
        self._current_mod = mod
        ACT = (
            "QPushButton{background:#6366f1;color:white;border:none;"
            "border-radius:9px;font-size:13px;font-weight:700;}"
        )
        IDL = (
            "QPushButton{background:#f1f5f9;color:#475569;"
            "border:1.5px solid #e2e8f0;border-radius:9px;"
            "font-size:13px;font-weight:600;}"
            "QPushButton:hover{background:#e2e8f0;}"
        )
        if mod == "sqlite":
            self._sqlite_btn.setStyleSheet(ACT)
            self._sqlite_btn.setChecked(True)
            self._pg_btn.setStyleSheet(IDL)
            self._pg_btn.setChecked(False)
            self._mod_hint.setText("Mevcut mod: Lokal (SQLite) — yalnızca bu bilgisayar")
        else:
            self._pg_btn.setStyleSheet(ACT)
            self._pg_btn.setChecked(True)
            self._sqlite_btn.setStyleSheet(IDL)
            self._sqlite_btn.setChecked(False)
            self._mod_hint.setText("Mevcut mod: Sunucu (PostgreSQL) — çok kullanıcılı")
        if hasattr(self, "_pg_frame"):
            self._pg_frame.setVisible(mod == "postgres")

    def _load(self):
        from db.db_config import load_config
        cfg = load_config()
        self._update_mod_ui(cfg.get("mode", "sqlite"))
        self._host_inp.setText(cfg.get("pg_host", ""))
        self._port_inp.setText(str(cfg.get("pg_port", 5432)))
        self._db_inp.setText(cfg.get("pg_db", "postgres"))
        self._user_inp.setText(cfg.get("pg_user", "postgres"))
        self._pass_inp.setText(cfg.get("pg_pass", ""))
        idx = self._ssl_combo.findText(cfg.get("pg_sslmode", "require"))
        if idx >= 0:
            self._ssl_combo.setCurrentIndex(idx)

    def _on_mod(self, mod):
        self._update_mod_ui(mod)

    def _on_test(self):
        h = self._host_inp.text().strip()
        db = self._db_inp.text().strip()
        u = self._user_inp.text().strip()
        if not h or not db or not u:
            self._test_result.setText("❌  Host, DB Adı ve Kullanıcı zorunludur.")
            self._test_result.setStyleSheet("font-size:12px;color:#dc2626;")
            return
        try:
            port = int(self._port_inp.text().strip() or "5432")
        except ValueError:
            self._test_result.setText("❌  Port sayı olmalıdır.")
            self._test_result.setStyleSheet("font-size:12px;color:#dc2626;")
            return
        self._test_btn.setEnabled(False)
        self._test_result.setText("⏳  Bağlanılıyor...")
        self._test_result.setStyleSheet("font-size:12px;color:#6366f1;")
        self._test_worker = VeriTabaniTestWorker(
            h, port, db, u, self._pass_inp.text(), self._ssl_combo.currentText()
        )
        self._test_worker.islendi.connect(self._on_test_done)
        self._test_worker.start()

    def _on_test_done(self, res):
        self._test_btn.setEnabled(True)
        if res.get("success"):
            msg = f"✅  {res['message']}  ({res['ver']})"
            self._test_result.setText(msg)
            self._test_result.setStyleSheet(
                "font-size:12px;color:#059669;font-weight:600;"
            )
        else:
            self._test_result.setText(f"❌  {res['message']}")
            self._test_result.setStyleSheet("font-size:12px;color:#dc2626;")

    def _on_kaydet(self):
        from db.db_config import load_config, save_config
        mod = self._current_mod
        cfg = load_config()
        old_mod = cfg.get("mode", "sqlite")
        try:
            port = int(self._port_inp.text().strip() or "5432")
        except ValueError:
            port = 5432
        cfg.update({
            "mode":       mod,
            "pg_host":    self._host_inp.text().strip(),
            "pg_port":    port,
            "pg_db":      self._db_inp.text().strip(),
            "pg_user":    self._user_inp.text().strip(),
            "pg_pass":    self._pass_inp.text(),
            "pg_sslmode": self._ssl_combo.currentText(),
        })
        save_config(cfg)
        if old_mod != mod:
            restart = SweetConfirmDialog.confirm(
                self,
                "Mod Değiştirildi",
                f"Veritabanı modu değiştirildi:\n  {old_mod.upper()} → {mod.upper()}\n\n"
                "Değişikliğin geçerli olması için uygulama yeniden başlatılmalı.\n"
                "Şimdi kapatılsın mı?",
                confirm_text="Evet, Kapat",
                cancel_text="Sonra",
                is_danger=False
            )
            if restart:
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
            SweetConfirmDialog.confirm(
                self,
                "Önce Bağlantı Gerekli",
                "PostgreSQL bağlantı bilgilerini girin,\n"
                "bağlantıyı test edin ve kaydedin.",
                confirm_text="Tamam",
                cancel_text="",
                is_danger=False
            )
            return
        _MAP = {0: 50, 1: 100, 2: 250, 3: 500, 4: 1000}
        bs = _MAP.get(self._batch_combo.currentIndex(), 250)
        if not SweetConfirmDialog.confirm(
            self,
            "Veri Taşıma",
            f"SQLite'daki tüm kayıtlar PostgreSQL'e kopyalanacak.\n\n"
            f"📦  Paket boyutu: {bs} satır\n"
            "Bu işlem birkaç dakika sürebilir.",
            confirm_text="Evet, Taşı",
            cancel_text="Vazgeç",
            is_danger=False
        ):
            return
        dlg = MigrasyonDialog(self)
        dlg.show()
        dlg.start(batch_size=bs)

    def refresh(self):
        self._load()
