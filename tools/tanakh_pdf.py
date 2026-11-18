"""The whole Tanakh in one PDF: a title page and a table of contents, a title page for the
Torah, Nevi'im and Ketuvim, and each book after its own title page. The pages are numbered
straight through, and each book is laid out knowing which side of the spread its pages fall on.

    python tools/tanakh_pdf.py PROJECTS_DIR OUT.pdf [--font FONTFILE ...] [--main FAMILY]

PROJECTS_DIR is what tools/build_tanakh.py wrote. Prints the layout check of every book.
"""
import json
import os
import sys
import time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "perush-python")
sys.path.insert(0, ROOT)

from PySide6.QtGui import QFontDatabase, QGuiApplication  # noqa: E402

app = QGuiApplication(sys.argv[:1])

from perush.checks import check, describe, summary  # noqa: E402
from perush.engine import Engine  # noqa: E402
from perush.model import DEDICATION, heb, normalize  # noqa: E402
from perush.render import export_pdf  # noqa: E402
from perush.textlayout import load_bundled_fonts  # noqa: E402
from perush.titlepage import title_page, toc_page  # noqa: E402

SECTION_LINES = {
    "תורה": ["חמשה חומשי תורה", "עם תרגום אונקלוס ופירוש רש\"י"],
    "נביאים": ["נביאים ראשונים ונביאים אחרונים", "עם פירוש רש\"י, מצודת דוד ומצודת ציון"],
    "כתובים": ["עם פירוש רש\"י, מצודת דוד ומצודת ציון"],
}


def main(src, out, fonts, family):
    load_bundled_fonts(os.path.join(ROOT, "fonts"))
    for f in fonts:
        QFontDatabase.addApplicationFont(f)
    order = json.load(open(os.path.join(src, "tanakh.json"), encoding="utf-8"))
    first = normalize(json.load(open(os.path.join(src, order[0]["file"]), encoding="utf-8")))
    if family:
        first["mainFont"] = family
    probe = Engine(dict(first, main="", comms=[]))
    pw, ph, m = probe.page_w, probe.page_h, probe.m
    font = first["mainFont"]

    pages = [None, None]                 # the title page and the table of contents, made at the end
    contents, report, total_err = [], [], 0
    section = None
    for book in order:
        if book["section"] != section:
            section = book["section"]
            pages.append(title_page(pw, ph, m, font, section, SECTION_LINES.get(section, []), []))
            contents.append((section, heb(len(pages)), 0))
        p = normalize(json.load(open(os.path.join(src, book["file"]), encoding="utf-8")))
        if family:
            p["mainFont"] = family
        start = len(pages) + 1           # the book's first page of text, after its title page
        p["firstPage"] = start + 1       # (pages are counted from 1)
        p["pageParity"] = start % 2
        t = time.time()
        eng = Engine(p)
        bp = eng.run()
        err, exc, warn = summary(check(eng, bp))
        total_err += len(err)
        report.append(f"{book['title']}: {len(bp)} עמודים, {len(err)} תקלות, {len(exc)} חריגים, {len(warn)} אזהרות"
                      f" ({time.time() - t:.0f} שניות)")
        report += [f"    {x.severity}: {describe(x)}" for x in err + exc]
        print("\n".join(report[-1 - len(err) - len(exc):]), flush=True)
        contents.append((book["title"], heb(start + 1), 1))
        pages += bp
    pages[0] = title_page(pw, ph, m, font, "תורה נביאים כתובים",
                          ["עם תרגום אונקלוס, פירוש רש\"י,", "מצודת דוד ומצודת ציון"],
                          [l for l in DEDICATION.split("\n") if l.strip()])
    pages[1] = toc_page(pw, ph, m, font, contents, probe.gutter)
    export_pdf(pages, out, "תורה נביאים כתובים")
    print(f"{len(pages)} עמודים, {total_err} תקלות -> {out}")
    return report


if __name__ == "__main__":
    args = sys.argv[1:]
    fonts = [args[i + 1] for i, a in enumerate(args) if a == "--font"]
    family = next((args[i + 1] for i, a in enumerate(args) if a == "--main"), None)
    rest = [a for i, a in enumerate(args) if a not in ("--font", "--main") and (i == 0 or args[i - 1] not in ("--font", "--main"))]
    main(rest[0], rest[1], fonts, family)
