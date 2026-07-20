import pdfplumber

pdf_path = "/Users/cemergun/Downloads/2026 FPPRO KREDİ KARTLARI/İŞ BANKASI 5243 OSMAN ŞAMLI 04.06.pdf"
try:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    
    for i, line in enumerate(text.split("\n")):
        if "57" in line:
            print(f"Line {i+1}: {line}")

except Exception as e:
    print("ERROR:", e)
