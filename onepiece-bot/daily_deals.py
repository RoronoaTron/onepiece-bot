"""Monitor prezzi (eseguito ogni ora da GitHub Actions).
1. aggiorna il valore di mercato (venduti eBay, se verificabili) e cerca le offerte per ogni box ENG
2. aggiunge rilevazioni datate allo storico (append-only)
3. controlla gli alert  4. dopo le 09:00 invia il riepilogo giornaliero (una volta al giorno)
"""
import datetime as dt
import json
import os
import time
from zoneinfo import ZoneInfo

import engine
import sources
import storage
from common import broadcast, esc, fmt_eur

CFG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), encoding="utf-8"))
PAUSE = float(os.environ.get("SCAN_PAUSE", "1.2"))


def load_last_history():
    last = {}
    for r in storage.history_read():
        last[(r["set"], r["kind"])] = r
    return last


def record(last, now, code, kind, price, n, source):
    """Nuova rilevazione datata; salta i doppioni (stesso prezzo ±2% entro 6 ore)."""
    prev = last.get((code, kind))
    if prev:
        age = (now - dt.datetime.fromisoformat(prev["ts"])).total_seconds()
        if age < 6 * 3600 and abs(prev["price_eur"] - price) <= 0.02 * prev["price_eur"]:
            return
    rec = {"ts": now.isoformat(timespec="minutes"), "set": code, "kind": kind,
           "price_eur": round(price, 2), "n": n, "source": source}
    storage.history_append(rec)
    last[(code, kind)] = rec


def update_market(code, ref_e, prev_market, now, errors, last):
    base = {"value": ref_e["cardmarket_reference_min_eur"], "source": "ref_json", "n": 0, "date": None, "verified": False}
    pm = prev_market or {}
    fresh = None
    if pm.get("source") == "sold_ebay" and pm.get("date"):
        age = now - dt.datetime.fromisoformat(pm["date"])
        if age < dt.timedelta(hours=20):
            return pm                                       # già aggiornato oggi
        if age < dt.timedelta(days=30):
            fresh = pm                                      # fallback se la nuova lettura fallisce
    if CFG["fonti"]["ebay_venduti_html"]:
        sold, err = sources.ebay_sold_html(code)
        time.sleep(PAUSE)
        if err:
            errors.append(err)
        m = engine.market_from_sold(sold, code, base["value"], CFG, now.isoformat(timespec="minutes"))
        if m:
            record(last, now, code, "sold_median", m["value"], m["n"], "ebay_venduti_html")
            return m
    return fresh or base


def scan_set(code, name, ref_e, prev_market, token, now, errors, last):
    market = update_market(code, ref_e, prev_market, now, errors, last)
    thr = engine.thresholds(ref_e, market)
    pmin, pmax = market["value"] * CFG["verifica"]["prezzo_minimo_pct_mercato"] / 100, market["value"] * 1.6

    items = []
    if CFG["fonti"]["ebay_api"] and token:
        its, err = sources.ebay_api_search(token, code, pmin, pmax, CFG)
        items += its
        err and errors.append(err)
        if err and CFG["fonti"]["ebay_html"]:
            fallback, fallback_error = sources.ebay_html_search(code)
            items += fallback
            fallback_error and errors.append(fallback_error)
    elif CFG["fonti"]["ebay_html"]:
        its, err = sources.ebay_html_search(code)
        items += its
        err and errors.append(err)
    time.sleep(PAUSE)
    if CFG["fonti"]["vinted"]:
        its, err = sources.vinted_search(code, CFG)
        items += its
        err and errors.append(err)
        time.sleep(PAUSE)
    if CFG["fonti"]["negozi"]:
        for shop in CFG.get("negozi", []):
            its, err = sources.shop_search(shop, code, CFG["fonti"]["trustpilot"])
            items += its
            err and errors.append(err)
            time.sleep(PAUSE)

    if token:
        cands = [i for i in items if i["source"] == "ebay" and i.get("item_id")
                 and engine.title_ok(i["title"], engine.set_regex(code))]
        cands.sort(key=lambda i: i["item_eur"])
        for candidate in cands[: CFG["verifica"]["max_candidati_verifica"]]:
            candidate.update(sources.ebay_api_details(token, candidate["item_id"], CFG))
    offers = engine.evaluate(items, code, thr, market, CFG)

    complete = [o for o in offers if o.get("total_complete")]
    if complete:
        record(last, now, code, "ask_min_total", complete[0]["total_eur"], len(complete), "monitor")
    return {"name": name, "market": market, "thresholds": thr, "n_offerte": len(offers), "n_candidati": len(items), "offers": offers[:5]}


