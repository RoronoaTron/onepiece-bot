"""Verifica reale su richiesta; nessun token o chat ID nei log."""
import common
import poll_cards
from cards import build_reply

def main():
    common.telegram_request("getMe", {})
    print("Autenticazione Telegram: OK")
    if not common.CHAT_IDS:
        raise RuntimeError("Nessuna chat configurata")
    for chat_id in common.CHAT_IDS:
        chat = common.telegram_request("getChat", {"chat_id": chat_id})["result"]
        if chat.get("type") in ("group", "supergroup"):
            result = common.telegram_request("getChatMemberCount", {"chat_id": chat_id})
            print("Accesso gruppo: OK; membri (bot inclusi):", result["result"])
    latest = poll_cards.load_latest()
    if not latest or not any(s.get("offers") for s in latest["sets"].values()):
        raise RuntimeError("Nessuna offerta live salvata: eseguire prima il monitor")
    common.broadcast(["🧪 <b>Verifica bot</b> · accesso Telegram e offerte salvate: OK", poll_cards.HELP])
    common.broadcast(poll_cards.h_box("OP13", None))
    common.broadcast([build_reply("OP13-017")])
    print("Risposte help, box OP13 e carta OP13-017: accettate da Telegram per tutte le chat configurate")

if __name__ == "__main__":
    main()
