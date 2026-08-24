# -*- coding: utf-8 -*-
"""
Pannello di controllo per sync.py — Dropbox synchronizer.
Permette di lanciare push / pull / bidirezionale (con dry-run opzionale)
e visualizzare l'output in tempo reale.
"""
import os
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import scrolledtext

CREATE_NO_WINDOW = 0x08000000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SYNC_SCRIPT = os.path.join(BASE_DIR, "sync.py")

# ── GUI ────────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("Pannello Sync — Dropbox")
root.geometry("850x520")

toolbar = tk.Frame(root)
toolbar.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)

sync_process = None
out_queue: queue.Queue = queue.Queue()
dry_var = tk.BooleanVar(value=False)


# ── helpers ────────────────────────────────────────────────────────────
def log(msg: str) -> None:
    text.insert(tk.END, msg + "\n")
    text.see(tk.END)


def _reader(proc: subprocess.Popen) -> None:
    try:
        for line in proc.stdout:
            out_queue.put(("line", line))
    except Exception as e:
        out_queue.put(("line", f"\n[errore lettura: {e}]\n"))
    finally:
        out_queue.put(("eof", proc, proc.wait()))


def _start_process(cmd, cwd, name):
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        out_queue.put(("line", f"[{name}] ERRORE: comando non trovato: {cmd[0]}\n"))
        return None
    except Exception as e:
        out_queue.put(("line", f"[{name}] ERRORE avvio: {e}\n"))
        return None
    proc.panel_name = name
    threading.Thread(target=_reader, args=(proc,), daemon=True).start()
    return proc


def _run_sync(mode: str, dry: bool = False) -> None:
    global sync_process
    if sync_process is not None and sync_process.poll() is None:
        log("⚠ Un sync è già in esecuzione, aspetta che finisca.")
        return
    cmd = ["py", SYNC_SCRIPT]
    if dry:
        cmd.append("--dry-run")
    cmd.append(mode)
    env_extra = {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    }
    env = os.environ.copy()
    env.update(env_extra)
    sync_process = _start_process(cmd, BASE_DIR, f"sync {mode}" + (" (dry)" if dry else ""))
    if sync_process is not None:
        log(f"▶ Avviato: {' '.join(cmd)}  (PID {sync_process.pid})\n")


def poll_output() -> None:
    global sync_process
    try:
        while True:
            item = out_queue.get_nowait()
            if item[0] == "line":
                text.insert(tk.END, item[1])
                text.see(tk.END)
            else:
                _, proc, code = item
                name = getattr(proc, "panel_name", "sync")
                if proc is sync_process:
                    sync_process = None
                    log(f"\n[{name} terminato — exit code {code}]")
                else:
                    log(f"[{name} terminato — exit code {code}]")
    except queue.Empty:
        pass
    root.after(100, poll_output)


def on_close() -> None:
    if sync_process is not None and sync_process.poll() is None:
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(sync_process.pid)],
                capture_output=True,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception:
            pass
    root.destroy()


# ── callbacks (bottoni) ────────────────────────────────────────────────
def click_push():
    _run_sync("push", dry_var.get())

def click_pull():
    _run_sync("pull", dry_var.get())

def click_both():
    _run_sync("both", dry_var.get())

def click_stop():
    global sync_process
    if sync_process is None or sync_process.poll() is not None:
        log("Nessun sync in esecuzione.")
        return
    pid = sync_process.pid
    log(f"⛔ Interruzione sync (PID {pid}) …")
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
        )
        sync_process = None
        log("Sync interrotto.")
    except Exception as e:
        log(f"ERRORE arresto: {e}")

def clear_output():
    text.delete("1.0", tk.END)
    log("Output cancellato.")


# ── barra strumenti ────────────────────────────────────────────────────
btn_push = tk.Button(toolbar, text="⬆ Push  (locale→remoto)", command=click_push, width=22)
btn_push.pack(side=tk.LEFT, padx=4)

btn_pull = tk.Button(toolbar, text="⬇ Pull  (remoto→locale)", command=click_pull, width=22)
btn_pull.pack(side=tk.LEFT, padx=4)

btn_both = tk.Button(toolbar, text="🔄 Both (bidirezionale)", command=click_both, width=22)
btn_both.pack(side=tk.LEFT, padx=4)

chk_dry = tk.Checkbutton(toolbar, text="Dry-run", variable=dry_var)
chk_dry.pack(side=tk.LEFT, padx=(10, 4))

btn_stop = tk.Button(toolbar, text="⏹ Stop", command=click_stop, fg="red")
btn_stop.pack(side=tk.LEFT, padx=4)

btn_clear = tk.Button(toolbar, text="🗑 Clear", command=clear_output)
btn_clear.pack(side=tk.LEFT, padx=4)

btn_exit = tk.Button(toolbar, text="✖ Exit", command=on_close)
btn_exit.pack(side=tk.LEFT, padx=4)


# ── area output ────────────────────────────────────────────────────────
text = scrolledtext.ScrolledText(
    root, bg="black", fg="#00FF00",
    font=("Consolas", 11), insertbackground="#00FF00",
)
text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)


# ── init ───────────────────────────────────────────────────────────────
log("Pannello Sync pronto.")
log(f"Script: {SYNC_SCRIPT}")
log("Modalità: Push (locale→remoto) · Pull (remoto→locale) · Both (bidirezionale)")
log("Opzione 'Dry-run': mostra cosa farebbe senza modificare nulla.\n")

root.protocol("WM_DELETE_WINDOW", on_close)
root.after(100, poll_output)
root.mainloop()
