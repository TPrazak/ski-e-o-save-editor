"""Ski-E-O Save Editor

A small tool that edits a Ski-E-O! Ski Resort Tycoon save file (single-player only):
money balance, loans, reputation and staff. Every change makes a backup first and is
verified afterwards. See README.md for details.

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

VERSION = "1.2.0"
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
# Core: loans (same on-disk layout as the balance: 9 header bytes, then the value)
# --------------------------------------------------------------------------
LOAN_RATE_MAX = 1.0  # monthly rate as a fraction; 1.0 = 100 % per month


def _fstring(text):
    raw = text.encode() + b"\x00"
    return struct.pack("<I", len(raw)) + raw


def _value_offsets(data, name, prop_type, start=0, end=None):
    """Offsets of the 4-byte values of every property called name (in file order),
    optionally only inside data[start:end]."""
    marker = _fstring(name) + _fstring(prop_type)
    offsets = []
    end = len(data) if end is None else end
    while True:
        i = data.find(marker, start, end)
        if i < 0:
            return offsets
        pos = i + len(marker)
        hdr = data[pos:pos + SKIP]
        if (len(hdr) < SKIP or hdr[0:4] != b"\x00\x00\x00\x00"
                or hdr[4:8] != b"\x04\x00\x00\x00" or hdr[8] != 0
                or pos + SKIP + 4 > len(data)):
            raise EditorError(f"The '{name}' entry has an unexpected layout; refusing to edit.")
        offsets.append(pos + SKIP)
        start = i + 1


def find_loans(data):
    """Return the save's active loans (possibly an empty list).

    Each loan is a dict: index, tier, original, remaining, rate (fraction per
    month), months and the byte offsets of its editable values.
    """
    if data[:4] != b"GVAS":
        raise EditorError("This does not look like a Ski-E-O save (missing GVAS header).")
    fields = (("original", "OriginalPrincipal", "IntProperty"),
              ("remaining", "RemainingBalance", "IntProperty"),
              ("rate", "MonthlyInterestRate", "FloatProperty"),
              ("months", "PaybackMonths", "IntProperty"))
    offs = {key: _value_offsets(data, name, ptype) for key, name, ptype in fields}
    counts = {len(v) for v in offs.values()}
    if len(counts) != 1:
        raise EditorError("The loan entries in this save do not match the expected layout; "
                          "refusing to edit loans.")
    n = counts.pop()
    tier_marker = _fstring("Tier") + _fstring("EnumProperty")
    tier_hits = []
    start = 0
    while True:
        i = data.find(tier_marker, start)
        if i < 0:
            break
        tier_hits.append(i)
        start = i + 1
    loans = []
    for i in range(n):
        o, r, rt, m = (offs[k][i] for k in ("original", "remaining", "rate", "months"))
        nxt = offs["original"][i + 1] if i + 1 < n else None
        if not (o < r < rt < m) or (nxt is not None and not m < nxt):
            raise EditorError("The loan entries are in an unexpected order; refusing to edit loans.")
        tier = "?"
        before = [h for h in tier_hits if h < o]
        if before:
            seg = data[before[-1]:o]
            j = seg.find(b"ELoanTier::")
            if j >= 0:
                end = seg.find(b"\x00", j)
                tier = seg[j + len(b"ELoanTier::"):end].decode("ascii", "replace")
        loans.append({
            "index": i, "tier": tier,
            "original": struct.unpack_from("<i", data, o)[0],
            "remaining": struct.unpack_from("<i", data, r)[0],
            "rate": struct.unpack_from("<f", data, rt)[0],
            "months": struct.unpack_from("<i", data, m)[0],
            "offsets": {"remaining": r, "rate": rt},
        })
    return loans


def f32(x):
    """The value as the game will store it (32-bit float)."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


def patch_loans(data, changes):
    """changes: {loan_index: {"remaining": int and/or "rate": float fraction}}.
    Returns a patched copy of data."""
    loans = find_loans(data)
    out = bytearray(data)
    for idx, ch in changes.items():
        if not (0 <= idx < len(loans)):
            raise EditorError(f"There is no loan number {idx + 1} in this save.")
        offs = loans[idx]["offsets"]
        if "remaining" in ch:
            rem = ch["remaining"]
            if not isinstance(rem, int) or not (0 <= rem <= INT_MAX):
                raise EditorError(f"Remaining balance must be a whole number from 0 to {INT_MAX:,}.")
            struct.pack_into("<i", out, offs["remaining"], rem)
        if "rate" in ch:
            rate = ch["rate"]
            if not (0.0 <= rate <= LOAN_RATE_MAX):
                raise EditorError("Interest must be between 0% and 100% per month.")
            struct.pack_into("<f", out, offs["rate"], rate)
    return bytes(out)


