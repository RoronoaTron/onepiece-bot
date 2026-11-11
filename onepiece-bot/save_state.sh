#!/usr/bin/env bash
# Salva nel repository i file della cartella data/ (storico, alert, ultimi prezzi).
set -e
git config user.name "onepiece-bot"
git config user.email "onepiece-bot@users.noreply.github.com"
git add data
if git diff --cached --quiet; then echo "Nessuna modifica da salvare"; exit 0; fi
git commit -q -m "Aggiorna dati"
for i in 1 2 3 4; do
  if git pull --rebase -q && git push -q; then exit 0; fi
  sleep $((i * 3))
done
exit 1
