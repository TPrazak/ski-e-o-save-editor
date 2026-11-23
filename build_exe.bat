@echo off
rem Builds the window version as a folder (dist\ski_e_o_save_editor_gui) and a zip.
rem Needs Python; installs PyInstaller if missing.
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller || goto :err
python -m PyInstaller --noconfirm --onedir --windowed --name ski_e_o_save_editor_gui ski_e_o_save_editor_gui.py || goto :err
powershell -NoProfile -Command "Compress-Archive -Path 'dist\ski_e_o_save_editor_gui' -DestinationPath 'dist\ski_e_o_save_editor_gui.zip' -Force" || goto :err
echo.
echo Done: dist\ski_e_o_save_editor_gui\ski_e_o_save_editor_gui.exe and dist\ski_e_o_save_editor_gui.zip
pause
exit /b 0
:err
echo Build failed.
pause
exit /b 1
