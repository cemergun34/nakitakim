import re

line = "11/05/2026 613007389904 1048-1667134HESAPTANAKTARIM1048İNTERAKTİF-696.506,55"
p = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(.+?)\s*(-?\d{1,3}(?:\.\d{3})*(?:,\d+))(?:\s|$)")

m = p.search(line)
if m:
    print("MATCH!")
    print(m.groups())
else:
    print("NO MATCH")