def parse_percent(raw):
    cleaned = raw.replace(",", ".").replace("%", "").replace(" ", "")
    try:
        value = float(cleaned)
    except ValueError:
        raise EditorError("Interest must be a number such as 1.5 (percent per month).")
    if not (0.0 <= value <= LOAN_RATE_MAX * 100):
        raise EditorError("Interest must be between 0 and 100 percent per month.")
    return value / 100.0


# --------------------------------------------------------------------------
# Core: reputation (XP is a plain int; the game works out the level from it)
# --------------------------------------------------------------------------
REPUTATION_LEVELS = [
    "SmallHill", "HiddenGem", "LocalFavorite", "PowderStash", "RegionalHotspot",
    "RisingStar", "DestinationResort", "PowderMecca", "PremierMountain", "EliteResort",
    "PrestigiousDestination", "WorldClass", "IconicDestination", "LegendaryResort",
]
REPUTATION_MAX_XP = 1_000_000  # tested in game: reaches the top level ("Legendary Resort")
# XP needed to get from this level to the next, as read from the game's reputation screen.
# XP in the save is the progress WITHIN the current level (it restarts after a level-up).
REPUTATION_XP_TO_NEXT = {
    1: 280, 2: 1050, 3: 2300, 4: 4950, 5: 9050, 6: 18700, 7: 35000,
    8: 65000, 9: 130000, 10: 230000, 11: 350000, 12: 600000, 13: 900000,
}


def level_up_warning(level_number, xp):
    """Text to show if the XP progress is at/above the level-up amount, else ''."""
    need = REPUTATION_XP_TO_NEXT.get(level_number)
    if need is not None and xp >= need:
        return (f"Note: {xp:,} XP is at or above the {need:,} XP needed to leave this level, "
                "so the game will most likely level up when you load the save.")
    return ""


def pretty_level(name):
    import re
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)


def read_reputation(data):
    """Return (xp, level_name) or None if the save has no reputation data."""
    if data[:4] != b"GVAS":
        raise EditorError("This does not look like a Ski-E-O save (missing GVAS header).")
    offs = _value_offsets(data, "CurrentXP", "IntProperty")
    if not offs:
        return None
    if len(offs) != 1:
        raise EditorError("Found more than one reputation entry; refusing to edit.")
    xp = struct.unpack_from("<i", data, offs[0])[0]
    seg = data[offs[0]:offs[0] + 300]
    j = seg.find(b"EReputationLevel::")
    level = "?"
    if j >= 0:
        end = seg.find(b"\x00", j)
        level = seg[j + len(b"EReputationLevel::"):end].decode("ascii", "replace")
    return xp, level


def _reputation_layout(data):
    """Locate the pieces that depend on the level name's length (all checked)."""
    offs = _value_offsets(data, "CurrentXP", "IntProperty")
    if len(offs) != 1:
        raise EditorError("This save has no (or more than one) reputation block; refusing to edit.")
    xp_off = offs[0]
    cx = data.find(_fstring("CurrentXP") + _fstring("IntProperty"))
    size_off = cx - 5                       # size of the whole reputation block (+1 flag byte)
    body_size = struct.unpack_from("<I", data, size_off)[0]
    body_end = cx + body_size
    if body_end > len(data) or data[body_end - 9:body_end] != b"\x05\x00\x00\x00None\x00":
        raise EditorError("The reputation block has an unexpected layout; refusing to edit.")
    lv = data.find(b"EReputationLevel::", xp_off, body_end)
    if lv < 0:
        raise EditorError("Could not find the reputation level in this save.")
    lend = data.find(b"\x00", lv)
    old_len = lend + 1 - lv
    if (struct.unpack_from("<I", data, lv - 4)[0] != old_len            # text length
            or struct.unpack_from("<I", data, lv - 9)[0] != old_len + 4  # enum property size
            or data[lv - 5] != 0 or lend + 1 + 9 != body_end):
        raise EditorError("The reputation level has an unexpected layout; refusing to edit.")
    return {"xp": xp_off, "size": size_off, "body_size": body_size, "text": lv, "text_len": old_len}


