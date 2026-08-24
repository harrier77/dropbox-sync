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
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "drpbx")


LOCAL = _resolve_local()


def server_epoch(md):
    """Epoch (utc) della data di modifica remota."""
    return md.server_modified.replace(tzinfo=timezone.utc).timestamp()


def list_all(dbx, path):
    """Restituisce tutti gli entry (con paginazione)."""
    entries = []
    res = dbx.files_list_folder(path, recursive=True)
    entries += res.entries
    cursor = res.cursor
    while res.has_more:
        res = dbx.files_list_folder_continue(cursor)
        entries += res.entries
        cursor = res.cursor
    return entries


def build_indexes(dbx):
    """Indici locali e remoti: relpath -> (percorso locale | FileMetadata)."""
    remote = {}
    for e in list_all(dbx, REMOTE):
        if isinstance(e, files.FileMetadata):
            remote[e.path_display.lstrip("/")] = e

    local = {}
    seen = {os.path.realpath(LOCAL)}   # evita cicli di symlink

    def walk_dir(base, rel_prefix=""):
        for entry in os.scandir(base):
            rp = os.path.realpath(entry.path)
            if rp in seen:
                continue
            seen.add(rp)
            rel = entry.name if not rel_prefix else f"{rel_prefix}/{entry.name}"
            if entry.is_dir():          # follow_symlinks=True di default: entra anche nei symlink-dir
                walk_dir(entry.path, rel)
            else:
                local[rel] = entry.path

    walk_dir(LOCAL)
    return local, remote


def download(dbx, remote, local, dry=False):
    """Remote -> locale. Restituisce il numero di file scaricati."""
    n = 0
    for rel, md in remote.items():
        local_p = os.path.join(LOCAL, rel.replace("/", os.sep))
        current = os.path.getmtime(local_p) if rel in local else 0
        if rel not in local or current < server_epoch(md):
            print(("  [dry] DOWN " if dry else "  DOWN  ") + rel)
            n += 1
            if not dry:
                os.makedirs(os.path.dirname(local_p), exist_ok=True)
                dbx.files_download_to_file(local_p, "/" + rel)
                # allinea la data locale a quella remota per evitare ri-upload
                os.utime(local_p, (server_epoch(md),) * 2)
    return n


def upload(dbx, local, remote, dry=False):
    """Locale -> remoto. Restituisce il numero di file caricati."""
    n = 0
    for rel, local_p in local.items():
        rm = remote.get(rel)
        if rm is None or os.path.getmtime(local_p) > server_epoch(rm):
            print(("  [dry] UP   " if dry else "  UP    ") + rel)
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
    os.makedirs(LOCAL, exist_ok=True)
    dbx = dbx_auth.get_dbx()

    desc = {"push": "locale -> remoto",
            "pull": "remoto -> locale",
            "both": "bidirezionale"}[mode]
    what = " (DRY-RUN)" if dry else ""
    print(f"Sync {desc} tra '{LOCAL}{os.sep}' e '/'{what}\n" + "-" * 40)

    local, remote = build_indexes(dbx)
    if mode == "pull":
        n = download(dbx, remote, local, dry)
        print(f"\nFatto: {n} scaricati.")
    elif mode == "push":
        n = upload(dbx, local, remote, dry)
        print(f"\nFatto: {n} caricati.")
    else:
        d = download(dbx, remote, local, dry)
        u = upload(dbx, local, remote, dry)
        print(f"\nFatto: {d} scaricati, {u} caricati.")


if __name__ == "__main__":
    argp = argparse.ArgumentParser()
    argp.add_argument("mode", nargs="?", default="both",
                      choices=["push", "pull", "both"])
    argp.add_argument("--dry-run", action="store_true", help="solo anteprima")
    args = argp.parse_args(sys.argv[1:])

    main(args.mode, args.dry_run)