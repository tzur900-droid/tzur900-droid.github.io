"""The whole Shas of the Rosh and the Rif: every masechet laid out (several at a time),
checked (shas_check), and put together into files of 300 to 500 pages.

  * In a file (no title page of its own): each masechet: the Rosh with its own title page
    and the Rif with its own, each from a left-hand page (in a Hebrew book the first page is on
    the left). Blank pages where needed for that.
  * The pages keep the masechet's own numbers in letters at the head; at the foot of
    each page, small, its number in the file.
  * The whole Shas in one file when it is 500 pages or less; otherwise files that keep
    to the sedarim where they can, each of 300 to 500 pages.
  * A report (report.json) of the check and of the layout of every masechet.
"""
import json
import os
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp

from . import shas
from .engine import Page
from .model import heb
from .textlayout import PT_PER_MM, Style

B5 = (165, 235)        # the page in mm (the printer's B5)
SIZES = {"margin": 12, "inner": 22, "outer": 15, "rosh_size": 9.5, "rif_size": 11.5, "rif_lead": 1.12, "comm_size": 8.75, "head_size": 8}
SEDARIM = [("זרעים", ["ברכות"]),
           ("מועד", ["שבת", "עירובין", "פסחים", "יומא", "סוכה", "ביצה", "ראש השנה", "תענית", "מגילה", "מועד קטן"]),
           ("נשים", ["יבמות", "כתובות", "נדרים", "גיטין", "קידושין"]),
           ("נזיקין", ["בבא קמא", "בבא מציעא", "בבא בתרא", "סנהדרין", "מכות", "שבועות", "עבודה זרה"]),
           ("קדשים", ["מנחות", "חולין", "בכורות"]),
           ("טהרות", ["נידה"])]
SEDER_OF = {m: s for s, ms in SEDARIM for m in ms}
LO, HI = 300, 500
COVER = "שמנת"           # the colours of the covers (design.PALETTES)
LEAF = 0.09              # the paper: mm a leaf (two pages), for the spine


def _init(fonts):
    global _app
    from PySide6.QtGui import QGuiApplication
    _app = QGuiApplication.instance() or QGuiApplication([])
    from .textlayout import load_bundled_fonts
    load_bundled_fonts(fonts)


def _one(args):
    root, m, first, n, page, sizes = args
    from . import shas_check
    pages, report, info = shas.build_masechet(root, m, first, n, page, sizes, fix=shas_check.fix)
    return m, pages, report, info


def build_all(root, fonts, page=B5, sizes=SIZES, jobs=4, only=None, log=print):
    """Lay out every masechet. -> {masechet: (pages, report, info)} in the Shas's order."""
    days, first = shas.day_plan(root)
    names = [m for m in shas.MASECHTOT if (only is None or m in only)]
    todo = [(root, m, first[m], days[m], page, sizes) for m in names]
    # the longest first, so that the workers finish together
    todo.sort(key=lambda t: -t[3])
    out = {}
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=jobs, mp_context=ctx, initializer=_init, initargs=(fonts,)) as ex:
        for m, pages, report, info in ex.map(_one, todo):
            out[m] = (pages, report, info)
            log(f"{m}: {len(pages)} עמודים")
    return {m: out[m] for m in names if m in out}


def block_size(info):
    """The pages a masechet takes in a file: for the Rosh and for the Rif, a title page
    and the blank page behind it, the pages, and a blank page after them when they end
    on a left-hand page."""
    return sum(2 + n + n % 2 for n in (info["rosh_pages"], info["rif_pages"]) if n)


def group(books):
    """Files of LO to HI pages, keeping to the sedarim where they can: the whole Shas in
    one when it fits. -> [[masechet]]"""
    names = list(books)
    size = [block_size(books[m][2]) for m in names]
    if sum(size) <= HI:
        return [names]
    n = len(names)
    INF = float("inf")
    best = [INF] * (n + 1)
    back = [0] * (n + 1)
    best[0] = 0.0
    for e in range(1, n + 1):
        for s in range(e):
            pages = sum(size[s:e])
            if pages > HI and e - s > 1:
                continue
            cost = 0.0 if pages >= LO or e - s == n else (LO - pages) * 2.0
            if pages > HI:
                cost += pages - HI        # a masechet longer than a file: a file of its own
            # a file that crosses a seder costs a little; one that holds whole sedarim none
            cost += 15 * len({SEDER_OF.get(m) for m in names[s:e]}) - 15
            if s and SEDER_OF.get(names[s - 1]) == SEDER_OF.get(names[s]):
                cost += 10                # a seder broken between two files
            if best[s] + cost < best[e]:
                best[e], back[e] = best[s] + cost, s
    out, e = [], n
    while e:
        out.append(names[back[e]:e])
        e = back[e]
    return out[::-1]