def patch_reputation(data, level=None, xp=None):
    """Return a copy of data with the reputation level (name from REPUTATION_LEVELS)
    and/or XP progress changed. Changing the level changes the file size."""
    if level is None and xp is None:
        raise EditorError("Nothing to change.")
    if level is not None and level not in REPUTATION_LEVELS:
        raise EditorError("Unknown reputation level.")
    if xp is not None and (not isinstance(xp, int) or not (0 <= xp <= INT_MAX)):
        raise EditorError(f"Reputation XP must be a whole number from 0 to {INT_MAX:,}.")
    lay = _reputation_layout(data)
    out = bytearray(data)
    if xp is not None:
        struct.pack_into("<i", out, lay["xp"], xp)
    if level is not None:
        new_text = b"EReputationLevel::" + level.encode("ascii") + b"\x00"
        lv, new_len = lay["text"], len(new_text)
        struct.pack_into("<I", out, lv - 9, new_len + 4)
        struct.pack_into("<I", out, lv - 4, new_len)
        out[lv:lv + lay["text_len"]] = new_text
        struct.pack_into("<I", out, lay["size"], lay["body_size"] + new_len - lay["text_len"])
    return bytes(out)


def apply_reputation(sav_path, level=None, xp=None):
    """Back up, set the reputation level and/or XP, write and verify.
    Returns the backup folder."""
    with open(sav_path, "rb") as f:
        original = f.read()
    patched = patch_reputation(original, level, xp)
    old_lay = _reputation_layout(original)

    def check(after):
        rep = read_reputation(after)
        if rep is None:
            return False
        if xp is not None and rep[0] != xp:
            return False
        if level is not None and rep[1] != level:
            return False
        if level is None and rep[1] != read_reputation(original)[1]:
            return False
        lay = _reputation_layout(after)
        # everything before the XP value and everything after the level text is unchanged
        tail_old = original[old_lay["text"] + old_lay["text_len"]:]
        tail_new = after[lay["text"] + lay["text_len"]:]
        return (original[:old_lay["size"]] == after[:old_lay["size"]] and tail_old == tail_new)

    return _write_verified(sav_path, original, patched, check)


# --------------------------------------------------------------------------
# Core: staff (employees). Every value is a fixed-size number, so edits are in place.
# --------------------------------------------------------------------------
STAFF_ROLES = ("Liftie", "Groomer", "SkiPatrol", "Maintenance")
STAFF_STAMINA_MAX = 100.0


def find_staff(data):
    """Return the roster as a list of dicts (index, role, wage, xp, promotions,
    stamina and the offsets of the editable values). Empty list if there is none."""
    if data[:4] != b"GVAS":
        raise EditorError("This does not look like a Ski-E-O save (missing GVAS header).")
    r0 = data.find(_fstring("Roster") + _fstring("ArrayProperty"))
    if r0 < 0:
        return []
    r1 = data.find(_fstring("HiringPool") + _fstring("ArrayProperty"), r0)
    if r1 < 0:
        raise EditorError("The staff block has an unexpected layout; refusing to edit staff.")
    spec = (("wage", "DailyWage", "IntProperty"), ("xp", "XP", "IntProperty"),
            ("promotions", "PromotionsApplied", "IntProperty"), ("stamina", "Stamina", "FloatProperty"))
    offs = {k: _value_offsets(data, n, t, r0, r1) for k, n, t in spec}
    role_marker = b"EStaffRole::"
    roles = []
    pos = r0
    while True:
        i = data.find(role_marker, pos, r1)
        if i < 0:
            break
        end = data.find(b"\x00", i)
        roles.append((i, data[i + len(role_marker):end].decode("ascii", "replace")))
        pos = end
    n = len(roles)
    if any(len(v) != n for v in offs.values()):
        raise EditorError("The staff entries do not match the expected layout; refusing to edit staff.")
    staff = []
    for i in range(n):
        rp = roles[i][0]
        w, x, p, s = (offs[k][i] for k in ("wage", "xp", "promotions", "stamina"))
        nxt = roles[i + 1][0] if i + 1 < n else r1
        if not (rp < w < x < p < s < nxt):
            raise EditorError("The staff entries are in an unexpected order; refusing to edit staff.")
        staff.append({
            "index": i, "role": roles[i][1],
            "wage": struct.unpack_from("<i", data, w)[0],
            "xp": struct.unpack_from("<i", data, x)[0],
            "promotions": struct.unpack_from("<i", data, p)[0],
            "stamina": struct.unpack_from("<f", data, s)[0],
            "offsets": {"wage": w, "xp": x, "stamina": s},
        })
    return staff


