# One Piece TCG ENG — Telegram

Monitor su GitHub Actions pubblico: ogni ora, comandi ogni circa 5 minuti, riepilogo dopo le 09:00 Europe/Rome. Gli orari possono subire ritardi. Nessun servizio a pagamento aggiunto.

## Correzione del monitor

Il catalogo era nella data/ della radice, mentre il programma cercava in onepiece-bot/data/. Ora tutti i dati operativi usano data/ della radice; un catalogo vuoto fa fallire il job con errore esplicito. I vecchi file annidati sono conservati ma non usati. I workflow serializzano le scritture dello stato.

## Secrets GitHub

Configurare TELEGRAM_TOKEN e TELEGRAM_CHAT_ID (ID autorizzati separati da virgola: privato e/o gruppo). Non servono chiavi eBay: la modalità attiva usa soltanto le pagine pubbliche eBay, senza API. Non inserire credenziali nei file o in chat. Il CAP di consegna gia configurato e 00100: verificare la spedizione per la destinazione effettiva.

## Prezzi e fonti

- eBay: ricerca HTML pubblica per box sigillati ENG e singole carte, solo prezzi richiesti EUR. Le API sono disattivate. Gli errori HTTP e le pagine illeggibili vengono segnalati; non vengono aggirati blocchi.
- Nessun prezzo richiesto viene presentato come vendita conclusa. Browse non restituisce i venduti; le pagine pubbliche non certificano il prezzo di una proposta accettata. Le mediane automatiche da tali pagine sono disabilitate.
- Cardmarket: nessuna ricerca attiva. I riferimenti del database sono stime storiche non verificate, non prezzi aggiornati.
- Vinted: integrazione opzionale conservata, disattivata di default. Se attivata, spedizione e commissioni non note restano da verificare. Nessun aggiramento di accessi o blocchi.
- Negozi e Trustpilot: disattivati nella modalità solo eBay.
- Carte: solo annunci eBay; nessuna chiamata OPTCG, TCGplayer o API di cambio. Varianti, lingua e feedback vanno verificati nella singola inserzione.

Totali incompleti sono indicati come minimo noto. Gli alert richiedono totale completo, lingua ENG, nuovo, sigillo dichiarato, disponibilita e reputazione verificata. Il riepilogo mostra anche inserzioni con avvertenze, senza etichettarle come affari verificati.

## Catalogo e comandi

23 espansioni ENG pubblicate al 11/11/2026: OP01–OP17, EB01–EB03 ed EB05, PRB01–PRB02. OP14 e OP15 includono EB04 nella versione inglese; non si aggiunge un box EB04 separato. Fonte: https://en.onepiece-cardgame.com/products/?page=1&subcategory=boosters (pagine 1–3). Le nuove uscite richiedono aggiornamento del catalogo dopo verifica ufficiale.

/prezzi, /offerte, /box OP13, /storico OP13, /alert OP13 200, /alert, /alert OP13 off, /carta OP13-017, /id, /help. Gli alert sono condivisi. Un ID di gruppo autorizza i membri del gruppo, compreso un gruppo di tre persone. Con privacy Telegram attiva usare /carta nei gruppi: i codici scritti senza slash potrebbero non arrivare al bot.

## Collaudo reale

Avviare Monitor prezzi con force_daily=true. Verificare data/latest.json: 23 set, candidati, offerte ed errori per fonte. Avviare Risposte comandi con verify_commands=true per verificare getMe, accesso al gruppo e invio delle risposte help, box e carta alle chat configurate. Un retry dopo invio parziale puo duplicare messaggi nelle chat gia raggiunte. I secrets e gli ID non vengono stampati nei log. I dati prezzi e le soglie alert sono pubblici nel repository.
