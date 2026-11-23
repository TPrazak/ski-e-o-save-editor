"""Ski-E-O Save Editor - window version.

Same engine as ski_e_o_save_editor.py, with a simple window instead of a console.
Unofficial fan tool. Use at your own risk. See README.md.
"""
import os
import sys
import time
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox, ttk

import ski_e_o_save_editor as core

# ---- look & feel ----
BG = "#f4f6f9"
CARD = "#ffffff"
TEXT = "#1f2933"
MUTED = "#6b7785"
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
BORDER = "#dde3ea"
NEG = "#c0392b"
FONT = "Segoe UI"


def fmt_time(ts):
    return time.strftime("%d %b %Y, %H:%M", time.localtime(ts))


def enable_hidpi():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


class FlatButton(tk.Label):
    """A flat button that looks the same on every Windows version."""

    def __init__(self, parent, text, command, primary=False, **kw):
        self.primary = primary
        self.command = command
        self.normal = ACCENT if primary else CARD
        self.hover = ACCENT_HOVER if primary else "#eef2f7"
        super().__init__(
            parent, text=text, bg=self.normal, fg="white" if primary else TEXT,
            font=(FONT, 10, "bold" if primary else "normal"), cursor="hand2",
            padx=18 if primary else 12, pady=7,
            highlightthickness=0 if primary else 1, highlightbackground=BORDER, **kw)
        self.bind("<Enter>", lambda e: self.configure(bg=self.hover))
        self.bind("<Leave>", lambda e: self.configure(bg=self.normal))
        self.bind("<Button-1>", lambda e: self.command())


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Ski-E-O Save Editor v{core.VERSION}")
        self.configure(bg=BG)
        self.minsize(680, 680)
        self.geometry("720x720")
        self.save_dir = core.default_save_dir()
        self.all_saves = []
        self.saves = []
        self.show_all = tk.BooleanVar(value=False)
        self.amount = tk.StringVar()
        self.current_text = tk.StringVar(value="Pick a save above")
        self.status = tk.StringVar(value="")
        self._style()
        self._menu()
        self._build()
        self.after(100, self.startup)

    # ---- layout ----
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
                    rowheight=34, borderwidth=0, font=(FONT, 10))
        s.configure("Treeview.Heading", background=CARD, foreground=MUTED,
                    font=(FONT, 9, "bold"), borderwidth=0, relief="flat", padding=(8, 6))
        s.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", TEXT)])
        s.map("Treeview.Heading", background=[("active", CARD)])
        s.configure("TCheckbutton", background=BG, foreground=MUTED, font=(FONT, 9))
        s.configure("Vertical.TScrollbar", background=BORDER, troughcolor=CARD, borderwidth=0)

    def _menu(self):
        bar = tk.Menu(self)
        tools = tk.Menu(bar, tearoff=0)
        tools.add_command(label="Restore a backup...", command=self.restore_dialog)
        tools.add_command(label="Open backups folder", command=self.open_backups)
        tools.add_separator()
        tools.add_command(label="Change save folder...", command=self.choose_dir)
        tools.add_command(label="Refresh", command=self.refresh)
        bar.add_cascade(label="Tools", menu=tools)
        help_ = tk.Menu(bar, tearoff=0)
        help_.add_command(label="About", command=lambda: messagebox.showinfo(
            "About", f"Ski-E-O Save Editor v{core.VERSION}\n\nUnofficial fan tool for single-player "
                     "saves. Not affiliated with the game's developers. Use at your own risk."))
        bar.add_cascade(label="Help", menu=help_)
        self.config(menu=bar)

    def _card(self, parent, title):
        wrap = tk.Frame(parent, bg=BG)
        tk.Label(wrap, text=title, bg=BG, fg=TEXT, font=(FONT, 11, "bold")).pack(anchor="w", pady=(0, 6))
        card = tk.Frame(wrap, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="both", expand=True)
        return wrap, card

    def _build(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=22, pady=18)

        tk.Label(outer, text="Ski-E-O Save Editor", bg=BG, fg=TEXT,
                 font=(FONT, 18, "bold")).pack(anchor="w")
        tk.Label(outer, text="Close the game first. A backup is made automatically before every change.",
                 bg=BG, fg=MUTED, font=(FONT, 10)).pack(anchor="w", pady=(0, 14))

        # step 1
        w1, c1 = self._card(outer, "1   Pick a save")
        w1.pack(fill="both", expand=True)
        cols = ("resort", "slot", "saved", "balance")
        self.tree = ttk.Treeview(c1, columns=cols, show="headings", selectmode="browse", height=6)
        for c, text, width, anchor in (
            ("resort", "RESORT", 210, "w"), ("slot", "SAVE", 110, "w"),
            ("saved", "LAST SAVED", 150, "w"), ("balance", "BALANCE", 100, "e"),
        ):
            self.tree.heading(c, text=text, anchor=anchor)
            self.tree.column(c, width=width, anchor=anchor)
        self.tree.tag_configure("odd", background="#f8fafc")
        self.tree.tag_configure("neg", foreground=NEG)
        sb = ttk.Scrollbar(c1, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())
        self.tree.bind("<Double-1>", lambda e: self.focus_amount())

        ttk.Checkbutton(outer, text="Show all save slots (autosaves 1-5 and manual saves)",
                        variable=self.show_all, command=self.refresh).pack(anchor="w", pady=(6, 10))

        # step 2
        w2, c2 = self._card(outer, "2   Set the new balance")
        w2.pack(fill="x")
        inner = tk.Frame(c2, bg=CARD)
        inner.pack(fill="x", padx=16, pady=14)

        tk.Label(inner, textvariable=self.current_text, bg=CARD, fg=MUTED,
                 font=(FONT, 10)).grid(row=0, column=0, columnspan=3, sticky="w")
        self.entry = tk.Entry(inner, textvariable=self.amount, font=(FONT, 16), relief="flat",
                              bg="#f1f5f9", fg=TEXT, insertbackground=TEXT, width=14,
                              highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        self.entry.grid(row=1, column=0, sticky="w", pady=(8, 0), ipady=6)
        self.entry.bind("<Return>", lambda e: self.apply())
        FlatButton(inner, "Apply", self.apply, primary=True).grid(row=1, column=1, padx=(12, 0), pady=(8, 0))

        chips = tk.Frame(inner, bg=CARD)
        chips.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        tk.Label(chips, text="Quick amounts:", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(0, 8))
        for label, value in (("100K", 100_000), ("1M", 1_000_000), ("5M", 5_000_000), ("10M", 10_000_000)):
            b = FlatButton(chips, label, lambda v=value: self.amount.set(f"{v:,}"))
            b.configure(padx=10, pady=3, font=(FONT, 9))
            b.pack(side="left", padx=(0, 6))

        more = tk.Frame(inner, bg=CARD)
        more.grid(row=3, column=0, columnspan=3, sticky="w", pady=(14, 0))
        tk.Label(more, text="More edits:", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(0, 8))
        FlatButton(more, "Loans...", self.loans_dialog).pack(side="left", padx=(0, 8))
        FlatButton(more, "Reputation...", self.reputation_dialog).pack(side="left", padx=(0, 8))
        FlatButton(more, "Staff...", self.staff_dialog).pack(side="left")

        tk.Label(outer, textvariable=self.status, bg=BG, fg=MUTED, font=(FONT, 9),
                 anchor="w", justify="left", wraplength=640).pack(fill="x", pady=(12, 0))

    # ---- helpers ----
    def focus_amount(self):
        self.entry.focus_set()
        self.entry.select_range(0, "end")

    def startup(self):
        if not os.path.isdir(self.save_dir):
            messagebox.showinfo(
                "Save folder not found",
                "Could not find the save folder:\n" + self.save_dir + "\n\nPlease choose it.")
            if not self.choose_dir():
                return
        self.refresh()

    def choose_dir(self):
        d = filedialog.askdirectory(title="Choose your SaveGames folder",
                                    initialdir=os.path.dirname(self.save_dir) or None)
        if d:
            self.save_dir = d
            self.refresh()
            return True
        return False

    def refresh(self):
        try:
            self.all_saves = core.list_saves(self.save_dir) if os.path.isdir(self.save_dir) else []
        except OSError as e:
            self.all_saves = []
            messagebox.showerror("Error", f"Could not read the save folder:\n{e}")
        if self.show_all.get():
            self.saves = list(self.all_saves)
        else:  # newest save per playthrough (the list is already newest first)
            seen, self.saves = set(), []
            for s in self.all_saves:
                if s["playthrough"] not in seen:
                    seen.add(s["playthrough"])
                    self.saves.append(s)
        self.tree.delete(*self.tree.get_children())
        for i, s in enumerate(self.saves):
            tags = ["odd"] if i % 2 else []
            if s["balance"] < 0:
                tags.append("neg")
            self.tree.insert("", "end", iid=str(i), tags=tags, values=(
                s["resort"], (s["label"] or "Autosave") if s["is_auto"] else "Manual save",
                fmt_time(s["mtime"]), f"{s['balance']:,}"))
        if self.saves:
            self.tree.selection_set("0")
            self.status.set(f"{len(self.saves)} save(s) shown.  Saves folder: {self.save_dir}")
        else:
            self.current_text.set("No saves found")
            self.status.set("No editable saves found in " + self.save_dir)

    def selected(self):
        sel = self.tree.selection()
        return self.saves[int(sel[0])] if sel else None

    def _on_select(self):
        s = self.selected()
        if s:
            self.current_text.set(f"{s['resort']}  -  current balance {s['balance']:,}")

    def open_backups(self):
        root = core.backup_root()
        os.makedirs(root, exist_ok=True)
        try:
            os.startfile(root)  # Windows only
        except Exception:
            messagebox.showinfo("Backups folder", root)

    def _guard_game_and_version(self, save):
        if save["version"] != (None, None) and save["version"] != core.TESTED_SAVE_VERSION:
            v = ".".join(str(x) for x in save["version"])
            t = ".".join(str(x) for x in core.TESTED_SAVE_VERSION)
            if not messagebox.askyesno(
                    "Untested save version",
                    f"This save is version {v}; the tool was tested with {t}.\n"
                    "The game may have been updated. The tool still checks the file "
                    "layout before changing anything.\n\nContinue anyway?"):
                return False
        if core.game_is_running():
            if not messagebox.askyesno(
                    "Game is running",
                    "The game seems to be running. Close it first, otherwise it can "
                    "overwrite your change with an autosave.\n\nContinue anyway?"):
                return False
        return True

    # ---- actions ----
    def apply(self):
        try:
            save = self.selected()
            if not save:
                messagebox.showinfo("Pick a save", "Select a save in the list first.")
                return
            try:
                new = core.parse_amount(self.amount.get().strip())
            except core.EditorError as e:
                messagebox.showwarning("New balance", f"{e}\nType a whole number such as 2000000.")
                return
            if not (core.INT_MIN <= new <= core.INT_MAX):
                messagebox.showwarning("New balance", f"Balance must be between {core.INT_MIN:,} and {core.INT_MAX:,}.")
                return
            if not self._guard_game_and_version(save):
                return
            warn = ("\n\nNote: very large values may overflow in game calculations."
                    if new > 1_000_000_000 else "")
            if not messagebox.askyesno(
                    "Confirm",
                    f"Resort: {save['resort']}\nFile: {save['name']}\n\n"
                    f"Change balance {save['balance']:,}  ->  {new:,} ?{warn}"):
                return
            backup_dir = core.apply_edit(save["path"], new)
            self.refresh()
            messagebox.showinfo(
                "Done",
                f"The balance is now {new:,}.\n\nBackup saved to:\n{backup_dir}\n\n"
                "Start the game and load this save. If Steam Cloud brings back the old "
                "file, turn Steam Cloud off for the game and retry.")
        except core.EditorError as e:
            messagebox.showerror("Nothing was changed", str(e))
        except PermissionError as e:
            messagebox.showerror("Access denied",
                                 f"Windows denied access to {e.filename or 'a file'}.\n"
                                 "Close the game and any program using the save, then try again.")
        except Exception:
            messagebox.showerror("Unexpected error", traceback.format_exc())

    def loans_dialog(self):
        try:
            save = self.selected()
            if not save:
                messagebox.showinfo("Pick a save", "Select a save in the list first.")
                return
            with open(save["path"], "rb") as f:
                loans = core.find_loans(f.read())
        except core.EditorError as e:
            messagebox.showerror("Loans", str(e))
            return
        except Exception:
            messagebox.showerror("Unexpected error", traceback.format_exc())
            return
        if not loans:
            messagebox.showinfo("Loans", f"{save['resort']} has no active loans.")
            return

        win = tk.Toplevel(self)
        win.title("Edit loans")
        win.configure(bg=BG)
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="Edit loans", bg=BG, fg=TEXT, font=(FONT, 14, "bold")).pack(anchor="w", padx=18, pady=(14, 0))
        tk.Label(win, text=f"{save['resort']}.  Leave a box unchanged to keep its value.\n"
                           "Remaining 0 wipes the debt: click \"pay off\" on that loan in the game "
                           "afterwards to remove it (it costs nothing).",
                 bg=BG, fg=MUTED, font=(FONT, 10), justify="left").pack(anchor="w", padx=18, pady=(0, 10))

        card = tk.Frame(win, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=18)
        grid = tk.Frame(card, bg=CARD)
        grid.pack(fill="x", padx=14, pady=12)
        heads = ("LOAN", "ORIGINAL", "REMAINING NOW", "NEW REMAINING", "INTEREST NOW", "NEW INTEREST %")
        for c, h in enumerate(heads):
            tk.Label(grid, text=h, bg=CARD, fg=MUTED, font=(FONT, 8, "bold")).grid(
                row=0, column=c, sticky="w", padx=(0, 14), pady=(0, 6))
        rem_vars, rate_vars = [], []
        for r, ln in enumerate(loans, 1):
            tk.Label(grid, text=ln["tier"], bg=CARD, fg=TEXT, font=(FONT, 10, "bold")).grid(
                row=r, column=0, sticky="w", padx=(0, 14), pady=4)
            tk.Label(grid, text=f"{ln['original']:,}", bg=CARD, fg=TEXT, font=(FONT, 10)).grid(
                row=r, column=1, sticky="w", padx=(0, 14))
            tk.Label(grid, text=f"{ln['remaining']:,}", bg=CARD, fg=TEXT, font=(FONT, 10)).grid(
                row=r, column=2, sticky="w", padx=(0, 14))
            rv = tk.StringVar(value=f"{ln['remaining']}")
            tk.Entry(grid, textvariable=rv, width=12, font=(FONT, 10), relief="flat", bg="#f1f5f9",
                     highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT).grid(
                row=r, column=3, sticky="w", padx=(0, 14), ipady=3)
            tk.Label(grid, text=f"{ln['rate'] * 100:.2f}% / month", bg=CARD, fg=TEXT, font=(FONT, 10)).grid(
                row=r, column=4, sticky="w", padx=(0, 14))
            pv = tk.StringVar(value=f"{ln['rate'] * 100:.2f}")
            tk.Entry(grid, textvariable=pv, width=8, font=(FONT, 10), relief="flat", bg="#f1f5f9",
                     highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT).grid(
                row=r, column=5, sticky="w", ipady=3)
            rem_vars.append(rv)
            rate_vars.append(pv)

        quick = tk.Frame(win, bg=BG)
        quick.pack(fill="x", padx=18, pady=(10, 0))
        tk.Label(quick, text="Quick:", bg=BG, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(0, 8))

        def zero(vars_):
            for v in vars_:
                v.set("0")

        b1 = FlatButton(quick, "Remaining -> 0 for all", lambda: zero(rem_vars))
        b1.configure(padx=10, pady=3, font=(FONT, 9))
        b1.pack(side="left", padx=(0, 6))
        b2 = FlatButton(quick, "Interest -> 0% for all", lambda: zero(rate_vars))
        b2.configure(padx=10, pady=3, font=(FONT, 9))
        b2.pack(side="left")

        def do_apply():
            try:
                changes = {}
                for i, ln in enumerate(loans):
                    ch = {}
                    rem_txt = rem_vars[i].get().strip()
                    if rem_txt and core.parse_amount(rem_txt) != ln["remaining"]:
                        ch["remaining"] = core.parse_amount(rem_txt)
                    rate_txt = rate_vars[i].get().strip()
                    if rate_txt:
                        new_rate = core.parse_percent(rate_txt)
                        if round(new_rate * 100, 2) != round(ln["rate"] * 100, 2):
                            ch["rate"] = new_rate
                    if ch:
                        changes[i] = ch
                if not changes:
                    messagebox.showinfo("Edit loans", "Nothing to change.", parent=win)
                    return
                for i, ch in changes.items():
                    if "remaining" in ch and not (0 <= ch["remaining"] <= core.INT_MAX):
                        raise core.EditorError(f"Remaining balance must be from 0 to {core.INT_MAX:,}.")
                lines = []
                for i, ch in changes.items():
                    ln = loans[i]
                    parts = []
                    if "remaining" in ch:
                        parts.append(f"remaining {ln['remaining']:,} -> {ch['remaining']:,}")
                    if "rate" in ch:
                        parts.append(f"interest {ln['rate'] * 100:.2f}% -> {ch['rate'] * 100:.2f}%")
                    lines.append(f"{ln['tier']}: " + ", ".join(parts))
                if not self._guard_game_and_version(save):
                    return
                if not messagebox.askyesno("Confirm", "Apply these loan changes?\n\n" + "\n".join(lines), parent=win):
                    return
                backup_dir = core.apply_loan_edits(save["path"], changes)
                win.destroy()
                self.refresh()
                messagebox.showinfo(
                    "Done", f"Loans updated.\n\nBackup saved to:\n{backup_dir}\n\n"
                            "Load the save in the game. A loan with 0 remaining shows a \"pay off\" "
                            "button; click it to remove the loan (it costs nothing).")
            except core.EditorError as e:
                messagebox.showerror("Nothing was changed", str(e), parent=win)
            except PermissionError as e:
                messagebox.showerror("Access denied",
                                     f"Windows denied access to {e.filename or 'a file'}.\n"
                                     "Close the game and try again.", parent=win)
            except Exception:
                messagebox.showerror("Unexpected error", traceback.format_exc(), parent=win)

        btns = tk.Frame(win, bg=BG)
        btns.pack(pady=14)
        FlatButton(btns, "Apply", do_apply, primary=True).pack(side="left", padx=6)
        FlatButton(btns, "Cancel", win.destroy).pack(side="left", padx=6)

    def reputation_dialog(self):
        try:
            save = self.selected()
            if not save:
                messagebox.showinfo("Pick a save", "Select a save in the list first.")
                return
            with open(save["path"], "rb") as f:
                rep = core.read_reputation(f.read())
        except core.EditorError as e:
            messagebox.showerror("Reputation", str(e))
            return
        except Exception:
            messagebox.showerror("Unexpected error", traceback.format_exc())
            return
        if rep is None:
            messagebox.showinfo("Reputation", f"{save['resort']} has no reputation data.")
            return
        xp, level = rep
        levels = core.REPUTATION_LEVELS
        cur_n = levels.index(level) + 1 if level in levels else None

        def label(i):
            need = core.REPUTATION_XP_TO_NEXT.get(i)
            return f"{i}  -  {core.pretty_level(levels[i - 1])}" + (f"   ({need:,} XP to level up)" if need else "")

        win = tk.Toplevel(self)
        win.title("Edit reputation")
        win.configure(bg=BG)
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="Edit reputation", bg=BG, fg=TEXT, font=(FONT, 14, "bold")).pack(anchor="w", padx=18, pady=(14, 0))
        tk.Label(win, text=f"{save['resort']}\n"
                           "Pick a level and the XP progress inside that level (XP restarts at 0 after a level-up).",
                 bg=BG, fg=MUTED, font=(FONT, 10), justify="left").pack(anchor="w", padx=18, pady=(0, 10))
        card = tk.Frame(win, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=18)
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=16, pady=14)
        now = (f"level {cur_n} of {len(levels)} ({core.pretty_level(level)})" if cur_n else core.pretty_level(level))
        tk.Label(inner, text=f"Now: {now},  {xp:,} XP progress", bg=CARD, fg=TEXT,
                 font=(FONT, 11, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")

        tk.Label(inner, text="Level:", bg=CARD, fg=MUTED, font=(FONT, 10)).grid(row=1, column=0, sticky="w", pady=(14, 0))
        combo = ttk.Combobox(inner, state="readonly", width=42, font=(FONT, 10),
                             values=[label(i) for i in range(1, len(levels) + 1)])
        combo.current((cur_n or 1) - 1)
        combo.grid(row=1, column=1, columnspan=2, sticky="w", padx=(10, 0), pady=(14, 0))

        tk.Label(inner, text="XP progress:", bg=CARD, fg=MUTED, font=(FONT, 10)).grid(row=2, column=0, sticky="w", pady=(10, 0))
        var = tk.StringVar(value=f"{xp}")
        ent = tk.Entry(inner, textvariable=var, font=(FONT, 14), relief="flat", bg="#f1f5f9", fg=TEXT,
                       width=14, highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        ent.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(10, 0), ipady=4)

        def on_level_change(_e=None):
            if combo.current() + 1 != cur_n:
                var.set("0")  # a new level normally starts with no progress
            else:
                var.set(f"{xp}")

        combo.bind("<<ComboboxSelected>>", on_level_change)

        quick = tk.Frame(inner, bg=CARD)
        quick.grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 0))
        tk.Label(quick, text="Quick:", bg=CARD, fg=MUTED, font=(FONT, 9)).pack(side="left", padx=(0, 8))

        def set_max():
            combo.current(len(levels) - 1)
            var.set("0")

        b = FlatButton(quick, "Maximum level", set_max)
        b.configure(padx=10, pady=3, font=(FONT, 9))
        b.pack(side="left")
        tk.Label(inner, text="Going down a level may lock buildings you unlocked earlier. "
                             "At the top level the game no longer shows the exact XP.",
                 bg=CARD, fg=MUTED, font=(FONT, 9), wraplength=560, justify="left").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))

        def do_apply():
            try:
                new_n = combo.current() + 1
                new_xp = core.parse_amount(var.get().strip())
                if not (0 <= new_xp <= core.INT_MAX):
                    raise core.EditorError(f"Reputation XP must be from 0 to {core.INT_MAX:,}.")
                new_level = levels[new_n - 1] if new_n != cur_n else None
                if new_level is None and new_xp == xp:
                    messagebox.showinfo("Edit reputation", "Nothing to change.", parent=win)
                    return
                if not self._guard_game_and_version(save):
                    return
                warn = core.level_up_warning(new_n, new_xp)
                if not messagebox.askyesno(
                        "Confirm",
                        f"Resort: {save['resort']}\n\nLevel {cur_n} -> {new_n}\n"
                        f"XP progress {xp:,} -> {new_xp:,}" + (f"\n\n{warn}" if warn else ""),
                        parent=win):
                    return
                backup_dir = core.apply_reputation(save["path"], new_level,
                                                   new_xp if (new_xp != xp or new_level) else None)
                win.destroy()
                self.refresh()
                messagebox.showinfo(
                    "Done", f"Reputation updated.\n\nBackup saved to:\n{backup_dir}\n\n"
                            "Load the save in the game.")
            except core.EditorError as e:
                messagebox.showerror("Nothing was changed", str(e), parent=win)
            except PermissionError as e:
                messagebox.showerror("Access denied",
                                     f"Windows denied access to {e.filename or 'a file'}.\n"
                                     "Close the game and try again.", parent=win)
            except Exception:
                messagebox.showerror("Unexpected error", traceback.format_exc(), parent=win)

        btns = tk.Frame(win, bg=BG)
        btns.pack(pady=14)
        FlatButton(btns, "Apply", do_apply, primary=True).pack(side="left", padx=6)
        FlatButton(btns, "Cancel", win.destroy).pack(side="left", padx=6)
        ent.focus_set()

    def staff_dialog(self):
        try:
            save = self.selected()
            if not save:
                messagebox.showinfo("Pick a save", "Select a save in the list first.")
                return
            with open(save["path"], "rb") as f:
                staff = core.find_staff(f.read())
        except core.EditorError as e:
            messagebox.showerror("Staff", str(e))
            return
        except Exception:
            messagebox.showerror("Unexpected error", traceback.format_exc())
            return
        if not staff:
            messagebox.showinfo("Staff", f"{save['resort']} has no staff.")
            return
        summary = core.staff_summary(staff)
        roles_present = [r["role"] for r in summary]

        win = tk.Toplevel(self)
        win.title("Edit staff")
        win.configure(bg=BG)
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="Edit staff", bg=BG, fg=TEXT, font=(FONT, 14, "bold")).pack(anchor="w", padx=18, pady=(14, 0))
        tk.Label(win, text=f"{save['resort']}  -  {len(staff)} employees. Choose who to change and what to change; "
                           "leave an option off to keep it.",
                 bg=BG, fg=MUTED, font=(FONT, 10), justify="left", wraplength=620).pack(anchor="w", padx=18, pady=(0, 10))

        card = tk.Frame(win, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=18)
        grid = tk.Frame(card, bg=CARD)
        grid.pack(fill="x", padx=14, pady=12)
        for c, h in enumerate(("ROLE", "COUNT", "AVG WAGE / DAY", "AVG XP", "AVG STAMINA")):
            tk.Label(grid, text=h, bg=CARD, fg=MUTED, font=(FONT, 8, "bold")).grid(
                row=0, column=c, sticky="w", padx=(0, 18), pady=(0, 4))
        for r, row in enumerate(summary, 1):
            vals = (core.pretty_role(row["role"]), f"{row['count']}", f"{row['wage']:,.0f}",
                    f"{row['xp']:,.0f}", f"{row['stamina']:.0f}%")
            for c, v in enumerate(vals):
                tk.Label(grid, text=v, bg=CARD, fg=TEXT, font=(FONT, 10, "bold" if c == 0 else "normal")).grid(
                    row=r, column=c, sticky="w", padx=(0, 18), pady=2)

        opts = tk.Frame(win, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        opts.pack(fill="x", padx=18, pady=(10, 0))
        o = tk.Frame(opts, bg=CARD)
        o.pack(fill="x", padx=14, pady=12)

        tk.Label(o, text="Change:", bg=CARD, fg=MUTED, font=(FONT, 10)).grid(row=0, column=0, sticky="w")
        who = ttk.Combobox(o, state="readonly", width=22, font=(FONT, 10),
                           values=["Everybody"] + [core.pretty_role(r) + " only" for r in roles_present])
        who.current(0)
        who.grid(row=0, column=1, sticky="w", padx=(10, 0))

        stam = tk.BooleanVar(value=False)
        tk.Checkbutton(o, text="Refill stamina to 100%", variable=stam, bg=CARD, activebackground=CARD,
                       fg=TEXT, font=(FONT, 10)).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 0))

        tk.Label(o, text="Daily wage:", bg=CARD, fg=MUTED, font=(FONT, 10)).grid(row=2, column=0, sticky="w", pady=(8, 0))
        wage_mode = ttk.Combobox(o, state="readonly", width=22, font=(FONT, 10),
                                 values=["Keep", "Set to amount", "Scale by percent"])
        wage_mode.current(0)
        wage_mode.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(8, 0))
        wage_var = tk.StringVar()
        tk.Entry(o, textvariable=wage_var, width=10, font=(FONT, 10), relief="flat", bg="#f1f5f9",
                 highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT).grid(
            row=2, column=2, sticky="w", padx=(10, 0), pady=(8, 0), ipady=3)
        tk.Label(o, text="(e.g. 150, or 50 for 50 %)", bg=CARD, fg=MUTED, font=(FONT, 9)).grid(
            row=2, column=3, sticky="w", padx=(8, 0), pady=(8, 0))

        tk.Label(o, text="XP:", bg=CARD, fg=MUTED, font=(FONT, 10)).grid(row=3, column=0, sticky="w", pady=(8, 0))
        xp_mode = ttk.Combobox(o, state="readonly", width=22, font=(FONT, 10), values=["Keep", "Set to"])
        xp_mode.current(0)
        xp_mode.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=(8, 0))
        xp_var = tk.StringVar()
        tk.Entry(o, textvariable=xp_var, width=10, font=(FONT, 10), relief="flat", bg="#f1f5f9",
                 highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT).grid(
            row=3, column=2, sticky="w", padx=(10, 0), pady=(8, 0), ipady=3)
        tk.Label(o, text="(enough XP makes a promotion available)", bg=CARD, fg=MUTED, font=(FONT, 9)).grid(
            row=3, column=3, sticky="w", padx=(8, 0), pady=(8, 0))

        def do_apply():
            try:
                sel = who.current()
                roles = None if sel == 0 else [roles_present[sel - 1]]
                who_text = "everybody" if roles is None else core.pretty_role(roles[0])
                stamina = core.STAFF_STAMINA_MAX if stam.get() else None
                wage = None
                if wage_mode.current() == 1:
                    wage = core.parse_wage_spec(wage_var.get())
                    if wage is None or wage[0] != "set":
                        raise core.EditorError("Type the daily wage as a whole number, e.g. 150.")
                elif wage_mode.current() == 2:
                    raw = wage_var.get().strip().rstrip("%")
                    wage = core.parse_wage_spec(raw + "%")
                    if wage is None:
                        raise core.EditorError("Type the percent, e.g. 50 for half.")
                xp = None
                if xp_mode.current() == 1:
                    xp = core.parse_amount(xp_var.get().strip())
                    if not (0 <= xp <= core.INT_MAX):
                        raise core.EditorError(f"XP must be from 0 to {core.INT_MAX:,}.")
                if stamina is None and wage is None and xp is None:
                    messagebox.showinfo("Edit staff", "Nothing to change. Tick or choose something first.", parent=win)
                    return
                changes = core.build_staff_changes(staff, roles, wage, xp, stamina)
                if not changes:
                    messagebox.showinfo("Edit staff", "No matching employees.", parent=win)
                    return
                parts = []
                if stamina is not None:
                    parts.append("stamina -> 100%")
                if wage is not None:
                    parts.append(f"wage -> {wage[1]:,}" if wage[0] == "set" else f"wage x {wage[1] * 100:g}%")
                if xp is not None:
                    parts.append(f"XP -> {xp:,}")
                if not self._guard_game_and_version(save):
                    return
                if not messagebox.askyesno(
                        "Confirm", f"Resort: {save['resort']}\n\nChange {len(changes)} employee(s) ({who_text}):\n"
                                   + "\n".join(parts), parent=win):
                    return
                backup_dir = core.apply_staff_edits(save["path"], changes)
                win.destroy()
                self.refresh()
                messagebox.showinfo(
                    "Done", f"Updated {len(changes)} employee(s).\n\nBackup saved to:\n{backup_dir}\n\n"
                            "Load the save in the game.")
            except core.EditorError as e:
                messagebox.showerror("Nothing was changed", str(e), parent=win)
            except PermissionError as e:
                messagebox.showerror("Access denied",
                                     f"Windows denied access to {e.filename or 'a file'}.\n"
                                     "Close the game and try again.", parent=win)
            except Exception:
                messagebox.showerror("Unexpected error", traceback.format_exc(), parent=win)

        btns = tk.Frame(win, bg=BG)
        btns.pack(pady=14)
        FlatButton(btns, "Apply", do_apply, primary=True).pack(side="left", padx=6)
        FlatButton(btns, "Cancel", win.destroy).pack(side="left", padx=6)

    def restore_dialog(self):
        entries = core.list_backups()
        if not entries:
            messagebox.showinfo("Restore", "No backups yet. They are created automatically when you edit a save.")
            return
        win = tk.Toplevel(self)
        win.title("Restore a backup")
        win.configure(bg=BG)
        win.geometry("640x400")
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="Restore a backup", bg=BG, fg=TEXT, font=(FONT, 14, "bold")).pack(anchor="w", padx=18, pady=(14, 0))
        tk.Label(win, text="Choose a backup to put back into your saves folder.\n"
                           "Your current file is backed up first.", bg=BG, fg=MUTED,
                 font=(FONT, 10), justify="left").pack(anchor="w", padx=18, pady=(0, 10))
        holder = tk.Frame(win, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        holder.pack(fill="both", expand=True, padx=18)
        tree = ttk.Treeview(holder, columns=("when", "file", "balance"), show="headings", selectmode="browse")
        for c, t, w, a in (("when", "BACKUP TIME", 170, "w"), ("file", "SAVE FILE", 240, "w"), ("balance", "BALANCE", 90, "e")):
            tree.heading(c, text=t, anchor=a)
            tree.column(c, width=w, anchor=a)
        for i, e in enumerate(entries):
            tree.insert("", "end", iid=str(i), values=(
                e["stamp"], e["name"],
                f"{e['balance']:,}" if e["balance"] is not None else "?"))
        tree.pack(fill="both", expand=True)
        tree.selection_set("0")

        def do_restore():
            sel = tree.selection()
            if not sel:
                return
            e = entries[int(sel[0])]
            if core.game_is_running() and not messagebox.askyesno(
                    "Game is running", "Close the game before restoring.\n\nContinue anyway?", parent=win):
                return
            if not messagebox.askyesno(
                    "Confirm", f"Overwrite {e['name']} with this backup?\n"
                               "Your current file is backed up first.", parent=win):
                return
            try:
                pre = core.restore_backup(e, self.save_dir)
            except PermissionError:
                messagebox.showerror("Access denied", "Close the game and try again.", parent=win)
                return
            except Exception:
                messagebox.showerror("Unexpected error", traceback.format_exc(), parent=win)
                return
            win.destroy()
            self.refresh()
            messagebox.showinfo("Restored", "Backup restored." + (f"\nPrevious file saved to:\n{pre}" if pre else ""))

        FlatButton(win, "Restore selected", do_restore, primary=True).pack(pady=14)


def main():
    enable_hidpi()
    try:
        App().mainloop()
    except Exception:
        # No console in the windowed .exe, so show the error in a dialog.
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Ski-E-O Save Editor", traceback.format_exc())
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
