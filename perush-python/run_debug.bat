@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo מפעיל את התוכנה עם חלון הודעות. אם יש שגיאה, היא תופיע כאן.
echo.
if not exist ".venv\Scripts\python.exe" (
  echo התוכנה עוד לא הותקנה. הריצו קודם את run.bat
  pause
  exit /b 1
)
".venv\Scripts\python.exe" main.py
echo.
echo התוכנה נסגרה. אם היתה שגיאה, צלמו את המסך או שלחו את הקובץ perush.log
pause