def patch_staff(data, changes):
    """changes: {staff_index: {"wage": int, "xp": int, "stamina": float}} (any subset).
    Returns a patched copy of data (same size)."""
    staff = find_staff(data)
    out = bytearray(data)
    for idx, ch in changes.items():
        if not (0 <= idx < len(staff)):
            raise EditorError(f"There is no employee number {idx + 1} in this save.")
        offs = staff[idx]["offsets"]
        for key in ("wage", "xp"):
            if key in ch:
                v = ch[key]
                if not isinstance(v, int) or not (0 <= v <= INT_MAX):
                    raise EditorError(f"Staff {key} must be a whole number from 0 to {INT_MAX:,}.")
                struct.pack_into("<i", out, offs[key], v)
        if "stamina" in ch:
            v = ch["stamina"]
            if not (0.0 <= v <= STAFF_STAMINA_MAX):
                raise EditorError(f"Stamina must be between 0 and {STAFF_STAMINA_MAX:.0f}.")
            struct.pack_into("<f", out, offs["stamina"], v)
    return bytes(out)


def pretty_role(role):
    return {"SkiPatrol": "Ski Patrol"}.get(role, role)


def staff_summary(staff):
    """Per role: count and average wage / xp / stamina."""
    out = []
    for role in STAFF_ROLES:
        grp = [s for s in staff if s["role"] == role]
        if grp:
            n = len(grp)
            out.append({"role": role, "count": n,
                        "wage": sum(s["wage"] for s in grp) / n,
                        "xp": sum(s["xp"] for s in grp) / n,
                        "stamina": sum(s["stamina"] for s in grp) / n})
    return out


def parse_wage_spec(raw):
    """'150' -> ('set', 150); '50%' -> ('scale', 0.5); '' -> None."""
    raw = raw.strip().replace(" ", "").replace(",", "")
    if not raw:
        return None
    try:
        if raw.endswith("%"):
            pct = float(raw[:-1])
            if not (0 < pct <= 1000):
                raise ValueError
            return ("scale", pct / 100.0)
        value = int(raw)
        if not (1 <= value <= INT_MAX):
            raise ValueError
        return ("set", value)
    except ValueError:
        raise EditorError("Wage: type a whole number (e.g. 150) or a percent (e.g. 50%).")


def build_staff_changes(staff, roles=None, wage=None, xp=None, stamina=None):
    """Make a changes dict for patch_staff.

    roles: iterable of role names or None for everybody.
    wage: ('set', n) or ('scale', factor) or None.  xp: int or None.
    stamina: float or None.  Wages are never set below 1.
    """
    changes = {}
    for s in staff:
        if roles is not None and s["role"] not in roles:
            continue
        c = {}
        if wage is not None:
            kind, v = wage
            c["wage"] = max(1, int(round(s["wage"] * v))) if kind == "scale" else int(v)
        if xp is not None:
            c["xp"] = xp
        if stamina is not None:
            c["stamina"] = stamina
        if c:
            changes[s["index"]] = c
    return changes


def apply_staff_edits(sav_path, changes):
    """Back up, patch employees, write and verify. Returns the backup folder."""
    if not changes:
        raise EditorError("No staff changes were requested.")
    with open(sav_path, "rb") as f:
        original = f.read()
    patched = patch_staff(original, changes)

    def check(after):
        staff = find_staff(after)
        if len(staff) != len(find_staff(original)):
            return False
        for idx, ch in changes.items():
            s = staff[idx]
            for key in ("wage", "xp"):
                if key in ch and s[key] != ch[key]:
                    return False
            if "stamina" in ch and s["stamina"] != f32(ch["stamina"]):
                return False
        return True

    return _write_verified(sav_path, original, patched, check)


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
    return os.path.join(documents_dir(), "Ski-E-O Save Editor Backups")


def legacy_backup_root():
    """Folder used by versions before the rename (still listed for restoring)."""
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
            "playthrough": meta.get("PlaythroughId") or meta.get("ResortName") or name,
            "is_auto": bool(meta.get("bIsAutoSave", name.lower().startswith("autosave"))),
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


