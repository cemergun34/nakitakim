"""
Ayarlar Ekranı — PyQt6
PHP ayarlar.php → Eklentiler tab → E-Fatura Çek + VOMSİS API bölümlerinin karşılığı.
"""
from __future__ import annotations
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFileDialog, QFrame, QScrollArea,
    QMessageBox, QProgressBar, QDialog, QDialogButtonBox,
    QLineEdit, QDateEdit, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont

from ui.theme import COLORS
from services.efatura_service import (
    import_xml,
    get_alt_hesap_kodlari, get_cari_hesaplar
)
from db.database import get_connection

import datetime
CURRENT_YEAR = datetime.datetime.now().year


# ── Arka plan iş parçacığı ───────────────────────────────────────────────────

class ImportWorker(QThread):
    progress = pyqtSignal(int, int, str, str)  # (current, total, dosya, durum)
    finished = pyqtSignal(int, int, int, int)  # (basarili, atlandi, hatali, eslesmez)

    def __init__(self, paths: list[str], userid: int):
        super().__init__()
        self.paths = paths
        self.userid = userid

    def run(self):
        basarili = atlandi = hatali = eslesmez = 0
        for i, path in enumerate(self.paths):
            res = import_xml(path, self.userid)
            if res.get("skipped"):
                atlandi += 1
                durum = "atlandi"
            elif res.get("no_match"):
                eslesmez += 1
                durum = "eslesmez"
            elif res["success"]:
                basarili += 1
                durum = "ok"
            else:
                hatali += 1
                durum = "hata"
            self.progress.emit(i + 1, len(self.paths), os.path.basename(path), durum)
        self.finished.emit(basarili, atlandi, hatali, eslesmez)



# ── E-Fatura Çek Kartı ───────────────────────────────────────────────────────

class EFaturaCard(QFrame):
    def __init__(self, userid: int, parent=None):
        super().__init__(parent)
        self.userid = userid
        self._worker: ImportWorker | None = None

        self.setStyleSheet(
            "QFrame{background:white;border:1.5px solid #e2e8f0;"
            "border-radius:14px;}"
        )
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        # Başlık
        h = QHBoxLayout()
        ic = QLabel("🧾")
        ic.setStyleSheet("font-size:20px;")
        h.addWidget(ic)
        t = QLabel("E-Fatura Çek")
        t.setStyleSheet("font-size:14px;font-weight:700;color:#000000;letter-spacing:.5px;")
        h.addWidget(t)
        h.addStretch()
        root.addLayout(h)

        # Bilgi chip
        self._profil_chip = QLabel("")
        self._profil_chip.setWordWrap(True)
        self._profil_chip.setStyleSheet(
            "background:#e6edfa;color:#000000;border-radius:6px;"
            "padding:9px 12px;font-size:12px;border:none;"
        )
        root.addWidget(self._profil_chip)

        # Butonlar
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.aktar_btn = QPushButton("\U0001f4c1  Klasör Seç & Tüm XML'leri Aktar")
        self.aktar_btn.setFixedHeight(38)
        self.aktar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.aktar_btn.setStyleSheet(self._btn_style("#418def"))
        self.aktar_btn.clicked.connect(self._on_aktar)
        btn_row.addWidget(self.aktar_btn)

        btn_row.addStretch()
        root.addLayout(btn_row)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.progress.setStyleSheet(
            "QProgressBar{background:#f1f5f9;border-radius:3px;border:none;}"
            "QProgressBar::chunk{background:#418def;border-radius:3px;}"
        )
        root.addWidget(self.progress)

        # Durum etiketi
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("font-size:12px;color:#000000;")
        self.status_lbl.hide()
        root.addWidget(self.status_lbl)

        # aktar_btn olustuktan sonra profil durumunu guncelle
        self._update_profil_chip()

    def _btn_style(self, color: str) -> str:
        return (f"QPushButton{{background:{color};color:white;border:none;"
                f"border-radius:9px;font-size:13px;font-weight:600;"
                f"padding:0 18px;letter-spacing:.5px;}}"
                f"QPushButton:hover{{opacity:.85;background:{color}cc;}}"
                f"QPushButton:disabled{{background:#cbd5e1;color:#94a3b8;}}")

    def _update_profil_chip(self):
        from services.sirket_service import get_sirket_profili
        p = get_sirket_profili(self.userid)
        if p and (p.get("vergino") or p.get("tckn")):
            vkn = p.get("vergino") or p.get("tckn")
            self._profil_chip.setText(
                f"✅  Aktif Şirket: <b>{p.get('unvan','')}</b>  |  VKN: {vkn}  |  "
                "Gelen/Kesilen ayrımı otomatik yapılacak."
            )
            self._profil_chip.setStyleSheet(
                "background:#dcfce7;color:#166534;border-radius:6px;"
                "padding:9px 12px;font-size:12px;border:none;"
            )
            self.aktar_btn.setEnabled(True)
        else:
            self._profil_chip.setText(
                "⚠️  Şirket profili tanımlanmamış. "
                "Önce 'Hesap & Güvenlik' sekmesinden şirket bilgilerini kaydedin."
            )
            self._profil_chip.setStyleSheet(
                "background:#fef3c7;color:#92400e;border-radius:6px;"
                "padding:9px 12px;font-size:12px;border:none;"
            )
            self.aktar_btn.setEnabled(False)

    def refresh(self):
        self._update_profil_chip()

    def _on_aktar(self):
        from services.sirket_service import get_sirket_profili
        p = get_sirket_profili(self.userid)
        if not p or not (p.get("vergino") or p.get("tckn")):
            QMessageBox.warning(self, "Şirket Profili Yok",
                "Önce 'Hesap & Güvenlik' sekmesinden şirket profilinizi kaydedin.")
            return

        klasor = QFileDialog.getExistingDirectory(
            self, "XML Fatura Klasörü Seç", ""
        )
        if not klasor:
            return

        paths = [
            os.path.join(klasor, f)
            for f in os.listdir(klasor)
            if f.lower().endswith(".xml")
        ]

        if not paths:
            QMessageBox.information(
                self, "Dosya Bulunamadı",
                f"Seçilen klasörde hiç .xml dosyası yok:\n{klasor}"
            )
            return

        self.status_lbl.setText(f"📁  {len(paths)} XML dosyası bulundu, aktarılıyor...")
        self.status_lbl.show()
        self._start_import(paths)

    def _start_import(self, paths: list[str]):
        """İmport worker'ı başlatır — UI'yi bloklamaz."""
        self.aktar_btn.setEnabled(False)
        self.progress.setMaximum(len(paths))
        self.progress.setValue(0)
        self.progress.show()

        self._worker = ImportWorker(paths, self.userid)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_import_done)
        self._worker.start()

    def _on_progress(self, current: int, total: int, dosya: str, durum: str):
        self.progress.setValue(current)
        icon = {"ok": "✔", "atlandi": "⏩", "hata": "✖", "eslesmez": "❓"}.get(durum, "")
        self.status_lbl.setText(f"{icon}  {dosya}  ({current}/{total})")

    def _on_import_done(self, basarili: int, atlandi: int, hatali: int, eslesmez: int):
        self.progress.hide()
        self.aktar_btn.setEnabled(True)
        parts = []
        if basarili:
            parts.append(f"✔ {basarili} aktarıldı")
        if atlandi:
            parts.append(f"⏩ {atlandi} zaten mevcuttu")
        if eslesmez:
            parts.append(f"❓ {eslesmez} VKN eşleşmedi")
        if hatali:
            parts.append(f"✖ {hatali} hatalı")
        self.status_lbl.setText("  ·  ".join(parts) if parts else "Tamamlandı")




# ── VOMSİS API Worker ────────────────────────────────────────────────────────

class VomsisTestWorker(QThread):
    """'Kontrol Et' butonu için arka plan iş parçacığı."""
    result = pyqtSignal(dict)   # {'success': bool, 'message': str, ...}

    def __init__(self, api_base: str, app_key: str, app_secret: str):
        super().__init__()
        self._api_base   = api_base
        self._app_key    = app_key
        self._app_secret = app_secret

    def run(self):
        from services.vomsis_service import vomsis_test_connection
        r = vomsis_test_connection(self._api_base, self._app_key, self._app_secret)
        self.result.emit(r)


