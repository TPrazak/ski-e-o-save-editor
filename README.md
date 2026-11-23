# Ski-E-O Balance Editor

A small, open-source tool that changes the **money balance** in a save file of
**Ski-E-O! Ski Resort Tycoon** (single-player). Pick a save in a simple window, type the
new balance, click Apply. A backup is made first and can be restored from the same window.

> Unofficial fan tool. Not affiliated with the game's developers. Use at your own risk.

## Download

**Windows (no install):**
1. Download `ski_e_o_balance_editor_gui_v1.1.0.zip` from the [Releases](../../releases) page.
2. **Extract the whole zip** (right-click > Extract All). Do not run it from inside the zip.
3. Open the extracted folder and run `ski_e_o_balance_editor_gui.exe`.
   Keep the `_internal` folder next to the `.exe`.

**From source (any system with Python 3.10+, no extra packages):**
```
python ski_e_o_balance_editor_gui.py     # window version
python ski_e_o_balance_editor.py         # console version
```
On Windows you can also double-click `run_gui.bat`.

### About antivirus warnings (please read)

The `.exe` is an unsigned [PyInstaller](https://pyinstaller.org) build, and antivirus
engines flag such files by mistake fairly often. Current status of the v1.1.0 `.exe`:

- VirusTotal: **4 of 69 engines flag it** (Microsoft, Arctic Wolf, SecureAge, Skyhigh;
  generic machine-learning style labels such as `Trojan:Win32/Wacatac.C!ml`).
  [Scan report](https://www.virustotal.com/gui/file/bf7a3f7bf8b6b8381adf41159533d6a176fddee45f2cee418df15fdd208b03db)
- I submitted the file to Microsoft as a false positive. *Result: pending* (this section
  will be updated when Microsoft answers).

I believe these are false positives, but you do not have to take my word for it:

- The tool has **no network code**. It only reads/writes save files in
  `%LOCALAPPDATA%\Ski-E-O\SaveGames`, writes backups to your Documents folder, and runs
  `tasklist` once to check whether the game is running. Read the source to check.
- If you would rather not run an `.exe`, **run the Python source instead** (see above),
  or build the `.exe` yourself (see below).
- SHA-256 of `ski_e_o_balance_editor_gui.exe` inside the zip, to confirm it is the scanned file:
  `BF7A3F7BF8B6B8381ADF41159533D6A176FDDEE45F2CEE418DF15FDD208B03DB`

Windows SmartScreen may also show a warning because the file is new and unsigned.

## How to use

1. **Close the game completely.**
2. *(Recommended)* In Steam, right-click the game > Properties > General, and turn off
   **Steam Cloud** for it. Otherwise Steam can bring back your old save.
3. Start the tool.
4. **Step 1 - Pick a save.** The list shows one row per resort (its newest save) with the
   current balance. Tick *Show all save slots* to see every autosave and manual save.
5. **Step 2 - Set the new balance.** Type a whole number (for example `2000000`) or use the
   quick-amount buttons, then click **Apply** and confirm.
6. Start the game and load the save.

## Backups and restoring

Before every change the tool copies the save (and its `.meta` file) to:

```
Documents\Ski-E-O Balance Editor Backups\<date_time>\
```

To undo a change use **Tools > Restore a backup...** (or **Tools > Open backups folder** to
copy files back by hand into `%LOCALAPPDATA%\Ski-E-O\SaveGames`). Restoring also backs up
your current file first, so nothing is lost by mistake.

## Where are the saves?

```
%LOCALAPPDATA%\Ski-E-O\SaveGames
```
(for example `C:\Users\<you>\AppData\Local\Ski-E-O\SaveGames`). Paste that into the
Windows Explorer address bar to open it. The window has **Tools > Change save folder...**
if yours is elsewhere.

## Safety checks built in

- Refuses to edit anything that is not a recognised save, or whose layout it does not
  understand, rather than guessing.
- Warns if the game seems to be running.
- Warns if the save version differs from the version this tool was tested with.
- Writes through a temporary file, verifies the result, and puts the original back if
  verification fails.
- The balance is a 32-bit number: allowed range is -2,147,483,648 to 2,147,483,647.
  Huge values can overflow inside the game, so something like 1-10 million is safer.

## Limitations

- Only the balance is edited. Loans keep their interest and payback schedule.
- Tested with save version 51.102 on Windows. A game update can change the save format;
  the tool is designed to stop with a message instead of damaging a save, but always keep
  your own backups.
- Editing a save may affect achievements or leaderboards if the game ever adds them.
  Use it for single-player fun only.

## Build the .exe yourself

```
pip install pyinstaller
pyinstaller --onedir --windowed --name ski_e_o_balance_editor_gui ski_e_o_balance_editor_gui.py
```
The result is in `dist\ski_e_o_balance_editor_gui\`. Or run `build_exe.bat`, which also
creates the zip. Building yourself gives a different file hash than the release.

## Tests

```
python -m unittest discover -s tests
```
The tests use a synthetic save, so no real save files are in this repository.

## Reporting problems

Open an issue and include the tool version, what you did, and the message shown.
**Do not upload your save file** unless asked: it contains your Steam ID.

## License

MIT, see [LICENSE](LICENSE).
