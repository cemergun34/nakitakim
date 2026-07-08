import sys
import traceback
sys.path.insert(0, "/Applications/XAMPP/xamppfiles/htdocs/moyTr/dev")
import isbank_isle as ib

try:
    df = ib.process_pdf("/Users/cemergun/Downloads/2026 FPPRO KREDİ KARTLARI/İŞ BANKASI 5243 OSMAN ŞAMLI 04.01.pdf")
    print(df)
except Exception as e:
    traceback.print_exc()
