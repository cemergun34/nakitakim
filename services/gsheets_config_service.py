"""
gsheets_config_service.py
─────────────────────────────────────────────────────────────────
Google Sheets bağlantı ayarlarını saklar/yükler.
Dosya konumu: ~/NakitAkim/data/gsheets_config.json

Kullanıcı Sheet URL'si veya ID girebilir; extract_sheet_id()
her ikisini de kabul eder.
─────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_CONFIG_PATH = Path.home() / "NakitAkim" / "data" / "gsheets_config.json"

# ── Fabrika değerleri (önceki sabit ID'ler) ──────────────────────────────────
_DEFAULTS: dict = {
    "kasa_sheet_id":        "10L3gSinp4cY6dwDzmZvjCtpZK6ykmMiG9xXxXFgfbVA",
    "kasa_tab_name":        "Kasa",
    "gider_sheet_id":       "1bxN5D_UEtgzxBJd6hQyhZzeKHP5QAXTgEGyTnBH45Tk",
    "genel_hesap_sheet_id": "1cdV-a6yyYeFm8TIMipaEhphmV-IfIGD_y7os8IkSAsA",
}


def load_config() -> dict:
    """Kayıtlı ayarları yükler; yoksa fabrika değerlerini döndürür."""
    cfg = dict(_DEFAULTS)
    try:
        if _CONFIG_PATH.exists():
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                saved = json.load(f)
            cfg.update({k: v for k, v in saved.items() if k in _DEFAULTS})
    except Exception:
        pass
    return cfg


def save_config(cfg: dict) -> None:
    """Ayarları JSON dosyasına yazar."""
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    current = load_config()
    current.update({k: v for k, v in cfg.items() if k in _DEFAULTS})
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)


def extract_sheet_id(url_or_id: str) -> str:
    """
    Google Sheets URL'sinden ID çıkarır.
    Tam URL:  https://docs.google.com/spreadsheets/d/XXXX/edit  → XXXX
    Sadece ID: XXXX  → XXXX (değişmeden döner)
    """
    url_or_id = url_or_id.strip()
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url_or_id)
    if m:
        return m.group(1)
    return url_or_id
