#!/usr/bin/env python3
"""
Sincronizzazione (bidirezionale o unidirezionale) tra la cartella locale
`drpbx` e il folder remoto della tua app Dropbox
(/ = Dropbox/Apps/<Nome App>/).

Uso:
    python sync.py push             # locale -> remoto  (fine sessione)
    python sync.py pull             # remoto -> locale  (al ritorno)
    python sync.py                  # bidirezionale, una passata
    python sync.py --dry-run push   # mostra cosa farebbe senza modificare nulla

Criterio: confronta la data di modifica (mtime locale vs server_modified remoto).
"""
import os
import sys
import argparse
from datetime import timezone
import dropbox
from dropbox import files
import dbx_auth

REMOTE = "/"         # root del folder dell'app su Dropbox


def _resolve_local():
    """Cartella locale: 'working-folder' dal config se presente,
    altrimenti 'drpbx' accanto a questo script."""
    wf = getattr(dbx_auth, "WORKING_FOLDER", None)
    if wf:
        return os.path.abspath(wf)
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), "drpbx")


LOCAL = None  # risolta in main(), dopo che dbx_auth ha caricato il config


def server_epoch(md):
    """Epoch (utc) della data di modifica remota."""
    return md.server_modified.replace(tzinfo=timezone.utc).timestamp()


def list_all(dbx, path):
    """Restituisce tutti gli entry (con paginazione)."""
    entries = []
    res = dbx.files_list_folder(path.rstrip("/"), recursive=True)
    entries += res.entries
    cursor = res.cursor
    while res.has_more:
        res = dbx.files_list_folder_continue(cursor)
        entries += res.entries
        cursor = res.cursor
    return entries


def _local_path(root, rel):
    """Ritorna il path locale per un relpath, con traversal check.

    Usa normpath (non realpath) per il containment check: un symlink dentro
    la root (es. drpbx/target -> translator/target) e' legittimo e non va
    risolto, altrimenti il check sembra un escape.
    """
    parts = rel.split("/")
    if not rel or any(p in ("", "..") or "\\" in p or ":" in p for p in parts):
        raise ValueError("Percorso di sincronizzazione non valido")
    path = os.path.normpath(os.path.join(root, *parts))
    root_norm = os.path.normpath(root)
    if path != root_norm and not path.startswith(root_norm + os.sep):
        raise ValueError("Percorso fuori dalla cartella selezionata")
    return path


def build_indexes(dbx, local_dir=None, remote_dir=None):
    """Indici locali e remoti: relpath -> (percorso locale | FileMetadata)."""
    root = local_dir if local_dir is not None else LOCAL
    remote_root = (remote_dir if remote_dir is not None else REMOTE).rstrip("/")
    prefix = remote_root + "/"
    remote = {}
    try:
        entries = list_all(dbx, remote_root)
    except dropbox.exceptions.ApiError as exc:
        if exc.error.is_path() and exc.error.get_path().is_not_found():
            entries = []
        else:
            raise
    for e in entries:
        if isinstance(e, files.FileMetadata):
            if not e.path_display.lower().startswith(prefix.lower()):
                raise ValueError("Percorso remoto fuori dalla cartella selezionata")
            rel = e.path_display[len(prefix):]
            _local_path(root, rel)
            remote[rel] = e

    local = {}
    seen = {os.path.realpath(root)}   # evita cicli di symlink

    def walk_dir(base, rel_prefix=""):
        for entry in os.scandir(base):
            rp = os.path.realpath(entry.path)
            if rp in seen:
                continue
            seen.add(rp)
            rel = entry.name if not rel_prefix else f"{rel_prefix}/{entry.name}"
            if local_dir is not None:
                _local_path(root, rel)
            if entry.name.endswith(".tmp"):
                continue
            if entry.is_dir():          # follow_symlinks=True di default: entra anche nei symlink-dir
                walk_dir(entry.path, rel)
            else:
                local[rel] = entry.path

    walk_dir(root)
    return local, remote


