import pdfplumber
import os

pdf_dir = "/Users/cemergun/Downloads/2026 FPPRO KREDİ KARTLARI/"
for f in os.listdir(pdf_dir):
    if f.endswith(".pdf"):
        pdf_path = os.path.join(pdf_dir, f)
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        for line in text.split("\n"):
                            if "57.067" in line or "57067" in line:
                                print(f"Found in {f}: {line}")
        except Exception as e:
            pass
