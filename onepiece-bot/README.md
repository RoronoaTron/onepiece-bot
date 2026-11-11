# One Piece TCG – tracker prezzi box ENG (Telegram, costo 0)

Gira su GitHub Actions (repository pubblico). Dati in `data/` (storico append-only `history.jsonl`).

- **Monitor** (ogni ora): cerca offerte, aggiorna lo storico, controlla gli alert, dopo le 09:00 manda il riepilogo.
- **Comandi** (controllo ogni ~5 min): /prezzi /offerte /box /storico /alert /carta /id /help.

## Segreti GitHub (Settings → Secrets and variables → Actions)
- `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` (es. `357230695,-100123...` utente e gruppo)
- facoltativi ma consigliati: `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` (chiavi gratuite eBay Developer, API Browse).
  Senza chiavi il bot legge le pagine eBay: non può verificare venditore e disponibilità, quindi nessun 🔥 AFFARE da eBay.

## Dati e soglie
`data/reference.json` = database iniziale (non verificato in tempo reale, non viene mai modificato dal bot).
Il bot aggiunge rilevazioni datate a `data/history.jsonl` senza sovrascrivere nulla. Il valore di mercato diventa
"verificato" solo con ≥5 venduti eBay ENG recenti; in quel caso le soglie del JSON vengono scalate con gli stessi rapporti.

## Limiti
- Cardmarket: nessuna API gratuita aperta → solo link e riferimento dal JSON.
- eBay venduti, Vinted, negozi, Trustpilot: lettura pagine non ufficiale, può rompersi o non essere consentita
  dai termini dei siti. Ogni fonte si spegne in `config.json` → `fonti`.
- Le Actions programmate su repo pubblici vengono sospese dopo 60 giorni senza attività del repo
  (qui i commit dei dati contano come attività).
- Il repository è pubblico: tutto in `data/` (anche gli alert) è visibile a chiunque. Gli alert non contengono chat ID.
