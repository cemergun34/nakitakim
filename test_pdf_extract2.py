import pdfplumber
import os

pdf_dir = "/Users/cemergun/Downloads/2026 FPPRO KREDİ KARTLARI/"
target = None
for f in os.listdir(pdf_dir):
    if "04.06.pdf" in f:
        target = os.path.join(pdf_dir, f)

if target:
    with pdfplumber.open(target) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            for line in text.split('\n'):
                if "HESAP" in line.upper() or "ÖDEME" in line.upper() or "AKTARIM" in line.upper() or "-" in line:
                    print(line)
