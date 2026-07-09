"""
UBL-TR e-Fatura XML Parser
PHP lib/filereader/efatura_reader.php dosyasının birebir Python karşılığı.

Desteklenen format: UBL 2.1 / UBLTR fatura (InvoiceDoc)
Kullanım:
    from db.efatura_parser import parse_invoice_xml
    result = parse_invoice_xml("/path/to/fatura.xml")
"""

from __future__ import annotations
import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

# ── UBL-TR Namespace tanımları ──────────────────────────────────────────────
NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    # Bazı eski UBL-TR versiyonlarında kök namespace farklı olabilir
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


@dataclass
class UrunSatiri:
    """Bir fatura satırını temsil eder."""
    urun_adi: str = ""
    miktar: str = ""
    birim_fiyat: str = ""
    satir_toplam: str = ""


@dataclass
class ParsedInvoice:
    """Parsed UBL-TR fatura verisi."""
    success: bool = False
    message: str = ""

    # Fatura temel bilgileri
    fatura_no: str = ""
    tarih: str = ""           # YYYY-MM-DD
    genel_toplam: str = ""    # PayableAmount

    # Fatura tipi — cbc:InvoiceTypeCode
    # UBL-TR standart kodları: 380=SATIS, 381=IADE, 389=IPTAL
    # Bazı e-Arşiv XML'lerinde metin değer gelir ("SATIS", "IADE", "IPTAL")
    # Parser normalize ederek sayısal koda çevirir.
    fatura_tipi: str = ""     # Normalize edilmiş: "380", "381", "389" veya boş
    profil_id: str = ""       # cbc:ProfileID: TEMELFATURA / TICARIFATURA / EARSIVFATURA

    # Tedarikçi (faturayı kesen — AccountingSupplierParty)
    unvan: str = ""
    vergi_no: str = ""
    tc: str = ""
    vergi_dairesi: str = ""
    mersis_no: str = ""

    # Alıcı (faturanın kesildiği — AccountingCustomerParty)
    alici_unvan: str = ""
    alici_vergi_no: str = ""
    alici_tc: str = ""
    alici_vergi_dairesi: str = ""
    alici_mersis_no: str = ""

    urunler: list[UrunSatiri] = field(default_factory=list)

    # ── Fatura tipi yardımcı özellikleri ────────────────────────────────────
    @property
    def is_satis(self) -> bool:
        """Satış faturası mı? (InvoiceTypeCode=380 veya boş/bilinmeyen)"""
        return self.fatura_tipi in ("", "380")

    @property
    def is_iade(self) -> bool:
        """İade faturası mı? (InvoiceTypeCode=381)"""
        return self.fatura_tipi == "381"

    @property
    def is_iptal(self) -> bool:
        """İptal faturası mı? (InvoiceTypeCode=389)"""
        return self.fatura_tipi == "389"

    @property
    def fatura_tipi_adi(self) -> str:
        """Fatura tipi insan-okunabilir adı."""
        return {
            "380": "SATIŞ",
            "381": "İADE",
            "389": "İPTAL",
        }.get(self.fatura_tipi, self.fatura_tipi or "SATIŞ")

    def meta_dict(self, mod: str) -> dict:
        """
        mod='gelir' → alıcı bilgileri (biz kestik, müşteri aldı)
        mod='gider' → tedarikçi bilgileri (karşı firma kesti, biz aldık)
        """
        if mod == "gelir":
            unvan = self.alici_unvan
            vergi_no = self.alici_vergi_no
            vergi_dairesi = self.alici_vergi_dairesi
            mersis_no = self.alici_mersis_no
            tc = self.alici_tc
        else:  # gider
            unvan = self.unvan
            vergi_no = self.vergi_no
            vergi_dairesi = self.vergi_dairesi
            mersis_no = self.mersis_no
            tc = self.tc

        return {
            "unvan": unvan,
            "faturaNo": self.fatura_no,
            "vergiNo": vergi_no,
            "vergiDairesi": vergi_dairesi,
            "mersisNo": mersis_no,
            "tc": tc,
            "tarih": self.tarih,
            "genel_toplam": self.genel_toplam,
            "gelirGider": mod,
        }

    def compute_hash(self, mod: str) -> str:
        """PHP'deki md5(faturaNo|unvan|vergiNo|tc|vergiDairesi) ile aynı hash."""
        meta = self.meta_dict(mod)
        raw = "|".join([
            meta.get("faturaNo", ""),
            meta.get("unvan", ""),
            meta.get("vergiNo", ""),
            meta.get("tc", ""),
            meta.get("vergiDairesi", ""),
        ])
        return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _ns_text(element: ET.Element, tag: str, ns_prefix: str = "cbc") -> str:
    """Namespace-aware element text okuma."""
    el = element.find(f"{ns_prefix}:{tag}", NS)
    return el.text.strip() if el is not None and el.text else ""


