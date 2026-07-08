import re

lines = [
    "05/12/2025 533912652140 CLOUDFLARECLOUDFLARE.COCAUS35,78USDSATIŞ 1.563,60 6,25",
    "06/12/2025 524940897909 UZMANTEKNOLOJISANALMISTANBULTR 7.499,92 4/4taksidi(29.999,74)",
    "21/12/2025 535410764416 QPAYA.Ş./QUICKSİGORTAİSTANBULTR -5.674,98 -11,35",
    "1.231.428,00",
    "09/12/2025 534211159613 1048-1667134HESAPTANAKTARIM1048İNTERAKTİF -",
    "30/12/2025 536416220480 MAXIMILESSEYAHATALIMI"
]

# regex
isbank_pattern = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(.+?)\s+(-?\d{1,3}(?:\.\d{3})*(?:,\d+))(?:\s|$)")

for line in lines:
    match = isbank_pattern.search(line)
    if match:
        print("MATCH:", match.groups())
    else:
        print("NO MATCH:", line)
