"""The page layout engine (the Mikraot Gedolot method).

Fonts never change size. On every page:
  * the text runs on word by word (a verse may continue on the next page);
  * the translation sits in a column beside the text and never runs ahead of it: a
    verse's translation is set on the page where the verse's text is complete. If the
    translation is shorter than the text, the text runs on under it at full width; if
    it is longer, it runs on under the text at full width (an L);
  * every commentary is a full-width block of columns under the text;
  * a page takes the most text for which the translation and the commentary of every
    verse completed on it fit on that page in full. The verse that continues on the
    next page uses the room left, and the rest of its commentary follows it;
  * only a commentary longer than a whole page (beyond the minimum lines of text)
    runs on to the next page;
  * the text ends on a full line and the last block is stretched to the bottom, so a
    page has no hole;
  * a haftara ('## …', no commentary) starts under the end of the parasha, and the
    next parasha starts under the end of the haftara.

Everything is measured in points and laid out line by line, so heights are exact.
"""
import math
import re
import time
from dataclasses import dataclass, field

from .model import entry_tokens, heb, page_mm, parse_comm, parse_main
from .textlayout import PT_PER_MM, Line, Style, Word, break_lines, full_width, space, width, words_of

EPS = 0.01
# an automatic-width translation column: its share of the line stays within these (%)
AUTO_MIN, AUTO_MAX = 20.0, 40.0
# the letter (פ / ס) at the end of an open / a closed section
SECTION_FONT = "David Libre"


class Cancelled(Exception):
    pass


# ---------------------------------------------------------------- output pages

@dataclass
class Frame:
    """Lines placed on the page: x_right is the frame's right edge, top its top (absolute pt)."""
    lines: list
    x_right: float
    top: float
    src: object = None   # where the lines come from: ("main", items) or ("comm", c), for clicks on the page


@dataclass
class Page:
    width: float
    height: float
    frames: list = field(default_factory=list)
    rules: list = field(default_factory=list)   # (x1, y, x2)
    head: tuple = None                           # (right text, center text, left text, style, baseline y)
    overfull: bool = False


# ---------------------------------------------------------------- helpers

@dataclass
class Spec:
    """A paragraph of the main text (or a heading)."""
    words: list
    base: Style
    lh: float
    align: str = "justify"
    mt: float = 0.0
    mb: float = 0.0
    cut: bool = False
    kind: str = "p"


def layout_specs(specs, width_at):
    lines = []
    y = 0.0
    for sp in specs:
        y += sp.mt
        ls = break_lines(sp.words, sp.base, sp.lh, width_at, y, sp.align)
        for k, l in enumerate(ls):
            l.mt = sp.mt if k == 0 else 0.0
            l.mb = sp.mb if k == len(ls) - 1 else 0.0
            l.kind = sp.kind
        if ls and sp.cut:
            ls[-1].last = False
            ls[-1].force = getattr(sp, "force", False)
        if ls:
            y = ls[-1].y + ls[-1].h
        y += sp.mb
        lines += ls
    return lines, y


def restack(lines):
    """Recompute the y of lines after their heights changed."""
    y = 0.0
    for l in lines:
        y += getattr(l, "mt", 0.0)
        l.y = y
        y += l.h + getattr(l, "mb", 0.0)
    return y


# ---------------------------------------------------------------- the engine

