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
# lines spread more than this (times their normal spacing) to fill a page: it shows
LOOSE = 1.3


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
    "lone": "מילה אחת לבד בשורה באמצע פסקה",
    "text": "סימן משובש בטקסט",
    "number": "מספר פסוק לבד בסוף שורה",
    "short_end": "פירוש שנגמר בשורה קצרה באמצע העמוד",
    "text_end": "פסוקים שממשיכים בעמוד הבא ונגמרים בשורה קצרה",
    "heading_foot": "כותרת בתחתית העמוד עם פחות משתי שורות תחתיה",
    "last_alone": "עמוד אחרון עם שורות בודדות",
    "loose": "מרווח שורות שנפתח הרבה מעבר לרגיל",
    "integrity": "מילים שחסרות, כפולות או לא בסדר הנכון",
    "early": "תרגום שמתחיל לפני הפסוק שלו",
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

    starts = [n for n in range(off, len(pages)) if opens_section(pages[n], 80 + eng.gm_band())]
    for k, (r, chapter, parasha) in enumerate(eng.pages):
        n = k + off
        pg = pages[n]
        check_bounds(eng, pg, n, add)
        check_spaces(pg, n, add)
        check_numbers(pg, n, add)
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
        # a commentary (or the Onkelos column) that ends in the middle of the page ends on a full line
        ends = [(s["c"], s["lines"]) for s in r.get("sections", [])] + [(c, s["col"]) for c, s in r.get("side", {}).items()] \
            + list(r.get("gm", {}).items())
        for c, lines in ends:
            if (len(lines) > 1 and lines[-1].last and lines[-1].align != "center" and sum(w.w for w in lines[-1].words) < lines[-1].width * 0.5
                    and not (r.get("at_end") and eng.done(c, r["ptrs"][c]))):
                add("short_end", n, eng.comms[c]["name"], "warning")
        # the room left on a page is spread over its lines, but never so much that it shows
        loose = [eng.comms[s_["c"]]["name"] for s_ in r.get("sections", []) if s_["nlh"] > eng.note_lh[s_["c"]] * LOOSE]
        if any(l.kind == "p" and l.h > eng.main_lh * LOOSE for l in r.get("text", [])):
            loose.append("הפסוקים")
        if loose:
            add("loose", n, ", ".join(loose))
        text = [l for l in r.get("text", []) if l.kind == "p"]
        heads = any(l.kind == "h" for l in r.get("text", []))
        # the verses go on on the next page: they end on a full line (rule 8)
        b, items = r.get("b"), r.get("items") or []
        if (text and r["text"][-1].kind == "p" and not r.get("at_end") and "gm" not in r and b
                and b[0] < len(items) and (b[1] > 0 or (items[b[0]]["type"] == "v" and not eng.P.get("verseNewLine")))
                and text[-1].natural < text[-1].width * 0.6):
            add("text_end", n, " ".join(w.text for w in text[-1].words)[:30], "exception" if r.get("short_ok") else "error")
        if len(text) == 1 and r.get("sections") and not heads:
            add("thin", n, " ".join(w.text for w in text[0].words)[:40], "exception" if r.get("thin_ok") else "error")
        # a page that should be full: not the last one, nor the last before a new section
        if n + 1 < len(pages) and (n + 1) not in starts:
            gap = room_left(eng, pg)
            if gap > HOLE:
                add("hole", n, f"{gap:.0f} נקודות")
    check_integrity(eng, pages, off, add)
    for n in range(off, len(pages)):
        check_foot(pages[n], n, add, n + 1 < len(pages))
    if len(pages) - off > 1:
        rows = sum(len(fr.lines) for fr in pages[-1].frames)
        if rows <= 3:
            add("last_alone", len(pages) - 1, f"{rows} שורות")
    for n in range(off, len(pages)):
        r = eng.pages[n - off][0]
        pre = r.get("pre") or {}
        # a parasha may begin under the short end of a haftara (see engine.HAFTARA_TAIL)
        under_tail = bool(pre.get("tail"))
        for t, y in section_headings(pages[n]):
            if y > eng.m + eng.head_h + eng.gm_band() + 10 and not (under_tail and t.startswith("פרשת")):
                add("parasha", n, t)
    return out


def opens_section(pg, top=80):
    """Whether the page begins with a parasha (or the haftarot of the festivals)."""
    hs = section_headings(pg)
    return bool(hs) and hs[0][1] < top


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


