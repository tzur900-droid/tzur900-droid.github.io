"""Updating the program from GitHub: the version published with Rav-windows.zip is compared with
this one; the new zip is downloaded and unpacked aside, and a small PowerShell script waits until
the program closed, copies the new files over its folder and opens it again. The books (in the
Documents folder) and the connection key (in AppData) are not in the program's folder: they stay."""
import base64
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

from .log import log
from .version import VERSION

BASE = "https://github.com/tzur900-droid/tzur900-droid.github.io/releases/download/rav-exe/"
ZIP_URL = BASE + "Rav-windows.zip"
VERSION_URL = BASE + "rav-version.txt"


def frozen():
    return bool(getattr(sys, "frozen", False))


def program_dir():
    return os.path.dirname(sys.executable) if frozen() else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _num(v):
    return tuple(int(x) for x in v.strip().split(".") if x.isdigit())


def latest():
    """The version on the site ('2026.11.3.2'), or None when it cannot be checked."""
    import requests
    try:
        r = requests.get(VERSION_URL, timeout=20)
        if r.status_code == 200 and _num(r.text):
            return r.text.strip()
    except Exception as e:
        log(f"בדיקת עדכון נכשלה: {type(e).__name__}")
    return None


def newer(remote, local=VERSION):
    return bool(remote) and _num(remote) > _num(local)


def download(progress=log):
    """The new version, downloaded and unpacked aside. Returns the folder with Rav.exe in it."""
    import requests
    work = tempfile.mkdtemp(prefix="rav-update-")
    zpath = os.path.join(work, "Rav-windows.zip")
    with requests.get(ZIP_URL, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        got, shown = 0, -10
        with open(zpath, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                got += len(chunk)
                if total and got * 100 // total >= shown + 10:
                    shown = got * 100 // total
                    progress(f"מוריד את העדכון: {shown}% ({got >> 20} מתוך {total >> 20} MB)")
    progress("פותח את העדכון…")
    out = os.path.join(work, "new")
    with zipfile.ZipFile(zpath) as z:
        z.extractall(out)
    os.remove(zpath)
    for root, _dirs, files in os.walk(out):
        if "Rav.exe" in files:
            return root
    shutil.rmtree(work, ignore_errors=True)
    raise RuntimeError("בקובץ העדכון לא נמצא Rav.exe")


def install_and_restart(new_dir):
    """Start the script that puts the new files in place once this program has closed, and
    opens it again. The caller closes the program right after."""
    app = program_dir()
    work = new_dir
    while work and not os.path.basename(work).startswith("rav-update-"):
        parent = os.path.dirname(work)
        work = "" if parent == work else parent
    q = lambda p: "'" + p.replace("'", "''") + "'"
    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
Wait-Process -Id {os.getpid()} -Timeout 120
Start-Sleep -Seconds 1
$ok = $false
for ($i = 0; $i -lt 30 -and -not $ok; $i++) {{
  robocopy {q(new_dir)} {q(app)} /E /R:3 /W:2 /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -lt 8) {{ $ok = $true }} else {{ Start-Sleep -Seconds 2 }}
}}
Start-Process -FilePath (Join-Path {q(app)} 'Rav.exe')
{"Remove-Item -LiteralPath " + q(work) + " -Recurse -Force" if work else ""}
"""
    enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    log(f"מתקין את העדכון ב־{app} ומפעיל מחדש")
    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
                      "-EncodedCommand", enc], creationflags=0x08000000 | 0x00000008)  # no window, detached
