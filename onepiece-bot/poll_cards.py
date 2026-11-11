"""Legge i messaggi nuovi su Telegram (chat privata o gruppo) e risponde ai comandi.
Stateless: conferma gli update da solo. Scrive solo data/alerts.json."""
import datetime as dt
import re
import time

import requests

import engine
import storage
from cards import build_reply, extract_code, cardmarket_link
from common import CHAT_IDS, TOKEN, esc, fmt_eur, send, send_long, telegram_request

API = f"https://api.telegram.org/bot{TOKEN}"

HELP = (
    "<b>Comandi</b>\n"
    "/prezzi – valore di mercato di tutti i box\n"
    "/offerte – migliori offerte ora\n"
    "/box OP13 – prezzi, offerte e andamento di un set\n"
    "/storico OP13 – storico delle rilevazioni\n"
    "/alert OP13 200 – avviso quando OP13 scende a 200 € (totale con spedizione)\n"
    "/alert – elenca gli alert · /alert OP13 off – li cancella\n"
    "/carta OP13-017 – valore di una carta\n"
    "Puoi anche scrivere solo il codice carta, es. OP13-017."
)
NO_DATA = ["Dati non ancora disponibili: il monitor non ha ancora girato. Avvialo da GitHub → Actions → Monitor prezzi."]


def norm_code(s):
    c = re.sub(r"[^A-Za-z0-9]", "", s or "").upper()
    return c if re.fullmatch(r"[A-Z]{2,4}\d{2}", c) else None


def load_latest():
    d = storage.load("latest.json", None)
    return d if d and d.get("sets") else None


def _updated(latest):
    return f"Aggiornato: {latest['updated'][8:10]}/{latest['updated'][5:7]} {latest['updated'][11:16]}"


def h_prezzi(args, ctx):
    latest = load_latest()
    if not latest:
        return NO_DATA
    lines = ["<b>Box ENG · prezzi richiesti e riferimenti</b>"]
    for code, s in latest["sets"].items():
        m = s["market"]
        mk = fmt_eur(m["value"], 0) + ("" if m["source"] == "sold_ebay" else "*")
        best = s["offers"][0] if s["offers"] else None
        b = f" · migliore {fmt_eur(best['total_eur'], 0)} {engine.ICON[best['cls']]}" if best else ""
        lines.append(f"{code}: {mk}{b}")
    lines.append("\n* stima storica del database, non quotazione Cardmarket verificata. Senza *: mediana venduti eBay.")
    lines.append(_updated(latest))
    return ["\n".join(lines)]


def h_offerte(args, ctx):
    latest = load_latest()
    if not latest:
        return NO_DATA
    blocks = engine.offer_blocks(latest)
    if not blocks:
        blocks = ["Nessun affare verificato. Inserzioni con prezzi richiesti:"]
        blocks += [engine.fmt_offer(s["offers"][0], code, s["name"], s["market"])
                   for code, s in latest["sets"].items() if s["offers"]][:8]
    return blocks + [_updated(latest)]


def _series(code, kind):
    rows = {}
    for r in storage.history_read(code):
        if r["kind"] == kind:
            rows[r["ts"][:10]] = r            # ultima rilevazione del giorno
    return [rows[d] for d in sorted(rows)]


def _trend(code, kind, days=7):
    ser = _series(code, kind)
    if len(ser) < 2:
        return None
    cur = ser[-1]
    target = (dt.date.fromisoformat(cur["ts"][:10]) - dt.timedelta(days=days)).isoformat()
    old = [r for r in ser[:-1] if r["ts"][:10] <= target]
    ref = old[-1] if old else ser[0]
    if ref["price_eur"] <= 0:
        return None
    return (cur["price_eur"] - ref["price_eur"]) / ref["price_eur"] * 100, ref["ts"][:10]


def h_box(args, ctx):
    code = norm_code(args)
    latest = load_latest()
    if not latest:
        return NO_DATA
    if not code or code not in latest["sets"]:
        return ["Uso: /box OP13 (set monitorati: " + ", ".join(latest["sets"]) + ")"]
    s = latest["sets"][code]
    m, thr = s["market"], s["thresholds"]
    out = [f"<b>{esc(code)} – {esc(s['name'])}</b>\nMercato {fmt_eur(m['value'], 0)} ({engine.market_label(m)})"]
    if thr:
        out[0] += f"\nSoglie: 🔥 ≤ {fmt_eur(thr['excellent'], 0)} · ✅ ≤ {fmt_eur(thr['max'], 0)}"
    tr = _trend(code, "ask_min_total")
    if tr:
        out[0] += f"\nAndamento minimo offerte: {tr[0]:+.1f}% dal {tr[1][8:10]}/{tr[1][5:7]}".replace(".", ",")
    if s["offers"]:
        out += [engine.fmt_offer(o, code, s["name"], m) for o in s["offers"][:3]]
    else:
        out.append("Nessuna inserzione valida trovata.")
    out.append(f'<a href="{esc(cardmarket_link(code))}">Confronta su Cardmarket</a> · prezzo live non acquisito')
    out.append(_updated(latest))
    return out


