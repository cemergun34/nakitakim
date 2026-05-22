"""
Uygulama genelinde kullanılan renk paleti ve stil sabitleri.
PHP admin.css ve widgets.css'den elde edilmiştir.
"""

# ─── RENK PALETİ ──────────────────────────────────────────────────────────────
COLORS = {
    # Temel
    "bg":           "#F5F6FA",
    "sidebar_bg":   "#FFFFFF",
    "card_bg":      "#FFFFFF",
    "border":       "#E8EAED",
    "text_primary": "#1A1D23",
    "text_secondary":"#6B7280",
    "text_muted":   "#9CA3AF",

    # Kart renkleri (PHP'deki bg-* sınıfları karşılığı)
    "green":        "#10B981",
    "green_dark":   "#059669",
    "teal":         "#0EA5E9",
    "purple":       "#8B5CF6",
    "pink":         "#EC4899",
    "orange":       "#F59E0B",
    "dark_blue":    "#1E3A5F",
    "dark":         "#1F2937",
    "grey":         "#6B7280",
    "red":          "#EF4444",
    "yellow":       "#F59E0B",

    # KPI kartları (12 kart rengi)
    "kpi_nakit_gelir":   "#10B981",  # yeşil
    "kpi_nakit_odeme":   "#0EA5E9",  # mavi
    "kpi_kesilen":       "#8B5CF6",  # mor
    "kpi_gelen":         "#EC4899",  # pembe/kırmızı
    "kpi_gider_pusulasi":"#10B981",  # yeşil
    "kpi_kurum":         "#1E3A5F",  # koyu mavi
    "kpi_maas":          "#374151",  # koyu gri
    "kpi_banka":         "#6B7280",  # gri
    "kpi_sanal_pos":     "#111827",  # siyah
    "kpi_fiziksel_pos":  "#1F2937",  # koyu
    "kpi_kredi_karti":   "#D97706",  # sarı/amber
    "kpi_genel_hesap":   "#EA580C",  # turuncu

    # Butonlar
    "btn_primary":  "#3B82F6",
    "btn_success":  "#10B981",
    "btn_excel":    "#059669",
    "btn_danger":   "#EF4444",

    # Tablo
    "table_header":  "#F9FAFB",
    "table_hover":   "#F0F9FF",
    "table_total_bg":"#EFF6FF",
    "table_total_fg":"#1E40AF",
    "row_alt":       "#FAFAFA",
}

# ─── FON ──────────────────────────────────────────────────────────────────────
FONTS = {
    "primary":   "Segoe UI",
    "fallback":  "Arial, sans-serif",
    "mono":      "Consolas, monospace",
    "size_xs":   "10px",
    "size_sm":   "12px",
    "size_md":   "14px",
    "size_lg":   "16px",
    "size_xl":   "18px",
    "size_2xl":  "22px",
    "size_kpi":  "26px",
}

# ─── BOYUTLAR ─────────────────────────────────────────────────────────────────
SIDEBAR_WIDTH   = 72
HEADER_HEIGHT   = 60
KPI_CARD_MIN_W  = 190
KPI_CARD_H      = 140
BORDER_RADIUS   = 14
CARD_RADIUS     = 16
