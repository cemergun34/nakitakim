import pdfplumber
import re

pdf_path = "/Users/cemergun/Downloads/2026 FPPRO KREDİ KARTLARI/YAPIKREDİ 1635 OSMAN ŞAMLI 22.06.pdf"
try:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    
    yk_pattern = re.compile(
        r"^(\d{1,2})\s+(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+(\d{4})"
        r"\s+(.+?)\s+(\+?-?\d{1,3}(?:\.\d{3})*,\d+)"
        r"(?:\s+[\d.,/]+)*(?:\s+\d+)?$", re.MULTILINE
    )
    
    matches = yk_pattern.findall(text)
    
    pos = 0.0
    neg = 0.0
    for m in matches:
        tutar_raw = m[4]
        is_odeme = tutar_raw.startswith("+")
        tutar_str = tutar_raw.replace('+', '').strip()
        tutar = tutar_str.replace('.', '').replace(',', '.')
        val = float(tutar)
        if is_odeme:
            val = -val
            neg += val
        else:
            pos += val
            
    print(f"Bulunan satır sayısı: {len(matches)}")
    print(f"Toplam Pozitif (Harcamalar): {pos}")
    print(f"Toplam Negatif (Ödemeler): {neg}")
    print(f"Genel Toplam: {pos + neg}")

except Exception as e:
    print("ERROR:", e)