class Engine:
    def __init__(self, project, progress=None):
        self.P = project
        self.progress = progress
        self.warnings = []
        P = project
        wmm, hmm = page_mm(P)
        self.page_w = wmm * PT_PER_MM
        self.page_h = hmm * PT_PER_MM
        self.m = P["margin"] * PT_PER_MM
        # a book is bound on its inner side: extra margin there (the pages alternate)
        self.gutter = float(P.get("gutter") or 0) * PT_PER_MM if P.get("bookMode") else 0.0
        self.W = self.page_w - 2 * self.m - self.gutter
        self.body_h = self.page_h - 2 * self.m
        # the dedication at the foot of the first page
        self.ded_style = Style(P["mainFont"], 8.5)
        self.ded_lines = [l.strip() for l in str(P.get("dedication") or "").split("\n") if l.strip()]
        self.ded_lh = 8.5 * 1.45
        self.ded_h = (len(self.ded_lines) * self.ded_lh + 4 * PT_PER_MM) if self.ded_lines else 0.0
        self.gap = P["colGap"] * PT_PER_MM
        self.sgap = P["sectionGap"] * PT_PER_MM
        self.lh_k = P["lineHeight"]
        self.note_k = max(1.2, P["lineHeight"] - 0.12)
        self.main = Style(P["mainFont"], P["mainSize"])
        self.main_lh = P["mainSize"] * self.lh_k
        self.head_style = Style(P["mainFont"], 9.0)
        self.head_h = (9.0 * 1.3 + 1 * PT_PER_MM + 2 * PT_PER_MM) if P["header"] else 0.0
        self.min_text_h = P["minLines"] * self.main_lh - 1

        self.all_items, self.count = parse_main(P["main"])
        self.comms = P["comms"]
        self.parsed = {}
        for i, c in enumerate(self.comms):
            entries, problem, _ = parse_comm(c, self.count)
            self.parsed[i] = entries
            if problem:
                self.warnings.append(f"{c['name']}: {problem}")
        self.sides = [i for i, c in enumerate(self.comms) if c["place"] == "side"]
        self.bottoms = [i for i, c in enumerate(self.comms) if c["place"] == "bottom"]
        self.unders = [i for i, c in enumerate(self.comms) if c["place"] == "under"]
        self.style = {i: Style(c["font"], float(c["size"])) for i, c in enumerate(self.comms)}
        self.side_lh = {i: self.comms[i]["size"] * self.lh_k for i in self.sides}
        self.note_lh = {i: self.comms[i]["size"] * self.note_k for i in self.bottoms}

        labels = [it["label"] for it in self.all_items if it["type"] == "v" and not it["noComm"]]
        # each translation / commentary is one stream of entries in verse order
        self.streams, self.first_idx = {}, {}
        for i in self.sides + self.bottoms:
            st, first = [], {}
            for v, raws in enumerate(self.parsed[i]):
                if not raws:
                    continue
                first[v] = len(st)
                if i in self.sides:
                    st.append({"v": v, "label": labels[v], "tokens": [t for r in raws for t in entry_tokens(r)], "note": False})
                else:
                    for k, r in enumerate(raws):
                        # the verse's letter only before its first passage, not before each one
                        st.append({"v": v, "label": f"({labels[v]})" if k == 0 else "", "tokens": entry_tokens(r), "note": True,
                                   "p": k})
            self.streams[i], self.first_idx[i] = st, first
        self.ptrs = {i: (0, 0) for i in self.streams}
        self.sec_end = {}
        self.items = [it for it in self.all_items if not it["noComm"]]
        self.col_w = {}
        self.memo = {}
        self.ew_cache = {}
        self.last_breath = 0.0
        self._auto_widths()

    # ------------------------------------------------------------ text of the page

    def segments(self, a, b, lst=None):
        lst = self.items if lst is None else lst
        segs = []
        last_i = b[0] if b[1] > 0 else b[0] - 1
        for i in range(a[0], min(last_i, len(lst) - 1) + 1):
            it = lst[i]
            n = len(it["words"]) if it["type"] == "v" else 0
            segs.append((i, it, a[1] if i == a[0] else 0, b[1] if i == b[0] else n))
        return segs

    def text_specs(self, segs, cut_at_end):
        P = self.P
        specs, para = [], []
        bold = self.main.with_bold(True)

        def flush():
            if para:
                specs.append(Spec(list(para), self.main, self.main_lh))
                para.clear()

        for i, it, frm, to in segs:
            if self.is_inline(it):
                # the chapter is marked inside the running text: its letter, larger and bold,
                # followed by verse 1 with its own letter
                letter = it["text"].split()[-1]
                st = self.main.scaled(1.4, bold=True)
                para.append(Word(letter, st, width(st, letter), ("h", i)))
                continue
            if it["type"] == "h":
                flush()
                st = self.main.scaled(1.2, bold=True)
                hw = words_of([(w, True) for w in it["text"].split()], st, lambda k, i=i: ("h", i))
                mt = 1 * PT_PER_MM if it["noComm"] else 0.0
                specs.append(Spec(hw, st, st.size * self.lh_k, "center", mt, 0.6 * PT_PER_MM if it["noComm"] else 0.0, kind="h"))
                continue
            if it.get("aliyah") and frm == 0:
                # the aliyah, small and bold, inside the text before its first verse
                ast = self.main.scaled(0.68, bold=True)
                t = f"({it['aliyah']})"
                para.append(Word(t, ast, width(ast, t), ("l", i), glue=True))
            if P["numbers"] and frm == 0:
                para.append(Word(it["label"], bold, width(bold, it["label"]), ("l", i)))
            para.extend(words_of(it["words"][frm:to], self.main, lambda k, i=i, frm=frm: (i, frm + k)))
            und = []
            if to == len(it["words"]) and it["idx"] >= 0:
                for u in self.unders:
                    ent = self.parsed[u][it["idx"]]
                    if ent:
                        st = self.style[u]
                        toks = [t for r in ent for t in entry_tokens(r)]
                        und.append(Spec(words_of(toks, st), st, st.size * self.note_k, mt=0.3 * PT_PER_MM, kind="u"))
            if to == len(it["words"]) and it.get("sec"):
                # the end of an open / a closed section: its letter, bold, in another font, the
                # text running on (the letter is never alone at the start of a line)
                sst = Style(SECTION_FONT, self.main.size, True)
                if para:
                    para[-1].glue = True
                para.append(Word(it["sec"], sst, width(sst, it["sec"]), ("l", i)))
            if P["verseNewLine"] or und:
                flush()
                specs.extend(und)
        flush()
        if cut_at_end and specs:
            specs[-1].cut = True
            specs[-1].force = True
        return specs

    def is_inline(self, it):
        return (it["type"] == "h" and self.P.get("inlineChapters")
                and re.match(r"^פרק\s+\S+$", it["text"]) is not None)

    def is_break(self, it):
        """Whether an item breaks the running text (a heading on its own line)."""
        return it["type"] == "h" and not self.is_inline(it)

    # ------------------------------------------------------------ streams

    def list_from(self, c, ptr, max_v):
        st, out = self.streams[c], []
        for j in range(ptr[0], len(st)):
            e = st[j]
            if max_v is not None and e["v"] > max_v:
                break
            if j == ptr[0] and ptr[1]:
                out.append(dict(e, start=ptr[1], cont=True, j=j))
            else:
                out.append(dict(e, start=0, cont=False, j=j))
        return out

    def entry_words(self, c, lst):
        """The words of the entries in lst: each entry's label (bold), then its words. A
        word's ref is (entry index, word index), the label's ('L', entry index)."""
        words = []
        for e in lst:
            key = (c, e["j"])
            ws = self.ew_cache.get(key)
            if ws is None:
                base = self.style[c]
                bold = base.with_bold(True)
                j = e["j"]
                ws = [Word(e["label"], bold, width(bold, e["label"]), ("L", j))] if e["label"] else []
                for k, (t, b) in enumerate(e["tokens"]):
                    st = bold if b else base
                    ws.append(Word(t, st, width(st, t), (j, k)))
                self.ew_cache[key] = ws
            skip = 1 if e["label"] else 0
            words.extend(ws[skip + e["start"]:] if e["cont"] else ws)
        return words

    def advance(self, ptr, words, n_taken, n_entries):
        if n_taken >= len(words):
            return (ptr[0] + n_entries, 0)
        ref = words[n_taken].ref
        if ref[0] == "L":
            return (ref[1], 0)
        return (ref[0], ref[1])

    def started(self, c, v, ptr):
        idx = self.first_idx[c].get(v)
        if idx is None:
            return True
        return ptr[0] > idx or (ptr[0] == idx and ptr[1] >= 3)

    def done(self, c, ptr):
        return ptr[0] >= self.sec_end.get(c, len(self.streams[c]))

    def take(self, words, base, lh, w, max_lines, tight=1.0):
        """The first max_lines lines of words at width w (a new entry is not started
        with fewer than three of its words). Returns (lines, number of words taken)."""
        lines = break_lines(words, base, lh, full_width(w), tight=tight)
        if len(lines) <= max_lines:
            return lines, len(words)
        lines = lines[:max(0, max_lines)]
        n = sum(len(l.words) for l in lines)
        # find where the entry that is cut began
        k = n - 1
        while k >= 0 and words[k].ref[0] != "L" and words[k].ref[1] != 0:
            k -= 1
        if k > 0 and words[k].ref[0] != "L" and words[k - 1].ref == ("L", words[k].ref[0]):
            k -= 1      # the entry's letter goes with it
        taken = n - k - (1 if k >= 0 and words[k].ref[0] == "L" else 0)
        if k >= 0 and 0 < taken < 3:
            lines = break_lines(words[:k], base, lh, full_width(w), tight=tight)
            n = k
        if lines:
            lines[-1].last = False
        return lines, n

    # ------------------------------------------------------------ geometry

    def side_of(self, c):
        """Which side of the text a translation column stands on. In book form it is
        always the inner side: the book opens on a left-hand page, whose inner side is
        the right, and the pages alternate from there."""
        if self.P.get("bookMode"):
            return "right" if len(self.pages) % 2 == 0 else "left"
        return "right" if self.comms[c]["side"] == "right" else "left"

    def side_width(self, c):
        return self.W * self.col_w[c] / 100 - self.gap / 2

    def width_at(self, heights):
        def f(y):
            right = left = 0.0
            for c in self.sides:
                if heights.get(c, 0) > y + EPS:
                    if self.side_of(c) == "right":
                        right += self.side_width(c) + self.gap
                    else:
                        left += self.side_width(c) + self.gap
            return right, self.W - right - left
        return f

    def title_h(self, c):
        if not self.P["names"]:
            return 0.0
        return self.style[c].size * 1.05 * self.lh_k + 0.5 * PT_PER_MM

    def note_title_h(self, c):
        if not self.P["names"]:
            return 0.0
        return self.style[c].size * 1.1 * self.note_k + 0.5 * PT_PER_MM

    def note_col_w(self, c):
        n = self.comms[c]["cols"]
        return (self.W - (n - 1) * self.gap) / n

    def note_pad(self):
        return self.sgap * 0.6

    def section_h(self, c, n_lines, nlh=None):
        rows = math.ceil(n_lines / self.comms[c]["cols"])
        return self.note_pad() + self.note_title_h(c) + rows * (nlh or self.note_lh[c])

    def _auto_widths(self):
        """Give an automatic-width translation column the share of the line at which the
        text and the translation come out the same height, so they run out together."""
        for c in self.sides:
            self.col_w[c] = min(60, max(10, float(self.comms[c]["width"] or 30)))
        sample = self.items[:600]
        segs = [(i, it, 0, len(it["words"]) if it["type"] == "v" else 0) for i, it in enumerate(sample)]
        specs = self.text_specs(segs, False)
        verses = {it["idx"] for it in sample if it["type"] == "v"}
        for c in self.sides:
            if not self.comms[c]["autoW"]:
                continue
            toks = [t for v, raws in enumerate(self.parsed[c]) if v in verses for r in raws for t in entry_tokens(r)]
            if not toks:
                continue
            sw = words_of(toks, self.style[c])
            others = sum(self.col_w[o] for o in self.sides if o != c)
            lo, hi = AUTO_MIN, min(AUTO_MAX, 90.0 - others)
            for _ in range(9):
                w = (lo + hi) / 2
                _, h_main = layout_specs(specs, full_width(self.W * (100 - others - w) / 100))
                n_side = len(break_lines(sw, self.style[c], self.side_lh[c], full_width(self.W * w / 100)))
                if n_side * self.side_lh[c] > h_main * 0.89:
                    lo = w
                else:
                    hi = w
            self.col_w[c] = round(hi, 1)
        total = sum(self.col_w[c] for c in self.sides)
        if total > 75:
            self.warnings.append("סכום רוחב הטורים הצמודים גדול מדי — הוקטן כך שלטקסט העיקרי יישאר 25%.")
            for c in self.sides:
                self.col_w[c] *= 75 / total

    # ------------------------------------------------------------ one page

    def compose(self, a, b, force=False, pre=None, comm_only=False, tight=1.0):
        """Lay out the page that holds the text from a to b. pre: lines of a haftara's
        end set above it. comm_only: a page of the commentaries under the text only.
        The same page is tried many times while a page is chosen: it is laid out once."""
        key = (a, b, force, id(pre), comm_only, tight, tuple(sorted(self.ptrs.items())),
               tuple(sorted(self.col_w.items())), len(self.pages) % 2)
        hit = self.memo.get(key)
        if hit is not None:
            return hit
        self.breathe()
        r = self._compose(a, b, force, pre, comm_only, tight)
        self.memo[key] = r
        return r

    def breathe(self):
        """Let the window answer now and then during a long layout."""
        if self.progress:
            now = time.monotonic()
            if now - self.last_breath > 0.1:
                self.last_breath = now
                self.progress(len(self.pages))

    def _compose(self, a, b, force=False, pre=None, comm_only=False, tight=1.0):
        items = self.items
        segs = self.segments(a, b)
        at_end = b[0] >= len(items)
        # the text on the page ends on a full line unless the section or a paragraph ends here
        cut = b[1] > 0 or (not at_end and not self.is_break(items[b[0]]) and not self.P["verseNewLine"])
        r = {"a": a, "b": b, "at_end": at_end, "pre": pre, "ptrs": dict(self.ptrs), "side": {}, "sections": [],
             "side_dir": {c: self.side_of(c) for c in self.sides},
             "post": None, "req_fit": True, "side_short": False}
        max_v = last_full = -1
        for i in range(min(b[0] if b[1] > 0 else b[0] - 1, len(items) - 1), -1, -1):
            if items[i]["type"] == "v":
                max_v = items[i]["idx"]
                break
        for i in range(min(b[0] - 1, len(items) - 1), -1, -1):
            if items[i]["type"] == "v":
                last_full = items[i]["idx"]
                break
        used = self.head_h + (pre["h"] + self.sgap + 3 * PT_PER_MM if pre else 0.0)
        avail = self.contentH - used

        # Translation columns beside the text. A column runs the full height of the text and
        # ends with it on the same line; the translation of the last verse may continue at
        # the top of the column on the next page, but never comes before its verse. Only
        # when the translation runs out (at the end of a section) does the text continue
        # under the column.
        specs = self.text_specs(segs, cut)
        heights, info = {}, {}
        for c in self.sides:
            ptr = self.ptrs[c]
            lst = self.list_from(c, ptr, max_v)
            words = self.entry_words(c, lst)
            lines = break_lines(words, self.style[c], self.side_lh[c], full_width(self.side_width(c)))
            th = self.title_h(c) if lines else 0.0
            info[c] = {"lst": lst, "words": words, "nat": lines, "th": th, "ptr": ptr}
            heights[c] = 1e9 if lines and segs else 0.0
        text_lines, text_h = layout_specs(specs, self.width_at(heights))
        r["col_full"] = True
        if segs:
            short = False
            for c in self.sides:
                inf = info[c]
                if not inf["nat"]:
                    continue
                # as many lines as are closest to the height of the text (their spacing is
                # then opened or closed by at most half a line over the column)
                cap = max(1, int(round((text_h - inf["th"]) / self.side_lh[c])))
                if len(inf["nat"]) >= cap:
                    inf["k"], inf["mode"] = cap, "full"
                else:
                    inf["k"], inf["mode"] = len(inf["nat"]), "wrap"
                    heights[c] = inf["th"] + len(inf["nat"]) * self.side_lh[c]
                    short = True
            if short:
                r["col_full"] = False
                text_lines, text_h = layout_specs(specs, self.width_at(heights))
        top_h = text_h
        for c in self.sides:
            inf = info[c]
            slh = self.side_lh[c]
            if not inf["nat"] or comm_only:
                r["side"][c] = {"col": [], "band": [], "th": 0.0, "mode": "wrap", "slh": slh, "h": 0.0}
                r["ptrs"][c] = inf["ptr"]
                continue
            band, n_band, col_lines = [], 0, []
            if segs:
                col_lines = inf["nat"][:inf["k"]]
                if inf["mode"] == "full" and col_lines and inf["k"] < len(inf["nat"]):
                    col_lines[-1].last = False
                mode = inf["mode"]
                if at_end and inf["k"] < len(inf["nat"]):
                    # the end of the parasha: the rest of the translation goes under the text
                    n_c = sum(len(l.words) for l in col_lines)
                    room = avail - max(top_h, inf["th"] + len(col_lines) * slh) - 1 * PT_PER_MM
                    max_lines = int((room + EPS) // slh) if room > 0 else 0
                    band, n_band = self.take(inf["words"][n_c:], self.style[c], slh, self.W, max_lines)
                    if band:
                        top_h = max(top_h, inf["th"] + len(col_lines) * slh) + 1 * PT_PER_MM + len(band) * slh
            else:
                # no text left on the page: what remains of the translation goes across the page
                room = avail - top_h - 1 * PT_PER_MM
                max_lines = int((room + EPS) // slh) if room > 0 else 0
                if force and max_lines < 1:
                    max_lines = 1
                band, n_band = self.take(inf["words"], self.style[c], slh, self.W, max_lines)
                if band:
                    top_h += 1 * PT_PER_MM + len(band) * slh
                mode = "band"
            n_col = sum(len(l.words) for l in col_lines)
            r["ptrs"][c] = self.advance(inf["ptr"], inf["words"], n_col + n_band, len(inf["lst"]))
            h = (inf["th"] + len(col_lines) * slh) if col_lines else 0.0
            top_h = max(top_h, h) if mode != "band" and not band else top_h
            r["side"][c] = {"col": col_lines, "band": band, "th": inf["th"] if col_lines else 0.0, "mode": mode,
                            "slh": slh, "h": h}
        r["text"] = text_lines
        r["text_h"] = text_h
        r["top_h"] = top_h
        top_fits = used + top_h <= self.contentH + EPS
        r["top_fits"] = top_fits

        # commentaries under the text
        room = self.contentH - used - top_h - self.sgap
        plans = []
        for c in self.bottoms:
            ptr = self.ptrs[c]
            req = self.list_from(c, ptr, last_full)
            alll = self.list_from(c, ptr, max_v)
            req_h = 0.0
            if req:
                rw = self.entry_words(c, req)
                req_h = self.section_h(c, len(break_lines(rw, self.style[c], self.note_lh[c], full_width(self.note_col_w(c)))))
            plans.append((c, ptr, req, alll, req_h))
        req_total = sum(p[4] for p in plans if p[2]) + 1.2 * PT_PER_MM * max(0, sum(1 for p in plans if p[2]) - 1)
        r["req_fit"] = top_fits and req_total <= room + EPS
        placed_any = False
        for n, (c, ptr, req, alll, req_h) in enumerate(plans):
            r["ptrs"][c] = ptr
            if not alll:
                continue
            later = sum(self.reserve(p, r["req_fit"]) for p in plans[n + 1:])
            budget = room - later - (1.2 * PT_PER_MM if placed_any else 0.0)
            nlh = self.note_lh[c]
            rows = int((budget - self.note_pad() - self.note_title_h(c) + EPS) // nlh)
            if force and not placed_any and rows < 1:
                rows = 1
            if rows < 1:
                continue
            words = self.entry_words(c, alll)
            lines, ntake = self.take(words, self.style[c], nlh, self.note_col_w(c), rows * self.comms[c]["cols"], tight)
            if not lines:
                continue
            h = self.section_h(c, len(lines))
            r["sections"].append({"c": c, "lines": lines, "nlh": nlh, "cut": ntake < len(words), "h": h})
            room -= h + (1.2 * PT_PER_MM if placed_any else 0.0)
            placed_any = True
            r["ptrs"][c] = self.advance(ptr, words, ntake, len(alll))
        r["max_v"] = max_v
        r["min_v"] = next((it["idx"] for _, it, _, _ in segs if it["type"] == "v"), None)
        # every commentary of a verse whose text is on the page begins on the page
        r["start_ok"] = True
        for c, ptr, req, alll, req_h in plans:
            e, w = r["ptrs"][c]
            for v in {x["v"] for x in alll}:
                idx = self.first_idx[c].get(v)
                if idx is not None and not (e > idx or (e == idx and w > 0)):
                    r["start_ok"] = False
        r["req_fit"] = r["req_fit"] and r["start_ok"]
        if not r["req_fit"] and tight == 1.0 and segs and not force:
            # a little less room between the words of the commentaries (over all their lines)
            r2 = self._compose(a, b, force, pre, comm_only, 0.88)
            if r2["req_fit"]:
                return r2
        return r

    def reserve(self, p, req_fit):
        """Room kept for a commentary placed after another: all of what the page owes it,
        and the first lines of what it begins on the page."""
        c, ptr, req, alll, req_h = p
        if not alll:
            return 0.0
        start = self.section_h(c, self.comms[c]["cols"])
        if req_fit and req:
            h = req_h + (self.note_lh[c] if len(alll) > len(req) else 0.0)
        else:
            h = start
        return h + 1.2 * PT_PER_MM

    def can_close(self, r, hole):
        """Whether a hole of this height can be spread over the page's lines."""
        if hole <= self.main_lh * 1.5:
            return True
        units = len([l for l in r["text"] if l.kind == "p"])
        units += sum(math.ceil(len(s["lines"]) / self.comms[s["c"]]["cols"]) for s in r["sections"])
        lhs = [self.main_lh] + [s["nlh"] for s in r["sections"]]
        return units > 0 and hole / units <= 0.3 * min(lhs)

    def notes_h(self, r):
        if not r["sections"]:
            return 0.0
        return self.sgap + sum(s["h"] for s in r["sections"]) + 1.2 * PT_PER_MM * (len(r["sections"]) - 1)

    def total_h(self, r):
        h = self.head_h
        if r["pre"]:
            h += r["pre"]["h"] + self.sgap + 3 * PT_PER_MM
        h += r["top_h"] + self.notes_h(r)
        if r["post"]:
            h += r["post"]["mt"] + r["post"]["h"]
        return h

    def recompute_top(self, r):
        text_h = restack(r["text"])
        r["text_h"] = text_h
        top_h = max([text_h] + [s["h"] for s in r["side"].values()])
        for s in r["side"].values():
            if s["band"]:
                top_h += 1 * PT_PER_MM + len(s["band"]) * s["slh"]
        r["top_h"] = top_h

    # ------------------------------------------------------------ closing the gaps

    def align_columns(self, r):
        # the translation column ends exactly where the text beside it ends (band), or
        # exactly where the next line of the text under it begins (wrap)
        for c, s in r["side"].items():
            if not s["col"]:
                continue
            n = len(s["col"])
            if s["mode"] == "full":
                target = r["text_h"]
            elif s["mode"] == "wrap":
                tops = [l.y for l in r["text"] if l.y >= s["h"] - EPS]
                target = min(tops) if tops else r["text_h"]
            else:
                continue
            if n >= 1 and (0.3 < target - s["h"] or (s["mode"] == "full" and abs(target - s["h"]) > 0.3)) and (s["mode"] == "full" or target - s["h"] <= s["slh"] * 1.5):
                for l in s["col"]:
                    l.h = (target - s["th"]) / n
                s["h"] = target
        self.recompute_top(r)

    def justify(self, r):
        self.align_columns(r)
        spare = self.contentH - self.total_h(r)
        # no commentary on the page: open the text's line spacing to the bottom
        if not r["sections"] and not r["post"] and (not r["at_end"] or r.get("more")) and r["text"] and spare > 0:
            text = [l for l in r["text"] if l.kind == "p"]
            if text and (spare < self.main_lh * 1.5 or spare / len(text) <= self.main_lh * 0.16):
                for l in text:
                    l.h += spare / len(text)
                self.recompute_top(r)
        self.align_columns(r)
        self.recompute_top(r)
        spare = self.contentH - self.total_h(r)
        if spare < 0.5 or not r["sections"] or r["post"]:
            return
        secs = r["sections"]
        last = secs[-1]
        if not last["cut"]:
            rows = sum(math.ceil(len(s["lines"]) / self.comms[s["c"]]["cols"]) for s in secs)
            if rows and spare / rows < secs[0]["nlh"] * 0.25:
                for s in secs:
                    s["nlh"] += spare / rows
                    s["h"] = self.section_h(s["c"], len(s["lines"]), s["nlh"])
        else:
            rows = math.ceil(len(last["lines"]) / self.comms[last["c"]]["cols"])
            if rows:
                last["nlh"] += spare / rows
                last["h"] = self.section_h(last["c"], len(last["lines"]), last["nlh"])
        # still a little room: share it out between the lines of the text and of the commentaries
        spare = self.contentH - self.total_h(r)
        text = [l for l in r["text"] if l.kind == "p"]
        # the end of a haftara above the text shares in it too
        pre = r["pre"] if r["pre"] and "lines" in r["pre"] else None
        if pre:
            text += [l for l in pre["lines"] if l.kind == "p"]
        rows = sum(math.ceil(len(s["lines"]) / self.comms[s["c"]]["cols"]) for s in secs)
        units = len(text) + rows
        if spare > 0.5 and units and spare / units <= 0.35 * min([self.main_lh] + [s["nlh"] for s in secs]):
            d = spare / units
            for l in text:
                l.h += d
            if pre:
                pre["h"] = restack(pre["lines"])
            for s in secs:
                s["nlh"] += d
                s["h"] = self.section_h(s["c"], len(s["lines"]), s["nlh"])
            self.recompute_top(r)
            self.align_columns(r)

    # ------------------------------------------------------------ text without commentary

    def fill_plain(self, lst, a, budget):
        """Set as much plain text (a haftara) from position a as fits in budget, ending on
        a full line. Returns (lines, height, end position, done)."""
        n = len(lst)
        segs = self.segments(a, (n, 0), lst)
        specs = self.text_specs(segs, False)
        lines, h = layout_specs(specs, full_width(self.W))
        if h <= budget + EPS:
            return lines, h, (n, 0), True
        k = 0
        while k < len(lines) and lines[k].y + lines[k].h <= budget + EPS:
            k += 1
        while k > 0 and lines[k - 1].kind == "h":
            k -= 1
        if k == 0:
            return [], 0.0, a, False
        nxt = lines[k].words[0].ref
        end = (nxt[1], 0) if nxt[0] in ("h", "l") else nxt
        taken = lines[:k]
        taken[-1].last = False
        taken[-1].mb = 0.0
        h = restack(taken)
        return taken, h, end, False

    def spread_page(self, r):
        spare = self.contentH - self.total_h(r)
        text = [l for l in r["text"] if l.kind == "p"]
        post = [l for l in (r.get("post") or {}).get("lines", []) if l.kind == "p"]
        rows = sum(math.ceil(len(s["lines"]) / self.comms[s["c"]]["cols"]) for s in r["sections"])
        units = len(text) + len(post) + rows
        if spare < 0.5 or not units or spare / units > 0.3 * self.main_lh:
            return
        d = spare / units
        for l in text + post:
            l.h += d
        for s in r["sections"]:
            s["nlh"] += d
            s["h"] = self.section_h(s["c"], len(s["lines"]), s["nlh"])
        self.recompute_top(r)
        self.align_columns(r)
        if r.get("post"):
            r["post"]["h"] = restack(r["post"]["lines"])

    def stretch_lines(self, lines, spare, cap):
        n = len([l for l in lines if l.kind == "p"])
        if n and 0.5 < spare <= cap:
            for l in lines:
                if l.kind == "p":
                    l.h += spare / n
        return restack(lines)

    # ------------------------------------------------------------ the whole book

    def units(self, lst):
        off, t = [], 0
        for it in lst:
            off.append(t)
            t += len(it["words"]) if it["type"] == "v" else 1
        return off, t

    def to_pos(self, off, total, n, g):
        if g >= total:
            return (n, 0)
        lo, hi = 0, n - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if off[mid] <= g:
                lo = mid
            else:
                hi = mid - 1
        return (lo, g - off[lo])

    def set_items(self, lst):
        self.items = lst
        self.off, self.total = self.units(lst)
        vs = [it["idx"] for it in lst if it["type"] == "v"]
        last_v = vs[-1] if vs else None
        self.sec_end = {}
        for c, st in self.streams.items():
            k = 0
            while k < len(st) and last_v is not None and st[k]["v"] <= last_v:
                k += 1
            self.sec_end[c] = k

    def pos(self, g):
        return self.to_pos(self.off, self.total, len(self.items), g)

    def g_of(self, p):
        return self.total if p[0] >= len(self.items) else self.off[p[0]] + p[1]

    def text_height(self, a, g):
        b = self.pos(g)
        _, h = layout_specs(self.text_specs(self.segments(a, b), b[1] > 0), full_width(self.W))
        return h

    def full_line_end(self, r, g0, g):
        """If the text ends in the middle of a line, end it at the end of the line before."""
        if g >= self.total or not r["text"]:
            return g
        b = self.pos(g)
        nxt = self.items[b[0]]
        if b[1] == 0 and (self.P["verseNewLine"] or (b[0] > 0 and self.items[b[0] - 1]["type"] == "h")):
            return g
        if self.is_break(nxt):
            # the page ends with the end of a chapter: fine if its last line is well filled
            last = r["text"][-1]
            if last.kind != "p" or last.natural >= last.width * 0.6:
                return g
        last = r["text"][-1]
        if last.kind != "p":
            return g
        if nxt["type"] == "v":
            t, bold = nxt["words"][b[1]]
            st = self.main.with_bold(bold)
            nw = Word(t, st, width(st, t))
            if b[1] == 0 and self.P["numbers"]:
                bst = self.main.with_bold(True)
                nw.w += width(bst, nxt["label"]) + space(self.main)
            if not last.fits_more(nw):
                return g
        # a line that is nearly full is simply justified to the full width
        if last.natural >= last.width * 0.9:
            return g
        first = next((w.ref for w in last.words if isinstance(w.ref, tuple) and isinstance(w.ref[0], int)), None)
        if first is None:
            return g
        if last.words[0].ref and last.words[0].ref[0] in ("l", "h"):
            first = (last.words[0].ref[1], 0)
        g2 = self.g_of(first)
        return g2 if g2 > g0 else g

    def run(self):
        sections = []
        for it in self.all_items:
            if sections and sections[-1]["noComm"] == it["noComm"]:
                sections[-1]["items"].append(it)
            else:
                sections.append({"noComm": it["noComm"], "items": [it]})
        self.pages = []
        self.plain_start = (0, 0)
        self.pre = None
        for si, sec in enumerate(sections):
            nxt = sections[si + 1] if si + 1 < len(sections) else None
            if sec["noComm"]:
                self.run_plain(sec["items"], nxt)
                self.plain_start = (0, 0)
            else:
                after = sections[si + 2] if si + 2 < len(sections) else None
                self.comm_after_plain = bool(after and not after["noComm"])
                self.run_comm(sec["items"], nxt["items"] if nxt else None)
        pages = []
        first = int(self.P.get("firstPage") or 1)
        for n, (r, chapter, parasha) in enumerate(self.pages):
            pages.append(self.finalize(r, chapter, parasha, heb(first + n), n))
        if self.P.get("titlePage"):
            pages = self.title_pages(self.contents(pages, first)) + pages
        return pages

    def contents(self, pages, first):
        """(heading, page number, level) of the parashot and haftarot, for the table of
        contents — when the book has more than one parasha."""
        out = []
        for n, pg in enumerate(pages):
            for fr in pg.frames:
                for l in fr.lines:
                    if getattr(l, "kind", "") != "h":
                        continue
                    t = " ".join(w.text for w in l.words)
                    if t.startswith("פרשת"):
                        out.append((t, heb(first + n), 0))
                    elif t.startswith("הפטרת"):
                        out.append((t, heb(first + n), 1))
        if sum(1 for e in out if e[2] == 0) < 2 or not self.P.get("toc", True):
            return []
        return out

    def title_pages(self, contents=()):
        """The title page, and behind it the table of contents (or, in book form without one,
        a blank page, so that the text still begins on a left-hand page)."""
        from .titlepage import blank_page, title_page, toc_page, with_list
        P = self.P
        lines = []
        parashot = [it["text"] for it in self.all_items if it["type"] == "h" and not it["noComm"]
                    and re.match(r"^פרש(ת|ה)\s", it["text"])]
        if len(parashot) == 1 and parashot[0] != P["title"]:
            lines.append(parashot[0])
        sub = (P.get("titleSub") or "").strip()
        if not sub:
            names = []
            for c in self.comms:
                n = c["name"]
                names.append("תרגום " + n if n == "אונקלוס" else n)
            if any(it["noComm"] for it in self.all_items):
                names.append("הפטרות")
            sub = ("עם " + with_list(names)) if names else ""
        if sub:
            lines.append(sub)
        out = [title_page(self.page_w, self.page_h, self.m, P["mainFont"], P["title"] or "", lines, self.ded_lines)]
        if contents:
            # the back of the title page is a right-hand page: the binding is on its left
            out.append(toc_page(self.page_w, self.page_h, self.m, P["mainFont"], contents, self.gutter))
        elif P.get("bookMode"):
            out.append(blank_page(self.page_w, self.page_h))
        return out

    def tick(self):
        self.memo.clear()   # a new page: what was tried for the last one is no use
        if self.progress:
            self.progress(len(self.pages))

    def run_comm(self, lst, next_plain):
        self.set_items(lst)
        pre = self.pre
        self.pre = None
        pos = (0, 0)
        guard = 0

        def pending():
            return pos[0] < len(self.items) or any(not self.done(c, p) for c, p in self.ptrs.items())

        while pending() and guard < 5000:
            guard += 1
            self.tick()
            base = dict(self.col_w)
            best = self.search_page(pos, pre)
            # keep the translation in step with the text: widen the column a little on a
            # page where it falls behind, narrow it where it runs out
            if self.sides and not best["at_end"]:
                lag = self.page_lag(best)
                short = not best["col_full"]
                if lag > 1 or short:
                    sign = 1 if lag > 1 else -1
                    for step in (1.5, 3):
                        for c in self.sides:
                            top = AUTO_MAX if self.comms[c]["autoW"] else 60.0
                            self.col_w[c] = min(top, max(12.0, base[c] + sign * step))
                        cand = self.search_page(pos, pre)
                        lag2 = self.page_lag(cand)
                        ok = (cand["col_full"] or cand["at_end"]) and (cand["start_ok"] or not best["start_ok"])
                        if ok and (lag2 < lag or (short and sign < 0)):
                            best, lag, short = cand, lag2, False
                            best["col_w"] = dict(self.col_w)
                            if lag <= 1:
                                break
                    self.col_w = dict(best.get("col_w", base))
                if lag > 1:
                    # still behind: end the text on this page earlier, so that no more than one
                    # verse waits for its translation
                    best = self.shorten_for_lag(pos, pre, best)
            last = best["b"][0] >= len(self.items) and all(self.done(c, p) for c, p in best["ptrs"].items())
            if last and next_plain:
                budget = self.contentH - self.total_h(best) - self.sgap - 3 * PT_PER_MM
                lines, h, end, done = self.fill_plain(next_plain, self.plain_start, budget)
                if lines:
                    best["post"] = {"lines": lines, "h": h, "mt": self.sgap + 3 * PT_PER_MM, "items": next_plain}
                    self.plain_start = end
                    best["post"]["done"] = done
            # something follows on the next page (a haftara, the next parasha): no reason to
            # leave room at the bottom of this one
            best["more"] = not last or bool(next_plain)
            self.justify(best)
            if best.get("post") and not best["post"].get("done", True):
                # the haftara starts under the parasha and continues: fill the page to the bottom
                spare = self.contentH - self.total_h(best)
                best["post"]["h"] = self.stretch_lines(best["post"]["lines"], spare, self.main_lh * 3)
            best["col_w"] = dict(self.col_w)
            self.col_w = base
            first = self.items[min(pos[0], len(self.items) - 1)]
            chapter, parasha = first["chapter"], first["parasha"]
            if pre and pre.get("chapter") is not None:
                chapter, parasha = pre["chapter"], pre["parasha"]
            post = best.get("post")
            spare = self.contentH - self.total_h(best)
            if (last and post and post.get("done") and getattr(self, "comm_after_plain", False)
                    and spare > self.room_for_section()):
                # the haftara ends on this page too: the next parasha starts under it
                best["items"] = self.items
                self.pre = {"r": best, "h": self.total_h(best) - self.head_h, "chapter": chapter, "parasha": parasha}
                self.ptrs.update(best["ptrs"])
                break
            if last and post and post.get("done") and getattr(self, "comm_after_plain", False):
                # the next parasha doesn't fit under the haftara: spread the room over the
                # lines of the whole page (text, commentaries and haftara)
                self.spread_page(best)
            best["items"] = self.items
            self.pages.append((best, chapter, parasha))
            pre = None
            stuck = best["b"] == pos and all(best["ptrs"].get(c) == p for c, p in self.ptrs.items())
            self.ptrs.update(best["ptrs"])
            pos = best["b"]
            if stuck:
                self.warnings.append("חלק מהטקסט לא נכנס לעמוד (פסוק או פירוש ארוך מעמוד שלם). הקטינו את הגופן.")
                break

    def search_page(self, pos, pre):
        """The best page starting at pos, with the current column widths."""
        if pos[0] >= len(self.items):
            return self.compose(pos, pos, True, pre)
        g0 = self.g_of(pos)
        hi = min(self.total, g0 + 64)
        while hi < self.total and self.text_height(pos, hi) < self.contentH - self.head_h:
            hi = min(self.total, g0 + (hi - g0) * 2)
        lo, g = g0 + 1, 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.compose(pos, self.pos(mid), False, pre)["req_fit"]:
                g, lo = mid, mid + 1
            else:
                hi = mid - 1
        # wrapping the translation makes the fit only roughly monotone: look a little further
        if g:
            x, misses = g + 1, 0
            while x <= min(self.total, g + 60) and misses < 10:
                if self.compose(pos, self.pos(x), False, pre)["req_fit"]:
                    g, misses = x, 0
                else:
                    misses += 1
                x += 1
        if g:
            cur = self.compose(pos, self.pos(g), False, pre)
            if not cur["at_end"] and not self.can_close(cur, self.contentH - self.total_h(cur)):
                # the commentary of the next verse doesn't fit in full and the page would
                # have a hole: the text runs on, every commentary of its verses begins on
                # the page and what doesn't fit continues on the next one
                fill = self.start_fill(pos, g0, g, pre)
                if fill is not None:
                    g = fill
                elif self.text_height(pos, g) < self.min_text_h:
                    g = 0
        if not g:
            # the commentaries of the verses already set fill more than a page: a page of
            # commentary only, so they don't fall further behind their verses
            only = None
            if self.backlog(pos):
                only = self.compose(pos, pos, False, pre, comm_only=True)
                if only["sections"] and self.can_close(only, self.contentH - self.total_h(only)):
                    return only
            # a commentary longer than a page: the text runs to the end of its verse (so that
            # no later verse waits for its commentary), the commentaries begin under it
            k = pos[0]
            while k < len(self.items) - 1 and self.items[k]["type"] == "h":
                k += 1
            g = min(self.total, self.g_of((k + 1, 0)) if k + 1 < len(self.items) else self.total)
            g = max(g, g0 + 1)
            cand = self.compose(pos, self.pos(g), False, pre)
            if only is not None and only["sections"] and not cand["start_ok"]:
                return only
        best = self.compose(pos, self.pos(g), False, pre)
        # the translation runs out before the text ends: add text until it fills its column
        if self.sides and not best["col_full"] and not best["at_end"]:
            x = g + 1
            while x <= min(self.total, g + 400):
                r2 = self.compose(pos, self.pos(x), False, pre)
                if not r2["top_fits"] or not r2["start_ok"]:
                    break
                if r2["col_full"] or r2["at_end"]:
                    g, best = x, r2
                    break
                x += 1
            if not best["col_full"]:
                # it can't run on (a commentary would not begin on the page): a little less
                # text, so that the translation ends with it, if the page stays full
                for x in range(g - 1, max(g0, g - 80), -1):
                    r2 = self.compose(pos, self.pos(x), False, pre)
                    if r2["col_full"] and r2["start_ok"] and self.can_close(r2, self.contentH - self.total_h(r2)):
                        g, best = x, r2
                        break
        best, g = self.end_on_full_line(pos, g0, g, best, pre)
        hole = self.contentH - self.total_h(best)
        if not best["at_end"] and best["sections"] and not self.can_close(best, hole):
            best = self.fill_hole(pos, g0, g, pre) or best
        text = [l for l in best["text"] if l.kind == "p"]
        hole = self.contentH - self.total_h(best)
        if (not best["at_end"] and not best["sections"] and text and hole > 1.5 * self.main_lh
                and hole / len(text) > 0.16 * self.main_lh):
            # no commentary to fill the page and the translation can't go on: rather the
            # text running on under the translation column than a hole
            near = None
            for x in range(min(self.total, g + 80), g, -1):
                q = self.compose(pos, self.pos(x), False, pre)
                if not (q["req_fit"] and q["top_fits"] and self.contentH - self.total_h(q) < 1.5 * self.main_lh):
                    continue
                if self.full_line_end(q, g0, x) == x:
                    best = q
                    break
                if near is None and self.pos(x)[1] == 0:
                    near = q        # failing a full line: the end of a verse
            else:
                if near is not None:
                    best = near
        return best

    def fill_hole(self, pos, g0, g, pre):
        """The commentary of the next verse is too long for the room left under the text,
        which would leave a hole: run the text on to a full line and let the commentaries
        fill the page and continue on the next one."""
        for x in range(g + 1, min(self.total, g + 80) + 1):
            r = self.compose(pos, self.pos(x), False, pre)
            if not r["top_fits"]:
                break
            if r["at_end"] or not r["start_ok"] or (self.sides and not r["col_full"]) or self.full_line_end(r, g0, x) != x:
                continue
            spare = self.contentH - self.total_h(r)
            if -EPS <= spare and self.can_close(r, spare):
                return r
        return None

    def backlog(self, pos):
        """Whether commentary is still owed to verses that end before pos."""
        last = -1
        for i in range(min(pos[0], len(self.items)) - 1, -1, -1):
            if self.items[i]["type"] == "v":
                last = self.items[i]["idx"]
                break
        return last >= 0 and any(self.list_from(c, self.ptrs[c], last) for c in self.bottoms)

    def start_fill(self, pos, g0, g, pre):
        """The least text after g with which every commentary of the page's verses begins
        on it and the page is full, preferring an end on a full line."""
        first = None
        for x in range(g + 1, min(self.total, g + 80) + 1):
            q = self.compose(pos, self.pos(x), False, pre)
            if not q["top_fits"] or not q["start_ok"]:
                break
            if not self.can_close(q, self.contentH - self.total_h(q)):
                continue
            if first is None:
                first = x
            if self.full_line_end(q, g0, x) == x:
                return x
        return first

    def shorten_for_lag(self, pos, pre, best):
        g0, g = self.g_of(pos), self.g_of(best["b"])
        x = g - 1
        while x > g0 and g - x <= 250:
            r = self.compose(pos, self.pos(x), False, pre)
            closes = lambda q: self.can_close(q, self.contentH - self.total_h(q))
            if (r["col_full"] or r["at_end"]) and self.page_lag(r) <= 1:
                if self.text_h_ok(r) and closes(r):
                    r2, x2 = self.end_on_full_line(pos, g0, x, r, pre)
                    if self.page_lag(r2) <= 1 and (r2["col_full"] or r2["at_end"]) and closes(r2):
                        r2["col_w"] = best.get("col_w")
                        return r2
                    r["col_w"] = best.get("col_w")
                    return r
            x -= 1
        return best

    def text_h_ok(self, r):
        return r["text_h"] >= self.min_text_h or r["at_end"]

    def page_lag(self, r):
        """How many verses completed on the page still wait for (the end of) their translation."""
        b = r["b"]
        last_text = -1
        for i in range(min(b[0], len(self.items)) - 1, -1, -1):
            if self.items[i]["type"] == "v":
                last_text = self.items[i]["idx"]
                break
        lag = 0
        for c in self.sides:
            st = self.streams[c]
            e, w = r["ptrs"].get(c, self.ptrs[c])
            done_v = st[e - 1]["v"] if e > 0 else -1
            behind = len({x["v"] for x in st[e:] if x["v"] <= last_text})
            lag = max(lag, behind)
        return lag

    def end_on_full_line(self, pos, g0, g, best, pre):
        """End the text on a full line: run on to the end of the line if the page allows it,
        otherwise end at the end of the line before."""
        if best["at_end"] or not best["text"] or best["text"][-1].kind != "p":
            return best, g
        g2 = self.full_line_end(best, g0, g)
        end = self.pos(g2)
        heading_alone = end[1] == 0 and end[0] - 1 > pos[0] and self.items[end[0] - 1]["type"] == "h"
        if heading_alone:
            g2 = self.off[end[0] - 1]
            while g2 > g0 + 1 and self.items[self.pos(g2 - 1)[0]]["type"] == "h":
                g2 -= 1
        if g2 == g:
            return best, g
        # try finishing the line instead
        n_lines = len(best["text"])
        ext, gx = None, g
        x = g + 1
        while x <= min(self.total, g + 40):
            r2 = self.compose(pos, self.pos(x), False, pre)
            if not r2["top_fits"] or not r2["start_ok"] or len(r2["text"]) != n_lines or (
                    self.sides and not r2["col_full"] and not r2["at_end"]):
                break
            if self.total_h(r2) > self.contentH + EPS and not r2["sections"]:
                break
            ext, gx = r2, x
            if r2["at_end"]:
                break
            x += 1
        if ext is not None and not heading_alone and self.full_line_end(ext, g0, gx) == gx:
            return ext, gx
        alt = self.compose(pos, self.pos(g2), False, pre)
        if (not self.sides or alt["col_full"]) and (not best["req_fit"] or self.can_close(alt, self.total_h(best) - self.total_h(alt))):
            return alt, g2
        return best, g

    def run_plain(self, lst, next_sec):
        off, total = self.units(lst)
        guard = 0
        while (total if self.plain_start[0] >= len(lst) else off[self.plain_start[0]] + self.plain_start[1]) < total and guard < 5000:
            guard += 1
            self.tick()
            budget = self.contentH - self.head_h
            frm = self.plain_start
            lines, h, end, done = self.fill_plain(lst, frm, budget)
            if not lines:
                break
            self.plain_start = end
            it = lst[min(frm[0], len(lst) - 1)]
            spare = budget - h
            if done and next_sec and not next_sec["noComm"] and spare > self.room_for_section():
                # the commented text continues under the end of the haftara on this page
                self.pre = {"lines": lines, "h": h, "chapter": it["chapter"], "parasha": it["parasha"], "items": lst}
                break
            if not done or next_sec:
                n_lines = len([l for l in lines if l.kind == "p"])
                h = self.stretch_lines(lines, spare, max(self.main_lh * 3, n_lines * self.main_lh * 0.3))
            r = {"a": frm, "b": end, "at_end": True, "pre": None, "ptrs": {}, "side": {}, "sections": [],
                 "post": {"lines": lines, "h": h, "mt": 0.0, "items": lst}, "text": [], "text_h": 0.0, "top_h": 0.0}
            self.pages.append((r, it["chapter"], it["parasha"]))

    # ------------------------------------------------------------ to absolute coordinates

    def room_for_section(self):
        """The least room under a haftara for the next parasha to start on the same page:
        the gap, its heading and the minimum lines of text."""
        return self.sgap + 3 * PT_PER_MM + self.main_lh * 1.5 + self.min_text_h

    def place_body(self, r, page, y):
        """Put a page's content (everything under the running head) on page from y down."""
        if r.get("col_w"):
            self.col_w = dict(r["col_w"])
        L, R = self.m + self.gutter, self.page_w - self.m     # the text area (the binding margin on the left)
        pre = r.get("pre")
        if pre and "r" in pre:
            y = self.place_body(pre["r"], page, y) + self.sgap + 3 * PT_PER_MM
            if r.get("col_w"):
                self.col_w = dict(r["col_w"])
            pre = None
        if pre:
            restack(pre["lines"])
            page.frames.append(Frame(pre["lines"], R, y, ("main", pre.get("items"))))
            y += pre["h"] + self.sgap + 3 * PT_PER_MM
        if r["text"] or r["side"]:
            page.frames.append(Frame(r["text"], R, y, ("main", r.get("items"))))
            off_r = off_l = 0.0
            for c in self.sides:
                s = r["side"].get(c)
                if not s:
                    continue
                cw = self.side_width(c)
                if s["col"]:
                    lines = []
                    if s["th"]:
                        tst = self.style[c].scaled(1.05, bold=True)
                        t = break_lines(words_of([(w, True) for w in self.comms[c]["name"].split()], tst), tst, s["th"], full_width(cw), 0.0, "center")
                        lines += t[:1]
                    yy = s["th"]
                    for l in s["col"]:
                        l.y = yy
                        yy += l.h
                        l.right, l.width = 0.0, cw
                    lines += s["col"]
                    if r.get("side_dir", {}).get(c, self.comms[c]["side"]) == "right":
                        x = R - off_r
                        off_r += cw + self.gap
                    else:
                        x = L + off_l + cw
                        off_l += cw + self.gap
                    page.frames.append(Frame(lines, x, y, ("comm", c)))
            band_y = y + max([r["text_h"]] + [s["h"] for s in r["side"].values()])
            for c in self.sides:
                s = r["side"].get(c)
                if s and s["band"]:
                    band_y += 1 * PT_PER_MM
                    yy = 0.0
                    for l in s["band"]:
                        l.y = yy
                        yy += l.h
                    page.frames.append(Frame(s["band"], R, band_y, ("comm", c)))
                    band_y += yy
            y += r["top_h"]
        if r["sections"]:
            y += self.sgap
            for n, s in enumerate(r["sections"]):
                if n:
                    y += 1.2 * PT_PER_MM
                c = s["c"]
                y0 = y + self.note_pad()
                th = self.note_title_h(c)
                if th:
                    tst = self.style[c].scaled(1.1, bold=True)
                    t = break_lines(words_of([(w, True) for w in self.comms[c]["name"].split()], tst), tst, th, full_width(self.W), 0.0, "center")
                    page.frames.append(Frame(t[:1], R, y0))
                cols = self.comms[c]["cols"]
                cw = self.note_col_w(c)
                rows = math.ceil(len(s["lines"]) / cols)
                for k in range(cols):
                    chunk = s["lines"][k * rows:(k + 1) * rows]
                    for j, l in enumerate(chunk):
                        l.y = j * s["nlh"]
                        l.h = s["nlh"]
                    if chunk:
                        page.frames.append(Frame(chunk, R - k * (cw + self.gap), y0 + th, ("comm", c)))
                y += s["h"]
        if r.get("post"):
            y += r["post"]["mt"]
            restack(r["post"]["lines"])
            page.frames.append(Frame(r["post"]["lines"], R, y, ("main", r["post"].get("items"))))
            y += r["post"]["h"]
        return y

    @property
    def contentH(self):
        """The height of the page's body; the first page leaves room for the dedication."""
        index = getattr(self, "finalizing", None)
        if index is None:
            index = len(getattr(self, "pages", []))
        return self.body_h - (self.ded_h if index == 0 and not self.P.get("titlePage") else 0.0)

    def finalize(self, r, chapter, parasha, number, index=0):
        if r.get("col_w"):
            self.col_w = dict(r["col_w"])
        P = self.P
        L, R, T = self.m + self.gutter, self.page_w - self.m, self.m
        page = Page(self.page_w, self.page_h)
        y = T
        if P["header"]:
            title = P["title"]
            right = f"{title} · {parasha}" if parasha and title else (parasha or title)
            center = chapter if chapter and chapter != parasha else ""
            hs = self.head_style
            if P.get("bookMode") and index % 2 == 1:
                # a right-hand page: the page number goes on its outer side, the right
                right, number = number, right
            page.head = (right, center, number, hs, y + 9.0 * 1.3 * 0.8)
            ry = y + 9.0 * 1.3 + 1 * PT_PER_MM
            page.rules.append((L, ry, R))
            y += self.head_h
        self.finalizing = index
        y = self.place_body(r, page, y)
        page.overfull = y - T > self.contentH + 1
        if index == 0 and self.ded_lines and not P.get("titlePage"):
            st = self.ded_style
            lines = []
            for k, text in enumerate(self.ded_lines):
                ws = words_of([(w, False) for w in text.split()], st)
                ln = break_lines(ws, st, self.ded_lh, full_width(self.W), k * self.ded_lh, "center")
                for l in ln:
                    l.last = True
                lines.extend(ln)
            page.frames.append(Frame(lines, R, T + self.body_h - len(self.ded_lines) * self.ded_lh))
        self.finalizing = None
        page.links = self.links(page)
        if self.gutter and index % 2 == 0:
            # a left-hand page: its inner side, the binding, is on the right
            for fr in page.frames:
                fr.x_right -= self.gutter
            page.rules = [(x1 - self.gutter, y, x2 - self.gutter) for x1, y, x2 in page.rules]
            page.links = [(x1 - self.gutter, y1, x2 - self.gutter, y2, to) for x1, y1, x2, y2, to in page.links]
        return page

    def links(self, page):
        """Where a click on each line of the page leads: (x1, y1, x2, y2, target), target
        ('main', line number) or ('comm', commentary, verse, passage)."""
        out = []
        for fr in page.frames:
            if not fr.src:
                continue
            for l in fr.lines:
                to = None
                for w in l.words:
                    ref = w.ref
                    if not isinstance(ref, tuple) or len(ref) != 2:
                        continue
                    if fr.src[0] == "main":
                        items = fr.src[1]
                        i = ref[1] if ref[0] in ("l", "h") else ref[0]
                        if items and isinstance(i, int) and 0 <= i < len(items) and "line" in items[i]:
                            to = ("main", items[i]["line"])
                            break
                    else:
                        c = fr.src[1]
                        j = ref[1] if ref[0] == "L" else ref[0]
                        st = self.streams.get(c, [])
                        if isinstance(j, int) and 0 <= j < len(st):
                            e = st[j]
                            to = ("comm", c, e["v"], e.get("p", 0))
                            break
                if to:
                    right = fr.x_right - l.right
                    top = fr.top + l.y
                    out.append((right - l.width, top, right, top + l.h, to))
        return out


def layout_project(project, progress=None):
    """Lay out a whole project. Returns (pages, warnings)."""
    eng = Engine(project, progress)
    pages = eng.run()
    return pages, eng.warnings
