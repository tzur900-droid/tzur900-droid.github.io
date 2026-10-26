"""Checking a laid-out book against the layout rules (RULES.md).

check(engine, pages) -> a list of Problem. A problem is a fault ("error") unless the engine
marked it as a known exception it was forced into ("exception"); wide spaces are only a
"warning" until the lines are broken a paragraph at a time (see RULES.md). The program shows the
list after every layout, and tools/check_layout.py runs it over the ready books before a
release, so that a fault is found before anyone sees it in print.
"""
import re
from dataclasses import dataclass

from .engine import AUTO_MAX, EPS, space_ratio
from .model import heb

# a justified line whose spaces are wider than this many normal spaces
WIDE_SPACE = 5.0
# a hole: room left at the bottom of a page (pt) where the page should be full
HOLE = 2.0


@dataclass
class Problem:
    kind: str        # the rule (see RULES.md)
    page: int        # the page's index in the book as shown (0 = the first page)
    label: str       # the page's number as printed
    text: str        # what is wrong, in Hebrew
    severity: str = "error"


NAMES = {
    "outside": "טקסט מחוץ לשטח העמוד",
    "parasha": "פרשה שלא מתחילה בראש עמוד",
    "width": "טור צמוד רחב מהמותר",
    "side_start": "תרגום שלא מתחיל בעמוד של הפסוק",
    "comm_start": "פירוש שלא מתחיל בעמוד של הפסוק",
    "thin": "שורת פסוק אחת לבד מעל הפירושים",
    "hole": "מקום ריק בתחתית העמוד",
    "spaces": "רווחים גדולים בין המילים",
    "text": "סימן משובש בטקסט",
    "engine": "הודעה מהעימוד",
}


def check(eng, pages):
    out = []
    off = len(pages) - len(eng.pages)       # the title page and the table of contents come first

    first = int(eng.P.get("firstPage") or 1)

    def add(kind, n, text, severity="error"):
        label = heb(first + n - off) if n >= off else ("שער" if n >= 0 else "")
        out.append(Problem(kind, n, label, text, severity))

    for w in eng.warnings:
        add("engine", -1, w)
    for k, c in enumerate(eng.comms):
        if "???" in c.get("text", ""):
            out.append(Problem("text", -1, "", f"'???' ב{c['name']}"))
    if "???" in eng.P.get("main", ""):
        out.append(Problem("text", -1, "", "'???' בטקסט העיקרי"))

    starts = [n for n in range(off, len(pages)) if opens_section(pages[n])]
    for k, (r, chapter, parasha) in enumerate(eng.pages):
        n = k + off
        pg = pages[n]
        check_bounds(eng, pg, n, add)
        check_spaces(pg, n, add)
        if not r.get("ptrs"):
            continue                          # a page of a haftara only
        for c in eng.sides:
            w = (r.get("col_w") or {}).get(c, eng.col_w[c])
            if eng.comms[c].get("autoW") and w > AUTO_MAX + EPS:
                add("width", n, f"{eng.comms[c]['name']}: {w:.1f}% (המותר {AUTO_MAX:.0f}%)")
        if eng.page_unstarted(r):
            add("side_start", n, f"{eng.page_unstarted(r)} פסוקים בלי תחילת תרגום")
        late = late_commentaries(eng, r)
        if late:
            sev = "exception" if r.get("late_ok") else "error"
            add("comm_start", n, ", ".join(f"{name} על {where(eng, v)}" for name, v in late), sev)
        text = [l for l in r.get("text", []) if l.kind == "p"]
        heads = any(l.kind == "h" for l in r.get("text", []))
        if len(text) == 1 and r.get("sections") and not heads:
            add("thin", n, " ".join(w.text for w in text[0].words)[:40], "exception" if r.get("thin_ok") else "error")
        # a page that should be full: not the last one, nor the last before a new section
        if n + 1 < len(pages) and (n + 1) not in starts:
            gap = room_left(eng, pg)
            if gap > HOLE:
                add("hole", n, f"{gap:.0f} נקודות")
    for n in range(off, len(pages)):
        for t, y in section_headings(pages[n]):
            if y > eng.m + eng.head_h + 10:
                add("parasha", n, t)
    return out


def opens_section(pg):
    """Whether the page begins with a parasha (or the haftarot of the festivals)."""
    hs = section_headings(pg)
    return bool(hs) and hs[0][1] < 80


def section_headings(pg):
    out = []
    for fr in pg.frames:
        for l in fr.lines:
            if getattr(l, "kind", "") == "h":
                t = " ".join(w.text for w in l.words)
                if t.startswith("פרשת") or t.startswith("הפטרות "):
                    out.append((t, fr.top + l.y))
    return out


def room_left(eng, pg):
    if not pg.frames:
        return 0.0
    bottom = max(fr.top + max((l.y + l.h for l in fr.lines), default=0) for fr in pg.frames)
    return pg.height - eng.m - bottom


def check_bounds(eng, pg, n, add):
    if not pg.rules:
        return
    x1, _, x2 = pg.rules[0]
    for fr in pg.frames:
        for l in fr.lines:
            right = fr.x_right - l.right
            left = right - l.width
            used = right - sum(w.w for w in l.words)
            if right > x2 + 0.5 or left < x1 - 0.5 or used < x1 - 0.5:
                add("outside", n, " ".join(w.text for w in l.words)[:40])
                return
            if fr.top + l.y + l.h > pg.height - eng.m + 1.0:
                add("outside", n, "מתחת לשוליים: " + " ".join(w.text for w in l.words)[:30])
                return


def check_spaces(pg, n, add):
    for fr in pg.frames:
        for l in fr.lines:
            r = space_ratio(l)
            if r > WIDE_SPACE:
                add("spaces", n, f"פי {r:.1f}: " + " ".join(w.text for w in l.words)[:40], "warning")


def where(eng, v):
    """A verse by its number in the book (0, 1, …) as 'פרק כ פסוק ג'."""
    for it in eng.all_items:
        if it["type"] == "v" and it["idx"] == v:
            ch = re.sub(r"^פרק\s+", "", it["chapter"]) if it["chapter"].startswith("פרק") else it["chapter"]
            return f"{ch},{it['label']}" if ch else f"פסוק {it['label']}"
    return f"פסוק {v + 1}"


def late_commentaries(eng, r):
    """(name, verse) of the commentaries that should begin on the page and don't."""
    lo, hi = r.get("min_v"), r.get("max_v")
    out = []
    if lo is None or hi is None or hi < 0:
        return out
    for c in eng.bottoms:
        ptr = r["ptrs"].get(c)
        if ptr is None:
            continue
        for v in range(lo, hi + 1):
            idx = eng.first_idx[c].get(v)
            if idx is not None and not (ptr[0] > idx or (ptr[0] == idx and ptr[1] > 0)):
                out.append((eng.comms[c]["name"], v))
    return out


def summary(problems):
    """(faults, known exceptions, warnings)"""
    return ([p for p in problems if p.severity == "error"], [p for p in problems if p.severity == "exception"],
            [p for p in problems if p.severity == "warning"])


def describe(p):
    where = f"עמוד {p.label}" if p.label else ""
    return f"{where}: {NAMES.get(p.kind, p.kind)} — {p.text}" if where else f"{NAMES.get(p.kind, p.kind)} — {p.text}"
