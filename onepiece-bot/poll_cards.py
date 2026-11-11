"""Legge i messaggi nuovi su Telegram e risponde ai codici carta. Stateless: conferma gli update da solo."""
import requests

from cards import build_reply, is_card_code
from common import OWNER_CHAT_ID, TOKEN, send

API = f"https://api.telegram.org/bot{TOKEN}"


def main():
    r = requests.get(f"{API}/getUpdates", params={"timeout": 0}, timeout=30).json()
    updates = r.get("result", [])
    if not updates:
        return
    for u in updates:
        msg = u.get("message") or {}
        chat_id = str((msg.get("chat") or {}).get("id", ""))
        text = (msg.get("text") or "").strip()
        if not chat_id or not text:
            continue
        if OWNER_CHAT_ID and chat_id != OWNER_CHAT_ID:
            continue
        if text.startswith("/start") or text.startswith("/help"):
            send(chat_id, "Scrivimi il codice di una carta, es. <b>OP13-017</b>, e ti do prezzo e ultimi venduti.")
        elif is_card_code(text):
            try:
                send(chat_id, build_reply(text))
            except Exception as e:
                send(chat_id, f"Errore nella ricerca: {e}")
        else:
            send(chat_id, "Scrivimi solo il codice carta, es. OP13-017.")
    last = max(u["update_id"] for u in updates)
    requests.get(f"{API}/getUpdates", params={"offset": last + 1, "timeout": 0}, timeout=30)


if __name__ == "__main__":
    main()
