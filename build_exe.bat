@echo off
rem Builds dist\ski_e_o_balance_editor.exe (needs Python; installs PyInstaller if missing)
python -m pip install --upgrade pyinstaller || goto :err
python -m PyInstaller --onefile --name ski_e_o_balance_editor ski_e_o_balance_editor.py || goto :err
echo.
echo Done: dist\ski_e_o_balance_editor.exe
pause
exit /b 0
:err
echo Build failed.
pause
exit /b 1
