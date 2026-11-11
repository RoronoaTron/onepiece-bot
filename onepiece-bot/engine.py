"""Verifica, classificazione e formattazione delle offerte."""
import re
import statistics

from common import esc, fmt_eur, fmt_pct

AFFARE, CONV, NORMALE, NO_SOGLIA = "affare", "conveniente", "normale", "senza_soglia"
ICON = {AFFARE: "🔥", CONV: "✅", NORMALE: "⚪", NO_SOGLIA: "❔"}
LABEL = {AFFARE: "AFFARE", CONV: "CONVENIENTE", NORMALE: "NORMALE", NO_SOGLIA: "SENZA SOGLIA"}

BAD_WORDS = [
    "bustina", "booster pack", "singol", "empty", "vuot", "damaged", "danneggiat", "ripack", "resealed",
    "illustration", "double pack", "fresh box", "blister", "starter", "deck", "tin", "gift", "custodia", "vetrina", "acril", "acryl", "protector", "protezion", "storage", "topper", "aperto", "opened", "playmat", "sleeve", "proxy", "custom", "lotto", "case", "carton", "psa", "bgs", "replica",
]
BAD_LANG = ["jap", "giapp", "jpn", "chinese", "cinese", "korean", "coreano", "thai", "simplified", "french", "francese", "german", "tedesco", "spanish", "spagnolo", "portuguese"]
EN_RE = re.compile(r"\b(eng|english|inglese)\b", re.I)


def set_regex(code):
    m = re.match(r"([A-Za-z]+)(\d+)$", code)
    return re.compile(rf"\b{m.group(1).lower()}[\s\-]?0?{int(m.group(2))}\b(?![- ]\d{{3}}\b)", re.I)


def title_ok(title, set_re, lang="EN"):
    tl = title.lower()
    if not set_re.search(tl) or not re.search(r"box|display|scatola", tl):
        return False
    if any(w in tl for w in BAD_WORDS) or re.search(r"\b(?:[2-9]|1[0-9])\s*(?:x\s*)?(?:box|display)\b|\b(?:box|display)\s*[x×]\s*\d", tl):
        return False
    if lang == "EN" and any(w in tl for w in BAD_LANG):
        return False
    return True


# ---------------------------------------------------------------- mercato e soglie
def market_label(m):
    if m.get("source") == "sold_ebay":
        d = (m.get("date") or "")[:10]
        return f"mediana venduti eBay, n={m.get('n')}, {d[8:10]}/{d[5:7]}"
    return "stima storica del database, non verificata su Cardmarket"


def thresholds(ref_e, market):
    """Soglie dal JSON; se il mercato è verificato (venduti eBay) si scalano con gli stessi rapporti."""
    if not ref_e or "excellent_buy_at_or_below_eur" not in ref_e:
        return None
    ex, mx, base = ref_e["excellent_buy_at_or_below_eur"], ref_e["max_recommended_buy_eur"], ref_e["cardmarket_reference_min_eur"]
    if market.get("source") == "sold_ebay":
        return {"excellent": round(market["value"] * ex / base, 2), "max": round(market["value"] * mx / base, 2)}
    return {"excellent": ex, "max": mx}


def market_from_sold(sold, code, ref_value, cfg, now_iso):
    """Valore di mercato da venduti eBay: solo titoli ENG espliciti, almeno n_min, valore plausibile."""
    set_re = set_regex(code)
    prices = [p for t, p in sold if title_ok(t, set_re, "EN") and EN_RE.search(t)]
    if len(prices) < cfg["verifica"]["venduti_min_n"]:
        return None
    med = statistics.median(prices)
    if not (0.5 * ref_value <= med <= 2.0 * ref_value):
        return None  # incoerente col riferimento: scartato
    return {"value": round(med, 2), "source": "sold_ebay", "n": len(prices), "date": now_iso, "verified": True}