def apply_edit(sav_path, new_value):
    """Back up, patch, write and verify. Returns the backup folder.

    Raises EditorError on any problem; the original save is restored if
    verification fails.
    """
    with open(sav_path, "rb") as f:
        original = f.read()
    patched = patch_balance(original, new_value)
    return _write_verified(sav_path, original, patched, lambda after: read_balance(after) == new_value)


def apply_loan_edits(sav_path, changes):
    """Back up, patch the given loan values, write and verify. Returns the backup folder."""
    if not changes:
        raise EditorError("No loan changes were requested.")
    with open(sav_path, "rb") as f:
        original = f.read()
    patched = patch_loans(original, changes)

    def check(after):
        loans = find_loans(after)
        for idx, ch in changes.items():
            if "remaining" in ch and loans[idx]["remaining"] != ch["remaining"]:
                return False
            if "rate" in ch and loans[idx]["rate"] != f32(ch["rate"]):
                return False
        return len(loans) == len(find_loans(original))

    return _write_verified(sav_path, original, patched, check)


def _write_verified(sav_path, original, patched, check):
    backup_dir = make_backup(sav_path)
    write_atomic(sav_path, patched)
    with open(sav_path, "rb") as f:
        after = f.read()
    try:
        ok = len(after) == len(patched) and check(after)
    except EditorError:
        ok = False
    if not ok:
        shutil.copy2(os.path.join(backup_dir, os.path.basename(sav_path)), sav_path)
        raise EditorError("Verification failed, so your original save was put back. Nothing was changed.")
    return backup_dir


def list_backups():
    """Return backups newest first: dicts with dir, name, stamp, balance."""
    entries = []
    for root in (backup_root(), legacy_backup_root()):
        if not os.path.isdir(root):
            continue
        for stamp in sorted(os.listdir(root), reverse=True):
            d = os.path.join(root, stamp)
            if not os.path.isdir(d):
                continue
            for name in sorted(os.listdir(d)):
                if name.lower().endswith(".sav"):
                    try:
                        with open(os.path.join(d, name), "rb") as f:
                            bal = read_balance(f.read())
                    except (OSError, EditorError):
                        bal = None
                    entries.append({"dir": d, "name": name, "stamp": stamp, "balance": bal})
    entries.sort(key=lambda e: e["stamp"], reverse=True)
    return entries


def restore_backup(entry, save_dir):
    """Copy a backup over the live save. Backs up the current file first and
    returns that safety-backup folder (or None if there was no current file)."""
    target = os.path.join(save_dir, entry["name"])
    pre = make_backup(target) if os.path.isfile(target) else None
    for ext in (".sav", ".meta"):
        src = os.path.join(entry["dir"], os.path.splitext(entry["name"])[0] + ext)
        if os.path.isfile(src):
            with open(src, "rb") as f:
                write_atomic(os.path.join(save_dir, os.path.basename(src)), f.read())
    return pre


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


def pick_save_cli():
    """Ask which save to edit and run the version / game-running checks.
    Returns the chosen save dict, or None if the user cancelled."""
    save_dir = get_save_dir()
    if not save_dir:
        return None
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
        return None

    if chosen["version"] != (None, None) and chosen["version"] != TESTED_SAVE_VERSION:
        v = ".".join(str(x) for x in chosen["version"])
        t = ".".join(str(x) for x in TESTED_SAVE_VERSION)
        print(f"\nWARNING: this save is version {v}; this tool was tested with {t}.")
        print("The game may have been updated. The tool checks the file layout before it")
        print("changes anything, but a newer save format is untested.")
        if ask("Continue anyway? (y/n): ").lower() != "y":
            print("Cancelled.")
            return None

    if game_is_running():
        print("\nThe game seems to be running. Close it first, otherwise it can overwrite")
        print("your change with an autosave.")
        if ask("Continue anyway? (y/n): ").lower() != "y":
            print("Cancelled.")
            return None
    return chosen