class VomsisIsleWorker(QThread):
    """'VOMSİS İşle' butonu — seçilen tarih aralığında hareketleri çekip DB'e yazar."""
    progress = pyqtSignal(str)   # durum metni
    finished = pyqtSignal(dict)  # {'success': bool, 'message': str, 'count': int}

    def __init__(self, api_base: str, app_key: str, app_secret: str,
                 start_dt: datetime.datetime, end_dt: datetime.datetime,
                 userid: int):
        super().__init__()
        self._api_base   = api_base
        self._app_key    = app_key
        self._app_secret = app_secret
        self._start_dt   = start_dt
        self._end_dt     = end_dt
        self._userid     = userid

    def run(self):
        from services.vomsis_service import (
            vomsis_authenticate, vomsis_get_all_transactions_chunked
        )

        self.progress.emit("🔑  Token alınıyor...")
        token, err_msg = vomsis_authenticate(self._api_base, self._app_key, self._app_secret)
        if not token:
            self.finished.emit({
                "success": False,
                "message": err_msg or "Token alınamadı. API bilgilerini kontrol edin.",
                "count": 0
            })
            return

        self.progress.emit("📡  Banka hareketleri çekiliyor...")
        txs = vomsis_get_all_transactions_chunked(
            self._api_base, token, self._start_dt, self._end_dt
        )

        count = 0
        conn = get_connection()
        try:
            for tx in txs:
                # VOMSİS hareket alanlarını hareketler tablosuna yaz
                tarih_raw = tx.get("date") or tx.get("processDate") or ""
                aciklama  = tx.get("description") or tx.get("explanation") or ""
                tutar_raw = tx.get("amount") or tx.get("tryAmount") or 0
                try:
                    tutar = float(str(tutar_raw).replace(",", "."))
                except (ValueError, TypeError):
                    tutar = 0.0
                yon       = tx.get("direction") or tx.get("transactionDirection") or ""
                gelir_gider = "gelir" if str(yon).upper() in ("CREDIT", "ALACAK", "+") else "gider"
                borc   = tutar if gelir_gider == "gelir" else 0.0
                alacak = tutar if gelir_gider == "gider" else 0.0
                vomsis_key = tx.get("id") or tx.get("transactionId") or ""

                # Aynı VOMSİS kaydı zaten varsa atla
                if vomsis_key:
                    exists = conn.execute(
                        "SELECT id FROM hareketler WHERE womsisKey=? AND userid=? LIMIT 1",
                        (str(vomsis_key), self._userid)
                    ).fetchone()
                    if exists:
                        continue

                conn.execute(
                    """INSERT INTO hareketler
                       (tarih, aciklama, gelirGider, alinan_tutar1, kaynak, womsisKey, userid)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (tarih_raw, aciklama, gelir_gider, tutar, "vomsis",
                     str(vomsis_key), self._userid)
                )
                count += 1
                self.progress.emit(f"✔  {count} hareket işlendi...")
            conn.commit()
        except Exception as exc:
            conn.rollback()
            self.finished.emit({"success": False, "message": str(exc), "count": count})
            return
        finally:
            conn.close()

        self.finished.emit({
            "success": True,
            "message": f"{count} banka hareketi aktarıldı.",
            "count": count
        })


# ── VOMSİS API Kartı ──────────────────────────────────────────────────────────

class VomsisCard(QFrame):
    """
    PHP ayarlar.php → Eklentiler → VOMSİS API bölümünün PyQt6 karşılığı.
    Alanlar: API URL, API KEY, API SECRET KEY
    Butonlar: Kontrol Et | VOMSİS İşle (tarih aralığı seçerek)
    """

    def __init__(self, userid: int, parent=None):
        super().__init__(parent)
        self._userid  = userid
        self._test_worker: VomsisTestWorker | None = None
        self._isle_worker: VomsisIsleWorker | None = None
        self.setStyleSheet(
            "QFrame{background:white;border:1.5px solid #e0e7ff;"
            "border-radius:14px;}"
        )
        self._build()
        self._load()

    # ── Yardımcılar ────────────────────────────────────────────────────────

    def _input_style(self) -> str:
        return (
            "QLineEdit{background:#f8fafc;border:1.5px solid #e2e8f0;"
            "border-radius:8px;padding:0 10px;font-size:13px;color:#1f2937;}"
            "QLineEdit:focus{border-color:#6366f1;}"
        )

    def _label_style(self) -> str:
        return "font-size:12px;font-weight:600;color:#374151;"

    def _btn_style(self, color: str) -> str:
        return (
            f"QPushButton{{background:{color};color:white;border:none;"
            f"border-radius:9px;font-size:13px;font-weight:600;"
            f"padding:0 16px;letter-spacing:.4px;}}"
            f"QPushButton:hover{{background:{color}cc;}}"
            f"QPushButton:disabled{{background:#cbd5e1;color:#94a3b8;}}"
        )

    # ── UI inşası ──────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        # Başlık satırı
        h = QHBoxLayout()
        ic = QLabel("🔌")
        ic.setStyleSheet("font-size:20px;")
        h.addWidget(ic)
        t = QLabel("VOMSİS API")
        t.setStyleSheet("font-size:14px;font-weight:700;color:#000000;letter-spacing:.5px;")
        h.addWidget(t)
        h.addStretch()
        root.addLayout(h)

        # Bilgi chip
        info = QLabel(
            "💡  Vomsis bilgilerini girdikten sonra sistem otomatik olarak "
            "banka hareketlerinizi çekebilir. 'Kontrol Et' ile bağlantıyı doğrulayın."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "background:#ede9fe;color:#4c1d95;border-radius:6px;"
            "padding:9px 12px;font-size:12px;border:none;"
        )
        root.addWidget(info)

        # ── Alan satırı 1 — URL + APP KEY ──
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        url_col = QVBoxLayout()
        url_lbl = QLabel("API URL")
        url_lbl.setStyleSheet(self._label_style())
        self._url_inp = QLineEdit()
        self._url_inp.setFixedHeight(34)
        self._url_inp.setPlaceholderText("https://developers.vomsis.com/api/v2")
        self._url_inp.setStyleSheet(self._input_style())
        url_col.addWidget(url_lbl)
        url_col.addWidget(self._url_inp)
        row1.addLayout(url_col, 2)

        key_col = QVBoxLayout()
        key_lbl = QLabel("API KEY")
        key_lbl.setStyleSheet(self._label_style())
        self._key_inp = QLineEdit()
        self._key_inp.setFixedHeight(34)
        self._key_inp.setPlaceholderText("API KEY")
        self._key_inp.setStyleSheet(self._input_style())
        key_col.addWidget(key_lbl)
        key_col.addWidget(self._key_inp)
        row1.addLayout(key_col, 2)
        root.addLayout(row1)

        # ── Alan satırı 2 — SECRET KEY ──
        sec_lbl = QLabel("API SECRET KEY")
        sec_lbl.setStyleSheet(self._label_style())
        self._sec_inp = QLineEdit()
        self._sec_inp.setFixedHeight(34)
        self._sec_inp.setPlaceholderText("API SECRET KEY")
        self._sec_inp.setStyleSheet(self._input_style())
        root.addWidget(sec_lbl)
        root.addWidget(self._sec_inp)

        # ── Tarih aralığı (Manuel İşle için) ──
        date_row = QHBoxLayout()
        date_row.setSpacing(10)
        date_lbl = QLabel("Tarih Aralığı:")
        date_lbl.setStyleSheet(self._label_style())
        date_row.addWidget(date_lbl)

        DATE_STYLE = (
            "QDateEdit{background:#f8fafc;border:1.5px solid #e2e8f0;"
            "border-radius:8px;padding:0 8px;font-size:13px;color:#1f2937;}"
            "QDateEdit:focus{border-color:#6366f1;}"
        )
        self._start_date = QDateEdit()
        self._start_date.setFixedHeight(34)
        self._start_date.setFixedWidth(130)
        self._start_date.setDisplayFormat("dd.MM.yyyy")
        self._start_date.setDate(QDate.currentDate().addDays(-7))
        self._start_date.setCalendarPopup(True)
        self._start_date.setStyleSheet(DATE_STYLE)
        date_row.addWidget(self._start_date)

        dash = QLabel("—")
        dash.setStyleSheet("color:#6b7280;font-size:14px;")
        date_row.addWidget(dash)

        self._end_date = QDateEdit()
        self._end_date.setFixedHeight(34)
        self._end_date.setFixedWidth(130)
        self._end_date.setDisplayFormat("dd.MM.yyyy")
        self._end_date.setDate(QDate.currentDate())
        self._end_date.setCalendarPopup(True)
        self._end_date.setStyleSheet(DATE_STYLE)
        date_row.addWidget(self._end_date)
        date_row.addStretch()
        root.addLayout(date_row)

        # ── Butonlar ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._kontrol_btn = QPushButton("🔍  Kontrol Et")
        self._kontrol_btn.setFixedHeight(38)
        self._kontrol_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._kontrol_btn.setStyleSheet(self._btn_style("#6366f1"))
        self._kontrol_btn.clicked.connect(self._on_kontrol_et)
        btn_row.addWidget(self._kontrol_btn)

        self._kaydet_btn = QPushButton("💾  Kaydet")
        self._kaydet_btn.setFixedHeight(38)
        self._kaydet_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._kaydet_btn.setStyleSheet(self._btn_style("#2563eb"))
        self._kaydet_btn.clicked.connect(self._on_kaydet)
        btn_row.addWidget(self._kaydet_btn)

        self._isle_btn = QPushButton("⚡  VOMSİS İşle")
        self._isle_btn.setFixedHeight(38)
        self._isle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._isle_btn.setStyleSheet(self._btn_style("#0891b2"))
        self._isle_btn.clicked.connect(self._on_isle)
        btn_row.addWidget(self._isle_btn)

        btn_row.addStretch()
        root.addLayout(btn_row)

        # ── Durum etiketi ──
        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet("font-size:12px;color:#374151;")
        self._status_lbl.hide()
        root.addWidget(self._status_lbl)

    # ── Veri yükleme ────────────────────────────────────────────────────────

    def _load(self):
        from services.vomsis_service import get_vomsis_bilgileri, DEFAULT_API_URL
        bilgi = get_vomsis_bilgileri(self._userid)
        self._url_inp.setText(bilgi.get("url") or DEFAULT_API_URL)
        self._key_inp.setText(bilgi.get("appkey") or "")
        self._sec_inp.setText(bilgi.get("seckey") or "")

    def refresh(self):
        self._load()

    # ── Kaydet ──────────────────────────────────────────────────────────────

    def _on_kaydet(self):
        from services.vomsis_service import save_vomsis_bilgileri
        url    = self._url_inp.text().strip()
        appkey = self._key_inp.text().strip()
        seckey = self._sec_inp.text().strip()

        if not url or not appkey or not seckey:
            self._show_status("⚠️  Tüm alanları doldurunuz.", "#92400e")
            return

        result = save_vomsis_bilgileri(self._userid, appkey, seckey, url)
        if result["success"]:
            self._show_status(f"✅  {result['message']}", "#059669")
        else:
            self._show_status(f"❌  {result['message']}", "#dc2626")

    # ── Kontrol Et ──────────────────────────────────────────────────────────

    def _on_kontrol_et(self):
        url    = self._url_inp.text().strip()
        appkey = self._key_inp.text().strip()
        seckey = self._sec_inp.text().strip()

        if not url or not appkey or not seckey:
            self._show_status("⚠️  Tüm alanları doldurunuz.", "#92400e")
            return

        self._set_busy(True, "🔑  VOMSİS sunucusuna bağlanılıyor...")

        self._test_worker = VomsisTestWorker(url, appkey, seckey)
        self._test_worker.result.connect(self._on_test_result)
        self._test_worker.start()

    def _on_test_result(self, r: dict):
        self._set_busy(False)
        if r["success"]:
            self._show_status(f"✅  {r['message']}", "#059669")
        else:
            self._show_status(f"❌  {r['message']}", "#dc2626")

    # ── VOMSİS İşle ─────────────────────────────────────────────────────────

    def _on_isle(self):
        url    = self._url_inp.text().strip()
        appkey = self._key_inp.text().strip()
        seckey = self._sec_inp.text().strip()

        if not url or not appkey or not seckey:
            self._show_status("⚠️  Önce API bilgilerini kaydedin.", "#92400e")
            return

        start_qd = self._start_date.date()
        end_qd   = self._end_date.date()
        start_dt = datetime.datetime(start_qd.year(), start_qd.month(), start_qd.day())
        end_dt   = datetime.datetime(end_qd.year(),   end_qd.month(),   end_qd.day(),
                                     23, 59, 59)

        if start_dt > end_dt:
            self._show_status("⚠️  Başlangıç tarihi bitiş tarihinden büyük olamaz.", "#92400e")
            return

        dlg = QMessageBox(self)
        dlg.setWindowTitle("VOMSİS İşle")
        dlg.setIcon(QMessageBox.Icon.Question)
        dlg.setText(
            f"{start_qd.toString('dd.MM.yyyy')} — {end_qd.toString('dd.MM.yyyy')} "
            f"aralığındaki banka hareketleri aktarılacak.<br><br>"
            "Devam etmek istiyor musunuz?"
        )
        dlg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        dlg.button(QMessageBox.StandardButton.Yes).setText("⚡  İşle")
        dlg.button(QMessageBox.StandardButton.Cancel).setText("Vazgeç")
        if dlg.exec() != QMessageBox.StandardButton.Yes:
            return

        self._set_busy(True, "⚡  VOMSİS banka hareketleri alınıyor...")

        self._isle_worker = VomsisIsleWorker(
            url, appkey, seckey, start_dt, end_dt, self._userid
        )
        self._isle_worker.progress.connect(
            lambda msg: self._show_status(msg, "#0891b2")
        )
        self._isle_worker.finished.connect(self._on_isle_done)
        self._isle_worker.start()

    def _on_isle_done(self, r: dict):
        self._set_busy(False)
        if r["success"]:
            self._show_status(f"✅  {r['message']}", "#059669")
        else:
            self._show_status(f"❌  {r['message']}", "#dc2626")

    # ── Yardımcı metotlar ────────────────────────────────────────────────────

    def _set_busy(self, busy: bool, msg: str = ""):
        self._kontrol_btn.setEnabled(not busy)
        self._kaydet_btn.setEnabled(not busy)
        self._isle_btn.setEnabled(not busy)
        if busy and msg:
            self._show_status(msg, "#6366f1")

    def _show_status(self, text: str, color: str = "#374151"):
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(
            f"font-size:12px;color:{color};padding:4px 0;"
        )
        self._status_lbl.show()


# ── Fatura Yönetim Kartı ──────────────────────────────────────────────────────

class FaturaYonetimCard(QFrame):
    """Yıl + mod seçerek fatura kayıtlarını silen yönetim paneli."""

    def __init__(self, userid: int, parent=None):
        super().__init__(parent)
        self._userid = userid
        self.setStyleSheet(
            "QFrame{background:white;border:1.5px solid #fee2e2;"
            "border-radius:14px;}"
        )
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        # Başlık
        h = QHBoxLayout()
        ic = QLabel("🗑️")
        ic.setStyleSheet("font-size:20px;")
        h.addWidget(ic)
        t = QLabel("Fatura Yönetimi")
        t.setStyleSheet("font-size:14px;font-weight:700;color:#000000;letter-spacing:.5px;")
        h.addWidget(t)
        h.addStretch()
        root.addLayout(h)

        # Uyarı chip
        warn = QLabel(
            "⚠️  Silinen fatura kayıtları geri alınamaz. "
            "Silmeden önce doğru yıl ve türü seçtiğinizden emin olun."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet(
            "background:#fff3cd;color:#92400e;border-radius:6px;"
            "padding:9px 12px;font-size:12px;border:none;"
        )
        root.addWidget(warn)

        # Seçiciler
        sel_row = QHBoxLayout()
        sel_row.setSpacing(12)

        yil_lbl = QLabel("Yıl:")
        yil_lbl.setStyleSheet("font-size:13px;font-weight:600;color:#000000;")
        sel_row.addWidget(yil_lbl)

        self._yil_combo = QComboBox()
        self._yil_combo.setFixedHeight(34)
        self._yil_combo.setFixedWidth(110)
        self._yil_combo.addItem("Tüm Yıllar", None)
        for y in range(CURRENT_YEAR + 1, CURRENT_YEAR - 6, -1):
            self._yil_combo.addItem(str(y), y)
        idx = self._yil_combo.findData(CURRENT_YEAR)
        if idx >= 0:
            self._yil_combo.setCurrentIndex(idx)
        self._yil_combo.setStyleSheet(self._combo_style())
        self._yil_combo.currentIndexChanged.connect(self._on_yil_changed)
        sel_row.addWidget(self._yil_combo)

        ay_lbl = QLabel("Ay:")
        ay_lbl.setStyleSheet("font-size:13px;font-weight:600;color:#000000;")
        sel_row.addWidget(ay_lbl)

        self._ay_combo = QComboBox()
        self._ay_combo.setFixedHeight(34)
        self._ay_combo.setFixedWidth(130)
        AYLAR = [
            (None, "Tüm Aylar"),
            (1, "Ocak"), (2, "Şubat"), (3, "Mart"),
            (4, "Nisan"), (5, "Mayıs"), (6, "Haziran"),
            (7, "Temmuz"), (8, "Ağustos"), (9, "Eylül"),
            (10, "Ekim"), (11, "Kasım"), (12, "Aralık"),
        ]
        for val, txt in AYLAR:
            self._ay_combo.addItem(txt, val)
        self._ay_combo.setStyleSheet(self._combo_style())
        self._ay_combo.currentIndexChanged.connect(self._refresh_count)
        sel_row.addWidget(self._ay_combo)

        mod_lbl = QLabel("Fatura Türü:")
        mod_lbl.setStyleSheet("font-size:13px;font-weight:600;color:#000000;")
        sel_row.addWidget(mod_lbl)

        self._mod_combo = QComboBox()
        self._mod_combo.setFixedHeight(34)
        self._mod_combo.setFixedWidth(220)
        self._mod_combo.addItem("Tüm Türler", None)
        self._mod_combo.addItem("↑  Kesilen Faturalar (Gelir)", "gelir")
        self._mod_combo.addItem("↓  Gelen Faturalar (Gider)", "gider")
        self._mod_combo.setStyleSheet(self._combo_style())
        self._mod_combo.currentIndexChanged.connect(self._refresh_count)
        sel_row.addWidget(self._mod_combo)

        sel_row.addStretch()
        root.addLayout(sel_row)

        # Kayıt sayısı etiketi
        self._count_lbl = QLabel("")
        self._count_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._count_lbl.setStyleSheet(
            "font-size:12px;color:#374151;background:#f3f4f6;"
            "border-radius:6px;padding:6px 12px;border:none;"
        )
        root.addWidget(self._count_lbl)

        # Sil butonu
        btn_row = QHBoxLayout()
        self._sil_btn = QPushButton("🗑️  Seçili Faturaları Sil")
        self._sil_btn.setFixedHeight(38)
        self._sil_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sil_btn.setStyleSheet(
            "QPushButton{background:#dc2626;color:white;border:none;"
            "border-radius:9px;font-size:13px;font-weight:600;"
            "padding:0 18px;letter-spacing:.5px;}"
            "QPushButton:hover{background:#b91c1c;}"
            "QPushButton:disabled{background:#fca5a5;color:#fee2e2;}"
        )
        self._sil_btn.clicked.connect(self._on_sil)
        btn_row.addWidget(self._sil_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._refresh_count()

    def _combo_style(self) -> str:
        return (
            f"QComboBox{{background:#f8fafc;border:1.5px solid {COLORS.get('border','#e2e8f0')};"
            f"border-radius:8px;padding:0 10px;font-size:13px;color:#000000;}}"
            f"QComboBox::drop-down{{border:none;}}"
            f"QComboBox QAbstractItemView{{background:white;color:#1f2937;"
            f"selection-background-color:#dbeafe;selection-color:#1e40af;}}"
        )

    def _on_yil_changed(self):
        yil = self._yil_combo.currentData()
        self._ay_combo.setEnabled(yil is not None)
        if yil is None:
            self._ay_combo.setCurrentIndex(0)
        self._refresh_count()

    def _get_count(self) -> int:
        yil = self._yil_combo.currentData()
        ay  = self._ay_combo.currentData()
        mod = self._mod_combo.currentData()
        conn = get_connection()
        try:
            q = "SELECT COUNT(*) FROM faturalar WHERE userid=?"
            params = [self._userid]
            if yil:
                q += " AND substr(tarih,1,4)=?"
                params.append(str(yil))
                if ay:
                    q += " AND substr(tarih,6,2)=?"
                    params.append(f"{ay:02d}")
            if mod:
                q += " AND gelirGiderMod=?"
                params.append(mod)
            return conn.execute(q, params).fetchone()[0]
        finally:
            conn.close()

    def _refresh_count(self):
        count  = self._get_count()
        kriter = (
            f"{self._yil_combo.currentText()} / "
            f"{self._ay_combo.currentText()} / "
            f"{self._mod_combo.currentText()}"
        )
        if count == 0:
            self._count_lbl.setText(
                f"📊  <i>Seçilen kriterde ({kriter}) hiç fatura kaydı bulunamadı.</i>"
            )
        else:
            self._count_lbl.setText(
                f"📊  Seçilen kriterde ({kriter}): "
                f"<b style='color:#dc2626'>{count:,} fatura kaydı</b> bulunuyor."
            )
        self._sil_btn.setEnabled(count > 0)

    def _on_sil(self):
        count    = self._get_count()
        yil_txt  = self._yil_combo.currentText()
        ay_txt   = self._ay_combo.currentText()
        mod_txt  = self._mod_combo.currentText()
        kriter   = f"{yil_txt} / {ay_txt} / {mod_txt}"

        if count == 0:
            QMessageBox.information(self, "Bilgi", "Seçilen kriterde silinecek fatura yok.")
            return

        # ─ 1. Onay ─
        dlg = QMessageBox(self)
        dlg.setWindowTitle("⚠️  Fatura Silme Onayı")
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setText(
            f"<b>{yil_txt} / {mod_txt}</b> kriterindeki<br>"
            f"<b style='color:#dc2626;font-size:15px'>{count:,} fatura kaydı</b> silinecek.<br><br>"
            "<b>Bu işlem geri alınamaz!</b>"
        )
        dlg.setInformativeText("Devam etmek istiyor musunuz?")
        dlg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        dlg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        dlg.button(QMessageBox.StandardButton.Yes).setText("🗑️  Evet, Sil")
        dlg.button(QMessageBox.StandardButton.Cancel).setText("Vazgeç")

        if dlg.exec() != QMessageBox.StandardButton.Yes:
            return

        # ─ 2. İkinci onay ─
        second = QMessageBox(self)
        second.setWindowTitle("🔴  Son Onay — Geri Alınamaz")
        second.setIcon(QMessageBox.Icon.Critical)
        second.setText(
            f"<b style='color:#dc2626'>{count:,} fatura kaydı</b> kalıcı olarak silinecek.<br><br>"
            "Emin misiniz? Bu işlemi geri alamazsınız."
        )
        second.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        second.setDefaultButton(QMessageBox.StandardButton.Cancel)
        second.button(QMessageBox.StandardButton.Ok).setText("🔴  Kalıcı Olarak Sil")
        second.button(QMessageBox.StandardButton.Cancel).setText("Vazgeç")

        if second.exec() != QMessageBox.StandardButton.Ok:
            return

        # ─ 3. Sil ─
        yil_val = self._yil_combo.currentData()
        ay_val  = self._ay_combo.currentData()
        mod_val = self._mod_combo.currentData()
        conn = get_connection()
        try:
            q = "DELETE FROM faturalar WHERE userid=?"
            params = [self._userid]
            if yil_val:
                q += " AND substr(tarih,1,4)=?"
                params.append(str(yil_val))
                if ay_val:
                    q += " AND substr(tarih,6,2)=?"
                    params.append(f"{ay_val:02d}")
            if mod_val:
                q += " AND gelirGiderMod=?"
                params.append(mod_val)
            conn.execute(q, params)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            QMessageBox.critical(self, "Hata", f"Silme işlemi başarısız:\n{exc}")
            return
        finally:
            conn.close()

        QMessageBox.information(
            self, "✅  Tamamlandı",
            f"{count:,} fatura kaydı başarıyla silindi.\n"
            "Artık doğru klasörden yeniden aktarabilirsiniz."
        )
        self._refresh_count()



# ── MOY Workers ──────────────────────────────────────────────────────────────

class MoyTestWorker(QThread):
    """'Test' butonu — Moy MySQL sunucusuna bağlanıp kullanıcıyı doğrular."""
    result = pyqtSignal(dict)   # {success, data:[{adi,soyadim,kayitNo}]}

    def __init__(self, host: str, user: str, password: str, musteri_no: int):
        super().__init__()
        self._host       = host
        self._user       = user
        self._password   = password
        self._musteri_no = musteri_no

    def run(self):
        from services.moy_service import moy_test_connection
        r = moy_test_connection(self._host, self._user, self._password, self._musteri_no)
        self.result.emit(r)


class MoyKaydetWorker(QThread):
    """'Verileri Çek' butonu — seçilen yıla ait hareketleri aktarır."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)   # {success, message, eklenen}

    def __init__(self, musteri_no: int, yil: int):
        super().__init__()
        self._musteri_no = musteri_no
        self._yil        = yil

    def run(self):
        from services.moy_service import moy_kaydet_veriler
        r = moy_kaydet_veriler(
            self._musteri_no, self._yil,
            progress_cb=lambda msg: self.progress.emit(msg)
        )
        self.finished.emit(r)


# ── Moy Kartı ─────────────────────────────────────────────────────────────────

class MoyCard(QFrame):
    """
    PHP ayarlar.php → Eklentiler → Moy div'inin PyQt6 karşılığı.
    Alanlar  : URL (IP), Kullanıcı Adı, Şifre
    Butonlar : Test | Verileri Çek (Yıl seçerek)
    """
    # Veri başarıyla çekildiğinde dashboard’u haberdar eder
    data_changed = pyqtSignal()

    def __init__(self, userid: int, parent=None):
        super().__init__(parent)
        self._userid         = userid
        self._test_worker: MoyTestWorker   | None = None
        self._kaydet_worker: MoyKaydetWorker | None = None
        self._test_basarili  = False
        self.setStyleSheet(
            "QFrame{background:white;border:1.5px solid #d1fae5;"
            "border-radius:14px;}"
        )
        self._build()
        self._load()

    # ─ Stiller ────────────────────────────────────────────────────────

    def _inp(self) -> str:
        return (
            "QLineEdit{background:#f8fafc;border:1.5px solid #e2e8f0;"
            "border-radius:8px;padding:0 10px;font-size:13px;color:#1f2937;}"
            "QLineEdit:focus{border-color:#10b981;}"
            "QLineEdit[error='true']{border-color:#ef4444;}"
        )

    def _lbl(self) -> str:
        return "font-size:12px;font-weight:600;color:#374151;"

    def _btn(self, color: str) -> str:
        return (
            f"QPushButton{{background:{color};color:white;border:none;"
            f"border-radius:9px;font-size:13px;font-weight:600;padding:0 16px;}}"
            f"QPushButton:hover{{background:{color}cc;}}"
            f"QPushButton:disabled{{background:#cbd5e1;color:#94a3b8;}}"
        )

    # ─ UI inşası ─────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        # Başlık
        h = QHBoxLayout()
        ic = QLabel("🏢")
        ic.setStyleSheet("font-size:20px;")
        h.addWidget(ic)
        t = QLabel("Moy")
        t.setStyleSheet("font-size:14px;font-weight:700;color:#000;letter-spacing:.5px;")
        h.addWidget(t)
        self._aktif_chip = QLabel("✔  AKTİF")
        self._aktif_chip.setStyleSheet(
            "background:#d1fae5;color:#065f46;border-radius:5px;"
            "padding:2px 8px;font-size:11px;font-weight:700;border:none;"
        )
        self._aktif_chip.hide()
        h.addWidget(self._aktif_chip)
        h.addStretch()
        root.addLayout(h)

        # Bilgi
        info = QLabel("💡  Moy muhasebe programından yıllık vergi hareketlerini çekebilirsiniz.")
        info.setWordWrap(True)
        info.setStyleSheet(
            "background:#ecfdf5;color:#065f46;border-radius:6px;"
            "padding:9px 12px;font-size:12px;border:none;"
        )
        root.addWidget(info)

        # ─ URL (IP) satırı ─
        url_row = QHBoxLayout()
        url_row.setSpacing(10)

        proto_lbl = QLabel("Protokol")
        proto_lbl.setStyleSheet(self._lbl())
        self._proto_combo = QComboBox()
        self._proto_combo.addItems(["https://", "http://"])
        self._proto_combo.setFixedHeight(34)
        self._proto_combo.setFixedWidth(90)
        self._proto_combo.setStyleSheet(
            "QComboBox{background:#f8fafc;border:1.5px solid #e2e8f0;"
            "border-radius:8px;padding:0 6px;font-size:12px;color:#1f2937;}"
        )

        ip_lbl = QLabel("URL / IP Adresi")
        ip_lbl.setStyleSheet(self._lbl())
        self._ip_inp = QLineEdit()
        self._ip_inp.setFixedHeight(34)
        self._ip_inp.setPlaceholderText("123.121.121.122")
        self._ip_inp.setStyleSheet(self._inp())
        self._ip_inp.textChanged.connect(self._on_input_changed)

        url_col = QVBoxLayout()
        url_col.addWidget(ip_lbl)
        url_col.addWidget(self._ip_inp)

        proto_col = QVBoxLayout()
        proto_col.addWidget(proto_lbl)
        proto_col.addWidget(self._proto_combo)

        url_row.addLayout(proto_col)
        url_row.addLayout(url_col, 3)
        root.addLayout(url_row)

        # ─ Kullanıcı Adı + Şifre satırı ─
        cred_row = QHBoxLayout()
        cred_row.setSpacing(12)

        u_col = QVBoxLayout()
        u_lbl = QLabel("Kullanıcı Adı")
        u_lbl.setStyleSheet(self._lbl())
        self._user_inp = QLineEdit()
        self._user_inp.setFixedHeight(34)
        self._user_inp.setPlaceholderText("Moy Kullanıcı Adı")
        self._user_inp.setStyleSheet(self._inp())
        self._user_inp.textChanged.connect(self._on_input_changed)
        u_col.addWidget(u_lbl)
        u_col.addWidget(self._user_inp)
        cred_row.addLayout(u_col)

        p_col = QVBoxLayout()
        p_lbl = QLabel("Şifre")
        p_lbl.setStyleSheet(self._lbl())
        self._pass_inp = QLineEdit()
        self._pass_inp.setFixedHeight(34)
        self._pass_inp.setPlaceholderText("Moy Şifreniz")
        self._pass_inp.setStyleSheet(self._inp())
        self._pass_inp.textChanged.connect(self._on_input_changed)
        p_col.addWidget(p_lbl)
        p_col.addWidget(self._pass_inp)
        cred_row.addLayout(p_col)
        root.addLayout(cred_row)

        # ─ Butonlar (Test) ─
        btn_row1 = QHBoxLayout()
        btn_row1.setSpacing(10)
        self._test_btn = QPushButton("🔍  Test")
        self._test_btn.setFixedHeight(38)
        self._test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_btn.setStyleSheet(self._btn("#059669"))
        self._test_btn.clicked.connect(self._on_test)
        btn_row1.addWidget(self._test_btn)
        btn_row1.addStretch()
        root.addLayout(btn_row1)

        # ─ Sonuc satırı (PHP: .moysonucResponse) ─
        self._sonuc_lbl = QLabel("")
        self._sonuc_lbl.setWordWrap(True)
        self._sonuc_lbl.setStyleSheet("font-size:12px;color:#374151;")
        self._sonuc_lbl.hide()
        root.addWidget(self._sonuc_lbl)

        # ─ Ozel bilgi bolumu (PHP: .moyozelbilgi) ─ başlangıçta gizli ─
        self._ozel_frame = QFrame()
        self._ozel_frame.setStyleSheet(
            "QFrame{background:#f0fdf4;border:1px solid #bbf7d0;"
            "border-radius:10px;}"
        )
        ozel_layout = QVBoxLayout(self._ozel_frame)
        ozel_layout.setContentsMargins(14, 12, 14, 12)
        ozel_layout.setSpacing(10)

        self._ozel_info = QLabel(
            "Şimdi yıl seçip hangi aralıkta veri aktarılacağını seçin, "
            "daha sonra 'Verileri Çek' butonuna tıklayın."
        )
        self._ozel_info.setWordWrap(True)
        self._ozel_info.setStyleSheet("font-size:12px;color:#065f46;")
        ozel_layout.addWidget(self._ozel_info)

        self._ozel_veri = QLabel("")
        self._ozel_veri.setStyleSheet("font-size:13px;font-weight:600;color:#065f46;")
        self._ozel_veri.hide()
        ozel_layout.addWidget(self._ozel_veri)

        # Yıl seçimi (PHP: #yearSelect — son 5 yıl)
        yil_row = QHBoxLayout()
        yil_lbl = QLabel("📅  Yıl Seçin:")
        yil_lbl.setStyleSheet("font-size:12px;font-weight:600;color:#374151;")
        yil_row.addWidget(yil_lbl)
        self._yil_sec = QComboBox()
        self._yil_sec.setFixedHeight(32)
        self._yil_sec.setFixedWidth(100)
        self._yil_sec.setStyleSheet(
            "QComboBox{background:white;border:1.5px solid #d1fae5;"
            "border-radius:8px;padding:0 8px;font-size:13px;color:#1f2937;}"
        )
        import datetime as _dt
        cy = _dt.datetime.now().year
        for i in range(5):
            yr = cy - i
            self._yil_sec.addItem(str(yr), yr)
        yil_row.addWidget(self._yil_sec)
        yil_row.addStretch()
        ozel_layout.addLayout(yil_row)

        # Verileri Çek butonu — siyah arka plan
        self._cek_btn = QPushButton("⚡  Verileri Çek")
        self._cek_btn.setFixedHeight(38)
        self._cek_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cek_btn.setStyleSheet(
            "QPushButton{background:#1f2937;color:white;border:none;"
            "border-radius:9px;font-size:13px;font-weight:600;padding:0 16px;}"
            "QPushButton:hover{background:#111827;}"
            "QPushButton:disabled{background:#cbd5e1;color:#94a3b8;}"
        )
        self._cek_btn.setEnabled(False)   # Başlangıçta pasif (PHP .pasif sınıfı)
        self._cek_btn.clicked.connect(self._on_cek)
        ozel_layout.addWidget(self._cek_btn)

        # Detay alanı — çekilen verileri listeler
        self._detay_lbl = QLabel("")
        self._detay_lbl.setWordWrap(True)
        self._detay_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._detay_lbl.setStyleSheet(
            "font-size:11px;color:#1f2937;"
            "background:#f0fdf4;border-radius:6px;padding:6px;"
        )
        self._detay_lbl.hide()
        ozel_layout.addWidget(self._detay_lbl)

        self._ozel_frame.hide()   # PHP: .moyozelbilgi — test başarılı olunca görünür
        root.addWidget(self._ozel_frame)

    # ─ Veri yükleme ────────────────────────────────────────────────

    def _load(self):
        from services.moy_service import get_moy_bilgileri
        bilgi = get_moy_bilgileri(self._userid)
        if bilgi.get("success"):
            self._ip_inp.setText(bilgi.get("url") or "")
            self._user_inp.setText(bilgi.get("username") or "")
            self._pass_inp.setText(bilgi.get("sifre") or "")
            self._aktif_chip.show()

    def refresh(self):
        self._load()

    # ─ Input değişimi (PHP: .moyinput.on('input') — Kaydet butonunu pasif yap) ─

    def _on_input_changed(self):
        if self._test_basarili:
            self._test_basarili = False
            self._cek_btn.setEnabled(False)
            self._ozel_frame.hide()

    # ─ Test butonu (PHP: btnMoyTest click) ────────────────────────

    def _on_test(self):
        host  = self._ip_inp.text().strip()
        user  = self._user_inp.text().strip()
        passwd = self._pass_inp.text().strip()

        # Validasyon (PHP: validateMoy())
        import re as _re
        ip_rx = _re.compile(
            r"^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
            r"(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$"
        )
        if not host:
            self._show_sonuc("❌  IP boş olamaz", "#ef4444")
            return
        if not ip_rx.match(host):
            self._show_sonuc("❌  Bu IP hatalı", "#ef4444")
            return
        if not user:
            self._show_sonuc("❌  Kullanıcı adı boş olamaz", "#ef4444")
            return
        if not passwd:
            self._show_sonuc("❌  Şifre boş olamaz", "#ef4444")
            return

        self._set_busy(True, "🔍  Kontrol ediliyor...")

        self._test_worker = MoyTestWorker(host, user, passwd, self._userid)
        self._test_worker.result.connect(self._on_test_result)
        self._test_worker.start()

    def _on_test_result(self, r: dict):
        self._set_busy(False)
        if r.get("success"):
            data  = r.get("data", [])
            first = data[0] if data else {}
            ad    = first.get("adi", "") + " " + first.get("soyadim", "")
            self._show_sonuc("✅  Başarılı!", "#059669")
            self._ozel_veri.setText(f"👤  Moy bilgileriniz onaylandı: {ad.strip()}")
            self._ozel_veri.show()
            self._ozel_frame.show()
            self._cek_btn.setEnabled(True)   # PHP: addClass('aktif')
            self._aktif_chip.show()
            self._test_basarili = True
        else:
            msg = r.get("message", "Hata oluştu.")
            self._show_sonuc(f"❌  {msg}", "#ef4444")
            self._cek_btn.setEnabled(False)

    # ─ Verileri Çek (PHP: btnMoyKaydet click) ────────────────────

    def _on_cek(self):
        if not self._test_basarili:
            return
        yil = self._yil_sec.currentData()
        self._set_busy(True, f"⚡  {yil} yılı hareketleri alınıyor...")
        self._ozel_veri.hide()

        self._kaydet_worker = MoyKaydetWorker(self._userid, yil)
        self._kaydet_worker.progress.connect(
            lambda msg: self._show_sonuc(msg, "#0891b2")
        )
        self._kaydet_worker.finished.connect(self._on_cek_done)
        self._kaydet_worker.start()

    def _on_cek_done(self, r: dict):
        self._set_busy(False)
        if r.get("success"):
            eklenen  = r.get("eklenen", 0)
            detaylar = r.get("detaylar", [])

            # Özet metin
            msg = f"Başarıyla {eklenen} tane kayıt eklendi"
            self._ozel_veri.setText(f"✅  {msg}")
            self._ozel_veri.show()
            self._show_sonuc("", "")

            # Detay tablosu
            if detaylar:
                satirlar = "".join(
                    f"<tr>"
                    f"<td style='padding:2px 8px;color:#065f46;font-weight:600;'>{d['kod']}</td>"
                    f"<td style='padding:2px 8px;'>{d['tarih']}</td>"
                    f"<td style='padding:2px 8px;text-align:right;'>{d['tutar']:.2f}</td>"
                    f"</tr>"
                    for d in detaylar
                )
                html = (
                    f"<b>Çekilen Veriler ({len(detaylar)} satır):</b><br>"
                    f"<table width='100%' cellspacing='0'>"
                    f"<tr style='background:#d1fae5;'>"
                    f"<th style='text-align:left;padding:2px 8px;'>Hesap Kodu</th>"
                    f"<th style='text-align:left;padding:2px 8px;'>Tarih</th>"
                    f"<th style='text-align:right;padding:2px 8px;'>Tutar</th>"
                    f"</tr>"
                    f"{satirlar}"
                    f"</table>"
                )
                self._detay_lbl.setText(html)
                self._detay_lbl.show()
            else:
                self._detay_lbl.hide()

            # Dashboard’u otomatik yenile
            self.data_changed.emit()
        else:
            self._show_sonuc(f"❌  {r.get('message','Hata')}", "#ef4444")
            self._detay_lbl.hide()

    # ─ Yardımcılar ──────────────────────────────────────────────

    def _set_busy(self, busy: bool, msg: str = ""):
        self._test_btn.setEnabled(not busy)
        self._cek_btn.setEnabled(not busy and self._test_basarili)
        if busy and msg:
            self._show_sonuc(msg, "#6366f1")

    def _show_sonuc(self, text: str, color: str):
        if not text:
            self._sonuc_lbl.hide()
            return
        self._sonuc_lbl.setText(text)
        self._sonuc_lbl.setStyleSheet(f"font-size:12px;color:{color};padding:4px 0;")
        self._sonuc_lbl.show()


# ── Vergi Muhtasar Workers ───────────────────────────────────────────────────

class VergiMuhtasarYukleWorker(QThread):
    """CSV toplu yükleme arka plan iş parçacığı (PHP vergiMuhtasarTopluYukle.php)."""
    finished = pyqtSignal(dict)  # {'success', 'message', 'added', 'updated', 'skipped'}

    def __init__(self, userid: int, dosya_yolu: str):
        super().__init__()
        self._userid     = userid
        self._dosya_yolu = dosya_yolu

    def run(self):
        from services.vergi_muhtasar_service import toplu_yukle_csv
        r = toplu_yukle_csv(self._userid, self._dosya_yolu)
        self.finished.emit(r)


# ── Vergi Muhtasar Kartı ─────────────────────────────────────────────────────

class VergiMuhtasarCard(QFrame):
    """
    PHP ayarlar.php → Eklentiler → Vergi Muhtasar bölümünün PyQt6 karşılığı.

    Özellikler (PHP ile birebir):
    - CSV toplu yükle (vergiMuhtasarTopluYukle.php)
    - Dönem & açıklama filtresi
    - Kayıt listesi (DataTable karşılığı QTableWidget)
    - Inline düzenleme: gaytutar, vergkestutar (çift tık)
    - Silme (sil butonu)
    - Özet toplamlar barı: Gayri Safi Tutar | Vergi Kesinti | Fark
    - Şema CSV indir
    """

    # Sütun indeksleri (PHP DataTable sütun sırası)
    COL_HESAP  = 0
    COL_ACK    = 1
    COL_DONEM  = 2
    COL_GAY    = 3   # gaytutar — inline düzenlenebilir
    COL_VERG   = 4   # vergkestutar — inline düzenlenebilir
    COL_SIL    = 5

    def __init__(self, userid: int, parent=None):
        super().__init__(parent)
        self._userid       = userid
        self._yukle_worker: VergiMuhtasarYukleWorker | None = None
        self._all_data: list[dict] = []   # Cache: tüm kayıtlar
        self._row_ids:  list[int]  = []   # Tablo satır → DB id eşleşmesi

        self.setStyleSheet(
            "QFrame{background:white;border:1.5px solid #e0e7ff;"
            "border-radius:14px;}"
        )
        self._build()
        self.refresh()

    # ── Stil yardımcıları ─────────────────────────────────────────────────

    def _lbl_style(self) -> str:
        return "font-size:12px;font-weight:600;color:#374151;"

    def _btn_style(self, color: str) -> str:
        return (
            f"QPushButton{{background:{color};color:white;border:none;"
            f"border-radius:9px;font-size:13px;font-weight:600;"
            f"padding:0 14px;letter-spacing:.4px;}}"
            f"QPushButton:hover{{background:{color}cc;}}"
            f"QPushButton:disabled{{background:#cbd5e1;color:#94a3b8;}}"
        )

    def _combo_style(self) -> str:
        return (
            "QComboBox{background:#f8fafc;border:1.5px solid #e2e8f0;"
            "border-radius:8px;padding:0 10px;font-size:13px;color:#1f2937;}"
            "QComboBox::drop-down{border:none;}"
            "QComboBox QAbstractItemView{background:white;color:#1f2937;"
            "selection-background-color:#dbeafe;selection-color:#1e40af;}"
        )

    @staticmethod
    def _fmt_tutar(val) -> str:
        """float/None → '1.234,56 ₺' ya da '—' (PHP vmFormatTutar karşılığı)."""
        if val is None or val == "":
            return "—"
        try:
            f = float(str(val).replace(",", "."))
            return f"{f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " ₺"
        except (ValueError, TypeError):
            return "—"

    @staticmethod
    def _parse_float(val) -> float:
        """Herhangi formatı float'a çevirir (PHP vmParseFloat karşılığı)."""
        if val is None or val == "":
            return 0.0
        try:
            return float(str(val).replace(",", "."))
        except (ValueError, TypeError):
            return 0.0

    # ── UI İnşası ─────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        # Başlık satırı
        h = QHBoxLayout()
        ic = QLabel("🧾")
        ic.setStyleSheet("font-size:20px;")
        h.addWidget(ic)
        t = QLabel("Vergi Muhtasar")
        t.setStyleSheet("font-size:14px;font-weight:700;color:#000000;letter-spacing:.5px;")
        h.addWidget(t)
        h.addStretch()
        root.addLayout(h)

        # Bilgi chip (PHP açıklama paragrafı)
        info = QLabel(
            "💡  Muhtasar ve prim hizmetleri beyannamesi kapsamındaki stopaj vergisi "
            "verilerini CSV dosyası ile toplu olarak içeri aktarabilirsiniz. "
            "Hesap kodu, dönem ve vergi kesinti tutarları takip edilir."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "background:#ede9fe;color:#4c1d95;border-radius:6px;"
            "padding:9px 12px;font-size:12px;border:none;"
        )
        root.addWidget(info)

        # ── Butonlar (üst sıra) ──
        top_btn_row = QHBoxLayout()
        top_btn_row.setSpacing(8)

        # Verileri Yükle (PHP: vergiMuhtasarTopluBtn)
        self._yukle_btn = QPushButton("📤  Verileri Yükle")
        self._yukle_btn.setFixedHeight(36)
        self._yukle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._yukle_btn.setStyleSheet(self._btn_style("#7c3aed"))
        self._yukle_btn.clicked.connect(self._on_yukle)
        top_btn_row.addWidget(self._yukle_btn)

        # Şema İndir (PHP: vmSemaIndir)
        self._sema_btn = QPushButton("⬇  Şema İndir")
        self._sema_btn.setFixedHeight(36)
        self._sema_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sema_btn.setStyleSheet(self._btn_style("#64748b"))
        self._sema_btn.setToolTip(
            "💡 Şema dosyası — hızlı bir şekilde uygun formda veri girmeniz için"
        )
        self._sema_btn.clicked.connect(self._on_sema_indir)
        top_btn_row.addWidget(self._sema_btn)

        top_btn_row.addStretch()
        root.addLayout(top_btn_row)

        # ── Özet Toplamlar Barı (PHP: #vmTotalsBar) ──
        totals_frame = QFrame()
        totals_frame.setStyleSheet(
            "QFrame{background:#f8f9fc;border:1px solid #e8eaf0;"
            "border-radius:8px;}"
        )
        totals_layout = QHBoxLayout(totals_frame)
        totals_layout.setContentsMargins(14, 10, 14, 10)
        totals_layout.setSpacing(20)

        def _make_total_item(label_txt: str, value_id: str, color: str) -> QLabel:
            col = QVBoxLayout()
            lbl = QLabel(label_txt)
            lbl.setStyleSheet(
                "font-size:11px;color:#888;font-weight:600;letter-spacing:0.5px;"
                "border:none;background:transparent;"
            )
            val = QLabel("0,00 ₺")
            val.setStyleSheet(
                f"font-size:18px;font-weight:700;color:{color};"
                "border:none;background:transparent;"
            )
            val.setObjectName(value_id)
            col.addWidget(lbl)
            col.addWidget(val)
            wrapper = QWidget()
            wrapper.setLayout(col)
            return wrapper, val

        gay_w,  self._lbl_gay  = _make_total_item("GAYRİ SAFİ TUTAR",   "vmToplamGay",  "#2d5be3")
        verg_w, self._lbl_verg = _make_total_item("VERGİ KESİNTİ TUTARI","vmToplamVerg", "#e35d2d")
        fark_w, self._lbl_fark = _make_total_item("FARK",                  "vmToplamFark", "#22a06b")
        totals_layout.addWidget(gay_w,  1)
        totals_layout.addWidget(verg_w, 1)
        totals_layout.addWidget(fark_w, 1)
        root.addWidget(totals_frame)

        # ── Filtre Satırı (PHP: #vmDonemFilter + #vmSearchInput) ──
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self._donem_combo = QComboBox()
        self._donem_combo.setFixedHeight(32)
        self._donem_combo.setMinimumWidth(130)
        self._donem_combo.addItem("Tüm Dönemler", "")
        self._donem_combo.setStyleSheet(self._combo_style())
        self._donem_combo.currentIndexChanged.connect(self._on_donem_changed)
        filter_row.addWidget(self._donem_combo)

        self._ack_combo = QComboBox()
        self._ack_combo.setFixedHeight(32)
        self._ack_combo.setMinimumWidth(130)
        self._ack_combo.addItem("Tüm Açıklamalar", "")
        self._ack_combo.setStyleSheet(self._combo_style())
        self._ack_combo.currentIndexChanged.connect(self._on_ack_changed)
        filter_row.addWidget(self._ack_combo)

        filter_row.addStretch()
        root.addLayout(filter_row)

        # ── DataTable (QTableWidget) ──
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "Hesap Kodu", "Açıklama", "Dönem",
            "Gayri Safi Tutar", "Vergi Kesinti Tutarı", "İşlem"
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(5, 60)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setMinimumHeight(200)
        self._table.setStyleSheet(
            "QTableWidget{background:white;gridline-color:#f1f5f9;border:1px solid #e2e8f0;"
            "border-radius:8px;font-size:13px;color:#1f2937;}"
            "QTableWidget::item{padding:6px 10px;}"
            "QTableWidget::item:selected{background:#dbeafe;color:#1e40af;}"
            "QTableWidget::item.editing{background:#fef9c3;border:2px solid #f59e0b;}"
            "QHeaderView::section{background:#f8fafc;border:none;border-bottom:1px solid #e2e8f0;"
            "font-size:12px;font-weight:600;color:#374151;padding:8px 10px;}"
            "QTableWidget QScrollBar:horizontal{height:8px;}"
            "QTableWidget QScrollBar:vertical{width:8px;}"
        )
        # Çift tık ile inline düzenleme (PHP: dblclick 'td')
        self._table.cellDoubleClicked.connect(self._on_cell_double_click)
        root.addWidget(self._table)

        # ── Durum etiketi ──
        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet("font-size:12px;color:#374151;")
        self._status_lbl.hide()
        root.addWidget(self._status_lbl)

    # ── Veri Yükleme & Tablo Güncelleme ──────────────────────────────────

    def refresh(self):
        """Tablo + filtreler + toplamları yeniler."""
        from services.vergi_muhtasar_service import get_vergi_muhtasar
        donem  = self._donem_combo.currentData() or ""
        result = get_vergi_muhtasar(self._userid, donem)
        if not result["success"]:
            self._show_status(f"❌  {result.get('message', 'Hata')}", "#dc2626")
            return

        self._all_data = result["data"]
        self._fill_donem_combo(result["donemler"])
        self._fill_ack_combo(self._all_data)
        self._apply_filters()

    def _fill_donem_combo(self, donemler: list[str]):
        """PHP vmDonemFilter doldurma karşılığı."""
        current = self._donem_combo.currentData()
        self._donem_combo.blockSignals(True)
        self._donem_combo.clear()
        self._donem_combo.addItem("Tüm Dönemler", "")
        for d in donemler:
            self._donem_combo.addItem(d, d)
        # Eski seçimi koru
        idx = self._donem_combo.findData(current)
        if idx >= 0:
            self._donem_combo.setCurrentIndex(idx)
        self._donem_combo.blockSignals(False)

    def _fill_ack_combo(self, data: list[dict]):
        """PHP vmSearchInput doldurma karşılığı."""
        current = self._ack_combo.currentData()
        self._ack_combo.blockSignals(True)
        self._ack_combo.clear()
        self._ack_combo.addItem("Tüm Açıklamalar", "")
        seen = set()
        for row in data:
            ack = row.get("ack") or ""
            if ack and ack not in seen:
                seen.add(ack)
                self._ack_combo.addItem(ack, ack)
        idx = self._ack_combo.findData(current)
        if idx >= 0:
            self._ack_combo.setCurrentIndex(idx)
        self._ack_combo.blockSignals(False)

    def _apply_filters(self):
        """Seçili dönem + açıklamaya göre tabloyu filtreler ve doldurur."""
        donem_filter = self._donem_combo.currentData() or ""
        ack_filter   = self._ack_combo.currentData() or ""

        filtered = [
            r for r in self._all_data
            if (not donem_filter or r.get("donem", "") == donem_filter)
            and (not ack_filter  or (r.get("ack") or "") == ack_filter)
        ]
        self._fill_table(filtered)
        self._update_totals(filtered)

    def _fill_table(self, data: list[dict]):
        """QTableWidget'i veriyle doldurur."""
        self._row_ids = []
        self._table.setRowCount(0)
        self._table.setRowCount(len(data))

        for row_idx, row in enumerate(data):
            self._row_ids.append(row.get("id", -1))

            def _item(text: str, align=Qt.AlignmentFlag.AlignLeft) -> QTableWidgetItem:
                it = QTableWidgetItem(str(text) if text is not None else "")
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                return it

            self._table.setItem(row_idx, self.COL_HESAP, _item(row.get("hesapkodu", "")))
            self._table.setItem(row_idx, self.COL_ACK,   _item(row.get("ack", "")))
            self._table.setItem(row_idx, self.COL_DONEM, _item(row.get("donem", "")))
            self._table.setItem(
                row_idx, self.COL_GAY,
                _item(self._fmt_tutar(row.get("gaytutar")),
                      Qt.AlignmentFlag.AlignRight)
            )
            self._table.setItem(
                row_idx, self.COL_VERG,
                _item(self._fmt_tutar(row.get("vergkestutar")),
                      Qt.AlignmentFlag.AlignRight)
            )

            # Sil butonu
            sil_btn = QPushButton("🗑")
            sil_btn.setFixedSize(36, 28)
            sil_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            sil_btn.setStyleSheet(
                "QPushButton{background:#fee2e2;color:#dc2626;border:none;"
                "border-radius:6px;font-size:14px;}"
                "QPushButton:hover{background:#fecaca;}"
            )
            sil_btn.clicked.connect(lambda _, r=row_idx: self._on_sil(r))
            self._table.setCellWidget(row_idx, self.COL_SIL, sil_btn)

    def _update_totals(self, data: list[dict]):
        """Özet toplamları hesaplar ve günceller (PHP vmUpdateTotals karşılığı)."""
        gay  = sum(self._parse_float(r.get("gaytutar"))  for r in data)
        verg = sum(self._parse_float(r.get("vergkestutar")) for r in data)
        fark = gay - verg

        self._lbl_gay.setText(self._fmt_tutar(gay))
        self._lbl_verg.setText(self._fmt_tutar(verg))
        self._lbl_fark.setText(self._fmt_tutar(fark))

    # ── Dönem & Açıklama Filtresi ─────────────────────────────────────────

    def _on_donem_changed(self):
        """PHP: vmDonemFilter change → vmTable.ajax.url(…).load()"""
        self.refresh()

    def _on_ack_changed(self):
        """PHP: vmSearchInput change → vmTable.column(1).search(…).draw()"""
        self._apply_filters()

    # ── CSV Toplu Yükleme (PHP: vergiMuhtasarTopluBtn click) ─────────────

    def _on_yukle(self):
        dosya, _ = QFileDialog.getOpenFileName(
            self, "CSV Dosyası Seç", "", "CSV Dosyaları (*.csv)"
        )
        if not dosya:
            return

        self._yukle_btn.setEnabled(False)
        self._show_status("📤  CSV yükleniyor...", "#7c3aed")

        self._yukle_worker = VergiMuhtasarYukleWorker(self._userid, dosya)
        self._yukle_worker.finished.connect(self._on_yukle_done)
        self._yukle_worker.start()

    def _on_yukle_done(self, r: dict):
        self._yukle_btn.setEnabled(True)
        if r["success"]:
            msg = (
                f"✅  {r['added']} yeni kayıt eklendi, "
                f"{r['updated']} kayıt güncellendi, "
                f"{r['skipped']} satır atlandı."
            )
            self._show_status(msg, "#059669")
            self.refresh()
        else:
            self._show_status(f"❌  {r['message']}", "#dc2626")

    # ── Inline Düzenleme (PHP: dblclick 'td' — sadece col 3 & 4) ─────────

    def _on_cell_double_click(self, row: int, col: int):
        """Gayri Safi Tutar (col 3) ve Vergi Kesinti (col 4) düzenlenebilir."""
        if col not in (self.COL_GAY, self.COL_VERG):
            return
        if row >= len(self._row_ids):
            return

        kayit_id = self._row_ids[row]
        kolon    = "gaytutar" if col == self.COL_GAY else "vergkestutar"
        item     = self._table.item(row, col)
        if not item:
            return

        eski_display = item.text()
        # Türkçe tutar stringini ham float'a çevir
        eski_ham = eski_display.replace(" ₺", "").replace(".", "").replace(",", ".")
        try:
            eski_float = float(eski_ham)
        except ValueError:
            eski_float = 0.0

        # QLineEdit ile inline düzenleme (QDialog kullan)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Düzenle — {kolon}")
        dlg.setFixedWidth(280)
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setSpacing(10)
        dlg_layout.setContentsMargins(16, 16, 16, 16)

        dlg_layout.addWidget(QLabel(f"<b>{kolon}</b> değerini düzenleyin:"))
        edit = QLineEdit()
        edit.setText(str(eski_float).replace(".", ","))
        edit.setFixedHeight(34)
        edit.setStyleSheet(
            "QLineEdit{background:#f8fafc;border:1.5px solid #e2e8f0;"
            "border-radius:8px;padding:0 10px;font-size:13px;}"
            "QLineEdit:focus{border-color:#7c3aed;}"
        )
        edit.selectAll()
        dlg_layout.addWidget(edit)

        bilgi = QLabel("⚠️  Eski: " + eski_display)
        bilgi.setStyleSheet("font-size:11px;color:#6b7280;")
        dlg_layout.addWidget(bilgi)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Kaydet")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Vazgeç")
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        dlg_layout.addWidget(bb)

        edit.setFocus()
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        raw = edit.text().strip()
        normalized = raw.replace(".", "").replace(",", ".")
        try:
            yeni_float = float(normalized)
        except ValueError:
            QMessageBox.warning(self, "Geçersiz Değer", "Lütfen geçerli bir sayı girin.")
            return

        if yeni_float == eski_float:
            return  # Değişim yok

        from services.vergi_muhtasar_service import update_vergi_muhtasar_alan
        r = update_vergi_muhtasar_alan(self._userid, kayit_id, kolon, yeni_float)
        if r["success"]:
            item.setText(self._fmt_tutar(yeni_float))
            # Önbellekteki veriyi güncelle
            for d in self._all_data:
                if d.get("id") == kayit_id:
                    d[kolon] = yeni_float
                    break
            # Toplamları yenile
            visible = self._visible_data()
            self._update_totals(visible)
            self._show_status("✅  Güncellendi.", "#059669")
        else:
            self._show_status(f"❌  {r['message']}", "#dc2626")

    def _visible_data(self) -> list[dict]:
        """Şu an tabloda görünen satırlara karşılık gelen veri listesi."""
        donem_filter = self._donem_combo.currentData() or ""
        ack_filter   = self._ack_combo.currentData() or ""
        return [
            r for r in self._all_data
            if (not donem_filter or r.get("donem", "") == donem_filter)
            and (not ack_filter  or (r.get("ack") or "") == ack_filter)
        ]

    # ── Silme (PHP: .sil click → showAlert2 → pendingSilinecek) ─────────

    def _on_sil(self, row: int):
        if row >= len(self._row_ids):
            return
        kayit_id = self._row_ids[row]
        hesap    = (self._table.item(row, self.COL_HESAP) or QTableWidgetItem("")).text()
        donem    = (self._table.item(row, self.COL_DONEM) or QTableWidgetItem("")).text()

        dlg = QMessageBox(self)
        dlg.setWindowTitle("Kaydı Sil")
        dlg.setIcon(QMessageBox.Icon.Warning)
        dlg.setText(
            f"<b>{hesap}</b> — {donem} kaydını silmek istiyor musunuz?<br><br>"
            "Bu işlem geri alınamaz."
        )
        dlg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        dlg.button(QMessageBox.StandardButton.Yes).setText("🗑  Sil")
        dlg.button(QMessageBox.StandardButton.Cancel).setText("Vazgeç")
        if dlg.exec() != QMessageBox.StandardButton.Yes:
            return

        from services.vergi_muhtasar_service import delete_vergi_muhtasar
        r = delete_vergi_muhtasar(self._userid, kayit_id)
        if r["success"]:
            self._show_status("✅  Kayıt silindi.", "#059669")
            self.refresh()
        else:
            self._show_status(f"❌  {r['message']}", "#dc2626")

    # ── Şema İndir (PHP: #vmSemaIndir click) ─────────────────────────────

    def _on_sema_indir(self):
        from services.vergi_muhtasar_service import SEMA_CSV_ICERIK, SEMA_CSV_DOSYA_ADI
        kayit_yolu, _ = QFileDialog.getSaveFileName(
            self, "Şema CSV Kaydet", SEMA_CSV_DOSYA_ADI, "CSV Dosyaları (*.csv)"
        )
        if not kayit_yolu:
            return
        try:
            with open(kayit_yolu, "w", encoding="utf-8-sig") as f:
                f.write(SEMA_CSV_ICERIK)
            self._show_status(f"✅  Şema kaydedildi: {kayit_yolu}", "#059669")
        except Exception as exc:
            self._show_status(f"❌  Kayıt hatası: {exc}", "#dc2626")

    # ── Durum Etiketi ─────────────────────────────────────────────────────

    def _show_status(self, text: str, color: str = "#374151"):
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(f"font-size:12px;color:{color};padding:4px 0;")
        self._status_lbl.show()


