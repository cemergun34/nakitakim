import pdfplumber
import re

pdf_path = "/Users/cemergun/Downloads/2026 FPPRO KREDİ KARTLARI/İŞ BANKASI 5243 OSMAN ŞAMLI 04.06.pdf"
try:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    
    isbank_pattern = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(.+?)\s*(-?\d{1,3}(?:\.\d{3})*(?:,\d+))(?:\s|$)", re.MULTILINE)
    matches = isbank_pattern.findall(text)
    print(f"Regex bulduğu satır sayısı: {len(matches)}")
    
    # Also sum the amounts
    toplam = 0.0
    for m in matches:
        tutar_str = m[3]
        val = float(tutar_str.replace('.', '').replace(',', '.'))
        toplam += val
        
    print(f"Toplam tutar (mutlak değer olarak): {toplam}")

except Exception as e:
    print("ERROR:", e)
