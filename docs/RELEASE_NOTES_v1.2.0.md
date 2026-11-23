Title: v1.2.0 - Save Editor (loans, reputation, staff)
Tag: v1.2.0
Asset to attach: ski_e_o_save_editor_gui_v1.2.0.zip
-----------------------------------------------------------------------

The tool is now the **Ski-E-O Save Editor** and edits more than the money balance.

**New**
- **Loans:** set the remaining amount and monthly interest of each loan (custom values, or quick "remaining -> 0" / "interest -> 0%"). A loan with 0 remaining shows a "pay off" button in the game; clicking it removes the loan for free.
- **Reputation:** set the level (1-14) and the XP progress inside the level. The XP needed for every level is listed in the README.
- **Staff:** refill stamina, set or scale daily wages, set XP, for everybody or one role.
- New window layout, quick-amount buttons, a warning when a level-up is about to happen.
- Old backups (from the "Balance Editor" versions) are still listed for restoring; new backups go to `Documents\Ski-E-O Save Editor Backups`.

**Download (Windows):** `ski_e_o_save_editor_gui_v1.2.0.zip` below. Extract the **whole** zip (right-click > Extract All) and run `ski_e_o_save_editor_gui.exe` from the extracted folder. Do not run it from inside the zip.
**Or run from source** (Python 3.10+, no extra packages): `python ski_e_o_save_editor_gui.py`, or double-click `run_gui.bat`.

**About antivirus warnings:** the .exe is an unsigned PyInstaller build. On VirusTotal, 3 of 70 engines flag it (Arctic Wolf, SecureAge, Skyhigh; generic labels) and the other 67 find nothing, including Microsoft Defender. The tool has no network code and the full source is in this repository. If you are unsure, run the Python source instead.
VirusTotal report: https://www.virustotal.com/gui/file/1ad4df5450b8f3109d4632391e4ed66acd8a92106dc91a3692d9ce887528b86d

SHA-256 of `ski_e_o_save_editor_gui.exe` inside the zip: `1AD4DF5450B8F3109D4632391E4ED66ACD8A92106DC91A3692D9CE887528B86D`
SHA-256 of the zip itself: `1F0A3A3FCF096A4DE7BCBB9E93AC395D82E4AFC702B3EC3E3EC0C36DCE1C6360`

Tested with save version 51.102. Back up your saves before editing. Use at your own risk.

-----------------------------------------------------------------------
GitHub "About" box (description, 350 characters max):
Unofficial single-player save editor for Ski-E-O! Ski Resort Tycoon. Edit money, loans, reputation level/XP and staff (stamina, wages, XP) in a simple window. Automatic backups and restore. Windows, no install needed.

Topics:
ski-e-o, save-editor, game-save, unreal-engine, python, windows, steam, tkinter

Repository name: ski-e-o-save-editor
