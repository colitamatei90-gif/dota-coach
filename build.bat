@echo off
REM Construieste DotaCoach.exe (un singur fisier) cu PyInstaller.
python -m pip install --upgrade pyinstaller anthropic || goto :err
python -m PyInstaller --onefile --name DotaCoach --add-data "index.html;." --hidden-import anthropic server.py || goto :err
echo.
echo Gata: dist\DotaCoach.exe
pause
exit /b 0
:err
echo Build esuat.
pause
exit /b 1