def file_name(ms):
    sedarim = [s for s, all_ms in SEDARIM if all(m in ms for m in all_ms)]
    whole = [m for s in sedarim for m in dict(SEDARIM)[s]]
    if len(ms) == len(shas.MASECHTOT) or len(ms) > 20:
        return "רא\"ש ורי\"ף - כל הש\"ס"
    if whole and len(whole) == len(ms):
        return "רא\"ש ורי\"ף - סדר " + " וסדר ".join(sedarim)
    return f"רא\"ש ורי\"ף - {ms[0]}" + (f" עד {ms[-1]}" if len(ms) > 1 else "")


def blank(pw, ph):
    return Page(pw, ph)


DEDICATION = ("הספר עומד ועוצב בסיוע ומימון", "אבנר ובנו צור אליאסיאן",
              "זכות התורה תעמוד להם ולבני משפחותיהם עד עולם")


def gate(pw, ph, items, foot_title="", foot_lines=()):
    """A title page drawn after the gate of the Oz Vehadar Shas (design.gate_page), with
    the dedication at its foot."""
    from . import design
    p = Page(pw, ph)
    p.paint = [design.gate_page(pw, ph, items, foot_title, list(foot_lines), dedication=DEDICATION)]
    return p


def with_comm(comm):
    comm = comm.replace('"', "״")
    return "עם פירוש הר״ן" if comm == "ר״ן" else f"עם פירוש {comm}"


def masechet_title(pw, ph, m, info, part):
    """The title page of the Rosh of a masechet (part "rosh") or of its Rif ("rif")."""
    days = f"{heb(info['first_day'])}–{heb(info['last_day'])}"
    if part == "rosh":
        items = [("shaded", "פסקי הרא״ש", 60), ("text", "מסכת " + m, 28)]
    else:
        items = [("shaded", "הלכות רב אלפס", 60), ("text", "מסכת " + m, 28)]
        if info["comm_name"]:
            items += [("div",), ("text", with_comm(info["comm_name"]), 17)]
    return gate(pw, ph, items, "ימי הלימוד", [(days, 16)])


def name_items(ms, size=17, rosh=1.0):
    """the name of the work (the Rif, an ornament, the Rosh: rosh of the Rif's size) and
    the masechtot, a few to a line."""
    items = [("shaded", "הלכות רב אלפס", 52), ("div",), ("shaded", "פסקי הרא״ש", 52, rosh), ("div",)]
    rows = [ms[k:k + 3] for k in range(0, len(ms), 3)]
    if len(ms) == 1:
        rows = [["מסכת " + ms[0]]]
    items += [("text", " · ".join(r), size) for r in rows]
    return items


def assemble(ms, books, page=B5, margin=SIZES["margin"]):
    """The pages of a file, with the numbers at their feet."""
    pw, ph = page[0] * PT_PER_MM, page[1] * PT_PER_MM
    out = []
    for m in ms:
        pages, _, info = books[m]
        # a title page for the Rosh and one for the Rif, each on a left-hand page with a
        # blank page behind it (the blank page the masechet's pages have between them is
        # left out: the Rif's title takes its place)
        rosh, rif = pages[:info["rosh_pages"]], pages[len(pages) - info["rif_pages"]:] if info["rif_pages"] else []
        for part, ps in (("rosh", rosh), ("rif", rif)):
            if not ps:
                continue
            out += [masechet_title(pw, ph, m, info, part), blank(pw, ph)]
            out += ps
            if len(out) % 2:
                out.append(blank(pw, ph))
    out += contents(pw, ph, ms, books)
    if len(out) % 2:
        out.append(blank(pw, ph))
    st = Style("Frank Ruhl Libre", 7)
    for n, p in enumerate(out):
        if p.frames or getattr(p, "numbered", False):
            if not hasattr(p, "marks"):
                p.marks = []
            p.marks.append((pw / 2, ph - margin * PT_PER_MM / 2, str(n + 1), st))
    return out


