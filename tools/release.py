"""Prepare an update of the program: check the layout of every ready book first, and only if
there is no fault set the new version and build perush-python.zip.

    python tools/release.py 2026.10.27

(Then commit and push; the build on GitHub checks again before it publishes the exe.)
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)


def main():
    if len(sys.argv) != 2 or not re.match(r"^\d{4}\.\d{1,2}\.\d{1,2}(\.\d+)?$", sys.argv[1]):
        print(__doc__)
        return 2
    version = sys.argv[1]
    if subprocess.call([sys.executable, os.path.join(HERE, "check_layout.py")]) != 0:
        print("יש תקלות בעימוד — העדכון לא הוכן.")
        return 1
    vfile = os.path.join(TOP, "perush-python", "perush", "version.py")
    src = open(vfile, encoding="utf-8").read()
    open(vfile, "w", encoding="utf-8").write(re.sub(r'VERSION = "[^"]*"', f'VERSION = "{version}"', src))
    open(os.path.join(TOP, "perush-version.txt"), "w", encoding="utf-8").write(version + "\n")
    return subprocess.call([sys.executable, os.path.join(HERE, "make_zip.py"), os.path.join(TOP, "perush-python.zip"), TOP,
                            "perush-python", "--exclude", "*/__pycache__/*", "*.log"])


if __name__ == "__main__":
    sys.exit(main())
