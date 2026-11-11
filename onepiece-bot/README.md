# Bot Telegram One Piece TCG (costo 0)

- **Ogni giorno** ti manda le offerte dei box vicino al retail (negozi con voto Trustpilot, eBay, Vinted).
- **Scrivi un codice carta** (es. `OP13-017`) e ricevi prezzo di mercato, ultimi venduti eBay.it e link Cardmarket.

Gira interamente su GitHub Actions (gratis con repository pubblico).

## Setup (circa 5 minuti, una sola volta)

1. **Token bot**: su Telegram apri @BotFather → `/newbot` → copia il token.
2. **Chat ID**: scrivi un messaggio qualsiasi al tuo nuovo bot, poi apri nel browser
   `https://api.telegram.org/bot<TOKEN>/getUpdates` e copia il numero in `"chat":{"id":...}`.
3. **GitHub**: crea un repository **pubblico** e carica tutti questi file (cartella `.github` inclusa).
4. Nel repo: *Settings → Secrets and variables → Actions → New repository secret*:
   - `TELEGRAM_TOKEN` = il token
   - `TELEGRAM_CHAT_ID` = il tuo chat id
5. Scheda *Actions*: abilita i workflow e lancia a mano "Offerte box giornaliere" per provare.

## Personalizzazione
`config.json`: box da monitorare, prezzo retail, tolleranza %, voto Trustpilot minimo, negozi
(i negozi devono essere basati su Shopify per essere letti in automatico).

## Limiti onesti
- Risposta ai codici carta con ritardo fino a ~5-10 minuti (cron di GitHub). Per risposte istantanee serve un hosting sempre acceso.
- **Cardmarket** non ha un'API gratuita aperta: il prezzo numerico arriva da TCGplayer (USD) tramite OPTCG API; per Cardmarket ricevi il link diretto.
- **eBay venduti** e **Vinted** sono letti via scraping: possono smettere di funzionare se cambiano le pagine o bloccano le richieste. In quel caso ricevi comunque il link alla ricerca.
- Il codice non è stato testato dal vivo (nessun accesso di rete dal mio ambiente): al primo avvio controlla i log in *Actions*.