def run_sync(mode, dry=False, local_dir=None, remote_dir=None,
             progress=None):
    """Esegue la sincronizzazione e ritorna un riepilogo (dict).

    mode: "push", "pull" o "both"; dry=True non modifica nulla.
    local_dir: cartella locale da sincronizzare (default: LOCAL risolta).
    remote_dir: cartella remota (default: REMOTE, root dell'app).
    progress: callback opzionale(message:str) per log senza print.
    """
    def emit(msg):
        if progress:
            progress(msg)
        else:
            print(msg)

    dbx = dbx_auth.get_dbx(interactive=False)
    if local_dir is None:
        local_dir = LOCAL if LOCAL is not None else _resolve_local()
    if remote_dir is None:
        remote_dir = REMOTE
    local_dir = os.path.abspath(local_dir)
    os.makedirs(local_dir, exist_ok=True)

    desc = {"push": "locale -> remoto",
            "pull": "remoto -> locale",
            "both": "bidirezionale"}[mode]
    what = " (DRY-RUN)" if dry else ""
    emit(f"Sync {desc} tra '{local_dir}{os.sep}' e '{remote_dir}'{what}")

    local, remote = build_indexes(dbx, local_dir=local_dir, remote_dir=remote_dir)
    down = up = 0
    if mode == "pull":
        down = download(dbx, remote, local, dry, root=local_dir, progress=emit)
    elif mode == "push":
        up = upload(dbx, local, remote, dry, root=local_dir, progress=emit)
    else:
        down = download(dbx, remote, local, dry, root=local_dir, progress=emit)
        up = upload(dbx, local, remote, dry, root=local_dir, progress=emit)
    emit(f"Fatto: {down} scaricati, {up} caricati.")
    return {"mode": mode, "dry": bool(dry), "downloaded": down, "uploaded": up}


def download(dbx, remote, local, dry=False, root=None, progress=None):
    """Remote -> locale. Restituisce il numero di file scaricati."""
    base = root if root is not None else LOCAL

    def emit(msg):
        if progress:
            progress(msg)
        else:
            print(msg)

    n = 0
    for rel, md in remote.items():
        local_p = _local_path(base, rel)
        current = os.path.getmtime(local_p) if rel in local else 0
        if rel not in local or current < server_epoch(md):
            emit(("  [dry] DOWN " if dry else "  DOWN  ") + rel)
            n += 1
            if not dry:
                os.makedirs(os.path.dirname(local_p), exist_ok=True)
                dbx.files_download_to_file(local_p, "/" + rel)
                # allinea la data locale a quella remota per evitare ri-upload
                os.utime(local_p, (server_epoch(md),) * 2)
    return n


def upload(dbx, local, remote, dry=False, root=None, progress=None):
    """Locale -> remoto. Restituisce il numero di file caricati."""
    def emit(msg):
        if progress:
            progress(msg)
        else:
            print(msg)

    n = 0
    for rel, local_p in local.items():
        rm = remote.get(rel)
        if rm is None or os.path.getmtime(local_p) > server_epoch(rm):
            emit(("  [dry] UP   " if dry else "  UP    ") + rel)
            n += 1
            if not dry:
                with open(local_p, "rb") as f:
                    up = dbx.files_upload(
                        f.read(), "/" + rel,
                        mode=files.WriteMode.overwrite, autorename=True,
                    )
                # allinea la data locale a quella remota per evitare ri-download
                os.utime(local_p, (server_epoch(up),) * 2)
    return n


def main(mode="both", dry=False):
    run_sync(mode, dry=dry)


if __name__ == "__main__":
    argp = argparse.ArgumentParser()
    argp.add_argument("mode", nargs="?", default="both",
                      choices=["push", "pull", "both"])
    argp.add_argument("--dry-run", action="store_true", help="solo anteprima")
    args = argp.parse_args(sys.argv[1:])

    main(args.mode, args.dry_run)
    
    #input("Premi INVIO per uscire dalla shell...")