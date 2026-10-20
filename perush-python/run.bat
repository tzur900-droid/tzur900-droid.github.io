@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"

rem an installation that no longer works (Python was replaced, a file is missing): install again
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import PySide6" >nul 2>nul || (
    echo ההתקנה הקודמת לא עובדת, מתקין מחדש...
    rmdir /s /q ".venv"
  )
)
if not exist ".venv\Scripts\python.exe" (
  if not defined PY goto nopython
  echo מתקין בפעם הראשונה, זה לוקח כמה דקות. לא לסגור את החלון...
  %PY% -m venv .venv || goto nopython
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto fail
)

del perush.log >nul 2>nul
echo פותח את התוכנה...
start "" ".venv\Scripts\pythonw.exe" main.py
rem wait until the window is on the screen; if the program fails, show why
set /a n=0
:wait
timeout /t 1 /nobreak >nul
findstr /c:"WINDOW-SHOWN" perush.log >nul 2>nul && exit /b 0
findstr /c:"ERROR" perush.log >nul 2>nul && goto showlog
set /a n+=1
if %n% lss 60 goto wait
echo התוכנה עדיין לא נפתחה אחרי דקה.
:showlog
echo.
echo ===== מה שהתוכנה רשמה (perush.log) =====
type perush.log 2>nul || echo (התוכנה לא רשמה כלום - כנראה שהיא לא הצליחה להתחיל בכלל)
echo ==========================================
echo צלמו את המסך הזה ושלחו אותו.
pause
exit /b 1

:nopython
echo.
echo לא נמצא Python במחשב.
echo התקינו Python 3.10 ומעלה מהאתר python.org
echo ובחלון ההתקנה סמנו "Add python.exe to PATH". אחר כך הריצו את הקובץ הזה שוב.
pause
exit /b 1

:fail
echo.
echo ההתקנה נכשלה. בדקו שיש חיבור לאינטרנט ונסו שוב.
pause
exit /b 1
