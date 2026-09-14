@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --onefile --name Tidy --hidden-import watchdog --hidden-import watchdog.observers --hidden-import watchdog.events app.py
if exist dist\Tidy.exe copy /Y dist\Tidy.exe Tidy.exe >nul
echo.
echo Done. Run Tidy.exe or launch.vbs
pause
