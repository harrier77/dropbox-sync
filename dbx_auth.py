"""Autenticazione condivisa Dropbox (riusabile da più script).

I segreti NON sono nella cartella dell'app ma in ~/.mydrpbx/:
    refresh_token.txt   -> il refresh token (credenziale sensibile)
    config.json         -> app_key e scopes

Nella cartella dell'app resta solo codice, nessun segreto.
"""
import os
import json
import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect

# Directory segreta fuori dall'app: C:\Users\<utente>\.mydrpbx /
SECRET_DIR = os.path.join(os.path.expanduser("~"), ".mydrpbx")
TOKEN_FILE = os.path.join(SECRET_DIR, "refresh_token.txt")
CONFIG_FILE = os.path.join(SECRET_DIR, "config.json")

APP_KEY = None
SCOPE = None
WORKING_FOLDER = None


def _load_config():
    global APP_KEY, SCOPE, WORKING_FOLDER
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    APP_KEY = cfg["app_key"]
    SCOPE = cfg.get("scopes", [])
    wf = cfg.get("working-folder")
    if wf:
        WORKING_FOLDER = os.path.expandvars(os.path.expanduser(wf))


def get_token():
    if os.path.exists(TOKEN_FILE):
        return open(TOKEN_FILE).read().strip()
    if APP_KEY is None:
        _load_config()
    auth = DropboxOAuth2FlowNoRedirect(
        APP_KEY, token_access_type="offline", use_pkce=True, scope=SCOPE
    )
    print("1) Apri questo link nel browser:", auth.start())
    code = input("2) Incolla il codice mostrato: ").strip()
    oauth = auth.finish(code)
    open(TOKEN_FILE, "w").write(oauth.refresh_token)
    return oauth.refresh_token


def get_dbx():
    if APP_KEY is None:
        _load_config()
    try:
        dbx = dropbox.Dropbox(oauth2_refresh_token=get_token(), app_key=APP_KEY)
        dbx.files_list_folder("")  # verifica che il token funzioni
        return dbx
    except dropbox.exceptions.AuthError as e:
        if "missing_scope" in str(e):
            print("Token senza i permessi necessari: rigenero...")
            if os.path.exists(TOKEN_FILE):
                os.remove(TOKEN_FILE)
            dbx = dropbox.Dropbox(oauth2_refresh_token=get_token(), app_key=APP_KEY)
            return dbx
        raise