# ---------------------------------------------------------------- valutazione
def evaluate(items, code, thr, market, cfg):
    v = cfg["verifica"]
    lang = cfg.get("lingua", "EN").upper()
    set_re = set_regex(code)
    floor = market["value"] * v["prezzo_minimo_pct_mercato"] / 100
    seen, out = set(), []
    for it in items:
        if not it["url"] or it["url"] in seen:
            continue
        seen.add(it["url"])
        if it["item_eur"] is None or not title_ok(it["title"], set_re, lang):
            continue
        if it["item_eur"] <= 0:
            continue
        if it.get("in_stock") is False:                  # non disponibile
            continue
        l = it.get("language")
        if lang == "EN" and not EN_RE.search(it["title"]) and not (l and re.search(r"ingl|english|\beng?\b", l, re.I)):
            continue
        if l and lang == "EN" and not re.search(r"ingl|english|\beng?\b", l, re.I):
            continue
        if it["source"] == "ebay":
            if it.get("seller_pct") is not None and it["seller_pct"] < v["min_seller_pct"]:
                continue
            if it.get("seller_n") is not None and it["seller_n"] < v["min_seller_feedback"]:
                continue
        if it.get("trust") is not None and it["trust"] < v["min_trustpilot"]:
            continue

        warnings, checks = [], []
        if l or EN_RE.search(it["title"]):
            checks.append("ENG")
        else:
            warnings.append("lingua non esplicita")
        if it["item_eur"] < floor:
            warnings.append("prezzo molto basso: verificare prodotto e sigillo")
        if it.get("condition_new"):
            checks.append("nuovo")
        else:
            warnings.append("condizioni non verificate")
        if it.get("in_stock"):
            checks.append("disponibile")
        else:
            warnings.append("disponibilità non verificata")
        if not re.search(r"sealed|sigillat|factory seal|\bovp\b", it["title"], re.I):
            warnings.append("sigillo non esplicito nel titolo")
        ship = it.get("ship_eur")
        if ship is None:
            warnings.append("spedizione non verificata")
        reliability = "n/d"
        if it.get("seller_pct") is not None:
            reliability = f"{fmt_pct(it['seller_pct'])} positivi, {it.get('seller_n', 0)} feedback"
        elif it.get("trust") is not None:
            reliability = f"Trustpilot {str(it['trust']).replace('.', ',')}/5"
        else:
            warnings.append("venditore non verificato")

        total = round(it["item_eur"] + (ship or 0.0) + (it.get("fees_eur") or 0.0), 2)
        complete_total = ship is not None and it.get("fees_eur") is not None
        if it.get("fees_eur") is None:
            warnings.append("commissioni non verificate")
        cls = NO_SOGLIA
        if thr and complete_total and "ENG" in checks:
            cls = AFFARE if total <= thr["excellent"] else CONV if total <= thr["max"] else NORMALE
            if cls == AFFARE and warnings:               # un AFFARE richiede tutte le verifiche
                cls = CONV
        out.append({
            "title": it["title"][:90], "url": it["url"], "source": it["source"], "seller": it.get("seller") or "",
            "reliability": reliability, "item_eur": it["item_eur"], "ship_eur": ship, "fees_eur": it.get("fees_eur") or 0.0,
            "total_eur": total, "total_complete": complete_total, "price_kind": "asking", "cls": cls, "saving_pct": round((market["value"] - total) / market["value"] * 100, 1),
            "checks": checks, "warnings": warnings, "item_id": it.get("item_id"),
        })
    out.sort(key=lambda o: (not o["total_complete"], o["total_eur"]))
    return out


# ---------------------------------------------------------------- formattazione
def source_label(o):
    return {"ebay": "eBay", "vinted": "Vinted"}.get(o["source"], o["seller"] or "Negozio")


def fmt_offer(o, code, name, market):
    lines = [f"<b>{ICON[o['cls']]} {LABEL[o['cls']]} – {esc(code)} {esc(name)}</b>"]
    comp = f"articolo {fmt_eur(o['item_eur'])}"
    comp += f" + sped. {fmt_eur(o['ship_eur'])}" if o["ship_eur"] is not None else " + sped. n/d"
    if o["fees_eur"]:
        comp += f" + commissioni {fmt_eur(o['fees_eur'])}"
    qualifier = "totali" if o.get("total_complete", False) else "minimo noto; totale da verificare"
    lines.append(f"💶 <b>{fmt_eur(o['total_eur'])}</b> {qualifier} ({comp}) · prezzo richiesto")
    sav = o["saving_pct"]
    sav_txt = f"{fmt_pct(sav)} sotto il riferimento" if sav >= 0 else f"{fmt_pct(-sav)} sopra il riferimento"
    lines.append(f"📊 Riferimento {fmt_eur(market['value'], 0)} ({market_label(market)}) → {sav_txt}")
    who = source_label(o) + (f" – {esc(o['seller'])}" if o["source"] in ("ebay", "vinted") and o["seller"] else "")
    lines.append(f"🏪 {esc(who)} · affidabilità: {esc(o['reliability'])}")
    if o["checks"]:
        lines.append("✔ " + ", ".join(o["checks"]))
    if o["warnings"]:
        lines.append("⚠️ " + ", ".join(o["warnings"]))
    lines.append(f'🔗 <a href="{esc(o["url"])}">Apri annuncio</a>')
    return "\n".join(lines)


def good_offers(latest, limit=12):
    """Offerte AFFARE/CONVENIENTE di tutti i set, migliori per risparmio."""
    res = []
    for code, s in latest.get("sets", {}).items():
        for o in s.get("offers", []):
            if o["cls"] in (AFFARE, CONV):
                res.append((code, s, o))
    res.sort(key=lambda x: (x[2]["cls"] != AFFARE, -x[2]["saving_pct"]))
    return res[:limit]


def offer_blocks(latest, limit=12):
    return [fmt_offer(o, code, s["name"], s["market"]) for code, s, o in good_offers(latest, limit)]


def sparkline(values):
    if not values:
        return ""
    bars = "▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    if hi == lo:
        return bars[3] * len(values)
    return "".join(bars[int((v - lo) / (hi - lo) * 7)] for v in values)
