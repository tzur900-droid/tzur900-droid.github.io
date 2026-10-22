"""The whole Shas of the Rosh and the Rif: every masechet laid out (several at a time),
checked (shas_check), and put together into files of 300 to 500 pages.

  * In a file: a title page, then each masechet: the Rosh with its own title page and the
    Rif with its own, each from a left-hand page (in a Hebrew book the first page is on
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

B5 = (176, 250)
SIZES = {"margin": 12, "rosh_size": 9.5, "rif_size": 11.5, "rif_lead": 1.12, "comm_size": 8.75, "head_size": 8}
SEDARIM = [("זרעים", ["ברכות"]),
           ("מועד", ["שבת", "עירובין", "פסחים", "יומא", "סוכה", "ביצה", "ראש השנה", "תענית", "מגילה", "מועד קטן"]),
           ("נשים", ["יבמות", "כתובות", "נדרים", "גיטין", "קידושין"]),
           ("נזיקין", ["בבא קמא", "בבא מציעא", "בבא בתרא", "סנהדרין", "מכות", "שבועות", "עבודה זרה"]),
           ("קדשים", ["מנחות", "חולין", "בכורות"]),
           ("טהרות", ["נידה"])]
SEDER_OF = {m: s for s, ms in SEDARIM for m in ms}
LO, HI = 300, 500
COVER = "כחול"           # the colour of the covers (design.COLOURS)


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
    if 2 + sum(size) <= HI:
        return [names]
    n = len(names)
    INF = float("inf")
    best = [INF] * (n + 1)
    back = [0] * (n + 1)
    best[0] = 0.0
    for e in range(1, n + 1):
        for s in range(e):
            pages = 2 + sum(size[s:e])
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


def title_page(pw, ph, lines):
    """A title page drawn as a gate, as in the Vilna Shas (design.title): lines of
    (text, size, bold), the first in the arch."""
    from . import design
    p = Page(pw, ph)
    p.paint = [design.title(pw, ph, lines)]
    return p


def masechet_title(pw, ph, m, info, part):
    """The title page of the Rosh of a masechet (part "rosh") or of its Rif ("rif")."""
    comm = info["comm_name"]
    if part == "rosh":
        lines = [("פסקי הרא\"ש", 36, True), ("", 6, False), ("מסכת " + m, 24, False)]
    else:
        lines = [("הלכות רב אלפס", 36, True), ("", 6, False), ("מסכת " + m, 24, False)]
        if comm:
            lines.append((f"עם {comm}", 16, False))
    lines += [("", 10, False), (f"ימי הלימוד {heb(info['first_day'])}–{heb(info['last_day'])}", 12, False)]
    return title_page(pw, ph, lines)


def file_title(pw, ph, ms, books):
    lines = [("פסקי הרא\"ש", 36, True), ("והלכות רב אלפס", 22, True), ("", 14, False)]
    for m in ms:
        info = books[m][2]
        lines.append((f"מסכת {m}  ·  ימים {heb(info['first_day'])}–{heb(info['last_day'])}", 12, False))
    return title_page(pw, ph, lines)


def assemble(ms, books, page=B5, margin=SIZES["margin"]):
    """The pages of a file, with the numbers at their feet."""
    pw, ph = page[0] * PT_PER_MM, page[1] * PT_PER_MM
    out = [file_title(pw, ph, ms, books), blank(pw, ph)]
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
    st = Style("Frank Ruhl Libre", 7)
    for n, p in enumerate(out):
        if p.frames:
            if not hasattr(p, "marks"):
                p.marks = []
            p.marks.append((pw / 2, ph - margin * PT_PER_MM / 2, str(n + 1), st))
    return out


def cover_page(ms, n_pages, volume, colour=COVER, page=B5):
    """The whole cover of a file (back, spine and front) as one page."""
    from . import design
    W, H, paint = design.cover(page, n_pages, [("פסקי הרא\"ש", 44), ("והלכות רב אלפס", 28)], ms,
                               "כרך " + heb(volume), design.COLOURS[colour])
    p = Page(W, H)
    p.paint = [paint]
    return p


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