# ── Şirket Profili Kartı ──────────────────────────────────────────────────────

class SirketProfilCard(QFrame):
    """Hesap & Güvenlik sekmesindeki şirket profili formu."""

    def __init__(self, userid: int, parent=None):
        super().__init__(parent)
        self._userid = userid
        self.setStyleSheet(
            "QFrame{background:white;border:1.5px solid #e2e8f0;"
            "border-radius:14px;}"
        )
        self._fields = {}
        self._build()
        self._load()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        from PyQt6.QtWidgets import QLineEdit, QGridLayout

        # Baslik
        h = QHBoxLayout()
        ic = QLabel("🏢")
        ic.setStyleSheet("font-size:20px;")
        h.addWidget(ic)
        t = QLabel("Şirket Profili")
        t.setStyleSheet("font-size:14px;font-weight:700;color:#000000;letter-spacing:.5px;")
        h.addWidget(t)
        h.addStretch()
        root.addLayout(h)

        info = QLabel(
            "💡  Bu bilgiler fatura XML'indeki VKN ile karşılaştırılarak "
            "Gelen / Kesilen ayrımı otomatik yapılır."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "background:#e6edfa;color:#000000;border-radius:6px;"
            "padding:9px 12px;font-size:12px;border:none;"
        )
        root.addWidget(info)

        grid = QGridLayout()
        grid.setSpacing(10)

        FIELDS = [
            ("unvan",        "Şirket / Ünvan *",     0, 0, 1, 2),
            ("vergino",      "Vergi No (VKN) *",      1, 0, 1, 1),
            ("tckn",         "TCKN (Şahıs ise)",      1, 1, 1, 1),
            ("vergidairesi", "Vergi Dairesi",          2, 0, 1, 1),
            ("adres",        "Adres",                  3, 0, 1, 2),
            ("il",           "İl",                     4, 0, 1, 1),
            ("ilce",         "İlçe",                   4, 1, 1, 1),
        ]

        INPUT_STYLE = (
            "QLineEdit{background:#f8fafc;border:1.5px solid #e2e8f0;"
            "border-radius:8px;padding:0 10px;font-size:13px;color:#1f2937;}"
            "QLineEdit:focus{border-color:#2563eb;}"
        )
        LBL_STYLE = "font-size:12px;font-weight:600;color:#374151;"

        for key, lbl_txt, row, col, rspan, cspan in FIELDS:
            lbl = QLabel(lbl_txt)
            lbl.setStyleSheet(LBL_STYLE)
            inp = QLineEdit()
            inp.setFixedHeight(34)
            inp.setStyleSheet(INPUT_STYLE)
            inp.setPlaceholderText(lbl_txt)
            self._fields[key] = inp
            grid.addWidget(lbl, row * 2,     col, 1, cspan)
            grid.addWidget(inp, row * 2 + 1, col, 1, cspan)

        root.addLayout(grid)

        # Kaydet butonu
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._save_btn = QPushButton("💾  Profili Kaydet")
        self._save_btn.setFixedHeight(38)
        self._save_btn.setMinimumWidth(160)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setStyleSheet(
            "QPushButton{background:#2563eb;color:white;border:none;"
            "border-radius:9px;font-size:13px;font-weight:600;padding:0 18px;}"
            "QPushButton:hover{background:#1d4ed8;}"
        )
        self._save_btn.clicked.connect(self._on_kaydet)
        btn_row.addWidget(self._save_btn)
        root.addLayout(btn_row)

        self._result_lbl = QLabel("")
        self._result_lbl.setStyleSheet("font-size:12px;color:#059669;")
        root.addWidget(self._result_lbl)

    def _load(self):
        from services.sirket_service import get_sirket_profili
        p = get_sirket_profili(self._userid)
        for key, inp in self._fields.items():
            inp.setText(p.get(key, ""))

    def _on_kaydet(self):
        from services.sirket_service import save_sirket_profili
        unvan = self._fields["unvan"].text().strip()
        vergino = self._fields["vergino"].text().strip()
        if not unvan:
            self._result_lbl.setText("⚠️  Ünvan alanı zorunludur.")
            self._result_lbl.setStyleSheet("font-size:12px;color:#dc2626;")
            return
        if not vergino and not self._fields["tckn"].text().strip():
            self._result_lbl.setText("⚠️  VKN veya TCKN alanlarından biri zorunludur.")
            self._result_lbl.setStyleSheet("font-size:12px;color:#dc2626;")
            return

        ok = save_sirket_profili(
            userid=self._userid,
            unvan=unvan,
            vergino=vergino,
            tckn=self._fields["tckn"].text().strip(),
            vergidairesi=self._fields["vergidairesi"].text().strip(),
            adres=self._fields["adres"].text().strip(),
            il=self._fields["il"].text().strip(),
            ilce=self._fields["ilce"].text().strip(),
        )
        if ok:
            self._result_lbl.setText("✅  Şirket profili başarıyla kaydedildi.")
            self._result_lbl.setStyleSheet("font-size:12px;color:#059669;")
        else:
            self._result_lbl.setText("❌  Kayıt sırasında hata oluştu.")
            self._result_lbl.setStyleSheet("font-size:12px;color:#dc2626;")