def cover_page(ms, n_pages, volume, colour=COVER, page=B5):
    """The whole cover of a file (front, spine and back) as one page."""
    from . import design
    W, H, paint = design.gate_cover(page, n_pages, name_items(ms, 18, rosh=0.9), ["הלכות", "רב אלפס", "div", ("פסקי", 0.9), ("הרא״ש", 0.9)],
                                    ms, "כרך " + heb(volume), design.PALETTES[colour], leaf=LEAF)
    p = Page(W, H)
    p.paint = [paint]
    return p


def contents(pw, ph, ms, books, rows_per_page=44):
    """At the end of a volume: the days of learning in it, each with its masechet and the
    pages (as numbered at their heads) where it begins in the Rosh and in the Rif."""
    rows = []
    for m in ms:
        for d, where in books[m][2].get("day_pages", []):
            rows.append((heb(d), m, where.get("rosh", ""), where.get("rif", "")))
    pages = []
    for k in range(0, len(rows), rows_per_page):
        pages.append(contents_page(pw, ph, rows[k:k + rows_per_page], first=k == 0))
    return pages


def contents_page(pw, ph, rows, first):
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor
    from . import design

    def paint(p):
        m = 20 * PT_PER_MM
        mid = pw / 2
        y = m
        if first:
            design.text_c(p, mid, y + 14, "תוכן ימי הלימוד", Style(design.TITLE_FONT, 20, True))
            design.divider(p, mid, y + 28, 50, "#555555")
            y += 44
        else:
            y += 8
        # the columns, from the right: the day, the masechet, the Rosh, the Rif
        W = pw - 2 * m
        xs = [pw - m - W * f for f in (0.06, 0.32, 0.64, 0.88)]
        hst = Style("Frank Ruhl Libre", 10, True)
        rst = Style("Frank Ruhl Libre", 10)
        lh = 13.2
        p.fillRect(QRectF(m, y, W, lh + 2), QColor("#d6d6d6"))
        for x, t in zip(xs, ("יום", "מסכת", "רא״ש עמ'", "רי״ף עמ'")):
            design.text_c(p, x, y + lh - 2.5, t, hst, "#000000")
        y += lh + 4
        for k, row in enumerate(rows):
            if k % 2:
                p.fillRect(QRectF(m, y, W, lh), QColor("#efefef"))
            for x, t in zip(xs, row):
                design.text_c(p, x, y + lh - 3, t, rst, "#000000")
            y += lh
    pg = Page(pw, ph)
    pg.paint = [paint]
    pg.numbered = True
    return pg


def report(books, files):
    from .shas_check import KINDS
    rep = {"files": [], "masechtot": []}
    for name, ms, n in files:
        rep["files"].append({"name": name, "masechtot": ms, "pages": n})
    for m, (pages, lines, info) in books.items():
        issues = info["issues"] + [dict(x, fixed=False, where=f"עמ' {heb(x['page'])}", text="") for x in info["layout"]]
        counts = {}
        for x in issues:
            k = (x["kind"], x["fixed"])
            counts[k] = counts.get(k, 0) + 1
        rep["masechtot"].append({
            "name": m, "pages": len(pages), "rosh_pages": info["rosh_pages"], "rif_pages": info["rif_pages"],
            "days": [info["first_day"], info["last_day"]], "report": lines,
            "counts": [{"kind": k, "label": KINDS.get(k, k), "fixed": f, "n": n} for (k, f), n in sorted(counts.items())],
            "issues": issues})
    return rep


def build_shas(root, out_dir, fonts, jobs=4, only=None, log=print):
    from .render import export_pdf
    books = build_all(root, fonts, jobs=jobs, only=only, log=log)
    groups = group(books)
    os.makedirs(out_dir, exist_ok=True)
    files = []
    for ms in groups:
        name = file_name(ms)
        pages = assemble(ms, books)
        export_pdf(pages, os.path.join(out_dir, name + ".pdf"), name)
        export_pdf([cover_page(ms, len(pages), len(files) + 1)], os.path.join(out_dir, "כריכה - " + name + ".pdf"),
                   "כריכה - " + name)
        files.append((name, ms, len(pages)))
        log(f"{name}: {len(pages)} עמודים")
    rep = report(books, files)
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    from .shas_report import write
    write(rep, os.path.join(out_dir, "report.html"))
    return files, rep
