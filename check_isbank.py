import pdfplumber
import re

pdf_path = "/Users/cemergun/Downloads/2026 FPPRO KREDİ KARTLARI/İŞ BANKASI 5243 OSMAN ŞAMLI 04.06.pdf"
try:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    
    isbank_pattern = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(.+?)\s*(-?\d{1,3}(?:\.\d{3})*(?:,\d+))(?:\s|$)", re.MULTILINE)
    matches = isbank_pattern.findall(text)
    
    for m in matches:
        tutar_str = m[3]
        if "57" in tutar_str.replace('.', ''):
            print(m)

except Exception as e:
    print("ERROR:", e)
