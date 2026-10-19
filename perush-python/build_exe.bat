@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo הריצו קודם את run.bat פעם אחת כדי להתקין.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install pyinstaller || goto fail
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --windowed --name Perush --add-data "fonts;fonts" --add-data "projects;projects" main.py || goto fail
echo.
echo מוכן: התוכנה נמצאת בתיקייה dist\Perush  (הקובץ Perush.exe).
echo אפשר להעתיק את כל התיקייה dist\Perush לכל מחשב, גם בלי Python.
pause
exit /b 0
:fail
echo בניית הקובץ נכשלה.
pause
exit /b 1
