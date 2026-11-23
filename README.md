# Ski-E-O Balance Editor

A small, open-source tool that changes the **money balance** in a save file of
**Ski-E-O! Ski Resort Tycoon** (single-player). It shows your saves, creates a backup,
and changes only 4 bytes of the file.

> Unofficial fan tool. Not affiliated with the game's developers. Use at your own risk.

## Download

- **Easiest:** download `ski_e_o_balance_editor.exe` from the
  [Releases](../../releases) page and double-click it.
- **From source:** you need [Python 3.8+](https://www.python.org/downloads/). Download
  `ski_e_o_balance_editor.py` and run `python ski_e_o_balance_editor.py`.
  No extra packages are required.

### About antivirus warnings (please read)

The `.exe` is an unsigned [PyInstaller](https://pyinstaller.org) build, and some antivirus
engines flag such files by mistake. The v1.0.0 `.exe` was scanned on VirusTotal:
**3 of 69 engines flagged it** (Sangfor, Zillya and SecureAge, using generic labels such
as "Trojan.Stealer"); the other 66 found nothing.
[Scan report](https://www.virustotal.com/gui/file/47d124efe8dd3905db3138bd287e694b3fbc9a993e7bf25ec5849a51565e5c0e)

I believe these are false positives, but you do not have to take my word for it:

- The tool has **no network code**. It only reads/writes save files in
  `%LOCALAPPDATA%\Ski-E-O\SaveGames`, writes backups to your Documents folder, and runs
  `tasklist` once to check whether the game is running. Read the source to check.
- If you would rather not run an `.exe`, **run the Python source instead**
  (`python ski_e_o_balance_editor.py`), or build the `.exe` yourself (see below).
- SHA-256 of the v1.0.0 `.exe`, to confirm your download is the scanned file:
  `47D124EFE8DD3905DB3138BD287E694B3FBC9A993E7BF25EC5849A51565E5C0E`

Windows SmartScreen may also show a warning because the file is new and unsigned.

## How to use

1. **Close the game completely.**
2. *(Recommended)* In Steam, right-click the game > Properties > General, and turn off
   **Steam Cloud** for it. Otherwise Steam can bring back your old save.
3. Start the tool.
4. Choose **[1] Change the money balance of a save**.
5. Pick your save from the list. Each entry shows the resort name, in-game date, when
   it was saved, and the current balance. The game keeps several autosave slots;
   the newest one (top of the list) is normally the one the game loads.
6. Type the new balance (a whole number, e.g. `2000000`) and confirm with `y`.
7. Start the game and load the save.

## Backups and restoring

Before every change the tool copies the save (and its `.meta` file) to:

```
Documents\Ski-E-O Balance Editor Backups\<date_time>\
```

To undo a change, start the tool and choose **[2] Restore a backup**. You can also copy
the files from the backup folder back into `%LOCALAPPDATA%\Ski-E-O\SaveGames` by hand.
Restoring also backs up your current file first, so nothing is lost by mistake.

## Where are the saves?

```
%LOCALAPPDATA%\Ski-E-O\SaveGames
```
(for example `C:\Users\<you>\AppData\Local\Ski-E-O\SaveGames`). Paste that into the
Windows Explorer address bar to open it.

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
pyinstaller --onefile --name ski_e_o_balance_editor ski_e_o_balance_editor.py
```
The result is `dist\ski_e_o_balance_editor.exe`. Or run `build_exe.bat`.

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