# ── Kredi Kartı Worker ────────────────────────────────────────────────────────

class KrediKartYukleWorker(QThread):
    """
    Dosya yükleme arka plan iş parçacığı.
    PHP: bankaiceribtn → hiddenFileInput → AJAX (krediKartVeriAktar*.php)
    """
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)

    def __init__(self, userid, dosya_yolları, hesap_kodu,
                 banka_adi, dosya_turu, banka_adi_listesi):
        super().__init__()
        self._userid           = userid
        self._dosya_yolları    = dosya_yolları
        self._hesap_kodu       = hesap_kodu
        self._banka_adi        = banka_adi
        self._dosya_turu       = dosya_turu
        self._banka_listesi    = banka_adi_listesi

    def run(self):
        from services.kredi_kart_service import yukle_dosyalar
        r = yukle_dosyalar(
            userid          = self._userid,
            dosya_yolları   = self._dosya_yolları,
            hesap_kodu      = self._hesap_kodu,
            banka_adi       = self._banka_adi,
            dosya_turu      = self._dosya_turu,
            banka_adi_liste = self._banka_listesi,
        )
        self.finished.emit(r)


# ── Kredi Kartı Kartı ─────────────────────────────────────────────────────────

class KrediKartCard(QFrame):
    """
    PHP ayarlar.php → Eklentiler → Kredi Kartı div'inin PyQt6 karşılığı.

    Özellikler (PHP JS ayarlar.js + PHP backend ile birebir):
    - Kart seçimi (key_kartlari tablosundan — PHP: guncelleKartlar() + nocache.php)
    - Dosya türü seçimi: CSV | PDF | XLSX
    - Çoklu dosya seçimi (birden fazla PDF)
    - Banka uyum kontrolü (YapıKredi / İş Bankası)
    - İçeri Aktar butonu → KrediKartYukleWorker
    - Yeni kart tanımlama formu (key_kartlari INSERT)
    - Sonuç gösterimi (durum etiketi)
    """

    def __init__(self, userid: int, parent=None):
        super().__init__(parent)
        self._userid       = userid
        self._worker: KrediKartYukleWorker | None = None
        self._kart_listesi: list[dict] = []

        self.setStyleSheet(
            "QFrame{background:white;border:1.5px solid #dbeafe;"
            "border-radius:14px;}"
        )
        self._build()
        self.refresh()

    def _btn_style(self, color: str) -> str:
        return (
            f"QPushButton{{background:{color};color:white;border:none;"
            f"border-radius:9px;font-size:13px;font-weight:600;"
            f"padding:0 14px;letter-spacing:.4px;}}"
            f"QPushButton:hover{{background:{color}cc;}}"
            f"QPushButton:disabled{{background:#cbd5e1;color:#94a3b8;}}"
        )

    def _combo_style(self) -> str:
        return (
            "QComboBox{background:#f8fafc;border:1.5px solid #e2e8f0;"
            "border-radius:8px;padding:0 10px;font-size:13px;color:#1f2937;height:32px;}"
            "QComboBox::drop-down{border:none;}"
            "QComboBox QAbstractItemView{background:white;color:#1f2937;"
            "selection-background-color:#dbeafe;selection-color:#1e40af;}"
        )

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        # Başlık
        h = QHBoxLayout()
        ic = QLabel("💳")
        ic.setStyleSheet("font-size:20px;")
        h.addWidget(ic)
        t = QLabel("Kredi Kartı")
        t.setStyleSheet("font-size:14px;font-weight:700;color:#000000;letter-spacing:.5px;")
        h.addWidget(t)
        h.addStretch()
        root.addLayout(h)

        # Bilgi chip
        info = QLabel(
            "💡  Kayıtlı kredi kartınızı seçip CSV (YapıKredi), "
            "PDF (İş Bankası / YapıKredi) veya XLSX formatındaki "
            "banka ekstrenizi içeri aktarabilirsiniz."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            "background:#eff6ff;color:#1e3a8a;border-radius:6px;"
            "padding:9px 12px;font-size:12px;border:none;"
        )
        root.addWidget(info)

        # ── Kart Seçimi (PHP: #kartSelect) ──
        kart_row = QHBoxLayout()
        kart_row.setSpacing(10)
        kart_lbl = QLabel("Kredi Kartı Seçin:")
        kart_lbl.setStyleSheet("font-size:12px;font-weight:600;color:#374151;")
        kart_row.addWidget(kart_lbl)
        self._kart_combo = QComboBox()
        self._kart_combo.setMinimumWidth(220)
        self._kart_combo.addItem("Bir kart tanımı seçin", "")
        self._kart_combo.setStyleSheet(self._combo_style())
        self._kart_combo.currentIndexChanged.connect(self._on_kart_changed)
        kart_row.addWidget(self._kart_combo, 1)
        kart_row.addStretch()
        root.addLayout(kart_row)

        # ── Yeni Kart Ekleme Formu ──
        self._ekle_frame = QFrame()
        self._ekle_frame.setStyleSheet(
            "QFrame{background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;}"
        )
        ekle_layout = QVBoxLayout(self._ekle_frame)
        ekle_layout.setContentsMargins(14, 12, 14, 12)
        ekle_layout.setSpacing(10)
        ekle_title = QLabel("➕  Yeni Kart Ekle")
        ekle_title.setStyleSheet("font-size:13px;font-weight:700;color:#1e40af;")
        ekle_layout.addWidget(ekle_title)

        ekle_grid = QHBoxLayout()
        ekle_grid.setSpacing(10)

        def _inp_col(label_txt, placeholder=""):
            col = QVBoxLayout()
            lbl = QLabel(label_txt)
            lbl.setStyleSheet("font-size:11px;font-weight:600;color:#374151;")
            inp = QLineEdit()
            inp.setFixedHeight(32)
            inp.setPlaceholderText(placeholder)
            inp.setStyleSheet(
                "QLineEdit{background:white;border:1.5px solid #bfdbfe;"
                "border-radius:8px;padding:0 10px;font-size:13px;color:#1f2937;}"
                "QLineEdit:focus{border-color:#2563eb;}"
            )
            col.addWidget(lbl)
            col.addWidget(inp)
            return col, inp

        banka_col,  self._yeni_banka_inp  = _inp_col("Banka Adı *", "Yapı Kredi")
        etiket_col, self._yeni_etiket_inp = _inp_col("Kart Etiketi", "YapıKredi-5432")
        hesap_col,  self._yeni_hesap_inp  = _inp_col("Hesap Kodu", "100.01")
        ekle_grid.addLayout(banka_col, 2)
        ekle_grid.addLayout(etiket_col, 2)
        ekle_grid.addLayout(hesap_col, 1)
        ekle_layout.addLayout(ekle_grid)

        ekle_btn_row = QHBoxLayout()
        self._ekle_btn = QPushButton("➕  Kartı Kaydet")
        self._ekle_btn.setFixedHeight(34)
        self._ekle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ekle_btn.setStyleSheet(self._btn_style("#2563eb"))
        self._ekle_btn.clicked.connect(self._on_kart_ekle)
        ekle_btn_row.addWidget(self._ekle_btn)
        ekle_btn_row.addStretch()
        ekle_layout.addLayout(ekle_btn_row)
        root.addWidget(self._ekle_frame)

        # ── İçeri Aktar (PHP: #bankkapan) ──
        self._aktar_frame = QFrame()
        self._aktar_frame.setStyleSheet("QFrame{background:transparent;border:none;}")
        aktar_layout = QVBoxLayout(self._aktar_frame)
        aktar_layout.setContentsMargins(0, 0, 0, 0)
        aktar_layout.setSpacing(10)

        dosya_row = QHBoxLayout()
        dosya_row.setSpacing(10)
        dosya_lbl2 = QLabel("Dosya Türü:")
        dosya_lbl2.setStyleSheet("font-size:12px;font-weight:600;color:#374151;")
        dosya_row.addWidget(dosya_lbl2)

        self._dosya_combo = QComboBox()
        self._dosya_combo.setFixedWidth(120)
        self._dosya_combo.addItems(["PDF", "XLSX", "CSV"])
        self._dosya_combo.setStyleSheet(self._combo_style())
        self._dosya_combo.currentIndexChanged.connect(self._on_dosya_turu_changed)
        dosya_row.addWidget(self._dosya_combo)

        self._aktar_btn = QPushButton("↤  İçeri Aktar")
        self._aktar_btn.setFixedHeight(36)
        self._aktar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._aktar_btn.setStyleSheet(self._btn_style("#2563eb"))
        self._aktar_btn.clicked.connect(self._on_aktar)
        dosya_row.addWidget(self._aktar_btn)
        dosya_row.addStretch()
        aktar_layout.addLayout(dosya_row)

        self._dosya_lbl = QLabel("")
        self._dosya_lbl.setStyleSheet("font-size:11px;color:#6b7280;")
        self._dosya_lbl.setWordWrap(True)
        self._dosya_lbl.hide()
        aktar_layout.addWidget(self._dosya_lbl)

        self._durum_lbl = QLabel("")
        self._durum_lbl.setWordWrap(True)
        self._durum_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._durum_lbl.setStyleSheet("font-size:12px;color:#374151;")
        self._durum_lbl.hide()
        aktar_layout.addWidget(self._durum_lbl)

        root.addWidget(self._aktar_frame)
        self._aktar_frame.setEnabled(False)

    # ── Kart Listesi ─────────────────────────────────────────────────────

    def refresh(self):
        from services.kredi_kart_service import get_kart_listesi
        r = get_kart_listesi(self._userid)
        self._kart_listesi = r.get("data", [])
        self._fill_kart_combo()

    def _fill_kart_combo(self):
        self._kart_combo.blockSignals(True)
        self._kart_combo.clear()
        self._kart_combo.addItem("Bir kart tanımı seçin", "")
        eklenen: set = set()
        for item in self._kart_listesi:
            label     = item.get("banka", "").split("-")[0].strip()
            banka_adi = (item.get("bankaAdi") or label).strip()
            key       = banka_adi.lower()
            if key not in eklenen:
                eklenen.add(key)
                self._kart_combo.addItem(label, item.get("hesapKodu", ""))
                self._kart_combo.setItemData(
                    self._kart_combo.count() - 1,
                    banka_adi, Qt.ItemDataRole.UserRole + 1
                )
        self._kart_combo.blockSignals(False)

    def _get_secili_banka_adi(self) -> str:
        idx = self._kart_combo.currentIndex()
        return "" if idx <= 0 else (
            self._kart_combo.itemData(idx, Qt.ItemDataRole.UserRole + 1) or ""
        )

    def _on_kart_changed(self):
        kart = self._kart_combo.currentData()
        self._aktar_frame.setEnabled(bool(kart))
        self._durum_lbl.hide()
        self._dosya_lbl.hide()

    def _on_dosya_turu_changed(self):
        self._durum_lbl.hide()
        self._dosya_lbl.hide()

    # ── Yeni Kart Ekleme ──────────────────────────────────────────────

    def _on_kart_ekle(self):
        banka_adi  = self._yeni_banka_inp.text().strip()
        etiket     = self._yeni_etiket_inp.text().strip()
        hesap_kodu = self._yeni_hesap_inp.text().strip()
        if not banka_adi:
            self._show_durum("⚠️  Banka adı zorunludur.", "#dc2626")
            return
        banka_col_val = etiket or banka_adi
        from db.database import get_connection as _gc
        conn = _gc()
        try:
            conn.execute(
                "INSERT INTO key_kartlari (banka, no, userid, hesapKodu, bankaAdi) "
                "VALUES (?, '', ?, ?, ?)",
                (banka_col_val, self._userid, hesap_kodu, banka_adi)
            )
            conn.commit()
            self._show_durum(f"✅  '{banka_adi}' kartı kaydedildi.", "#059669")
            self._yeni_banka_inp.clear()
            self._yeni_etiket_inp.clear()
            self._yeni_hesap_inp.clear()
            self.refresh()
        except Exception as exc:
            self._show_durum(f"❌  Kayıt hatası: {exc}", "#dc2626")
        finally:
            conn.close()

    # ── İçeri Aktar ───────────────────────────────────────────────────

    def _on_aktar(self):
        kart = self._get_secili_kart()
        if not kart:
            self._show_durum("⚠️  Lütfen bir kart seçin.", "#f59e0b")
            return
        hesap_kodu = kart.get("hesapKodu", "")
        banka_adi  = kart.get("bankaAdi", "")
        dosya_turu = self._dosya_combo.currentText().lower()
        filtre_map = {"pdf": "PDF Dosyaları (*.pdf)", "xlsx": "Excel Dosyaları (*.xlsx)",
                      "csv": "CSV Dosyaları (*.csv)"}
        filtre = filtre_map.get(dosya_turu, "Tüm Dosyalar (*)")
        dosyalar, _ = QFileDialog.getOpenFileNames(self, "Dosya Seç", "", filtre)
        if not dosyalar:
            return
        self._dosya_lbl.setText(
            f"📄  {dosyalar[0].split('/')[-1]}" if len(dosyalar) == 1
            else f"📄  {len(dosyalar)} dosya seçildi"
        )
        self._dosya_lbl.show()
        if dosya_turu == "pdf" and not self._pdf_uyum_kontrol(dosyalar[0], banka_adi):
            self._show_durum("⚠️  Seçilen dosya ile kart uyumsuz olabilir.", "#f59e0b")
        self._set_busy(True)
        self._show_durum("⌛  Dosya yükleniyor...", "#2563eb")
        self._worker = KrediKartYukleWorker(
            userid=self._userid, dosya_yolları=dosyalar,
            hesap_kodu=hesap_kodu, banka_adi=banka_adi,
            dosya_turu=dosya_turu, banka_adi_listesi=[banka_adi] * len(dosyalar),
        )
        self._worker.finished.connect(self._on_aktar_done)
        self._worker.start()

    def _pdf_uyum_kontrol(self, dosya_yolu: str, banka_adi: str) -> bool:
        try:
            import pdfplumber
            norm = banka_adi.replace(" ", "").lower()
            is_yk = "yapıkredi" in norm or "yapikredi" in norm
            with pdfplumber.open(dosya_yolu) as pdf:
                text = (pdf.pages[0].extract_text() or "").lower().replace(" ", "") if pdf.pages else ""
            if len(text) < 50:
                return True
            return ("yapıkredi" in text or "yapikredi" in text) if is_yk else any(
                k in text for k in ["işbank", "isbank", "maximum", "hesapözet", "kredikart"]
            )
        except Exception:
            return True

    def _on_aktar_done(self, r: dict):
        self._set_busy(False)
        if r.get("success"):
            self._show_durum(
                f"✅  <b>İşlem tamamlandı!</b><br>"
                f"{r.get('message','')}<br>"
                f"<small style='color:#6b7280;'>{r.get('added',0)} kayıt, "
                f"{r.get('skipped',0)} mükerrer atlandı</small>",
                "#059669"
            )
        else:
            self._show_durum(
                f"❌  <b>Hata:</b> {r.get('errors', r.get('message','Bilinmeyen hata.'))}",
                "#dc2626"
            )

    def _set_busy(self, busy: bool):
        for w in [self._aktar_btn, self._ekle_btn, self._kart_combo, self._dosya_combo]:
            try:
                w.setEnabled(not busy)
            except Exception:
                pass

    def _show_durum(self, text: str, color: str = "#374151"):
        self._durum_lbl.setText(text)
        self._durum_lbl.setStyleSheet(
            f"font-size:12px;color:{color};padding:6px 10px;background:#f8fafc;border-radius:6px;"
        )
        self._durum_lbl.show()


    def refresh(self):
        """Kart listesini DB'den yükler (PHP: guncelleKartlar() + nocache.php)."""
        from services.kredi_kart_service import get_kart_listesi
        r = get_kart_listesi(self._userid)
        self._kart_listesi = r.get("data", [])
        self._fill_kart_combo()

    def _fill_kart_combo(self):
        """
        PHP ayarlar.php #kartSelect: her key_kartlari satırı ayrı seçenek.
        Etiket: 'BankaAdı — KartNo  (HesapKodu)'
        data() = id (her zaman unique), UserRole+1 = hesapKodu, UserRole+2 = bankaAdi
        """
        self._kart_combo.blockSignals(True)
        self._kart_combo.clear()
        self._kart_combo.addItem("Bir kart tanımı seçin", None)

        for item in self._kart_listesi:
            kart_id   = item.get("id")
            banka_adi = (item.get("bankaAdi") or item.get("banka") or "").strip()
            no        = (item.get("no") or "").strip()
            hesap     = (item.get("hesapKodu") or "").strip()

            # Etiket: 'YapıKredi — 455359****918  (309.01.0003)'
            etiket = banka_adi or "Kart"
            if no:
                etiket += f" — {no}"
            if hesap:
                etiket += f"  ({hesap})"

            self._kart_combo.addItem(etiket, kart_id)
            idx = self._kart_combo.count() - 1
            self._kart_combo.setItemData(idx, hesap,     Qt.ItemDataRole.UserRole + 1)
            self._kart_combo.setItemData(idx, banka_adi, Qt.ItemDataRole.UserRole + 2)

        self._kart_combo.blockSignals(False)

    def _get_secili_kart(self) -> dict:
        """Seçili kartı {id, hesapKodu, bankaAdi} olarak döndürür."""
        idx = self._kart_combo.currentIndex()
        if idx <= 0:
            return {}
        kart_id = self._kart_combo.currentData()
        if kart_id is None:
            return {}
        return {
            "id":        kart_id,
            "hesapKodu": self._kart_combo.itemData(idx, Qt.ItemDataRole.UserRole + 1) or "",
            "bankaAdi":  self._kart_combo.itemData(idx, Qt.ItemDataRole.UserRole + 2) or "",
        }

    def _get_secili_banka_adi(self) -> str:
        return self._get_secili_kart().get("bankaAdi", "")

    # ── Kart Seçimi Değişikliği (PHP: kartSelect + bankaDosyaTuru change) ───

    def _on_kart_changed(self):
        """Kart seçildiğinde İçeri Aktar bölümünü aktif et."""
        kart = self._get_secili_kart()
        aktif = bool(kart)
        self._aktar_frame.setEnabled(aktif)
        self._durum_lbl.hide()
        self._dosya_lbl.hide()

    def _on_dosya_turu_changed(self):
        """Dosya türü değişince durum temizle."""
        self._durum_lbl.hide()
        self._dosya_lbl.hide()

    # ── Yeni Kart Ekleme (key_kartlari INSERT) ──────────────────────────

    def _on_kart_ekle(self):
        """Yeni kart tanımını key_kartlari tablosuna kaydeder."""
        banka_adi  = self._yeni_banka_inp.text().strip()
        etiket     = self._yeni_etiket_inp.text().strip()
        hesap_kodu = self._yeni_hesap_inp.text().strip()

        if not banka_adi:
            self._show_durum("⚠️  Banka adı zorunludur.", "#dc2626")
            return

        banka_col_val = etiket or banka_adi  # 'banka' kolonu = etiket

        from db.database import get_connection
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO key_kartlari (banka, no, userid, hesapKodu, bankaAdi) "
                "VALUES (?, '', ?, ?, ?)",
                (banka_col_val, self._userid, hesap_kodu, banka_adi)
            )
            conn.commit()
            self._show_durum(
                f"✅  '{banka_adi}' kartı kaydedildi.", "#059669"
            )
            # Alanları temizle
            self._yeni_banka_inp.clear()
            self._yeni_etiket_inp.clear()
            self._yeni_hesap_inp.clear()
            # Listeyi yenile
            self.refresh()
        except Exception as exc:
            self._show_durum(f"❌  Kayıt hatası: {exc}", "#dc2626")
        finally:
            conn.close()

