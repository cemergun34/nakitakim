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
    
    for m in matches:
        print(m)

except Exception as e:
    print("ERROR:", e)
