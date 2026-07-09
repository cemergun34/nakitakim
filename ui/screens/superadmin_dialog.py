# -*- coding: utf-8 -*-
"""
SuperAdmin Dialog  — Yazılım sahibi sistem yönetim penceresi.

Erişim: Login ekranında  Ctrl + Shift + Alt + S
Müşteri bu pencereyi görmez / bilemez.

İçerik:
  • Veritabanı  — SQLite ↔ PostgreSQL / Supabase bağlantı + migrasyon
  • Kullanıcılar — Admin kullanıcı oluşturma / şifre sıfırlama
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QComboBox, QProgressBar, QWidget,
    QScrollArea, QGraphicsDropShadowEffect, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QBrush


# ─────────────────────────────────────────────────────────────────────────────
# Küçük yardımcılar
# ─────────────────────────────────────────────────────────────────────────────

def _lbl(text: str, style: str = "") -> QLabel:
    w = QLabel(text)
    if style:
        w.setStyleSheet(style)
    return w


_S_INP = (
    "QLineEdit{"
    "  background:#1e293b;"
    "  border:1.5px solid #334155;"
    "  border-radius:9px;"
    "  padding:0 14px;"
    "  font-size:13px;"
    "  color:#f1f5f9;"
    "}"
    "QLineEdit:focus{"
    "  border-color:#6366f1;"
    "  background:#0f172a;"
    "}"
    "QLineEdit::placeholder{"
    "  color:#475569;"
    "}"
)

_S_LBL = "font-size:11px;font-weight:600;color:#94a3b8;letter-spacing:.3px;"

_S_COMBO = (
    "QComboBox{"
    "  background:#1e293b;border:1.5px solid #334155;"
    "  border-radius:9px;padding:0 10px;"
    "  font-size:13px;color:#f1f5f9;"
    "}"
    "QComboBox:focus{border-color:#6366f1;}"
    "QComboBox QAbstractItemView{"
    "  background:#1e293b;color:#f1f5f9;border:1px solid #334155;"
    "  selection-background-color:#6366f1;"
    "}"
)


def _section(title: str) -> QLabel:
    l = QLabel(title)
    l.setStyleSheet(
        "font-size:12px;font-weight:700;color:#6366f1;"
        "letter-spacing:.5px;text-transform:uppercase;"
    )
    return l


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("color:#1e293b;")
    return f


def _btn(text, bg="#6366f1", hv="#4f46e5", h=40, w=None):
    b = QPushButton(text)
    b.setFixedHeight(h)
    if w:
        b.setMinimumWidth(w)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:{bg};color:white;border:none;"
        f"border-radius:9px;font-size:13px;font-weight:700;}}"
        f"QPushButton:hover{{background:{hv};}}"
        f"QPushButton:disabled{{background:#334155;color:#475569;}}"
    )
    return b


# ─────────────────────────────────────────────────────────────────────────────
# Arka plan worker'lar
# ─────────────────────────────────────────────────────────────────────────────

class _TestWorker(QThread):
    done = pyqtSignal(dict)

    def __init__(self, host, port, dbname, user, password, sslmode):
        super().__init__()
        self._p = dict(
            host=host, port=port, dbname=dbname,
            user=user, sslmode=sslmode, connect_timeout=8
        )
        if password:
            self._p["password"] = password

    def run(self):
        try:
            import psycopg2
            conn = psycopg2.connect(**self._p)
            v = conn.server_version
            conn.close()
            self.done.emit({
                "ok": True,
                "msg": f"Bağlantı başarılı — PostgreSQL {v//10000}.{(v%10000)//100}"
            })
        except ImportError:
            self.done.emit({"ok": False, "msg": "psycopg2 yüklü değil. pip install psycopg2-binary"})
        except Exception as e:
            self.done.emit({"ok": False, "msg": str(e)})


class _MigWorker(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(bool, str)

    def __init__(self, batch: int = 250):
        super().__init__()
        self._batch = batch

    def run(self):
        from db.sqlite_to_pg import migrate_all
        total = 0
        errors: list[str] = []
        try:
            for s in migrate_all(batch_size=self._batch):
                if s.bitti:
                    break
                if s.hata:
                    errors.append(f"{s.tablo}: {s.hata}")
                if not s.ara:
                    total += s.aktarilan
                self.progress.emit(s.tablo, s.aktarilan, s.toplam)
            if errors:
                self.finished.emit(False,
                    f"{total:,} kayıt aktarıldı.\nHatalar:\n" + "\n".join(errors[:5]))
            else:
                self.finished.emit(True, f"{total:,} kayıt başarıyla PostgreSQL'e taşındı.")
        except Exception as e:
            self.finished.emit(False, f"Hata: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Sürüklenebilir başlık çubuğu
# ─────────────────────────────────────────────────────────────────────────────

class _DragHeader(QFrame):
    """Frameless dialog için sürüklenebilir başlık."""

    def __init__(self, parent_dialog, title="", subtitle=""):
        super().__init__(parent_dialog)
        self._dlg = parent_dialog
        self._drag_pos = QPoint()
        self.setFixedHeight(68)
        self.setStyleSheet(
            "QFrame{"
            "  background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "    stop:0 #0f172a,stop:0.5 #1e293b,stop:1 #0f172a);"
            "  border-top-left-radius:16px;"
            "  border-top-right-radius:16px;"
            "}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(22, 0, 16, 0)
        lay.setSpacing(12)

        icon = _lbl("⚙️", "font-size:22px;background:transparent;border:none;")
        lay.addWidget(icon)

        txt = QVBoxLayout()
        txt.setSpacing(2)
        txt.addWidget(_lbl(title,
            "font-size:15px;font-weight:700;color:#f1f5f9;"
            "background:transparent;border:none;letter-spacing:.5px;"))
        if subtitle:
            txt.addWidget(_lbl(subtitle,
                "font-size:11px;color:#64748b;background:transparent;border:none;"))
        lay.addLayout(txt)
        lay.addStretch()

        close = QPushButton("✕")
        close.setFixedSize(30, 30)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(
            "QPushButton{background:#334155;color:#94a3b8;border:none;"
            "border-radius:15px;font-size:13px;font-weight:700;}"
            "QPushButton:hover{background:#ef4444;color:white;}"
        )
        close.clicked.connect(parent_dialog.reject)
        lay.addWidget(close)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self._dlg.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self._dlg.move(e.globalPosition().toPoint() - self._drag_pos)


# ─────────────────────────────────────────────────────────────────────────────
# Tab bar
# ─────────────────────────────────────────────────────────────────────────────

class _TabBar(QFrame):
    tab_changed = pyqtSignal(str)

    def __init__(self, tabs: list[tuple[str, str]]):
        super().__init__()
        self.setFixedHeight(44)
        self.setStyleSheet(
            "QFrame{background:#0f172a;border:none;"
            "border-bottom:1.5px solid #1e293b;}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(0)
        self._btns: dict[str, QPushButton] = {}
        for key, label in tabs:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setFixedHeight(44)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton{background:transparent;border:none;"
                "border-bottom:2px solid transparent;"
                "font-size:13px;font-weight:600;color:#475569;"
                "padding:0 20px;border-radius:0;}"
                "QPushButton:checked{color:#818cf8;"
                "border-bottom:2px solid #6366f1;}"
                "QPushButton:hover:!checked{color:#94a3b8;}"
            )
            b.clicked.connect(lambda _, k=key: self.tab_changed.emit(k))
            self._btns[key] = b
            lay.addWidget(b)
        lay.addStretch()

    def set_active(self, key: str):
        for k, b in self._btns.items():
            b.setChecked(k == key)


# ─────────────────────────────────────────────────────────────────────────────
# Veritabanı sekmesi
# ─────────────────────────────────────────────────────────────────────────────

class _DbPanel(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QScrollArea{background:#0f172a;border:none;}")
        self._test_w: _TestWorker | None = None
        self._mig_w: _MigWorker | None = None
        self._current_mod = "sqlite"

        inner = QWidget()
        inner.setStyleSheet("background:#0f172a;")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(20)
        self.setWidget(inner)

        # ── Mod ─────────────────────────────────────────────────────────────
        lay.addWidget(_section("Bağlantı Modu"))
        mr = QHBoxLayout(); mr.setSpacing(10)
        self._sq_btn = _btn("💻  Lokal  (SQLite)", "#1e293b", "#334155")
        self._sq_btn.setCheckable(True)
        self._sq_btn.clicked.connect(lambda: self._set_mod("sqlite"))
        mr.addWidget(self._sq_btn)
        self._pg_btn = _btn("🌐  Sunucu  (PostgreSQL / Supabase)", "#1e293b", "#334155")
        self._pg_btn.setCheckable(True)
        self._pg_btn.clicked.connect(lambda: self._set_mod("postgres"))
        mr.addWidget(self._pg_btn)
        lay.addLayout(mr)
        self._mod_hint = _lbl("", "font-size:11px;color:#475569;")
        lay.addWidget(self._mod_hint)

        # ── PG formu ─────────────────────────────────────────────────────────
        self._pg_card = QFrame()
        self._pg_card.setStyleSheet(
            "QFrame{background:#1e293b;border:1px solid #334155;border-radius:12px;}"
        )
        pgl = QVBoxLayout(self._pg_card)
        pgl.setContentsMargins(18, 16, 18, 18)
        pgl.setSpacing(14)
        pgl.addWidget(_lbl(
            "Supabase → Settings → Database → Connection pooling → Session mode\n"
            "Host: aws-0-eu-central-1.pooler.supabase.com  |  User: postgres.[proje-id]",
            "font-size:11px;color:#64748b;line-height:1.5;"
        ))

        # ── Hızlı Doldurma — Bağlantı Dizisi ─────────────────────────────
        cs_card = QFrame()
        cs_card.setStyleSheet(
            "QFrame{background:#0f172a;border:1.5px solid #6366f1;"
            "border-radius:10px;}"
        )
        csl = QVBoxLayout(cs_card)
        csl.setContentsMargins(14, 12, 14, 12)
        csl.setSpacing(8)

        cs_hdr = QHBoxLayout()
        cs_ic = QLabel("⚡")
        cs_ic.setStyleSheet("font-size:16px;")
        cs_hdr.addWidget(cs_ic)
        cs_t = QLabel("Hızlı Doldurma  —  Bağlantı Dizisi")
        cs_t.setStyleSheet(
            "font-size:12px;font-weight:700;color:#818cf8;"
        )
        cs_hdr.addWidget(cs_t)
        cs_hdr.addStretch()
        csl.addLayout(cs_hdr)

        cs_hint = QLabel(
            "Neon / Supabase / psql  →  bağlantı satırını yapıştır, tüm alanlar otomatik dolar"
        )
        cs_hint.setStyleSheet("font-size:10px;color:#475569;")
        csl.addWidget(cs_hint)

        cs_row = QHBoxLayout(); cs_row.setSpacing(8)
        self._cs_edit = QLineEdit()
        self._cs_edit.setFixedHeight(38)
        self._cs_edit.setPlaceholderText(
            "postgresql://user:pass@host:5432/dbname?sslmode=require  —  veya  host=... port=... user=... password=..."
        )
        self._cs_edit.setStyleSheet(
            "QLineEdit{background:#1e293b;color:#e2e8f0;"
            "border:1.5px solid #6366f1;border-radius:8px;"
            "padding:0 12px;font-size:11px;}"
            "QLineEdit:focus{border-color:#818cf8;}"
        )
        self._cs_edit.returnPressed.connect(self._parse_connection_string)
        cs_row.addWidget(self._cs_edit)

        cs_btn = QPushButton("✔  Uygula")
        cs_btn.setFixedHeight(38); cs_btn.setFixedWidth(95)
        cs_btn.setStyleSheet(
            "QPushButton{background:#6366f1;color:#fff;border:none;"
            "border-radius:8px;font-size:12px;font-weight:700;}"
            "QPushButton:hover{background:#818cf8;}"
            "QPushButton:pressed{background:#4f46e5;}"
        )
        cs_btn.clicked.connect(self._parse_connection_string)
        cs_row.addWidget(cs_btn)
        csl.addLayout(cs_row)

        self._cs_lbl = QLabel("")
        self._cs_lbl.setStyleSheet("font-size:11px;color:#94a3b8;")
        self._cs_lbl.setWordWrap(True)
        csl.addWidget(self._cs_lbl)

        pgl.addWidget(cs_card)
        # ── bağlantı dizisi sonu ──────────────────────────────────────────────

        def _row(*cols):
            r = QHBoxLayout(); r.setSpacing(12)
            for w, s in cols:
                r.addLayout(w, s)
            return r

        def _field(label, widget):
            c = QVBoxLayout(); c.setSpacing(4)
            c.addWidget(_lbl(label, _S_LBL))
            c.addWidget(widget)
            return c

        self._host = QLineEdit(); self._host.setFixedHeight(38); self._host.setStyleSheet(_S_INP)
        self._host.setPlaceholderText("aws-0-eu-central-1.pooler.supabase.com")
        self._port = QLineEdit(); self._port.setFixedHeight(38); self._port.setStyleSheet(_S_INP)
        self._port.setPlaceholderText("5432")
        pgl.addLayout(_row((_field("Sunucu (Host)", self._host), 3),
                           (_field("Port", self._port), 1)))

        self._db = QLineEdit(); self._db.setFixedHeight(38); self._db.setStyleSheet(_S_INP)
        self._db.setPlaceholderText("postgres")
        self._user = QLineEdit(); self._user.setFixedHeight(38); self._user.setStyleSheet(_S_INP)
        self._user.setPlaceholderText("postgres.proje-id")
        pgl.addLayout(_row((_field("Veritabanı", self._db), 1),
                           (_field("Kullanıcı Adı", self._user), 1)))

        self._pw = QLineEdit(); self._pw.setFixedHeight(38)
        self._pw.setEchoMode(QLineEdit.EchoMode.Password); self._pw.setStyleSheet(_S_INP)
        self._pw.setPlaceholderText("••••••••••••")
        self._ssl = QComboBox(); self._ssl.addItems(["require", "prefer", "disable"])
        self._ssl.setFixedHeight(38); self._ssl.setStyleSheet(_S_COMBO)
        pgl.addLayout(_row((_field("Şifre", self._pw), 3),
                           (_field("SSL", self._ssl), 1)))

        tr = QHBoxLayout(); tr.setSpacing(10)
        self._test_btn = _btn("🔌  Bağlantıyı Test Et", "#0ea5e9", "#0284c7", 38, 180)
        self._test_btn.clicked.connect(self._on_test)
        tr.addWidget(self._test_btn)
        self._test_lbl = QLabel("")
        self._test_lbl.setWordWrap(True)
        self._test_lbl.setStyleSheet("font-size:12px;color:#94a3b8;")
        tr.addWidget(self._test_lbl, 1)
        pgl.addLayout(tr)
        lay.addWidget(self._pg_card)

        # ── Kaydet ──────────────────────────────────────────────────────────
        sr = QHBoxLayout(); sr.setSpacing(12)
        self._save_btn = _btn("💾  Kaydet", "#6366f1", "#4f46e5", 40, 130)
        self._save_btn.clicked.connect(self._on_save)
        sr.addWidget(self._save_btn)
        self._save_lbl = QLabel("")
        self._save_lbl.setStyleSheet("font-size:12px;color:#34d399;font-weight:600;")
        sr.addWidget(self._save_lbl, 1)
        lay.addLayout(sr)

        lay.addWidget(_divider())

        # ── Migrasyon ────────────────────────────────────────────────────────
        lay.addWidget(_section("Veri Taşıma  —  SQLite → PostgreSQL"))
        lay.addWidget(_lbl(
            "Mevcut SQLite verilerini PostgreSQL'e kopyalar. "
            "Tekrar çalıştırılsa duplicate oluşmaz (ON CONFLICT DO NOTHING).",
            "font-size:12px;color:#475569;"
        ))

        br = QHBoxLayout(); br.setSpacing(10)
        br.addWidget(_lbl("📦  Paket:", "font-size:12px;color:#64748b;"))
        self._batch = QComboBox()
        self._batch.addItems(["50 (Çok yavaş)", "100 (Yavaş)", "250 (Normal)", "500 (Hızlı)", "1000 (LAN)"])
        self._batch.setCurrentIndex(2); self._batch.setFixedHeight(34)
        self._batch.setStyleSheet(_S_COMBO)
        br.addWidget(self._batch); br.addStretch()
        lay.addLayout(br)

        self._prog = QProgressBar()
        self._prog.setRange(0, 1000); self._prog.setValue(0)
        self._prog.setFixedHeight(6); self._prog.setTextVisible(False)
        self._prog.setStyleSheet(
            "QProgressBar{background:#1e293b;border-radius:3px;border:none;}"
            "QProgressBar::chunk{background:#6366f1;border-radius:3px;}"
        )
        self._prog.hide(); lay.addWidget(self._prog)

        self._mig_lbl = QLabel("")
        self._mig_lbl.setWordWrap(True)
        self._mig_lbl.setStyleSheet("font-size:12px;color:#94a3b8;")
        lay.addWidget(self._mig_lbl)

        self._mig_btn = _btn("🚀  Veriyi PostgreSQL'e Taşı", "#d97706", "#b45309", 42)
        self._mig_btn.clicked.connect(self._on_migrate)
        lay.addWidget(self._mig_btn)
        lay.addStretch()
        self._load()

    def _set_mod(self, mod: str):
        self._current_mod = mod
        ACT = (
            "QPushButton{background:#6366f1;color:#ffffff;border:none;"
            "border-radius:9px;font-size:13px;font-weight:700;}"
        )
        IDL = (
            "QPushButton{background:#1e293b;color:#64748b;"
            "border:1.5px solid #334155;border-radius:9px;"
            "font-size:13px;font-weight:600;}"
            "QPushButton:hover{background:#334155;color:#94a3b8;}"
        )
        if mod == "sqlite":
            self._sq_btn.setStyleSheet(ACT); self._sq_btn.setChecked(True)
            self._pg_btn.setStyleSheet(IDL); self._pg_btn.setChecked(False)
            self._mod_hint.setText("Lokal mod — tek bilgisayar, tek kullanıcı")
        else:
            self._pg_btn.setStyleSheet(ACT); self._pg_btn.setChecked(True)
            self._sq_btn.setStyleSheet(IDL); self._sq_btn.setChecked(False)
            self._mod_hint.setText("Sunucu modu — birden fazla kullanıcı aynı anda bağlanabilir")
        self._pg_card.setVisible(mod == "postgres")

    def _load(self):
        from db.db_config import load_config
        cfg = load_config()
        self._set_mod(cfg.get("mode", "sqlite"))
        self._host.setText(cfg.get("pg_host", ""))
        self._port.setText(str(cfg.get("pg_port", 5432)))
        self._db.setText(cfg.get("pg_db", "postgres"))
        self._user.setText(cfg.get("pg_user", "postgres"))
        self._pw.setText(cfg.get("pg_pass", ""))
        idx = self._ssl.findText(cfg.get("pg_sslmode", "require"))
        if idx >= 0: self._ssl.setCurrentIndex(idx)

    def _on_test(self):
        h = self._host.text().strip(); d = self._db.text().strip(); u = self._user.text().strip()
        if not h or not d or not u:
            self._test_lbl.setText("❌  Host, Veritabanı ve Kullanıcı gerekli")
            return
        try: port = int(self._port.text().strip() or "5432")
        except ValueError:
            self._test_lbl.setText("❌  Port sayı olmalıdır"); return
        self._test_btn.setEnabled(False)
        self._test_lbl.setText("⏳  Bağlanılıyor...")
        self._test_lbl.setStyleSheet("font-size:12px;color:#818cf8;")
        self._test_w = _TestWorker(h, port, d, u, self._pw.text(), self._ssl.currentText())
        self._test_w.done.connect(self._on_test_done); self._test_w.start()

    def _on_test_done(self, res):
        self._test_btn.setEnabled(True)
        ok = res["ok"]
        self._test_lbl.setText(("✅  " if ok else "❌  ") + res["msg"])
        self._test_lbl.setStyleSheet(
            f"font-size:12px;font-weight:600;color:{'#34d399' if ok else '#f87171'};"
        )

    def _on_save(self):
        from db.db_config import load_config, save_config
        cfg = load_config()
        try: port = int(self._port.text().strip() or "5432")
        except ValueError: port = 5432
        cfg.update({
            "mode": self._current_mod,
            "pg_host": self._host.text().strip(),
            "pg_port": port,
            "pg_db": self._db.text().strip(),
            "pg_user": self._user.text().strip(),
            "pg_pass": self._pw.text(),
            "pg_sslmode": self._ssl.currentText(),
        })
        save_config(cfg)
        self._save_lbl.setText("✅  Kaydedildi — uygulamayı yeniden başlatın")

    # ─────────────────────────────────────────────────────────────────
    def _parse_connection_string(self):
        """Bağlantı dizisini parse edip formu otomatik doldurur.

        Desteklenen formatlar:
          1) postgresql://user:pass@host:port/dbname?sslmode=require
          2) postgres://user:pass@host:port/dbname
          3) host=X port=Y dbname=Z user=U password=P sslmode=S
        """
        raw = self._cs_edit.text().strip()
        if not raw:
            self._cs_lbl.setText("⚠️  Lütfen bir bağlantı dizisi yapıştırın.")
            self._cs_lbl.setStyleSheet("font-size:11px;color:#f59e0b;")
            return

        host = port = db = user = pw = ssl = ""

        # Format 1 & 2 : URL
        if raw.startswith(("postgresql://", "postgres://")):
            try:
                from urllib.parse import urlparse, parse_qs, unquote
                p = urlparse(raw)
                host = p.hostname or ""
                port = str(p.port or 5432)
                db   = (p.path or "").lstrip("/")
                user = unquote(p.username or "")
                pw   = unquote(p.password or "")
                qs   = parse_qs(p.query)
                ssl  = qs.get("sslmode", ["require"])[0]
            except Exception as e:
                self._cs_lbl.setText(f"❌  URL parse hatası: {e}")
                self._cs_lbl.setStyleSheet("font-size:11px;color:#f87171;")
                return

        # Format 3 : DSN key=value
        elif "=" in raw:
            import re
            def _v(key):
                m = re.search(rf"(?:^|\s){re.escape(key)}=([^\s]+)", raw)
                return m.group(1) if m else ""
            host = _v("host")
            port = _v("port") or "5432"
            db   = _v("dbname") or _v("database")
            user = _v("user") or _v("username")
            pw   = _v("password")
            ssl  = _v("sslmode") or "require"
        else:
            self._cs_lbl.setText(
                "❌  Tanınmayan format. "
                "postgresql://user:pass@host:5432/db  veya  host=... user=... formatı kullanın."
            )
            self._cs_lbl.setStyleSheet("font-size:11px;color:#f87171;")
            return

        # Alanları doldur
        if host: self._host.setText(host)
        if port: self._port.setText(port)
        if db:   self._db.setText(db)
        if user: self._user.setText(user)
        if pw:   self._pw.setText(pw)
        if ssl:
            idx = self._ssl.findText(ssl)
            if idx >= 0: self._ssl.setCurrentIndex(idx)

        dolu = [k for k, v in
                [("Host", host), ("Port", port), ("Veritabanı", db),
                 ("Kullanıcı", user), ("Şifre", pw)]
                if v]
        self._cs_lbl.setText(
            f"✅  Dolduruldu: {', '.join(dolu)}  —  "
            "Kontrol edip 'Kaydet'e basın."
        )
        self._cs_lbl.setStyleSheet(
            "font-size:11px;font-weight:600;color:#34d399;"
        )

    def _on_migrate(self):
        from db.db_config import load_config
        cfg = load_config()
        if cfg.get("mode") != "postgres" or not cfg.get("pg_host"):
            self._mig_lbl.setText("⚠️  Önce PostgreSQL bağlantısını kaydedin."); return
        _MAP = {0: 50, 1: 100, 2: 250, 3: 500, 4: 1000}
        bs = _MAP.get(self._batch.currentIndex(), 250)
        self._mig_btn.setEnabled(False)
        self._prog.setValue(0); self._prog.show()
        self._mig_lbl.setText("⏳  Veri taşınıyor...")
        self._mig_lbl.setStyleSheet("font-size:12px;color:#818cf8;")
        self._mig_w = _MigWorker(bs)
        self._mig_w.progress.connect(self._on_mig_prog)
        self._mig_w.finished.connect(self._on_mig_done)
        self._mig_w.start()

    def _on_mig_prog(self, tablo, akt, top):
        self._mig_lbl.setText(f"⏳  {tablo}  {akt:,}/{top:,}")
        self._prog.setValue(min(990, int(akt/top*900) if top > 0 else 0))

    def _on_mig_done(self, ok, msg):
        self._prog.setValue(1000)
        self._mig_btn.setEnabled(True)
        self._mig_lbl.setText(("✅  " if ok else "❌  ") + msg)
        self._mig_lbl.setStyleSheet(
            f"font-size:12px;font-weight:600;color:{'#34d399' if ok else '#f87171'};"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Kullanıcı yönetimi sekmesi
# ─────────────────────────────────────────────────────────────────────────────

class _UserPanel(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QScrollArea{background:#0f172a;border:none;}")

        inner = QWidget(); inner.setStyleSheet("background:#0f172a;")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(24, 20, 24, 24); lay.setSpacing(20)
        self.setWidget(inner)

        # ── Mevcut kullanıcılar ──────────────────────────────────────────────
        lay.addWidget(_section("Mevcut Kullanıcılar"))
        self._mevcut = QFrame()
        self._mevcut.setStyleSheet(
            "QFrame{background:#1e293b;border:1px solid #334155;border-radius:10px;}"
        )
        ml = QVBoxLayout(self._mevcut)
        ml.setContentsMargins(16, 12, 16, 12); ml.setSpacing(6)
        self._mevcut_lay = ml
        lay.addWidget(self._mevcut)

        # ── Yeni kullanıcı formu ────────────────────────────────────────────
        lay.addWidget(_divider())
        lay.addWidget(_section("Kullanıcı Oluştur / Şifre Sıfırla"))

        form = QFrame()
        form.setStyleSheet(
            "QFrame{background:#1e293b;border:1px solid #334155;border-radius:12px;}"
        )
        fl = QVBoxLayout(form)
        fl.setContentsMargins(20, 18, 20, 20); fl.setSpacing(14)

        def _field(label, widget):
            c = QVBoxLayout(); c.setSpacing(5)
            c.addWidget(_lbl(label, _S_LBL)); c.addWidget(widget)
            return c

        r1 = QHBoxLayout(); r1.setSpacing(12)
        self._ad = QLineEdit(); self._ad.setFixedHeight(38); self._ad.setStyleSheet(_S_INP)
        self._ad.setPlaceholderText("Ahmet Yılmaz")
        self._kadi = QLineEdit(); self._kadi.setFixedHeight(38); self._kadi.setStyleSheet(_S_INP)
        self._kadi.setPlaceholderText("admin")
        r1.addLayout(_field("Ad Soyad", self._ad))
        r1.addLayout(_field("Kullanıcı Adı", self._kadi))
        fl.addLayout(r1)

        r2 = QHBoxLayout(); r2.setSpacing(12)
        self._eposta = QLineEdit(); self._eposta.setFixedHeight(38); self._eposta.setStyleSheet(_S_INP)
        self._eposta.setPlaceholderText("admin@firma.com")
        self._rol = QComboBox(); self._rol.addItems(["admin", "analist", "verigiris"])
        self._rol.setFixedHeight(38); self._rol.setStyleSheet(_S_COMBO)
        r2.addLayout(_field("E-posta", self._eposta))
        r2.addLayout(_field("Rol", self._rol))
        fl.addLayout(r2)

        r3 = QHBoxLayout(); r3.setSpacing(12)
        self._sifre = QLineEdit(); self._sifre.setFixedHeight(38)
        self._sifre.setEchoMode(QLineEdit.EchoMode.Password)
        self._sifre.setPlaceholderText("Şifre"); self._sifre.setStyleSheet(_S_INP)
        self._sifre2 = QLineEdit(); self._sifre2.setFixedHeight(38)
        self._sifre2.setEchoMode(QLineEdit.EchoMode.Password)
        self._sifre2.setPlaceholderText("Şifre tekrar"); self._sifre2.setStyleSheet(_S_INP)
        r3.addLayout(_field("Şifre", self._sifre))
        r3.addLayout(_field("Şifre (tekrar)", self._sifre2))
        fl.addLayout(r3)

        self._form_msg = QLabel("")
        self._form_msg.setWordWrap(True)
        self._form_msg.setStyleSheet("font-size:12px;color:#f87171;")
        fl.addWidget(self._form_msg)

        self._create_btn = _btn("✅  Kullanıcıyı Oluştur / Güncelle", "#059669", "#047857", 44)
        self._create_btn.clicked.connect(self._on_create)
        fl.addWidget(self._create_btn)
        lay.addWidget(form)
        lay.addStretch()
        self._refresh()

    def _refresh(self):
        # Mevcut layoutu temizle
        while self._mevcut_lay.count():
            item = self._mevcut_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        from db.database import get_connection
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT kullanici_adi, ad, soyad, yetki FROM uyelik ORDER BY id LIMIT 30"
            ).fetchall()
            conn.close()
            if not rows:
                self._mevcut_lay.addWidget(_lbl(
                    "⚠️  Veritabanında kullanıcı yok — aşağıdan oluşturun.",
                    "font-size:12px;color:#f59e0b;font-weight:600;"
                ))
                return
            for r in rows:
                rd = dict(r)
                ad_goster = f"{rd.get('ad') or ''} {rd.get('soyad') or ''}".strip() or rd.get('kullanici_adi', '?')
                rol_goster = rd.get('yetki') or rd.get('rol') or '?'
                self._mevcut_lay.addWidget(_lbl(
                    f"✅  {ad_goster}  "
                    f"— @{rd.get('kullanici_adi','?')}  "
                    f"({rol_goster})",
                    "font-size:12px;color:#94a3b8;"
                ))
        except Exception as e:
            self._mevcut_lay.addWidget(_lbl(
                f"❌  {e}", "font-size:12px;color:#f87171;"
            ))

    def _on_create(self):
        import hashlib
        kadi  = self._kadi.text().strip()
        sifre = self._sifre.text()
        sifre2 = self._sifre2.text()
        ad    = self._ad.text().strip()
        eposta = self._eposta.text().strip()
        rol   = self._rol.currentText()

        if not kadi:
            self._msg("❌  Kullanıcı adı zorunludur."); return
        if not sifre:
            self._msg("❌  Şifre zorunludur."); return
        if sifre != sifre2:
            self._msg("❌  Şifreler eşleşmiyor."); return
        # Karakter sınırlaması YOK

        pw_hash = hashlib.md5(sifre.encode()).hexdigest()

        # Ad Soyad parçala
        parts = (ad or kadi).split(" ")
        if len(parts) > 1:
            ad_val = " ".join(parts[:-1])
            soyad_val = parts[-1]
        else:
            ad_val = parts[0]
            soyad_val = ""

        from db.database import get_connection
        try:
            conn = get_connection()
            existing = conn.execute(
                "SELECT id FROM uyelik WHERE kullanici_adi=?", (kadi,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE uyelik SET sifre=?, ad=?, soyad=?, eposta=?, yetki=? WHERE kullanici_adi=?",
                    (pw_hash, ad_val, soyad_val, eposta or f"{kadi}@firma.com", rol, kadi)
                )
                msg = f"✅  '{kadi}' şifresi güncellendi."
            else:
                conn.execute(
                    "INSERT INTO uyelik (kullanici_adi, sifre, ad, soyad, eposta, yetki) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (kadi, pw_hash, ad_val, soyad_val, eposta or f"{kadi}@firma.com", rol)
                )
                msg = f"✅  '{kadi}' kullanıcısı oluşturuldu!"
            conn.commit(); conn.close()
            self._msg(msg, ok=True)
            self._refresh()
        except Exception as e:
            self._msg(f"❌  {e}")

    def _msg(self, text: str, ok: bool = False):
        self._form_msg.setText(text)
        self._form_msg.setStyleSheet(
            f"font-size:12px;font-weight:600;color:{'#34d399' if ok else '#f87171'};"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Ana dialog
# ─────────────────────────────────────────────────────────────────────────────

class SuperAdminDialog(QDialog):
    """
    Yazılım sahibi sistem yönetim penceresi.
    Erişim: Ctrl + Shift + Alt + S  (login ekranında)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(740, 680)
        self._build()

    def _build(self):
        master = QVBoxLayout(self)
        master.setContentsMargins(12, 12, 12, 12)

        # Outer card
        card = QFrame()
        card.setObjectName("sa_card")
        card.setStyleSheet(
            "QFrame#sa_card{"
            "  background:#0f172a;"
            "  border:1px solid #1e293b;"
            "  border-radius:16px;"
            "}"
        )
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(40); sh.setColor(QColor(0, 0, 0, 120)); sh.setOffset(0, 8)
        card.setGraphicsEffect(sh)
        master.addWidget(card)

        root = QVBoxLayout(card)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # Header (sürüklenebilir)
        self._hdr = _DragHeader(self, "Sistem Ayarları", "Yazılım yönetim paneli — yalnızca yetkili personel")
        root.addWidget(self._hdr)

        # Tab bar
        self._tabs = _TabBar([
            ("db",   "🗄️  Veritabanı"),
            ("user", "👤  Kullanıcı Yönetimi"),
        ])
        self._tabs.tab_changed.connect(self._switch)
        root.addWidget(self._tabs)

        # Paneller
        self._db_panel   = _DbPanel()
        self._user_panel = _UserPanel()
        root.addWidget(self._db_panel, 1)
        root.addWidget(self._user_panel, 1)

        self._switch("db")

    def _switch(self, key: str):
        self._db_panel.setVisible(key == "db")
        self._user_panel.setVisible(key == "user")
        self._tabs.set_active(key)