def _find_ns(element: ET.Element, tag: str, ns_prefix: str = "cbc") -> Optional[ET.Element]:
    return element.find(f"{ns_prefix}:{tag}", NS)


def _party_info(party_el: ET.Element) -> dict:
    """
    cac:Party elementinden tedarikçi/alıcı bilgilerini çıkarır.
    Döndürür: {unvan, vergi_no, tc, vergi_dairesi, mersis_no}
    """
    info = {
        "unvan": "",
        "vergi_no": "",
        "tc": "",
        "vergi_dairesi": "",
        "mersis_no": "",
    }

    # Şirket adı — PartyName/Name
    party_name = party_el.find("cac:PartyName", NS)
    if party_name is not None:
        name_el = _find_ns(party_name, "Name")
        if name_el is not None and name_el.text:
            info["unvan"] = name_el.text.strip()

    # Şahıs faturası — Person/FirstName + FamilyName
    person = party_el.find("cac:Person", NS)
    if person is not None and not info["unvan"]:
        first = _ns_text(person, "FirstName")
        last = _ns_text(person, "FamilyName")
        info["unvan"] = f"{first} {last}".strip()

    # PartyIdentification — VKN / TCKN / MERSISNO
    for pid in party_el.findall("cac:PartyIdentification", NS):
        id_el = _find_ns(pid, "ID")
        if id_el is None:
            continue
        scheme = id_el.attrib.get("schemeID", "")
        value = (id_el.text or "").strip()
        if scheme == "VKN":
            info["vergi_no"] = value
        elif scheme == "TCKN":
            info["tc"] = value
        elif scheme == "MERSISNO":
            info["mersis_no"] = value

    # PartyTaxScheme → TaxScheme/Name (vergi dairesi)
    pts = party_el.find("cac:PartyTaxScheme", NS)
    if pts is not None:
        ts = pts.find("cac:TaxScheme", NS)
        if ts is not None:
            info["vergi_dairesi"] = _ns_text(ts, "Name")

    return info