def loans_flow():
    chosen = pick_save_cli()
    if not chosen:
        return
    with open(chosen["path"], "rb") as f:
        loans = find_loans(f.read())
    if not loans:
        raise EditorError("This save has no active loans.")
    print("\nActive loans:\n")
    for i, ln in enumerate(loans, 1):
        print(f"  [{i}] {ln['tier']:<7} original {ln['original']:>10,}  remaining {ln['remaining']:>10,}  "
              f"interest {ln['rate'] * 100:.2f}%/month  ({ln['months']} months)")
    print("\nFor each loan you can change the remaining amount and the monthly interest.")
    print("Press Enter to keep a value. 0 as remaining wipes the debt; click 'pay off' in the")
    print("game afterwards to remove the loan from the list (it costs nothing).\n")
    changes = {}
    for i, ln in enumerate(loans):
        print(f"Loan [{i + 1}] {ln['tier']}")
        ch = {}
        raw = ask(f"  New remaining amount (now {ln['remaining']:,}): ")
        if raw:
            ch["remaining"] = parse_amount(raw)
            if not (0 <= ch["remaining"] <= INT_MAX):
                raise EditorError(f"Remaining balance must be from 0 to {INT_MAX:,}.")
        raw = ask(f"  New monthly interest in % (now {ln['rate'] * 100:.2f}): ")
        if raw:
            ch["rate"] = parse_percent(raw)
        if ch:
            changes[i] = ch
    if not changes:
        print("Nothing to change.")
        return
    print("\nSummary:")
    for i, ch in changes.items():
        ln = loans[i]
        parts = []
        if "remaining" in ch:
            parts.append(f"remaining {ln['remaining']:,} -> {ch['remaining']:,}")
        if "rate" in ch:
            parts.append(f"interest {ln['rate'] * 100:.2f}% -> {ch['rate'] * 100:.2f}%")
        print(f"  Loan [{i + 1}] {ln['tier']}: " + ", ".join(parts))
    if ask("Apply these changes? (y/n): ").lower() != "y":
        print("Cancelled. Nothing was changed.")
        return
    backup_dir = apply_loan_edits(chosen["path"], changes)
    print(f"\nDone. A backup was saved to:\n  {backup_dir}")
    print("Load the save in the game. Loans with 0 remaining show a 'pay off' button.")


def staff_flow():
    chosen = pick_save_cli()
    if not chosen:
        return
    with open(chosen["path"], "rb") as f:
        staff = find_staff(f.read())
    if not staff:
        raise EditorError("This save has no staff.")
    summary = staff_summary(staff)
    print(f"\nStaff: {len(staff)} employees\n")
    print(f"  {'Role':<12}{'Count':>6}{'Avg wage/day':>14}{'Avg XP':>9}{'Avg stamina':>13}")
    for r in summary:
        print(f"  {pretty_role(r['role']):<12}{r['count']:>6}{r['wage']:>14,.0f}{r['xp']:>9,.0f}{r['stamina']:>12.0f}%")
    print("\nWho should be changed?")
    roles_present = [r["role"] for r in summary]
    for i, role in enumerate(roles_present, 1):
        print(f"  [{i}] {pretty_role(role)} only")
    print("  [a] Everybody")
    raw = ask("Choice (Enter to cancel): ").lower()
    if not raw:
        print("Cancelled.")
        return
    if raw == "a":
        roles, who = None, "everybody"
    elif raw.isdigit() and 1 <= int(raw) <= len(roles_present):
        roles = [roles_present[int(raw) - 1]]
        who = pretty_role(roles[0])
    else:
        raise EditorError("Please type one of the choices shown.")
    stamina = STAFF_STAMINA_MAX if ask("Refill stamina to 100%? (y/n): ").lower() == "y" else None
    wage = parse_wage_spec(ask("Daily wage: a number sets it for everyone chosen, a percent like 50% scales it, "
                               "Enter keeps: "))
    raw = ask("Set XP to (whole number, Enter keeps): ")
    xp = parse_amount(raw) if raw else None
    if xp is not None and not (0 <= xp <= INT_MAX):
        raise EditorError(f"XP must be from 0 to {INT_MAX:,}.")
    changes = build_staff_changes(staff, roles, wage, xp, stamina)
    if not changes or (stamina is None and wage is None and xp is None):
        print("Nothing to change.")
        return
    parts = []
    if stamina is not None:
        parts.append("stamina -> 100%")
    if wage is not None:
        parts.append(f"wage -> {wage[1]:,}" if wage[0] == "set" else f"wage x {wage[1] * 100:g}%")
    if xp is not None:
        parts.append(f"XP -> {xp:,}")
    print(f"\nChange {len(changes)} employee(s) ({who}): " + ", ".join(parts))
    if ask("Apply? (y/n): ").lower() != "y":
        print("Cancelled. Nothing was changed.")
        return
    backup_dir = apply_staff_edits(chosen["path"], changes)
    print(f"\nDone. A backup was saved to:\n  {backup_dir}")
    print("Load the save in the game. Wages and XP stay as set; stamina drains normally while working.")


