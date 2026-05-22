"""
Para formatı yardımcıları.
"""
import locale


def fmt_para(tutar: float, prefix: str = "₺") -> str:
    """12.345.678,90 formatında para birimi."""
    try:
        return f"{prefix}{tutar:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"{prefix}0,00"


def fmt_signed(tutar: float) -> str:
    """+ / - işaretli para formatı."""
    if tutar > 0:
        return f"+{fmt_para(tutar)}"
    elif tutar < 0:
        return f"-{fmt_para(abs(tutar))}"
    return fmt_para(0)
