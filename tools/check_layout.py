"""Lay out every ready book and check it against the layout rules (perush-python/RULES.md).

    python tools/check_layout.py [-v] [project.json ...]      (-v: the warnings too)

Without arguments: all the books in perush-python/projects. Prints the faults and the
known exceptions of each book; the exit code is 1 if there is any fault, so that a release
(or the build on GitHub) stops before a fault reaches anyone.
"""
import glob
import os
import sys
import time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "perush-python")
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

app = QGuiApplication(sys.argv[:1])

from perush.checks import check, describe, summary  # noqa: E402
from perush.engine import Engine  # noqa: E402
from perush.model import load_project  # noqa: E402
from perush.textlayout import load_bundled_fonts  # noqa: E402


def main():
    load_bundled_fonts(os.path.join(ROOT, "fonts"))
    flags = [a for a in sys.argv[1:] if a.startswith("-")]
    files = [a for a in sys.argv[1:] if not a.startswith("-")] or sorted(glob.glob(os.path.join(ROOT, "projects", "*", "*.json")))
    total_errors = 0
    for f in files:
        name = os.path.relpath(f, os.path.join(ROOT, "projects"))
        t = time.time()
        eng = Engine(load_project(f))
        pages = eng.run()
        errors, known, warns = summary(check(eng, pages))
        total_errors += len(errors)
        mark = "✗" if errors else "✓"
        print(f"{mark} {name}: {len(pages)} עמודים, {len(errors)} תקלות, {len(known)} חריגים מותרים, {len(warns)} אזהרות ({time.time() - t:.0f} שניות)")
        for p in errors:
            print("    תקלה:", describe(p))
        for p in known:
            print("    חריג מותר:", describe(p))
        if "-v" in flags:
            for p in warns:
                print("    אזהרה:", describe(p))
        sys.stdout.flush()
    print("סה\"כ תקלות:", total_errors)
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
