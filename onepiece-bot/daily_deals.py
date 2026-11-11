"""Report giornaliero: box One Piece vicino al retail su negozi (con voto Trustpilot), eBay e Vinted."""
import json
import re
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from common import HEADERS, OWNER_CHAT_ID, parse_eur, send

CFG = json.load(open("config.json", encoding="utf-8"))


def trustpilot(domain):
    try:
        r = requests.get(f"https://it.trustpilot.com/review/{domain}", headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return None
        m = re.search(r'"ratingValue"\s*:\s*"?([0-9.]+)"?', r.text)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def shop_offers(shop, query):
    """Funziona con negozi Shopify (endpoint pubblico di ricerca)."""
    out = []
    try:
        r = requests.get(
            f"https://{shop['domain']}/search/suggest.json",
            params={"q": query, "resources[type]": "product", "resources[limit]": 5},
            headers=HEADERS, timeout=30,
        )
        prods = r.json()["resources"]["results"]["products"]
        for p in prods:
            price = float(p.get("price", 0) or 0)
            if price:
                out.append((p["title"], price, f"https://{shop['domain']}{p['url']}"))
    except Exception:
        pass
    return out


def ebay_offers(query):
    url = "https://www.ebay.it/sch/i.html?_nkw=" + quote_plus(query + " sealed") + "&LH_BIN=1&_sop=15&_ipg=60"
    out = []
    try:
        soup = BeautifulSoup(requests.get(url, headers=HEADERS, timeout=30).text, "html.parser")
        for it in soup.select("li.s-item, li.s-card")[:20]:
            t = it.select_one(".s-item__title, .s-card__title")
            p = it.select_one(".s-item__price, .s-card__price")
            a = it.select_one("a")
            if t and p and a:
                price = parse_eur(p.get_text(" "))
                if price:
                    out.append((t.get_text(" ", strip=True), price, a.get("href", "").split("?")[0]))
    except Exception:
        pass
    return out, url


def vinted_offers(query):
    """Vinted non ha API pubblica: tentativo best-effort, può fallire."""
    out = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        s.get("https://www.vinted.it", timeout=30)
        r = s.get(
            "https://www.vinted.it/api/v2/catalog/items",
            params={"search_text": query, "order": "price_low_to_high", "per_page": 20},
            timeout=30,
        )
        for it in r.json().get("items", []):
            out.append((it["title"], float(it["price"]["amount"]), it["url"]))
    except Exception:
        pass
    return out


def main():
    tol = CFG["tolleranza_pct"] / 100
    blocks = []
    for box in CFG["boxes"]:
        limit = box["retail_eur"] * (1 + tol)
        lines = [f"<b>{box['name']}</b> (retail €{box['retail_eur']}, max €{limit:.0f})"]
        found = False

        for shop in CFG["shops"]:
            score = trustpilot(shop["domain"])
            if score is not None and score < CFG["min_trustpilot"]:
                continue
            for title, price, url in shop_offers(shop, box["query"]):
                if price <= limit and box["name"].split()[0].lower() in title.lower():
                    stars = f"Trustpilot {score}" if score else "Trustpilot n/d"
                    lines.append(f'🛒 {shop["name"]} €{price:.2f} ({stars}) <a href="{url}">link</a>')
                    found = True

        eb, eb_url = ebay_offers(box["query"])
        for title, price, url in eb:
            if box["retail_eur"] * 0.7 <= price <= limit:
                lines.append(f'🟦 eBay €{price:.2f} <a href="{url}">{title[:50]}</a>')
                found = True
                break
        lines.append(f'<a href="{eb_url}">Tutti i risultati eBay</a>')

        for title, price, url in vinted_offers(box["query"]):
            if box["retail_eur"] * 0.7 <= price <= limit:
                lines.append(f'🟩 Vinted €{price:.2f} <a href="{url}">{title[:50]}</a>')
                found = True
                break

        if not found:
            lines.append("Nessuna offerta sotto la soglia oggi.")
        blocks.append("\n".join(lines))

    send(OWNER_CHAT_ID, "📦 <b>Box One Piece TCG – offerte del giorno</b>\n\n" + "\n\n".join(blocks))


if __name__ == "__main__":
    main()
