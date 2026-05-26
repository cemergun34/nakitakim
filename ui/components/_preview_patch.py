"""
_show_fatura_preview metodunu QWebEngineView ile değiştirir.
"""

NEW_METHOD = '''
    def _show_fatura_preview(self, row_data):
        """
        XSLT transform ile orijinal e-fatura görünümünü
        QWebEngineView (Chromium motoru) içinde gösterir.
        """
        import os, base64, tempfile
        import xml.etree.ElementTree as ET
        from PyQt6.QtWidgets import (
            QMessageBox, QDialog, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton
        )
        from PyQt6.QtCore import QUrl
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWebEngineCore import QWebEngineSettings

        xml_path  = row_data.get("xml_dosya")
        fatura_no = row_data.get("faturano") or row_data.get("faturaNo") or "?"

        # ── 1. Dosya kontrolü ────────────────────────────────────────────────
        if not xml_path or not os.path.exists(str(xml_path)):
            QMessageBox.information(
                self,
                "Fatura Dosyası Yok",
                f"Bu fatura ({fatura_no}) sisteme XML olarak yüklenmemiş.\\n"
                "Yalnızca XML ile aktarılan faturalar önizlenebilir."
            )
            return

        # ── 2. XML oku ───────────────────────────────────────────────────────
        try:
            with open(xml_path, "rb") as fh:
                xml_bytes = fh.read()
        except Exception as exc:
            QMessageBox.critical(self, "Hata", f"XML okunamadı:\\n{exc}")
            return

        # ── 3. XSLT bul + dönüştür ──────────────────────────────────────────
        html_bytes = None
        xslt_filename = "style.xslt"
        try:
            from lxml import etree as let
            _NS = {
                "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
                "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            }
            xml_root = let.fromstring(xml_bytes)
            hits = xml_root.xpath(
                ".//cac:AdditionalDocumentReference"
                "[cbc:DocumentType=\\'XSLT\\']"
                "/cac:Attachment/cbc:EmbeddedDocumentBinaryObject",
                namespaces=_NS,
            )
            if hits and hits[0].text:
                xslt_raw  = base64.b64decode(hits[0].text.strip())
                xslt_root = let.fromstring(xslt_raw)
                transform = let.XSLT(xslt_root)
                result    = transform(xml_root)
                html_bytes = bytes(result)
                # XSLT dosya adını da al (href olarak kullanacağız)
                fname = hits[0].attrib.get("filename", "style.xslt")
                xslt_filename = fname if fname else "style.xslt"
        except Exception as exc:
            print(f"[EFatura] XSLT dönüşüm hatası: {exc}")

        # ── 4. Fallback: XSLT yoksa kendi HTML şablonumuzu yaz ──────────────
        if not html_bytes:
            NS = {
                "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
                "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
            }
            root = ET.fromstring(xml_bytes)

            def tx(el, tag, ns="cbc"):
                e = el.find(f"{ns}:{tag}", NS) if el is not None else None
                return (e.text or "").strip() if e is not None else ""

            fno   = tx(root, "ID") or fatura_no
            tarih = tx(root, "IssueDate")

            sup  = root.find("cac:AccountingSupplierParty/cac:Party", NS)
            pn   = sup.find("cac:PartyName", NS) if sup else None
            sup_unvan = tx(pn, "Name") if pn else ""
            sup_vkn = ""
            if sup:
                for pid in sup.findall("cac:PartyIdentification", NS):
                    ie = pid.find("cbc:ID", NS)
                    if ie is not None and ie.attrib.get("schemeID") == "VKN":
                        sup_vkn = (ie.text or "").strip()

            cus  = root.find("cac:AccountingCustomerParty/cac:Party", NS)
            pnc  = cus.find("cac:PartyName", NS) if cus else None
            cus_unvan = tx(pnc, "Name") if pnc else ""
            cus_vkn = ""
            if cus:
                for pid in cus.findall("cac:PartyIdentification", NS):
                    ie = pid.find("cbc:ID", NS)
                    if ie is not None and ie.attrib.get("schemeID") == "VKN":
                        cus_vkn = (ie.text or "").strip()

            lmt     = root.find("cac:LegalMonetaryTotal", NS)
            payable = tx(lmt, "PayableAmount")

            def fn(v):
                try:    return f"{float(v):,.2f} TL"
                except: return v or "-"

            rows_html = ""
            for i, line in enumerate(root.findall("cac:InvoiceLine", NS)):
                item  = line.find("cac:Item", NS)
                urun  = tx(item, "Name") if item else "-"
                qty   = tx(line, "InvoicedQuantity")
                price = line.find("cac:Price", NS)
                bp    = tx(price, "PriceAmount") if price else ""
                le    = tx(line, "LineExtensionAmount")
                bg    = "#ffffff" if i % 2 == 0 else "#f8faff"
                rows_html += (
                    f"<tr style=\\'background:{bg}\\'>"
                    f"<td style=\\'padding:8px\\'>{urun}</td>"
                    f"<td style=\\'padding:8px;text-align:center\\'>{qty}</td>"
                    f"<td style=\\'padding:8px;text-align:right\\'>{fn(bp)}</td>"
                    f"<td style=\\'padding:8px;text-align:right;font-weight:bold\\'>{fn(le)}</td>"
                    f"</tr>"
                )

            html_str = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
body{{font-family:Arial,sans-serif;font-size:13px;color:#1f2937;background:#f0f4ff;margin:0;padding:20px}}
.wrap{{max-width:900px;margin:0 auto}}
.card{{background:white;border-radius:8px;padding:20px;margin-bottom:14px;border:1px solid #e5e7eb}}
h1{{font-size:17px;color:#1e3a8a;margin:0 0 6px}} h2{{font-size:13px;color:#374151;margin:10px 0 6px;border-bottom:1px solid #e5e7eb;padding-bottom:4px}}
.label{{font-size:10px;color:#6b7280;text-transform:uppercase;font-weight:700}}
.val{{font-size:13px;margin-top:2px}}
.two{{display:flex;gap:20px}}.two>div{{flex:1}}
table{{width:100%;border-collapse:collapse}}
th{{background:#1e3a8a;color:white;padding:8px;text-align:left;font-size:11px}}
.total{{font-size:15px;font-weight:700;color:#059669;text-align:right;padding:10px 0}}
</style></head><body><div class="wrap">
<div class="card"><h1>Fatura No: {fno}</h1>
<div class="two">
  <div><div class="label">Tarih</div><div class="val">{tarih}</div></div>
  <div><div class="label">Tedarikçi</div><div class="val"><b>{sup_unvan}</b> (VKN: {sup_vkn})</div></div>
  <div><div class="label">Alıcı</div><div class="val"><b>{cus_unvan}</b> (VKN: {cus_vkn})</div></div>
</div></div>
<div class="card"><h2>Kalemler</h2>
<table><tr><th>Açıklama</th><th>Miktar</th><th style="text-align:right">Birim Fiyat</th><th style="text-align:right">Toplam</th></tr>
{rows_html}</table>
<div class="total">Ödenecek: {fn(payable)}</div>
</div></div></body></html>"""
            html_bytes = html_str.encode("utf-8")

        # ── 5. Geçici dizine yaz (yerel dosya sistemi üzerinden aç) ─────────
        tmp_dir  = tempfile.mkdtemp(prefix="efatura_preview_")
        html_file = os.path.join(tmp_dir, "fatura.html")
        with open(html_file, "wb") as fh:
            fh.write(html_bytes)

        # ── 6. QWebEngineView ile QDialog içinde göster ──────────────────────
        dialog = QDialog(self)
        dialog.setWindowTitle(f"E-Fatura Ön İzleme  —  {fatura_no}")
        dialog.setMinimumSize(1000, 820)
        dialog.resize(1100, 900)
        dialog.setStyleSheet("background:#1e3a8a;")

        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setContentsMargins(0, 0, 0, 0)
        dlg_layout.setSpacing(0)

        # Header
        hdr = QLabel()
        hdr.setFixedHeight(48)
        hdr.setText(f"  📄  E-Fatura Ön İzleme  —  {fatura_no}")
        hdr.setStyleSheet(
            "QLabel { background:#2563EB; color:white; font-size:13px; font-weight:700; padding-left:12px; }"
        )

        close_btn = QPushButton("✕  Kapat")
        close_btn.setFixedSize(100, 34)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,.22);color:white;"
            "border:none;border-radius:7px;font-size:13px;font-weight:700;}"
            "QPushButton:hover{background:rgba(255,255,255,.4);}"
        )
        close_btn.clicked.connect(dialog.reject)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 12, 0)
        top.setSpacing(0)
        top.addWidget(hdr, 1)
        top.addWidget(close_btn)

        hdr_widget = __import__("PyQt6.QtWidgets", fromlist=["QWidget"]).QWidget()
        hdr_widget.setFixedHeight(48)
        hdr_widget.setStyleSheet("background:#2563EB;")
        hdr_widget.setLayout(top)
        dlg_layout.addWidget(hdr_widget)

        # WebEngine
        web = QWebEngineView()
        web.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        web.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        web.load(QUrl.fromLocalFile(html_file))
        dlg_layout.addWidget(web, 1)

        dialog.exec()
'''

path = "/Users/cemergun/NakitAkim/ui/components/detay_dialog.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

start_marker = "\n    def _show_fatura_preview(self, row_data):"
end_marker   = "\n\n# ─── ANA DETAY DİYALOĞU"

start_idx = content.find(start_marker)
end_idx   = content.find(end_marker)

assert start_idx != -1, "start marker not found"
assert end_idx   != -1, "end marker not found"

new_content = content[:start_idx] + NEW_METHOD + content[end_idx:]

with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"Patch applied. New len={len(new_content)}")
