"""Builds the one-file version of the font maker: the page with its scripts, styles and the
fonts of the library inside it, to open by double-clicking, without internet.

    python3 build-standalone.py OUTPUT.html
"""
import base64
import os
import re
import sys

here = os.path.dirname(os.path.abspath(__file__))


def read(name):
    with open(os.path.join(here, name), encoding="utf-8") as f:
        return f.read()


page = read("index.html")
page = page.replace('<link rel="stylesheet" href="style.css">', "<style>\n" + read("style.css") + "</style>")

# the fonts and their licenses, as base64 inside a script
fonts_dir = os.path.join(here, "fonts")
data = {}
for name in sorted(os.listdir(fonts_dir)):
    with open(os.path.join(fonts_dir, name), "rb") as f:
        data[name] = base64.b64encode(f.read()).decode("ascii")
library_data = "FontMaker.libraryData = {\n" + ",\n".join(f'"{k}": "{v}"' for k, v in data.items()) + "\n};\n"


def script(m):
    src = m.group(1)
    js = read(src).replace("</script", "<\\/script")
    if src == "library.js":
        js += "\n" + library_data
    return "<script>\n" + js + "\n</script>"


page = re.sub(r'<script src="([^"]+)"></script>', script, page)
with open(sys.argv[1], "w", encoding="utf-8") as f:
    f.write(page)
print(sys.argv[1], round(len(page.encode("utf-8")) / 1e6, 1), "MB")