def check_alerts(latest, now):
    alerts, astate = storage.load("alerts.json", []), storage.load("alerts_state.json", {})
    changed = False
    for a in alerts:
        if a["id"] in astate:
            continue
        s = latest["sets"].get(a["code"])
        if not s or not s["offers"]:
            continue
        best = s["offers"][0]
        if best.get("total_complete") and "ENG" in best.get("checks", []) and not best.get("warnings") and best["total_eur"] <= a["target_eur"]:
            head = f"🔔 <b>ALERT {esc(a['code'])}</b>: sceso a {fmt_eur(best['total_eur'])} (soglia {fmt_eur(a['target_eur'])})"
            broadcast([head + "\n" + engine.fmt_offer(best, a["code"], s["name"], s["market"])])
            astate[a["id"]] = {"fired": now.isoformat(timespec="minutes"), "price_eur": best["total_eur"]}
            changed = True
    if changed:
        storage.save("alerts_state.json", astate)


def daily_summary(latest, now):
    blocks = [f"📦 <b>One Piece TCG ENG – riepilogo del {now:%d/%m/%Y}</b>"]
    good = engine.offer_blocks(latest)
    if not good:
        good = [engine.fmt_offer(s["offers"][0], code, s["name"], s["market"])
                for code, s in latest["sets"].items() if s["offers"]][:8]
    if good:
        blocks += good
    else:
        blocks.append("Nessun affare o offerta conveniente oggi.")
    n_sets = len(latest["sets"])
    n_with = sum(1 for s in latest["sets"].values() if s["offers"])
    blocks.append(f"Set monitorati: {n_sets}, con almeno un'inserzione valida: {n_with}.")
    blocks += [f"ℹ️ {esc(n)}" for n in latest.get("notes", [])]
    if latest.get("errors"):
        blocks.append("⚠️ Fonti con problemi: " + esc("; ".join(latest["errors"][:5])))
    return blocks


def main():
    tz = ZoneInfo(CFG["timezone"])
    now = dt.datetime.now(tz)
    ref = storage.load("reference.json", {"sets": []})
    if not ref.get("sets"):
        raise RuntimeError("Database espansioni assente o vuoto: controllare ONEPIECE_DATA_DIR/reference.json")
    prev = storage.load("latest.json", {"sets": {}})
    last = load_last_history()
    errors, notes = [], []

    token, err = (sources.ebay_token() if CFG["fonti"]["ebay_api"] else (None, None))
    if err:
        errors.append(err)
    if not token:
        notes.append("eBay API non configurata: leggo le pagine di eBay (venditore e disponibilità non verificabili, "
                     "quindi niente 🔥 AFFARE da quella fonte).")

    latest = {"updated": now.isoformat(timespec="minutes"), "sets": {}}
    for e in ref["sets"]:
        code = e["code"]
        latest["sets"][code] = scan_set(code, e["name"], e, (prev["sets"].get(code) or {}).get("market"),
                                        token, now, errors, last)
    latest["errors"] = list(dict.fromkeys(errors))
    notes.append("Cardmarket: solo link, nessuna quotazione live autorizzata. Vinted: " + ("attivo (totale e commissioni da verificare)." if CFG["fonti"]["vinted"] else "disattivato; nessun prezzo acquisito."))
    notes.append("Prezzi richiesti EUR; non equivalgono a vendite concluse. Riferimenti e soglie del database sono stime non verificate.")
    latest["notes"] = notes
    storage.save("latest.json", latest)

    check_alerts(latest, now)

    state = storage.load("state.json", {})
    today = now.date().isoformat()
    force = os.environ.get("FORCE_DAILY", "").lower() == "true"
    if force or (now.hour >= CFG["ora_riepilogo"] and state.get("last_daily") != today):
        broadcast(daily_summary(latest, now))
        state["last_daily"] = today
        storage.save("state.json", state)


if __name__ == "__main__":
    main()
