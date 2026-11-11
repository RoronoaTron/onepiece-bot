"""Fonti dati. Ogni funzione restituisce (lista_item, errore_o_None) e non solleva eccezioni.

- eBay Browse API (ufficiale, gratuita, serve una chiave): prezzi, spedizione, venditore, disponibilità.
- Lettura pagine HTML (eBay, negozi, Vinted, Trustpilot): NON ufficiale, può smettere di funzionare
  o non essere consentita dai termini del sito. Ogni fonte si può spegnere in config.json -> "fonti".
- Cardmarket: nessuna API gratuita aperta, qui solo link.
"""
import base64
import os
import re
from urllib.parse import quote, quote_plus

import requests
from bs4 import BeautifulSoup

from common import HEADERS, parse_eur

EBAY_API = "https://api.ebay.com"


def _letters_digits(code):
    return re.match(r"([A-Za-z]+)(\d+)$", code).groups()


def _query(code):
    letters, digits = _letters_digits(code)
    return f"one piece ({code},{letters}-{digits}) (box,display)"


def item(**kw):
    base = {
        "title": "", "item_eur": None, "ship_eur": None, "fees_eur": 0.0, "url": "", "source": "",
        "seller": "", "seller_pct": None, "seller_n": None, "trust": None, "item_id": None,
        "in_stock": None, "language": None, "condition_new": None,
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------- eBay API ufficiale
def ebay_token():
    cid = os.environ.get("EBAY_CLIENT_ID", "").strip()
    sec = os.environ.get("EBAY_CLIENT_SECRET", "").strip()
    if not cid or not sec:
        return None, None
    try:
        auth = base64.b64encode(f"{cid}:{sec}".encode()).decode()
        r = requests.post(
            f"{EBAY_API}/identity/v1/oauth2/token",
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["access_token"], None
    except Exception as e:
        return None, f"eBay API (token): {e}"


def _api_headers(token, cfg):
    c = cfg["consegna"]
    return {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_IT",
        "X-EBAY-C-ENDUSERCTX": f"contextualLocation=country={c['paese']},zip={c['cap']}",
    }


def ebay_api_search(token, code, price_min, price_max, cfg):
    filt = (
        "buyingOptions:{FIXED_PRICE},conditionIds:{1000},"
        f"price:[{int(price_min)}..{int(price_max)}],priceCurrency:EUR,deliveryCountry:{cfg['consegna']['paese']}"
    )
    params = {"q": _query(code), "limit": "50", "sort": "price", "filter": filt}
    out = []
    try:
        r = requests.get(f"{EBAY_API}/buy/browse/v1/item_summary/search", params=params,
                         headers=_api_headers(token, cfg), timeout=30)
        r.raise_for_status()
        for it in r.json().get("itemSummaries", []):
            pr = it.get("price") or {}
            if pr.get("currency") != "EUR":
                continue
            ship = None
            costs = [float(o["shippingCost"]["value"]) for o in (it.get("shippingOptions") or [])
                     if o.get("shippingCost") and o["shippingCost"].get("currency") == "EUR"]
            if costs:
                ship = min(costs)
            sel = it.get("seller") or {}
            pct = sel.get("feedbackPercentage")
            n = sel.get("feedbackScore")
            out.append(item(
                title=it.get("title", ""), item_eur=float(pr["value"]), ship_eur=ship,
                url=(it.get("itemWebUrl") or "").split("?")[0], source="ebay", seller=sel.get("username", ""),
                seller_pct=float(pct) if pct not in (None, "") else None,
                seller_n=int(n) if n not in (None, "") else None,
                item_id=it.get("itemId"), condition_new=True,
            ))
    except Exception as e:
        return out, f"eBay API (ricerca {code}): {e}"
    return out, None


def ebay_api_details(token, item_id, cfg):
    """Disponibilità e lingua dichiarata dall'inserzionista. Ritorna dict (campi None se non disponibili)."""
    res = {"in_stock": None, "language": None}
    try:
        r = requests.get(f"{EBAY_API}/buy/browse/v1/item/{quote(item_id, safe='')}",
                         headers=_api_headers(token, cfg), timeout=30)
        r.raise_for_status()
        d = r.json()
        av = d.get("estimatedAvailabilities") or []
        if av:
            res["in_stock"] = any(
                a.get("estimatedAvailabilityStatus") == "IN_STOCK" or (a.get("estimatedAvailableQuantity") or 0) > 0
                for a in av)
        for a in d.get("localizedAspects", []) or []:
            if re.search(r"lingua|language", a.get("name", ""), re.I):
                res["language"] = a.get("value")
    except Exception:
        pass
    return res


# ---------------------------------------------------------------- eBay HTML (non ufficiale)
def _parse_ship(text):
    if re.search(r"spedizione gratuita|consegna gratuita|free (delivery|shipping|postage)", text, re.I):
        return 0.0
    m = re.search(r"\+\s*(?:EUR|€)\s*(\d+(?:\.\d{3})*,\d{2}|\d+[.,]\d{2})\s*(?:di\s+)?(?:spedizione|consegna)", text, re.I)
    if m:
        return parse_eur(m.group(1))
    return None


def _parse_ebay_html(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for it in soup.select("li.s-item, li.s-card"):
        t = it.select_one(".s-item__title, .s-card__title")
        p = it.select_one(".s-item__price, .s-card__price")
        a = it.select_one("a.s-item__link, a.s-card__link, a[href*='/itm/']")
        if not (t and p and a):
            continue
        price = parse_eur(p.get_text(" "))
        if price is None:
            continue
        out.append({"title": t.get_text(" ", strip=True), "price": price,
                    "url": a.get("href", "").split("?")[0], "ship": _parse_ship(it.get_text(" ", strip=True))})
    return out


def ebay_html_search(code):
    url = ("https://www.ebay.it/sch/i.html?_nkw=" + quote_plus(_query(code))
           + "&LH_BIN=1&LH_ItemCondition=1000&_sop=15&_ipg=60")
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        rows = _parse_ebay_html(r.text)
    except Exception as e:
        return [], f"eBay pagine ({code}): {e}"
    items = [item(title=x["title"], item_eur=x["price"], ship_eur=x["ship"], url=x["url"], source="ebay",
                  condition_new=True) for x in rows]
    return items, (None if items else f"eBay pagine ({code}): nessun risultato leggibile")


def ebay_sold_html(code):
    """Venduti effettivi (prezzo articolo, senza spedizione). Ritorna [(titolo, prezzo)]."""
    url = ("https://www.ebay.it/sch/i.html?_nkw=" + quote_plus(_query(code))
           + "&LH_Sold=1&LH_Complete=1&LH_ItemCondition=1000&_sop=13&_ipg=60")
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        return [(x["title"], x["price"]) for x in _parse_ebay_html(r.text)], None
    except Exception as e:
        return [], f"eBay venduti ({code}): {e}"


# ---------------------------------------------------------------- Vinted / negozi (non ufficiali)
def vinted_search(code, cfg):
    fee_pct, fee_fix = cfg["vinted"]["fee_pct"], cfg["vinted"]["fee_fissa_eur"]
    out = []
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        s.get("https://www.vinted.it", timeout=30)
        r = s.get("https://www.vinted.it/api/v2/catalog/items",
                  params={"search_text": f"one piece {code} box", "order": "price_low_to_high", "per_page": 20},
                  timeout=30)
        for it in r.json().get("items", []):
            price = float(it["price"]["amount"])
            out.append(item(title=it["title"], item_eur=price, fees_eur=round(fee_fix + price * fee_pct / 100, 2),
                            url=it["url"], source="vinted", seller=(it.get("user") or {}).get("login", "")))
    except Exception as e:
        return out, f"Vinted ({code}): {e}"
    return out, None


_tp_cache = {}


def trustpilot(domain):
    if domain in _tp_cache:
        return _tp_cache[domain]
    score = None
    try:
        r = requests.get(f"https://it.trustpilot.com/review/{domain}", headers=HEADERS, timeout=30)
        if r.status_code == 200:
            m = re.search(r'"ratingValue"\s*:\s*"?([0-9.]+)"?', r.text)
            score = float(m.group(1)) if m else None
    except Exception:
        pass
    _tp_cache[domain] = score
    return score


def shop_search(shop, code, use_trustpilot):
    """Negozi Shopify (endpoint pubblico di ricerca)."""
    out = []
    try:
        r = requests.get(
            f"https://{shop['domain']}/search/suggest.json",
            params={"q": f"one piece {code} booster box", "resources[type]": "product", "resources[limit]": 5},
            headers=HEADERS, timeout=30,
        )
        trust = trustpilot(shop["domain"]) if use_trustpilot else None
        for p in r.json()["resources"]["results"]["products"]:
            price = float(p.get("price", 0) or 0)
            if price:
                out.append(item(title=p["title"], item_eur=price, ship_eur=shop.get("spedizione_eur"),
                                url=f"https://{shop['domain']}{p['url']}", source="shop",
                                seller=shop["name"], trust=trust, condition_new=True))
    except Exception as e:
        return out, f"Negozio {shop['name']} ({code}): {e}"
    return out, None
