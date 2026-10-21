"""Make a zip whose Hebrew file names Windows reads correctly (names marked as UTF-8).

    python tools/make_zip.py OUT.zip BASE_DIR FOLDER [--exclude PATTERN ...] [--store PATTERN ...]

FOLDER (relative to BASE_DIR) goes into the zip with its own name at the top.
"""
import fnmatch
import os
import sys
import zipfile


def main():
    out, base, folder = sys.argv[1:4]
    rest = sys.argv[4:]
    excl, store, mode = [], [], None
    for a in rest:
        if a in ("--exclude", "--store"):
            mode = a
        elif mode == "--exclude":
            excl.append(a)
        elif mode == "--store":
            store.append(a)
    if os.path.exists(out):
        os.remove(out)
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, files in os.walk(os.path.join(base, folder)):
            dirs.sort()
            for f in sorted(files):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, base).replace(os.sep, "/")
                if any(fnmatch.fnmatch(rel, p) for p in excl):
                    continue
                kind = zipfile.ZIP_STORED if any(fnmatch.fnmatch(rel, p) for p in store) else zipfile.ZIP_DEFLATED
                z.write(full, rel, compress_type=kind)   # non-ASCII names get the UTF-8 flag
                n += 1
    print(out, n, "files", os.path.getsize(out) // 1024, "KB")


if __name__ == "__main__":
    main()
