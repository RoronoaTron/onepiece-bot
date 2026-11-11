"""Ricerca carte esclusivamente nelle pagine pubbliche eBay, senza API."""
import re
from urllib.parse import quote_plus
from common import esc
import sources

CODE_RE = re.compile(r"^[A-Za-z]{2,4}\d{2}-\d{3}$")

def extract_code(text):
    t = re.sub(r"^/(carta|c)(@\w+)?\s*", "", text.strip(), flags=re.I)
    t = re.sub(r"@\w+", "", t).strip()
    return t.upper() if CODE_RE.match(t) else None

def ebay_sold(code, n=10):
    return [], "https://www.ebay.it/sch/i.html?_nkw=" + quote_plus(f"{code} one piece") + "&LH_Sold=1&LH_Complete=1&_sop=13"

def build_reply(code):
    code = code.strip().upper()
    if not CODE_RE.fullmatch(code):
        return "Codice non valido. Esempio: /carta OP13-017"
    lines = [f"<b>{esc(code)}</b>", "eBay · prezzi richiesti, non vendite concluse"]
    offers, err = sources.ebay_html_search(code)
    pattern = r"(?<![A-Z0-9])" + re.escape(code).replace(r"\-", r"[ -]?") + r"(?![0-9])"
    matching = [o for o in offers if re.search(pattern, o["title"], re.I)]
    for o in matching[:5]:
        shipping = f" + sped. €{o['ship_eur']:.2f}" if o["ship_eur"] is not None else " + spedizione n/d"
        lines.append(f'<a href="{esc(o["url"])}">{esc(o["title"][:120])}</a>: €{o["item_eur"]:.2f}{shipping}')
    if not matching:
        lines.append("Pagine eBay non accessibili o non leggibili: nessun prezzo verificato." if err else "Nessuna inserzione EUR corrispondente trovata.")
    search = "https://www.ebay.it/sch/i.html?_nkw=" + quote_plus(f"one piece {code}")
    lines.append(f'<a href="{esc(search)}">Apri ricerca eBay</a>')
    _, sold = ebay_sold(code)
    lines.append(f'<a href="{esc(sold)}">Consulta inserzioni concluse eBay</a> (prezzo effettivo di vendita non verificato)')
    lines.append("Verifica lingua ENG, variante, condizioni e feedback del venditore prima di confrontare: affidabilità non verificata automaticamente.")
    return "\n".join(lines)
