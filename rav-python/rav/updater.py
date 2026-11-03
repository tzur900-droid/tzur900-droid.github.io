"""Updating the program from GitHub: the version published with Rav-windows.zip is compared with
this one; the new zip is downloaded and unpacked aside, and a small PowerShell script waits until
the program closed, copies the new files over its folder and opens it again. The books (in the
Documents folder) and the connection key (in AppData) are not in the program's folder: they stay."""
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
    """Open the new Rav.exe (where it was unpacked) to put itself in place: it waits until this
    program has closed, copies its folder over the program's folder and opens the program
    there. No script is involved, nothing an antivirus would stop. The caller closes the
    program right after."""
    app = program_dir()
    exe = os.path.join(new_dir, "Rav.exe")
    log(f"מתקין את העדכון ב־{app} ומפעיל מחדש")
    subprocess.Popen([exe, "--install-update", app, str(os.getpid())], cwd=new_dir,
                     creationflags=0x00000008 | 0x00000200)   # detached, a process group of its own


def _wait_for(pid, seconds=120):
    """Wait until the process pid has ended."""
    import time
    if sys.platform == "win32":
        import ctypes
        k = ctypes.WinDLL("kernel32")
        k.OpenProcess.restype = ctypes.c_void_p
        h = k.OpenProcess(0x00100000, False, int(pid))      # SYNCHRONIZE
        if h:
            k.WaitForSingleObject(ctypes.c_void_p(h), int(seconds * 1000))
            k.CloseHandle(ctypes.c_void_p(h))
        time.sleep(1)
        return
    end = time.time() + seconds
    while time.time() < end:
        try:
            os.kill(int(pid), 0)
        except OSError:
            break
        time.sleep(0.5)
    time.sleep(1)


def copy_over(src, dst, tries=20):
    """Copy every file of src over dst (a file still in use is tried again for a while).
    Returns the files that could not be written."""
    import time
    failed = []
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(target, exist_ok=True)
        for f in files:
            if f.lower() == "rav.log":
                continue
            s, d = os.path.join(root, f), os.path.join(target, f)
            for i in range(tries):
                try:
                    shutil.copy2(s, d)
                    break
                except OSError:
                    time.sleep(1)
            else:
                failed.append(d)
    return failed


def install_here(app_dir, old_pid):
    """Run by the new Rav.exe from where it was unpacked: put it in place of the old one."""
    src = program_dir()
    log(f"עדכון: מחכה שהגרסה הקודמת תיסגר ({old_pid})")
    _wait_for(old_pid)
    log(f"עדכון: מעתיק את {src} אל {app_dir}")
    failed = copy_over(src, app_dir)
    if failed:
        log("עדכון: לא נכתבו " + ", ".join(failed[:10]))
    exe = os.path.join(app_dir, "Rav.exe" if frozen() else "main.py")
    log(f"עדכון: פותח את {exe}")
    if frozen():
        subprocess.Popen([exe], cwd=app_dir, creationflags=0x00000008 | 0x00000200)
    return not failed


def clean_old():
    """Folders left by earlier updates (in the temp folder) are removed."""
    tmp = tempfile.gettempdir()
    mine = program_dir()
    try:
        for name in os.listdir(tmp):
            p = os.path.join(tmp, name)
            if name.startswith("rav-update-") and not mine.startswith(p):
                shutil.rmtree(p, ignore_errors=True)
    except OSError:
        pass
