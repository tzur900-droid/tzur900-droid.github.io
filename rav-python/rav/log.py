"""rav.log beside the program (or in the temp folder): what the program did when, so that a
problem on another computer can be found. A listener (the window) can also see every line."""
import os
import sys
import threading
import time

_FILE = None
_T0 = time.time()
_LOCK = threading.Lock()
listeners = []


def program_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def log(msg):
    global _FILE
    with _LOCK:
        if _FILE is None:
            for folder in (program_dir(), os.environ.get("TEMP", ""), os.path.expanduser("~")):
                try:
                    _FILE = open(os.path.join(folder, "rav.log"), "w", encoding="utf-8")
                    # a crash inside Qt or another library: where it happened goes into rav.log too
                    import faulthandler
                    faulthandler.enable(_FILE, all_threads=True)
                    break
                except OSError:
                    continue
        line = f"{time.time() - _T0:7.1f}s  {msg}"
        if _FILE:
            _FILE.write(line + "\n")
            _FILE.flush()
    for f in list(listeners):
        try:
            f(str(msg))
        except Exception:
            pass