def check_integrity(eng, pages, off, add):
    """Every word of the text and of each commentary is on the pages once, in its order: the
    words as laid out, page by page, against the source (a word dropped, doubled or out of
    order between pages would show here)."""
    seen = {"main": []}
    for n in range(off, len(pages)):
        for fr in pages[n].frames:
            if not fr.src:
                continue
            if fr.src[0] == "main":
                items = fr.src[1] or []
                for l in fr.lines:
                    for w in l.words:
                        if isinstance(w.ref, tuple) and len(w.ref) == 2 and isinstance(w.ref[0], int) and w.ref[0] < len(items):
                            key = (id(items[w.ref[0]]), w.ref[1])
                            if not seen["main"] or seen["main"][-1][0] != key:      # (a word split at a maqaf)
                                seen["main"].append((key, n))
            elif fr.src[0] == "comm":
                lst = seen.setdefault(fr.src[1], [])
                for l in fr.lines[:-1]:
                    w = l.words[-1] if l.words else None
                    if w is not None and isinstance(w.ref, tuple) and w.ref[0] == "L":
                        add("number", n, f"{eng.comms[fr.src[1]]['name']}: {w.text}")
                for l in fr.lines:
                    for w in l.words:
                        if isinstance(w.ref, tuple) and len(w.ref) == 2 and (not lst or lst[-1][0] != w.ref):
                            lst.append((w.ref, n))
    want = [(id(it), k) for it in eng.all_items if it["type"] == "v" for k in range(len(it["words"]))]
    streams = {}
    for c, st in eng.streams.items():
        exp = streams[c] = []
        for j, e in enumerate(st):
            if e["label"]:
                exp.append(("L", j))
            exp.extend((j, k) for k in range(len(e["tokens"])))
    # a translation or commentary never begins before its verse: the page where each verse
    # begins, against the page where each passage on it begins
    verse_page = {}
    by_id = {id(it): it for it in eng.all_items if it["type"] == "v"}
    for (iid, k), n in seen["main"]:
        it = by_id.get(iid)
        if it is not None and it["idx"] >= 0 and it["idx"] not in verse_page:
            verse_page[it["idx"]] = n
    for c, st in eng.streams.items():
        first = {}
        for ref, n in seen.get(c, []):
            j = ref[1] if ref[0] == "L" else ref[0]
            first.setdefault(j, n)
        for j, n in sorted(first.items()):
            v = st[j]["v"] if j < len(st) else None
            if v is not None and v in verse_page and n < verse_page[v]:
                add("early", n, f"{eng.comms[c]['name']} על {where(eng, v)}")
    for name, got, exp in [("הטקסט", seen["main"], want)] + [(eng.comms[c]["name"], seen.get(c, []), streams[c]) for c in streams]:
        keys = [k for k, _ in got]
        if keys == exp:
            continue
        i = next((i for i, (a, b) in enumerate(zip(keys, exp)) if a != b), min(len(keys), len(exp)))
        n = got[min(i, len(got) - 1)][1] if got else -1
        add("integrity", n, f"{name}: {len(keys)} מילים במקום {len(exp)}, הראשונה שלא במקומה היא מספר {i + 1}")


def check_foot(pg, n, add, more):
    """A heading (a haftara's, a chapter's) at the foot of a page with fewer than two lines of
    its text under it, when the text goes on on the next page."""
    if not more or not pg.frames:
        return
    bottom = max(fr.top + max((l.y + l.h for l in fr.lines), default=0) for fr in pg.frames)
    for fr in pg.frames:
        if not fr.lines or fr.top + fr.lines[-1].y + fr.lines[-1].h < bottom - 1.0:
            continue
        heads = [i for i, l in enumerate(fr.lines) if getattr(l, "kind", "") == "h"]
        if heads and len(fr.lines) - heads[-1] - 1 < 2:
            t = " ".join(w.text for w in fr.lines[heads[-1]].words)
            if not t.startswith("פרשת"):
                add("heading_foot", n, t[:30])


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
            # a line in the middle of a paragraph that can't reach the end of the line: one word
            if (l.align == "justify" and not l.last and len(l.words) == 1 and getattr(l, "kind", "p") != "h"
                    and l.words[0].w < l.width * 0.8):
                add("lone", n, l.words[0].text)
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


def check_numbers(pg, n, add):
    """A verse's number is never the last word of a line (its verse begins on the next)."""
    for fr in pg.frames:
        if not (fr.src and fr.src[0] == "main"):
            continue
        items = fr.src[1] or []
        for l in fr.lines[:-1]:
            w = l.words[-1] if l.words else None
            ref = getattr(w, "ref", None)
            if not (isinstance(ref, tuple) and ref and ref[0] == "l" and ref[1] < len(items)):
                continue
            it = items[ref[1]]
            if it.get("label") == w.text and it.get("sec") != w.text:
                add("number", n, w.text)
                return


def late_commentaries(eng, r):
    """(name, verse) of the commentaries that should begin on the page and don't."""
    lo, hi = r.get("min_v"), r.get("max_v")
    out = []
    if lo is None or hi is None or hi < 0:
        return out
    for c in eng.bottoms + eng.gm:
        if c in r.get("deferred", ()):
            continue      # the commentary before it fills the page: it begins on the next one
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