def h_storico(args, ctx):
    code = norm_code(args)
    if not code:
        return ["Uso: /storico OP13"]
    ask, sold = _series(code, "ask_min_total"), {r["ts"][:10]: r for r in _series(code, "sold_median")}
    if not ask and not sold:
        return [f"Nessuna rilevazione registrata per {code}."]
    days = sorted({r["ts"][:10] for r in ask} | set(sold))[-10:]
    ask_d = {r["ts"][:10]: r for r in ask}
    lines = [f"<b>Storico {esc(code)}</b> (ultimi {len(days)} giorni con dati)"]
    for d in days:
        parts = []
        if d in ask_d:
            parts.append(f"min offerta {fmt_eur(ask_d[d]['price_eur'])}")
        if d in sold:
            parts.append(f"venduto (mediana) {fmt_eur(sold[d]['price_eur'])} n={sold[d]['n']}")
        lines.append(f"{d[8:10]}/{d[5:7]} · " + " · ".join(parts))
    if len(ask) > 1:
        lines.append("Trend: " + engine.sparkline([r["price_eur"] for r in ask][-20:]))
    return ["\n".join(lines)]


def h_alert(args, ctx):
    alerts = storage.load("alerts.json", [])
    astate = storage.load("alerts_state.json", {})
    parts = args.split()
    if not parts:
        if not alerts:
            return ["Nessun alert. Esempio: /alert OP13 200"]
        lines = ["<b>Alert</b>"]
        for a in alerts:
            st = "scattato ✔" if a["id"] in astate else "attivo"
            lines.append(f"{a['code']} ≤ {fmt_eur(a['target_eur'], 0)} – {st}")
        return ["\n".join(lines)]
    code = norm_code(parts[0])
    latest = load_latest()
    ref_codes = set((latest or {}).get("sets", {})) or {e["code"] for e in storage.load("reference.json", {"sets": []})["sets"]}
    if not code or code not in ref_codes:
        return ["Set non riconosciuto. Esempio: /alert OP13 200"]
    if len(parts) > 1 and parts[1].lower() in ("off", "del", "cancella"):
        keep = [a for a in alerts if a["code"] != code]
        storage.save("alerts.json", keep)
        return [f"Alert su {code} cancellati ({len(alerts) - len(keep)})."]
    m = re.search(r"(\d+(?:[.,]\d+)?)", " ".join(parts[1:]))
    if not m:
        return ["Uso: /alert OP13 200"]
    price = float(m.group(1).replace(",", "."))
    if len(alerts) >= 30:
        return ["Troppi alert attivi (max 30)."]
    alerts.append({"id": str(int(time.time() * 1000)), "code": code, "target_eur": price,
                   "created": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")})
    storage.save("alerts.json", alerts)
    return [f"🔔 Alert impostato: {code} ≤ {fmt_eur(price)} (totale con spedizione). "
            "Avviso a tutto il gruppo; controllo a ogni giro del monitor (ogni ora)."]


def h_carta(args, ctx):
    code = extract_code(args)
    if not code:
        return ["Uso: /carta OP13-017"]
    return [build_reply(code)]


COMMANDS = {"/prezzi": h_prezzi, "/offerte": h_offerte, "/box": h_box, "/storico": h_storico,
            "/alert": h_alert, "/carta": h_carta}


def main():
    if not CHAT_IDS:
        raise RuntimeError("TELEGRAM_CHAT_ID non configurato: nessuna chat autorizzata")
    state = storage.load("poll_state.json", {})
    r = telegram_request("getUpdates", {"timeout": 0, "offset": state.get("offset", 0)})
    updates = r.get("result", [])
    if not updates:
        return
    for u in updates:
        msg = u.get("message") or {}
        chat = msg.get("chat") or {}
        chat_id = str(chat.get("id", ""))
        text = (msg.get("text") or "").strip()
        if not chat_id or not text:
            continue
        is_group = chat.get("type") in ("group", "supergroup")
        mid = msg.get("message_id")
        cmd, args = "", ""
        if text.startswith("/"):
            first, _, args = text.partition(" ")
            cmd, args = first.split("@")[0].lower(), args.strip()
        try:
            if cmd == "/id":  # serve per scoprire l'ID del gruppo; funziona in qualsiasi chat
                send(chat_id, f"ID di questa chat: <code>{chat_id}</code>", mid)
                continue
            if CHAT_IDS and chat_id not in CHAT_IDS:
                continue  # chat non autorizzata
            if cmd in ("/start", "/help"):
                send(chat_id, HELP, mid)
            elif cmd in COMMANDS:
                send_long(chat_id, COMMANDS[cmd](args, None), reply_to=mid)
            elif extract_code(text):
                send(chat_id, build_reply(extract_code(text)), mid)
            elif cmd or not is_group:
                if not is_group:
                    send(chat_id, "Non ho capito. /help per la lista dei comandi.", mid)
        except Exception as e:
            print("Errore durante la risposta Telegram (dettagli riservati)")
            raise RuntimeError("Risposta non inviata; update non confermato") from None
    last = max(u["update_id"] for u in updates)
    storage.save("poll_state.json", {"offset": last + 1})
    telegram_request("getUpdates", {"offset": last + 1, "timeout": 0})


if __name__ == "__main__":
    main()
