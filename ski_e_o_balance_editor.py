"""Ski-E-O Balance Editor

A small tool that changes the money balance in a Ski-E-O! Ski Resort Tycoon
save file (single-player only). It edits exactly 4 bytes of the .sav file,
after making a backup. See README.md for details.

Unofficial fan tool. Not affiliated with the game's developers.
Use at your own risk.
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import traceback

VERSION = "1.0.0"
TESTED_SAVE_VERSION = (51, 102)  # SaveMajorVersion, SaveMinorVersion
GAME_PROCESS_HINTS = ("skieogame", "skiresortsimulator")

# "Balance" followed by an IntProperty header, as serialized in the GVAS file.
MARKER = b"Balance\x00" + struct.pack("<I", 12) + b"IntProperty\x00"
SKIP = 9  # 4 zero bytes, size (04 00 00 00), 1 flag byte, then the int32 value
INT_MIN, INT_MAX = -(2**31), 2**31 - 1


class EditorError(Exception):
    """An expected problem; the message is shown to the user as-is."""


# --------------------------------------------------------------------------
# Core: reading and patching the balance
# --------------------------------------------------------------------------
def find_balance_offset(data):
    """Return the offset of the int32 balance value inside the save bytes."""
    if data[:4] != b"GVAS":
        raise EditorError("This does not look like a Ski-E-O save (missing GVAS header).")
    hits = []
    start = 0
    while True:
        i = data.find(MARKER, start)
        if i < 0:
            break
        # The name string must be length-prefixed with 8 ("Balance\0"), which
        # excludes names such as "RemainingBalance".
        if i >= 4 and struct.unpack_from("<I", data, i - 4)[0] == 8:
            hits.append(i)
        start = i + 1
    if len(hits) != 1:
        raise EditorError(
            f"Could not find the balance in this save (found {len(hits)} matches). "
            "The game may have been updated and changed its save format."
        )
    pos = hits[0] + len(MARKER)
    hdr = data[pos:pos + SKIP]
    if (len(hdr) < SKIP or hdr[0:4] != b"\x00\x00\x00\x00"
            or hdr[4:8] != b"\x04\x00\x00\x00" or hdr[8] != 0):
        raise EditorError("The balance entry has an unexpected layout; refusing to edit.")
    if pos + SKIP + 4 > len(data):
        raise EditorError("The save file looks truncated.")
    return pos + SKIP


def read_balance(data):
    return struct.unpack_from("<i", data, find_balance_offset(data))[0]


def patch_balance(data, new_value):
    """Return a copy of data with the balance replaced."""
    if not (INT_MIN <= new_value <= INT_MAX):
        raise EditorError(f"Balance must be between {INT_MIN:,} and {INT_MAX:,}.")
    out = bytearray(data)
    struct.pack_into("<i", out, find_balance_offset(out), new_value)
    return bytes(out)


# --------------------------------------------------------------------------
# Locations
# --------------------------------------------------------------------------
def default_save_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    return os.path.join(base, "Ski-E-O", "SaveGames")


def documents_dir():
    try:
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        # CSIDL_PERSONAL = 5 (handles Documents moved to OneDrive/other drives)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def backup_root():
    return os.path.join(documents_dir(), "Ski-E-O Balance Editor Backups")


# --------------------------------------------------------------------------
# Save discovery
# --------------------------------------------------------------------------
def read_meta(sav_path):
    meta_path = os.path.splitext(sav_path)[0] + ".meta"
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def list_saves(save_dir):
    saves = []
    for name in os.listdir(save_dir):
        if not name.lower().endswith(".sav"):
            continue
        path = os.path.join(save_dir, name)
        try:
            with open(path, "rb") as f:
                data = f.read()
            balance = read_balance(data)
        except (OSError, EditorError):
            continue  # not a save we can edit (e.g. a settings file)
        meta = read_meta(path)
        saves.append({
            "path": path,
            "name": name,
            "mtime": os.path.getmtime(path),
            "balance": balance,
            "resort": meta.get("ResortName", "(unknown resort)"),
            "label": meta.get("DisplayName", ""),
            "ingame": str(meta.get("InGameDate", ""))[:10],
            "version": (meta.get("SaveMajorVersion"), meta.get("SaveMinorVersion")),
        })
    saves.sort(key=lambda s: s["mtime"], reverse=True)
    return saves


# --------------------------------------------------------------------------
# Safety helpers
# --------------------------------------------------------------------------
def game_is_running():
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                             text=True, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.lower()
    except Exception:
        return False
    return any(h in out for h in GAME_PROCESS_HINTS)


def make_backup(sav_path):
    stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    dest = os.path.join(backup_root(), stamp)
    n = 1
    while os.path.exists(dest):  # never reuse (and overwrite) an existing backup
        n += 1
        dest = os.path.join(backup_root(), f"{stamp}_{n}")
    os.makedirs(dest)
    base = os.path.splitext(sav_path)[0]
    for ext in (".sav", ".meta"):
        src = base + ext
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dest, os.path.basename(src)))
    return dest


def write_atomic(path, data):
    """Write to a temp file in the same folder, then swap it in."""
    tmp = path + ".tmp-editor"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


# --------------------------------------------------------------------------
# User interface (console)
# --------------------------------------------------------------------------
def ask(prompt):
    return input(prompt).strip()


def choose_from(items, prompt):
    while True:
        raw = ask(prompt)
        if raw.lower() in ("q", "quit", "exit", ""):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(items):
            return items[int(raw) - 1]
        print("  Please type one of the numbers shown, or press Enter to cancel.")


def fmt_time(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def get_save_dir():
    d = default_save_dir()
    if os.path.isdir(d):
        return d
    print(f"Could not find the save folder at:\n  {d}")
    while True:
        d = ask("Type the full path to your SaveGames folder (or press Enter to quit): ").strip('"')
        if not d:
            return None
        if os.path.isdir(d):
            return d
        print("  That folder does not exist.")


def parse_amount(raw):
    cleaned = raw.replace(",", "").replace(" ", "").replace("_", "")
    try:
        return int(cleaned)
    except ValueError:
        raise EditorError("That is not a whole number.")


def edit_flow():
    save_dir = get_save_dir()
    if not save_dir:
        return
    saves = list_saves(save_dir)
    if not saves:
        raise EditorError("No editable saves were found in:\n  " + save_dir)

    print("\nYour saves (newest first):\n")
    for i, s in enumerate(saves, 1):
        print(f"  [{i}] {s['resort']}  -  {s['label'] or s['name']}")
        print(f"       in-game {s['ingame'] or '?'}  |  saved {fmt_time(s['mtime'])}  |  balance {s['balance']:,}")
        print(f"       file: {s['name']}")
    print()
    chosen = choose_from(saves, "Which save do you want to edit? (number, Enter to cancel): ")
    if not chosen:
        print("Cancelled.")
        return

    if chosen["version"] != (None, None) and chosen["version"] != TESTED_SAVE_VERSION:
        v = ".".join(str(x) for x in chosen["version"])
        t = ".".join(str(x) for x in TESTED_SAVE_VERSION)
        print(f"\nWARNING: this save is version {v}; this tool was tested with {t}.")
        print("The game may have been updated. The tool checks the file layout before it")
        print("changes anything, but a newer save format is untested.")
        if ask("Continue anyway? (y/n): ").lower() != "y":
            print("Cancelled.")
            return

    if game_is_running():
        print("\nThe game seems to be running. Close it first, otherwise it can overwrite")
        print("your change with an autosave.")
        if ask("Continue anyway? (y/n): ").lower() != "y":
            print("Cancelled.")
            return

    print(f"\nCurrent balance: {chosen['balance']:,}")
    new = parse_amount(ask("New balance (whole number, for example 2000000): "))
    if not (INT_MIN <= new <= INT_MAX):
        raise EditorError(f"Balance must be between {INT_MIN:,} and {INT_MAX:,}.")
    if new > 1_000_000_000:
        print("Note: very large values may overflow in game calculations and show negative.")
    if ask(f"Change balance {chosen['balance']:,} -> {new:,} ? (y/n): ").lower() != "y":
        print("Cancelled. Nothing was changed.")
        return

    with open(chosen["path"], "rb") as f:
        original = f.read()
    patched = patch_balance(original, new)

    backup_dir = make_backup(chosen["path"])
    write_atomic(chosen["path"], patched)

    with open(chosen["path"], "rb") as f:
        after = f.read()
    if read_balance(after) != new or len(after) != len(original):
        shutil.copy2(os.path.join(backup_dir, chosen["name"]), chosen["path"])
        raise EditorError("Verification failed, so your original save was put back. Nothing was changed.")

    print(f"\nDone. The balance in {chosen['name']} is now {new:,}.")
    print(f"A backup was saved to:\n  {backup_dir}")
    print("\nTips: start the game and load this save. If Steam Cloud brings back the old")
    print("file, turn Steam Cloud off for the game (Properties > General) and retry.")


def restore_flow():
    root = backup_root()
    if not os.path.isdir(root):
        raise EditorError("No backups found yet. They are created automatically when you edit a save.")
    entries = []
    for stamp in sorted(os.listdir(root), reverse=True):
        d = os.path.join(root, stamp)
        for name in os.listdir(d) if os.path.isdir(d) else []:
            if name.lower().endswith(".sav"):
                p = os.path.join(d, name)
                try:
                    with open(p, "rb") as f:
                        bal = read_balance(f.read())
                except (OSError, EditorError):
                    bal = None
                entries.append({"dir": d, "name": name, "stamp": stamp, "balance": bal})
    if not entries:
        raise EditorError("No backups found yet.")
    print("\nBackups (newest first):\n")
    for i, e in enumerate(entries, 1):
        b = f"{e['balance']:,}" if e["balance"] is not None else "?"
        print(f"  [{i}] {e['stamp']}  -  {e['name']}  -  balance {b}")
    print()
    chosen = choose_from(entries, "Which backup do you want to restore? (number, Enter to cancel): ")
    if not chosen:
        print("Cancelled.")
        return
    save_dir = get_save_dir()
    if not save_dir:
        return
    if game_is_running():
        print("\nThe game seems to be running. Close it before restoring.")
        if ask("Continue anyway? (y/n): ").lower() != "y":
            print("Cancelled.")
            return
    target = os.path.join(save_dir, chosen["name"])
    if ask(f"Overwrite {chosen['name']} in your SaveGames with this backup? (y/n): ").lower() != "y":
        print("Cancelled.")
        return
    if os.path.isfile(target):
        pre = make_backup(target)  # keep the current file too
        print(f"(Your current file was backed up first to: {pre})")
    for ext in (".sav", ".meta"):
        src = os.path.join(chosen["dir"], os.path.splitext(chosen["name"])[0] + ext)
        if os.path.isfile(src):
            with open(src, "rb") as f:
                write_atomic(os.path.join(save_dir, os.path.basename(src)), f.read())
    print("Restored.")


def main():
    print(f"Ski-E-O Balance Editor v{VERSION}  (unofficial fan tool, single-player only)")
    print("Close the game first. Backups go to:")
    print(f"  {backup_root()}\n")
    while True:
        print("  [1] Change the money balance of a save")
        print("  [2] Restore a backup")
        print("  [Enter] Quit")
        choice = ask("> ")
        try:
            if choice == "1":
                edit_flow()
            elif choice == "2":
                restore_flow()
            else:
                return
        except EditorError as e:
            print(f"\nError: {e}\nNothing was changed.")
        except PermissionError as e:
            print(f"\nError: Windows denied access ({e.filename or 'file'}). "
                  "Close the game and any program using the save, then try again.")
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            return
        print()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("\nUnexpected error. Your saves were not modified unless a backup message appeared above.")
        print("Please include this when reporting the problem:\n")
        traceback.print_exc()
    if sys.stdin and sys.stdin.isatty():
        try:
            input("\nPress Enter to close...")
        except (EOFError, KeyboardInterrupt):
            pass
