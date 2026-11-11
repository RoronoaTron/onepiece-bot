import os
import re
import requests

TOKEN = os.environ["TELEGRAM_TOKEN"]
OWNER_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}


def send(chat_id, text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text[:4000],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    r.raise_for_status()


def parse_eur(text):
    """'EUR 1.234,56' / '€ 12,50' / '12,50 EUR' -> float (primo prezzo trovato)."""
    m = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+\.\d{2})", text)
    if not m:
        return None
    s = m.group(1)
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)
