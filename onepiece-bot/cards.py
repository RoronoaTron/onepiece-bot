"""Ricerca prezzo carta: OPTCG API (convertito in EUR) + ultimi venduti eBay.it + link Cardmarket."""
import re
import statistics
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from common import HEADERS, esc, parse_eur, usd_eur_rate

CODE_RE = re.compile(r"^[A-Za-z]{2,4}\d{2}-\d{3}$")


def extract_code(text):
    """Accetta 'OP13-017', '/carta OP13-017', '@bot OP13-017'. Altrimenti None."""
    t = re.sub(r"^/(carta|c)(@\w+)?\s*", "", text.strip(), flags=re.I)
    t = re.sub(r"@\w+", "", t).strip()
    return t.upper() if CODE_RE.match(t) else None


def cardmarket_link(code):
    return f"https://www.cardmarket.com/it/OnePiece/Products/Search?searchString={quote_plus(code)}"


def optcg_prices(code):
    """Prezzi di mercato (USD, fonte TCGplayer) dalla OPTCG API pubblica."""
    out = []
    try:
        r = requests.get(f"https://optcgapi.com/api/sets/card/{code}/", headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return out
        data = r.json()
        if isinstance(data, dict):
            data = [data]
        for c in data:
            out.append({
                "name": c.get("card_name", code),
                "set_id": c.get("card_image_id") or c.get("card_set_id", code),
                "market": c.get("market_price"),
                "rarity": c.get("rarity", ""),
            })
    except Exception:
        pass
    return out


def ebay_sold(code, n=10):
    """Link only: accepted prices and card variants cannot be verified here."""
    url = "https://www.ebay.it/sch/i.html?_nkw=" + quote_plus(f"{code} one piece") + "&LH_Sold=1&LH_Complete=1&_sop=13"
    return [], url


def build_reply(code):
    code = code.strip().upper()
    lines = [f"<b>{esc(code)}</b>"]
    rate = usd_eur_rate()

    cards = optcg_prices(code)
    if cards:
        for c in cards[:4]:
            m = c["market"]
            try:
                usd = float(m)
            except (TypeError, ValueError):
                usd = None
            if usd is None:
                price_txt = "prezzo n/d"
            elif rate:
                price_txt = f"€{usd * rate:.2f} (mercato TCGplayer, ${usd:.2f})"
            else:
                price_txt = f"${usd:.2f} (mercato TCGplayer)"
            lines.append(f"• {esc(c['name'])} [{esc(c['set_id'])}] {esc(c['rarity'])}: {price_txt}")
    else:
        lines.append("• Carta non trovata nel database prezzi (controlla il codice).")

    import json
    import os
    import sources
    cfg = json.load(open(os.path.join(os.path.dirname(__file__), "config.json"), encoding="utf-8"))
    token, err = sources.ebay_token()
    if token:
        offers, err = sources.ebay_api_search(token, code, 0, 0, cfg)
        matching = [o for o in offers if re.search(re.escape(code).replace(r"\-", r"[ -]?"), o["title"], re.I)]
        if matching:
            lines.append("\n<b>eBay · prezzi richiesti (non venduti)</b>")
            for o in matching[:3]:
                shipping = f" + sped. €{o['ship_eur']:.2f}" if o["ship_eur"] is not None else " + spedizione n/d"
                seller = f"{o['seller_pct']}% / {o['seller_n']} feedback" if o["seller_pct"] is not None else "affidabilità n/d"
                lines.append(f'<a href="{esc(o["url"])}">{esc(o["title"][:100])}</a>: €{o["item_eur"]:.2f}{shipping} · {esc(seller)}')
        else:
            lines.append("eBay: nessuna inserzione EUR corrispondente." if not err else "eBay API: ricerca non disponibile.")
    else:
        lines.append("eBay API non disponibile: verificare le chiavi di produzione.")
    prices, ebay_url = ebay_sold(code)
    if prices:
        med = statistics.median(prices)
        lines.append(
            f"\n<b>eBay.it ultimi {len(prices)} venduti</b>: mediana €{med:.2f} "
            f"(min €{min(prices):.2f} – max €{max(prices):.2f})"
        )
    else:
        lines.append("\nVendite concluse: prezzo effettivo non verificabile automaticamente con gli accessi disponibili.")
    lines.append(f'<a href="{esc(ebay_url)}">Venduti eBay</a>')
    lines.append(f'<a href="{esc(cardmarket_link(code))}">Cardmarket</a> (nessuna API gratuita: apri il link per il prezzo aggiornato)')
    lines.append("\nNota: le versioni parallele/alt art hanno prezzi diversi, controlla le righe sopra.")
    return "\n".join(lines)