def parse_invoice_xml(xml_path: str) -> ParsedInvoice:
    """
    UBL-TR XML dosyasını parse eder ve ParsedInvoice döndürür.
    Hata durumunda success=False olan nesne döner.
    """
    result = ParsedInvoice()

    try:
        # Namespace'leri kaldırarak parse et
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        result.message = f"XML parse hatası: {e}"
        return result
    except FileNotFoundError:
        result.message = f"Dosya bulunamadı: {xml_path}"
        return result
    except Exception as e:
        result.message = f"Dosya açma hatası: {e}"
        return result

    # Root namespace tespiti (farklı UBL-TR versiyonları)
    # Kök tag örneği: {urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice
    root_ns_uri = ""
    if root.tag.startswith("{"):
        root_ns_uri = root.tag.split("}")[0][1:]

    # ── Fatura No ───────────────────────────────────────────────────────────
    id_el = root.find("cbc:ID", NS)
    if id_el is not None and id_el.text:
        result.fatura_no = id_el.text.strip()

    # ── Tarih ────────────────────────────────────────────────────────────────
    date_el = root.find("cbc:IssueDate", NS)
    if date_el is not None and date_el.text:
        result.tarih = date_el.text.strip()

    # ── Fatura Tipi (InvoiceTypeCode) ────────────────────────────────────────
    # UBL-TR sayısal kodlar: 380=Satış, 381=İade, 389=İptal
    # e-Arşiv XML'lerinde metin değer gelebilir: SATIS, IADE, IPTAL
    # Her iki format normalize edilerek sayısal koda çevrilir.
    _TIP_NORMALIZE = {
        "SATIS": "380",  "SATIŞ": "380",
        "IADE":  "381",  "İADE":  "381",
        "IPTAL": "389",  "İPTAL": "389",
    }
    type_el = root.find("cbc:InvoiceTypeCode", NS)
    if type_el is not None and type_el.text:
        raw_tip = type_el.text.strip()
        result.fatura_tipi = _TIP_NORMALIZE.get(raw_tip.upper(), raw_tip)

    # ── Profil ID (ProfileID) ─────────────────────────────────────────────────
    profil_el = root.find("cbc:ProfileID", NS)
    if profil_el is not None and profil_el.text:
        result.profil_id = profil_el.text.strip()

    # ── Tedarikçi (AccountingSupplierParty) ─────────────────────────────────
    supplier_wrapper = root.find("cac:AccountingSupplierParty", NS)
    if supplier_wrapper is not None:
        party = supplier_wrapper.find("cac:Party", NS)
        if party is not None:
            sup = _party_info(party)
            result.unvan = sup["unvan"]
            result.vergi_no = sup["vergi_no"]
            result.tc = sup["tc"]
            result.vergi_dairesi = sup["vergi_dairesi"]
            result.mersis_no = sup["mersis_no"]

    # ── Alıcı (AccountingCustomerParty) ─────────────────────────────────────
    customer_wrapper = root.find("cac:AccountingCustomerParty", NS)
    if customer_wrapper is not None:
        party = customer_wrapper.find("cac:Party", NS)
        if party is not None:
            cust = _party_info(party)
            result.alici_unvan = cust["unvan"]
            result.alici_vergi_no = cust["vergi_no"]
            result.alici_tc = cust["tc"]
            result.alici_vergi_dairesi = cust["vergi_dairesi"]
            result.alici_mersis_no = cust["mersis_no"]

    # ── Genel Toplam (LegalMonetaryTotal/PayableAmount) ──────────────────────
    lmt = root.find("cac:LegalMonetaryTotal", NS)
    if lmt is not None:
        pa = _find_ns(lmt, "PayableAmount")
        if pa is not None and pa.text:
            result.genel_toplam = pa.text.strip()

    # ── Ürün Satırları (InvoiceLine) ─────────────────────────────────────────
    for line_el in root.findall("cac:InvoiceLine", NS):
        satir = UrunSatiri()

        # Ürün adı — Item/Name
        item = line_el.find("cac:Item", NS)
        if item is not None:
            satir.urun_adi = _ns_text(item, "Name")

        # Miktar
        qty = _find_ns(line_el, "InvoicedQuantity")
        if qty is not None and qty.text:
            satir.miktar = qty.text.strip()

        # Satır toplam
        lea = _find_ns(line_el, "LineExtensionAmount")
        if lea is not None and lea.text:
            satir.satir_toplam = lea.text.strip()

        # Birim fiyat — Price/PriceAmount
        price = line_el.find("cac:Price", NS)
        if price is not None:
            pa_el = _find_ns(price, "PriceAmount")
            if pa_el is not None and pa_el.text:
                satir.birim_fiyat = pa_el.text.strip()

        result.urunler.append(satir)

    result.success = True
    return result


if __name__ == "__main__":
    import sys, json

    if len(sys.argv) < 2:
        print("Kullanım: python -m db.efatura_parser <xml_dosyasi>")
        sys.exit(1)

    parsed = parse_invoice_xml(sys.argv[1])
    if not parsed.success:
        print(f"❌ Hata: {parsed.message}")
        sys.exit(1)

    print(f"✔ Fatura No   : {parsed.fatura_no}")
    print(f"  Tarih        : {parsed.tarih}")
    print(f"  Tedarikçi    : {parsed.unvan} ({parsed.vergi_no})")
    print(f"  Alıcı        : {parsed.alici_unvan} ({parsed.alici_vergi_no})")
    print(f"  Toplam       : {parsed.genel_toplam}")
    print(f"  Satır sayısı : {len(parsed.urunler)}")
    print(f"  Hash (gelir) : {parsed.compute_hash('gelir')}")
    print(f"  Hash (gider) : {parsed.compute_hash('gider')}")
