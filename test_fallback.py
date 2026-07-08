import re
import os
import pdfplumber

def _parse_pdf_fallback(dosya_yolu: str, banka: str = "") -> list:
    islemler = []
    kaynak_dosya = os.path.basename(dosya_yolu)
    
    isbank_pattern = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(.+?)\s+(-?\d{1,3}(?:\.\d{3})*(?:,\d+))(?:\s|$)")
    isbank_start_pattern = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(.+?)(?:\s+(-?\d{1,3}(?:\.\d{3})*(?:,\d+))(?:\s|$))?$")
    
    with pdfplumber.open(dosya_yolu) as pdf:
        pending_date = None
        pending_desc = None
        
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
                
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                if banka == "isbank":
                    if pending_date:
                        amt_match = re.match(r"^(-?\d{1,3}(?:\.\d{3})*(?:,\d+))$", line)
                        if amt_match:
                            tutar_str = amt_match.group(1)
                            tutar = tutar_str.replace('.', '').replace(',', '.')
                            islemler.append({
                                "islem_tarihi": pending_date,
                                "aciklama": pending_desc.strip(),
                                "tutar_str": tutar_str,
                                "tutar": float(tutar),
                                "kaynak_dosya": kaynak_dosya
                            })
                            pending_date = pending_desc = None
                            continue
                        else:
                            pending_date = pending_desc = None
                    
                    match = isbank_pattern.search(line)
                    if match:
                        tarih = match.group(1)
                        aciklama = match.group(3).strip()
                        tutar_str = match.group(4)
                        tutar = tutar_str.replace('.', '').replace(',', '.')
                        islemler.append({
                            "islem_tarihi": tarih,
                            "aciklama": aciklama,
                            "tutar_str": tutar_str,
                            "tutar": float(tutar),
                            "kaynak_dosya": kaynak_dosya
                        })
                    else:
                        match_start = isbank_start_pattern.search(line)
                        if match_start and not match_start.group(4):
                            pending_date = match_start.group(1)
                            pending_desc = match_start.group(3)

    return islemler

res = _parse_pdf_fallback("/Users/cemergun/Downloads/2026 FPPRO KREDİ KARTLARI/İŞ BANKASI 5243 OSMAN ŞAMLI 04.01.pdf", banka="isbank")
print(f"Total rows: {len(res)}")
for i, r in enumerate(res):
    print(i, r)
