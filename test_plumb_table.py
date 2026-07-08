import pdfplumber

with pdfplumber.open("/Users/cemergun/Downloads/2026 FPPRO KREDİ KARTLARI/İŞ BANKASI 5243 OSMAN ŞAMLI 04.01.pdf") as pdf:
    for i in range(1, len(pdf.pages)):
        table = pdf.pages[i].extract_table()
        if table:
            for row in table:
                print(row)
