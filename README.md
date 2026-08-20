# dropbox-sync

A small Python app that keeps a local folder in sync with a folder on your
**Dropbox**. Built for a single user who wants a simple, manual **push/pull**
workflow between a few devices (desktop + phone/tablet).

It uses a Dropbox **app-folder** app, so it only ever sees its own folder
(`Dropbox/Apps/<Your App Name>/`).

**License:** [MIT](LICENSE)

## Setup

```bash
pip install dropbox
```

## Getting started

```bash
python dropbox_app.py     # connect and list the app folder
```

- **First run**: opens a link in your browser → authorise → paste the code
  back. The refresh token is saved to `~/.mydrpbx/refresh_token.txt`.
- **Later runs**: reconnects automatically with no prompts.

> **Secrets live outside the app**, in `~/.mydrpbx/` (`config.json` +
> `refresh_token.txt`), so this repo contains **no credentials** and is safe
> to share. Copy that folder to each machine you run the app on.

## Syncing: push / pull

The `sync.py` script mirrors `drpbx/` with the Dropbox app folder, using a
manual push/pull model (ideal when you're the only editor).

```bash
python sync.py push           # local -> Dropbox  (end of a session)
python sync.py pull           # Dropbox -> local  (back on another device)
python sync.py                # both directions, one pass
python sync.py push --dry-run # preview without changing anything
```

How it decides what to copy:
- **Remote → local**: files missing locally or newer on Dropbox.
- **Local → remote**: files missing remotely or newer locally.
- Comparison is based on **modification time** (`mtime` vs `server_modified`).

Because Dropbox sets `server_modified` on its own clock, the comparison stays
consistent even when devices have different clocks.

### Suggested multi-device flow
1. Work on a desktop (Windows/Linux) → at the end: `python sync.py push`
2. On a phone/tablet, open the **Dropbox app** > `Apps/<Your App Name>/` to
   view or edit the files (no Python needed there)
3. Back on a desktop: `python sync.py pull` to fetch the changes

### Termux (Android)
The refresh token is tied to your app + account, **not** to a device, so the
same `~/.mydrpbx/refresh_token.txt` works on every device — no re-authorising.
Treat it like a password: anyone with it can reach your folder.

```bash
bash setup_termux.sh      # installs python + dropbox, creates drpbx/
python sync.py pull       # first sync: fetch everything
python sync.py push       # end of an editing session
```

If you want files in normal phone storage instead: `termux-setup-storage`.

## Project files

- `dbx_auth.py` — shared OAuth (app key + PKCE), reads secrets from `~/.mydrpbx`
- `dropbox_app.py` — minimal: connect and list the app folder
- `sync.py` — one-way push/pull or two-way sync
- `setup_termux.sh` — one-shot installer for Termux/Android

## Notes

### Timezone
Dropbox returns `server_modified` in **UTC but naive** (no timezone). Calling
`.timestamp()` on it makes Python read it as local time, causing a small offset
(here +2h) that produced a re-upload/re-download loop. Fixed by treating it
explicitly as UTC and aligning local timestamps after every sync.

### Deletions (TODO)
The sync currently handles **content and edits only**, not deletions:
- a file deleted **on Dropbox** stays in `drpbx/` (and comes back on next push),
- a file deleted **in `drpbx/`** stays on Dropbox (and comes back on next pull).

Planned (needs `files.metadata.write` scope for `files_delete`): compare lists
of files rather than just paths, and use a **persistent sync state** (e.g.
`sync_state.json`) to tell "new file to copy" apart from "removed file to
propagate", so you never delete a file you've never seen.