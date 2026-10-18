@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not exist ".venv\Scripts\python.exe" (
  if not defined PY goto nopython
  echo מתקין בפעם הראשונה, זה לוקח דקה או שתיים...
  %PY% -m venv .venv || goto nopython
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto fail
)
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

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