# ── Ana Ayarlar Ekranı ────────────────────────────────────────────────────────

class AyarlarScreen(QWidget):
    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self._user = user
        self._userid = user.get("GercekUserId", user.get("Kayitno", 1))
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(20)

        # Başlık
        title = QLabel("Ayarlar")
        title.setStyleSheet(
            "color:#000000;"
            "font-size:24px;font-weight:700;letter-spacing:1px;"
        )
        root.addWidget(title)

        # Tab butonları
        tab_row = QHBoxLayout()
        tab_row.setSpacing(8)
        self._tab_btns: dict[str, QPushButton] = {}
        tabs = [
            ("hesap",     "👤  Hesap & Güvenlik"),
            ("eklentiler","🔌  Eklentiler"),
        ]

        for key, label in tabs:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._tab_style())
            btn.clicked.connect(lambda _, k=key: self._switch_tab(k))
            self._tab_btns[key] = btn
            tab_row.addWidget(btn)
        tab_row.addStretch()
        root.addLayout(tab_row)

        # Scroll alan
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;}")

        self._content = QWidget()
        self._content.setStyleSheet("background:transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(16)

        scroll.setWidget(self._content)
        root.addWidget(scroll)

        # Hesap & Güvenlik sekmesi — Şirket Profili
        self._sirket_card = SirketProfilCard(self._userid)
        self._content_layout.addWidget(self._sirket_card)

        # Eklentiler kartı
        self._efatura_card = EFaturaCard(self._userid)
        self._content_layout.addWidget(self._efatura_card)

        # Fatura Yönetim kartı
        self._yonetim_card = FaturaYonetimCard(self._userid)
        self._content_layout.addWidget(self._yonetim_card)

        # VOMSİS API kartı — Fatura Yönetim'in altında
        self._vomsis_card = VomsisCard(self._userid)
        self._content_layout.addWidget(self._vomsis_card)

        # Moy kartı — VOMSİS'in altında
        self._moy_card = MoyCard(self._userid)
        self._content_layout.addWidget(self._moy_card)

        # Vergi Muhtasar kartı — Moy'un altında
        self._vergi_muhtasar_card = VergiMuhtasarCard(self._userid)
        self._content_layout.addWidget(self._vergi_muhtasar_card)

        # Kredi Kartı kartı — Vergi Muhtasar'ın altında
        self._kredi_kart_card = KrediKartCard(self._userid)
        self._content_layout.addWidget(self._kredi_kart_card)

        self._content_layout.addStretch()

        # Aktif tab
        self._switch_tab("eklentiler")

    def _tab_style(self) -> str:
        return (
            "QPushButton{background:#f1f5f9;border:1.5px solid #e2e8f0;"
            "border-radius:8px;font-size:13px;font-weight:600;color:#000000;"
            "padding:0 16px;}"
            "QPushButton:checked{background:#1e293b;color:white;border-color:#1e293b;}"
            "QPushButton:hover:!checked{background:#e2e8f0;}"
        )

    def _switch_tab(self, key: str):
        for k, btn in self._tab_btns.items():
            btn.setChecked(k == key)

        self._sirket_card.setVisible(key == "hesap")
        self._efatura_card.setVisible(key == "eklentiler")
        self._yonetim_card.setVisible(key == "eklentiler")
        self._vomsis_card.setVisible(key == "eklentiler")
        self._moy_card.setVisible(key == "eklentiler")
        self._vergi_muhtasar_card.setVisible(key == "eklentiler")
        self._kredi_kart_card.setVisible(key == "eklentiler")

        if key == "eklentiler":
            if hasattr(self._efatura_card, "refresh"):
                self._efatura_card.refresh()
            if hasattr(self._vomsis_card, "refresh"):
                self._vomsis_card.refresh()
            if hasattr(self._moy_card, "refresh"):
                self._moy_card.refresh()
            if hasattr(self._vergi_muhtasar_card, "refresh"):
                self._vergi_muhtasar_card.refresh()
            if hasattr(self._kredi_kart_card, "refresh"):
                self._kredi_kart_card.refresh()


    # ── Yardımcılar ──────────────────────────────────────────────────

    def _set_busy(self, busy: bool):
        self._aktar_btn.setEnabled(not busy)
        self._ekle_btn.setEnabled(not busy)
        self._kart_combo.setEnabled(not busy)
        self._dosya_combo.setEnabled(not busy)

    def _show_durum(self, text: str, color: str = "#374151"):
        self._durum_lbl.setText(text)
        self._durum_lbl.setStyleSheet(
            f"font-size:12px;color:{color};padding:6px 10px;"
            "background:#f8fafc;border-radius:6px;"
        )
        self._durum_lbl.show()

# ── Ana Ayarlar Ekranı ────────────────────────────────────────────────────────

class AyarlarScreen(QWidget):
    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self._user = user
        self._userid = user.get("GercekUserId", user.get("Kayitno", 1))
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(20)

        # Başlık
        title = QLabel("Ayarlar")
        title.setStyleSheet(
            "color:#000000;"
            "font-size:24px;font-weight:700;letter-spacing:1px;"
        )
        root.addWidget(title)

        # Tab butonları
        tab_row = QHBoxLayout()
        tab_row.setSpacing(8)
        self._tab_btns: dict[str, QPushButton] = {}
        tabs = [
            ("hesap",     "👤  Hesap & Güvenlik"),
            ("eklentiler","🔌  Eklentiler"),
        ]

        for key, label in tabs:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._tab_style())
            btn.clicked.connect(lambda _, k=key: self._switch_tab(k))
            self._tab_btns[key] = btn
            tab_row.addWidget(btn)
        tab_row.addStretch()
        root.addLayout(tab_row)

        # Scroll alan
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;}")

        self._content = QWidget()
        self._content.setStyleSheet("background:transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(16)

        scroll.setWidget(self._content)
        root.addWidget(scroll)

        # Hesap & Güvenlik sekmesi — Şirket Profili
        self._sirket_card = SirketProfilCard(self._userid)
        self._content_layout.addWidget(self._sirket_card)

        # Eklentiler kartı
        self._efatura_card = EFaturaCard(self._userid)
        self._content_layout.addWidget(self._efatura_card)

        # Fatura Yönetim kartı
        self._yonetim_card = FaturaYonetimCard(self._userid)
        self._content_layout.addWidget(self._yonetim_card)

        # VOMSİS API kartı — Fatura Yönetim'in altında
        self._vomsis_card = VomsisCard(self._userid)
        self._content_layout.addWidget(self._vomsis_card)

        # Moy kartı — VOMSİS'in altında
        self._moy_card = MoyCard(self._userid)
        self._content_layout.addWidget(self._moy_card)

        # Vergi Muhtasar kartı — Moy'un altında
        self._vergi_muhtasar_card = VergiMuhtasarCard(self._userid)
        self._content_layout.addWidget(self._vergi_muhtasar_card)

        # Kredi Kartı kartı — Vergi Muhtasar'ın altında
        self._kredi_kart_card = KrediKartCard(self._userid)
        self._content_layout.addWidget(self._kredi_kart_card)

        self._content_layout.addStretch()

        # Aktif tab
        self._switch_tab("eklentiler")

    def _tab_style(self) -> str:
        return (
            "QPushButton{background:#f1f5f9;border:1.5px solid #e2e8f0;"
            "border-radius:8px;font-size:13px;font-weight:600;color:#000000;"
            "padding:0 16px;}"
            "QPushButton:checked{background:#1e293b;color:white;border-color:#1e293b;}"
            "QPushButton:hover:!checked{background:#e2e8f0;}"
        )

    def _switch_tab(self, key: str):
        for k, btn in self._tab_btns.items():
            btn.setChecked(k == key)

        self._sirket_card.setVisible(key == "hesap")
        self._efatura_card.setVisible(key == "eklentiler")
        self._yonetim_card.setVisible(key == "eklentiler")
        self._vomsis_card.setVisible(key == "eklentiler")
        self._moy_card.setVisible(key == "eklentiler")
        self._vergi_muhtasar_card.setVisible(key == "eklentiler")
        self._kredi_kart_card.setVisible(key == "eklentiler")

        if key == "eklentiler":
            if hasattr(self._efatura_card, "refresh"):
                self._efatura_card.refresh()
            if hasattr(self._vomsis_card, "refresh"):
                self._vomsis_card.refresh()
            if hasattr(self._moy_card, "refresh"):
                self._moy_card.refresh()
            if hasattr(self._vergi_muhtasar_card, "refresh"):
                self._vergi_muhtasar_card.refresh()