def reputation_flow():
    chosen = pick_save_cli()
    if not chosen:
        return
    with open(chosen["path"], "rb") as f:
        rep = read_reputation(f.read())
    if rep is None:
        raise EditorError("This save has no reputation data.")
    xp, level = rep
    n = REPUTATION_LEVELS.index(level) + 1 if level in REPUTATION_LEVELS else None
    print(f"\nCurrent reputation: level {n or '?'} ({pretty_level(level)}), {xp:,} XP progress")
    print("XP is the progress inside the current level (it restarts after a level-up).")
    print("\nLevels:")
    for i, name in enumerate(REPUTATION_LEVELS, 1):
        need = REPUTATION_XP_TO_NEXT.get(i)
        print(f"  [{i:>2}] {pretty_level(name):<24}" + (f" needs {need:,} XP to level up" if need else "")
              + ("   <- current" if i == n else ""))
    raw = ask("\nNew level (1-14, 'max' for 14, Enter to keep): ").lower()
    new_level = None
    if raw:
        num = 14 if raw == "max" else int(raw) if raw.isdigit() else 0
        if not (1 <= num <= len(REPUTATION_LEVELS)):
            raise EditorError("Please type a level number from 1 to 14.")
        if REPUTATION_LEVELS[num - 1] != level:
            new_level = REPUTATION_LEVELS[num - 1]
    default_xp = "0" if new_level else str(xp)
    raw = ask(f"XP progress in that level (Enter = {int(default_xp):,}): ")
    new_xp = parse_amount(raw) if raw else int(default_xp)
    if not (0 <= new_xp <= INT_MAX):
        raise EditorError(f"Reputation XP must be from 0 to {INT_MAX:,}.")
    if new_level is None and new_xp == xp:
        print("Nothing to change.")
        return
    target = REPUTATION_LEVELS.index(new_level) + 1 if new_level else n
    print(f"\nChange: level {n} -> {target}, XP progress {xp:,} -> {new_xp:,}")
    warn = level_up_warning(target, new_xp) if target else ""
    if warn:
        print(warn)
    if ask("Apply? (y/n): ").lower() != "y":
        print("Cancelled. Nothing was changed.")
        return
    backup_dir = apply_reputation(chosen["path"], new_level, new_xp if new_xp != xp or new_level else None)
    print(f"\nDone. A backup was saved to:\n  {backup_dir}")
    print("Load the save in the game. (Going down a level may lock buildings you unlocked earlier.)")


def edit_flow():
    chosen = pick_save_cli()
    if not chosen:
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

    backup_dir = apply_edit(chosen["path"], new)

    print(f"\nDone. The balance in {chosen['name']} is now {new:,}.")
    print(f"A backup was saved to:\n  {backup_dir}")
    print("\nTips: start the game and load this save. If Steam Cloud brings back the old")
    print("file, turn Steam Cloud off for the game (Properties > General) and retry.")


def restore_flow():
    entries = list_backups()
    if not entries:
        raise EditorError("No backups found yet. They are created automatically when you edit a save.")
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
    if ask(f"Overwrite {chosen['name']} in your SaveGames with this backup? (y/n): ").lower() != "y":
        print("Cancelled.")
        return
    pre = restore_backup(chosen, save_dir)
    if pre:
        print(f"(Your current file was backed up first to: {pre})")
    print("Restored.")


def main():
    print(f"Ski-E-O Save Editor v{VERSION}  (unofficial fan tool, single-player only)")
    print("Close the game first. Backups go to:")
    print(f"  {backup_root()}\n")
    while True:
        print("  [1] Change the money balance of a save")
        print("  [2] Edit loans (remaining amount / interest)")
        print("  [3] Edit reputation (XP / level)")
        print("  [4] Edit staff (stamina / wages / XP)")
        print("  [5] Restore a backup")
        print("  [Enter] Quit")
        choice = ask("> ")
        try:
            if choice == "1":
                edit_flow()
            elif choice == "2":
                loans_flow()
            elif choice == "3":
                reputation_flow()
            elif choice == "4":
                staff_flow()
            elif choice == "5":
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
