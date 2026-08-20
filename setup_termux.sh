#!/usr/bin/env bash
# Setup one-shot per Termux (Android): installa Python + dropbox e
# prepara la cartella drpbx per la sync.
#
# Uso (dentro Termux):
#   pkg install -y git   # se vuoi clonare gli script via git
#   bash setup_termux.sh
#
# Poi copia qui refresh_token.txt oppure esegui una volta:
#   python dropbox_app.py   # autorizza nel browser e salva il token
set -e

echo "==> Aggiornamento pacchetti..."
pkg update -y
pkg upgrade -y

echo "==> Installazione python..."
pkg install -y python

echo "==> Installazione libreria dropbox..."
pip install dropbox

echo "==> Creazione cartella sync..."
mkdir -p drpbx

echo "==> FATTO. Ora:"
echo "  1) Assicurati che qui ci siano sync.py, dbx_auth.py e refresh_token.txt"
echo "     (puoi copiarli con git, adb, o facendo il primo pull)"
echo "  2) Test della connessione:   python dropbox_app.py"
echo "  3) Sincronizza:               python sync.py pull"
echo "  4) A fine sessione:           python sync.py push"