from services.moy_service import get_local_beyannameler
res = get_local_beyannameler(1, '20250225', '770.01')
print("Sıralanmış sonuç (ilk MUHSGK olmalı):")
for r in res:
    print(r['belge_turu'], r['kayit_no'])
