# App Dropbox (app folder)

## Setup
```bash
pip install dropbox
```

## Esegui
```bash
python dropbox_app.py
```

## Come funziona
- La **prima volta** apre il link nel browser → autorizzi l'app → incolli il codice → viene salvato `refresh_token.txt`
- Dalle volte successive si ricollega da solo, senza chiedere nulla

## Cosa può vedere
Un'app **single folder** vede **solo** la propria cartella:
```
Dropbox/Apps/<Nome della tua app>/
```
Per usare i file del tuo link condiviso (`rlkey=...`) devi **caricarli in quella cartella** — l'app non può accedere a cartelle condivise esterne. Puoi:
- caricare i file da questa app (basta aggiungere una riga con `files_upload`)
- oppure andare sul sito Dropbox e spostare i file dentro `Apps/<Nome App>/`

## Comandi utili
```python
# Upload
with open("file.jpg", "rb") as f:
    dbx.files_upload(f.read(), "/file.jpg", mute=True)

# Download
dbx.files_download_to_file("copia.jpg", "/file.jpg")
```

## Sincronizzazione locale <-> remota
Oltre alla versione minima (`dropbox_app.py`), è disponibile uno script di
**sincronizzazione** tra una cartella locale `drpbx/` e il folder remoto
dell'app, pensato per un flusso **manuale tipo push/pull** (utente unico).

```bash
python sync.py push          # locale -> remoto  (a fine sessione)
python sync.py pull          # remoto -> locale  (al ritorno ad altro device)
python sync.py               # bidirezionale, una passata
python sync.py push --dry-run # anteprima senza modificare nulla
```

### Come funziona
- **Remote → locale**: scarica i file assenti o più nuovi su Dropbox
- **Locale → remoto**: carica i file assenti o più nuovi in locale
- Il confronto usa la **data di modifica** (`mtime` locale vs `server_modified` remoto)

### Flusso consigliato con più device
1. Lavori su una macchina (Windows/Linux) → a fine sessione: `python sync.py push`
2. Su smartphone/tablet apri l'app **Dropbox** > `Apps/<Nome App>/` per vedere/modificare i file (li: non serve Python)
3. Di ritorno su un desktop: `python sync.py pull` per scaricare le modifiche

Il server Dropbox imposta `server_modified`, quindi il confronto resta coerente
anche se i device hanno orologi diversi.

### Termux (Android: smartphone/tablet)
Il **refresh token è legato all'app+account, non al device**: puoi **riusare lo
stesso `refresh_token.txt`** su tutti i device senza rifare OAuth (trattalo però
come una password: chi lo possiede accede al tuo folder).

Setup rapido su Termux:
```bash
bash setup_termux.sh          # installa python + dropbox, crea drpbx/
# poi copia qui gli script (sync.py, dbx_auth.py, refresh_token.txt)
# oppure scaricali facendo il primo pull da Desktop (vedi bootstrap qui sotto)
python sync.py pull           # prima sync: scarica tutto
python sync.py push           # a fine sessione di modifica
```

Se i file servono nello storage "normale" del telefono: `termux-setup-storage`.

### Bootstrap degli script sui nuovi device
Per portare `sync.py`/`dbx_auth.py` sugli altri device senza git/usb:
1. Da un desktop: carica una cartella `scripts/` nell'app folder (`sync.py`, `dbx_auth.py`, `refresh_token.txt`)
2. Su Termux: `bash setup_termux.sh` e poi `python sync.py pull`
3. Sposta gli script da `drpbx/scripts/` alla HOME e cancella `scripts/`

### File del progetto
- `dbx_auth.py` — autenticazione OAuth condivisa (app key + PKCE, riutilizzabile)
- `dropbox_app.py` — versione minima: connessione ed elenco cartella
- `sync.py` — sync bidirezionale o push/pull manuale
- `setup_termux.sh` — installer one-shot per Termux/Android

### Nota tecnica: timezone
Le date `server_modified` di Dropbox sono in **UTC ma naive** (senza timezone).
Convertendole con `.timestamp()` Python le interpreta come ora locale, generando
una discrepanza (es. +2h) che causava un loop infinito di ri-upload/ri-download.
Risolto dichiarando esplicitamente UTC prima della conversione e allineando la
data locale a quella remota dopo ogni download/upload.

## Nota: futura implementazione delle rimozioni (TODO)
Attualmente la sync **copre solo contenuto e modifiche**, non le eliminazioni:
- se cancelli un file **su Dropbox**, il file resta in `drpbx/` (e verrebbe
  ri-caricato al run successivo);
- se cancelli un file **in `drpbx/`**, resta su Dropbox (e verrebbe ri-scaricato).

Implementazione prevista (richiede scope `files.metadata.write` per `files_delete`):
1. Confrontare l'elenco dei file locali e remoti, invece che solo per percorso.
2. Se un file esiste solo in un lato e non era mai stato visto, è "nuovo" e va
   copiato; se invece era già sincronizzato in precedenza, la sua assenza indica
   una cancellazione da propagare all'altro lato.
3. Per distinguere i due casi servirebbe uno **stato di sync persistente**
   (es. un file `sync_state.json` che registra l'ultimo elenco sincronizzato),
   così non si rischia di cancellare file appena aggiunti o mai visti prima.