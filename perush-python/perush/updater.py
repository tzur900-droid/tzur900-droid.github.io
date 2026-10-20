"""Updating the program from the site: download the latest perush-python.zip and write its
files over the program's folder (the installed Python packages in .venv stay)."""
import io
import os
import subprocess
import sys
import urllib.request
import zipfile

from .version import VERSION

SOURCES = [
    "https://tzur900-droid.github.io/",
    "https://raw.githubusercontent.com/tzur900-droid/tzur900-droid.github.io/main/",
]
ZIP_NAME = "perush-python.zip"
TOP = "perush-python/"


def program_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fetch(name, timeout=30):
    """The file name from the first source that answers."""
    last = None
    for base in SOURCES:
        try:
            with urllib.request.urlopen(base + name, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # try the next source
            last = e
    raise RuntimeError(f"לא הצלחתי להוריד את {name}: {last}")


def newer(remote, local=VERSION):
    """Whether the version remote ('2026.10.20') is later than local."""
    num = lambda v: tuple(int(x) for x in v.strip().split(".") if x.isdigit())
    return num(remote) > num(local)


def remote_version():
    data = fetch("perush-version.txt", 15)
    return data.decode("utf-8").strip()


def install(data, progress=None):
    """Write the files of the zip (bytes) over the program's folder. Returns (number of
    files written, files that could not be written, whether requirements.txt changed)."""
    root = program_dir()
    req_path = os.path.join(root, "requirements.txt")
    old_req = open(req_path, encoding="utf-8").read() if os.path.exists(req_path) else ""
    written, failed = 0, []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = [n for n in z.namelist() if n.startswith(TOP) and not n.endswith("/")]
        for k, name in enumerate(names):
            rel = name[len(TOP):]
            if not rel or rel.startswith(".venv/") or "/__pycache__/" in "/" + rel:
                continue
            dst = os.path.join(root, *rel.split("/"))
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "wb") as f:
                    f.write(z.read(name))
                written += 1
            except OSError:
                failed.append(rel)   # e.g. a font file Windows keeps open
            if progress and k % 20 == 0:
                progress(k, len(names))
    new_req = open(req_path, encoding="utf-8").read() if os.path.exists(req_path) else ""
    return written, failed, new_req != old_req


def update_packages():
    """Install what requirements.txt asks for (when it changed)."""
    py = sys.executable
    if py.lower().endswith("pythonw.exe"):
        py = py[:-len("pythonw.exe")] + "python.exe"
    subprocess.run([py, "-m", "pip", "install", "-r", os.path.join(program_dir(), "requirements.txt")],
                   check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def restart():
    """Start the program again (the window that asked closes itself)."""
    main = os.path.join(program_dir(), "main.py")
    subprocess.Popen([sys.executable, main], cwd=program_dir(),
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))


def frozen():
    return getattr(sys, "frozen", False)


__all__ = ["VERSION", "newer", "remote_version", "fetch", "install", "update_packages", "restart", "frozen", "ZIP_NAME"]
