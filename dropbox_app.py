"""
App Dropbox (app folder) — versione minima con OAuth.

Prima esecuzione: apre il browser per autorizzare -> salva il token.
Dopo: si ricollega da solo (usa refresh token).

NOTA: un'app "single folder" può vedere SOLO la propria cartella:
    Dropbox/Apps/<Nome App>/
"""
import dropbox
import dbx_auth

dbx = dbx_auth.get_dbx()

# Elenca la cartella dell'app
print("\nContenuto di /Apps/<Nome App>:\n" + "-" * 40)
for e in dbx.files_list_folder("").entries:
    tipo = "[DIR] " if isinstance(e, dropbox.files.FolderMetadata) else "[FILE] "
    print(tipo + e.name)