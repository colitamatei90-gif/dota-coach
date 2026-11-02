@echo off
REM Construieste DotaCoach.exe (aplicatie desktop, un singur fisier) cu PyInstaller.
python -m pip install --upgrade pyinstaller anthropic pywebview || goto :err
python -m PyInstaller --onefile --windowed --name DotaCoach --icon icon.ico --add-data "index.html;." --hidden-import anthropic --collect-all webview app.py || goto :err
echo.
echo Gata: dist\DotaCoach.exe
pause
exit /b 0
:err
echo Build esuat.
pause
exit /b 1
