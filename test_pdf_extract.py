import pdfplumber
import re

pdf_path = "/Users/cemergun/Downloads/2026 FPPRO KREDİ KARTLARI/İŞ BANKASI 5243 OSMAN ŞAMLI 04.01.pdf"
try:
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            for line in text.split('\n'):
                if "ÖDEME" in line.upper() or "-" in line:
                    print(line)
except Exception as e:
    print("ERROR:", e)
