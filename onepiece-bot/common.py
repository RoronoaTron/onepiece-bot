import html
import os
import re
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
# Uno o più chat ID separati da virgola (tu + gruppo). Es: 357230695,-1001234567890
CHAT_IDS = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}


def esc(text):
    return html.escape(str(text), quote=True)


def fmt_eur(x, dec=2):
    s = f"{x:,.{dec}f}"
    return "€" + s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(x, dec=1):
    return f"{x:.{dec}f}".replace(".", ",") + "%"


def send(chat_id, text, reply_to=None):
    payload = {
        "chat_id": chat_id,
        "text": text[:4000],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_to:
        payload["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
    telegram_request("sendMessage", payload, method="post")


def telegram_request(endpoint, payload, method="get"):
    if not TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN non configurato")
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/{endpoint}"
        r = requests.post(url, json=payload, timeout=30) if method == "post" else requests.get(url, params=payload, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"Telegram {endpoint}: HTTP {r.status_code}")
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {endpoint}: API non riuscita")
        return data
    except requests.RequestException:
        raise RuntimeError(f"Telegram {endpoint}: errore di rete") from None


def send_long(chat_id, blocks, sep="\n\n", limit=3800, reply_to=None):
    chunk = ""
    for b in blocks:
        if chunk and len(chunk) + len(sep) + len(b) > limit:
            send(chat_id, chunk, reply_to)
            chunk = b
        else:
            chunk = chunk + sep + b if chunk else b
    if chunk:
        send(chat_id, chunk, reply_to)


def broadcast(blocks):
    """Invia a tutte le chat configurate (tu + gruppo); un errore su una chat non ferma le altre."""
    if not CHAT_IDS:
        raise RuntimeError("TELEGRAM_CHAT_ID non configurato")
    failures = 0
    for cid in CHAT_IDS:
        try:
            send_long(cid, blocks)
        except Exception as e:
            failures += 1
            print("Invio Telegram fallito (dettagli riservati)")
    if failures:
        raise RuntimeError(f"Invio fallito a {failures} chat; stato non confermato")


def parse_eur(text):
    """'EUR 1.234,56' / '€ 12,50' / '12,50 EUR' -> float (primo prezzo trovato)."""
    m = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+\.\d{2})", text)
    if not m:
        return None
    s = m.group(1)
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def usd_eur_rate():
    for url in (
        "https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR",
        "https://api.frankfurter.app/latest?from=USD&to=EUR",
    ):
        try:
            return float(requests.get(url, timeout=20).json()["rates"]["EUR"])
        except Exception:
            continue
    return None
