"""Pesakei HaRosh and the Rif with the Ran (or the commentary that is printed around
the Rif in its place), one book per masechet: first the Rosh, then the Rif with the
commentary on both sides of it, and a daily division of the whole Shas into 354 days.

  * The Rosh is set in two columns; each day begins at the start of a siman.
  * The Rif is set in the middle of the page and the commentary in two columns on its
    sides. Where the commentary is longer than the Rif on the page it runs on under it
    (each column widens to half the page); where it is shorter, the Rif widens under it.
    The commentary of a passage of the Rif is on the page where the passage ends; only
    the passage that continues on the next page takes its commentary with it, and when
    the commentary owed fills more than a page, a page of commentary only follows.
    Each day begins at the start of a passage (after the Rif's colon).
  * In the Rosh, what he quotes from the Rif is bold; in the commentary, what it quotes
    from Rashi is bold (beside the dibbur hamatchil, which is always bold).
  * Every page says in its head where the same place is in the other half of the book.
"""
import html
import os
import re
from dataclasses import dataclass

from .engine import Frame, Page
from .model import heb
from .textlayout import PT_PER_MM, Line, Style, Word, break_lines, full_width, space, width

EPS = 0.01
NIKUD = re.compile("[֑-ׇ]")
FINALS = str.maketrans("ךםןףץ", "כמנפצ")


# ---------------------------------------------------------------- reading the texts

def norm(w):
    return re.sub(r"[^א-ת]", "", NIKUD.sub("", w)).translate(FINALS)


def tokens(line, bold_tags=True):
    """An Otzaria line -> [(word, bold)]: <b>/<strong> are bold, other tags go."""
    s = re.sub(r"<i [^>]*>\s*</i>", "", line)
    s = s.replace("&nbsp;", " ").replace("&thinsp;", " ")
    if bold_tags:
        s = re.sub(r"<(b|strong)>", " \x01 ", s)
        s = re.sub(r"</(b|strong)>", " \x02 ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    out, bold = [], False
    for w in s.split():
        if w == "\x01":
            bold = True
        elif w == "\x02":
            bold = False
        else:
            out.append([w, bold])
    return out


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read().replace("\r", "").split("\n")


def gem_daf(label):
    """'(דף ב ע"א)' or 'ב.' -> a sortable number (amud)."""
    m = re.search(r"([א-ת]+)\s*(?:ע\"([אב])|([.:]))", label)
    if not m:
        return None
    n = sum({"א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5, "ו": 6, "ז": 7, "ח": 8, "ט": 9, "י": 10, "כ": 20, "ל": 30,
             "מ": 40, "נ": 50, "ס": 60, "ע": 70, "פ": 80, "צ": 90, "ק": 100, "ר": 200, "ש": 300, "ת": 400}.get(c, 0)
            for c in m.group(1))
    side = 1 if (m.group(2) == "ב" or m.group(3) == ":") else 0
    return n * 2 + side


def parse_rosh(lines):
    """-> [{'perek': name, 'num': siman letter, 'paras': [tokens]}]"""
    simanim, perek = [], ""
    for l in lines[1:]:
        m = re.match(r"\s*<h2>(.*?)</h2>", l)
        if m:
            perek = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            continue
        m = re.match(r"\s*<h3>(?:הלכה|סימן)\s*(\S+)\s*</h3>", l)
        if m:
            simanim.append({"perek": perek, "num": m.group(1), "paras": []})
            continue
        if l.startswith("<h") or not simanim:
            continue
        t = tokens(l)
        if t and re.match(r"^\(\S{1,3}\)$", t[0][0]):
            t = t[1:]
        if t and not simanim[-1]["paras"] and t[0][0] == simanim[-1]["num"]:
            t = t[1:]
        if t:
            simanim[-1]["paras"].append(t)
    return simanim


def parse_rif(lines):
    """-> [{'tokens', 'daf' (Rif page label at the start), 'dafs': [(word index, label)]}]"""
    paras, daf, pending = [], None, None
    for l in lines[1:]:
        m = re.match(r"\s*<h2>\s*דף\s*(.*?)\s*</h2>", l)
        if m:
            daf = m.group(1)
            pending = daf
            continue
        if l.startswith("<h") or not l.strip() or daf is None:
            continue
        t = tokens(l)
        if not t:
            continue
        prev = paras[-1] if paras else None
        if pending and prev and not re.search(r"[:.]\)?$", prev["tokens"][-1][0]):
            prev["dafs"].append((len(prev["tokens"]), daf))
            prev["tokens"].extend(t)
        else:
            paras.append({"tokens": t, "daf": daf, "dafs": [(0, daf)]})
        pending = None
    return paras


def parse_comm(lines):
    """A commentary on the Rif, by the Rif's pages -> [{'daf', 'tokens'}]"""
    out, daf = [], None
    for l in lines[1:]:
        m = re.match(r"\s*<h2>\s*דף\s*(.*?)\s*</h2>", l)
        if m:
            daf = m.group(1)
            continue
        if l.startswith("<h") or not l.strip() or daf is None:
            continue
        t = tokens(l)
        if t:
            out.append({"daf": daf, "tokens": t})
    return out


# ---------------------------------------------------------------- quotations

def grams(words, n):
    seq = [w for w in (norm(x) for x in words) if w]
    return {tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)}


def mark_quotes(toks, ref, excl, n=4, min_run=6):
    """Make bold the runs of words (min_run or more) of toks that come from ref and not
    from excl (sets of n-grams)."""
    idx = [i for i, t in enumerate(toks) if norm(t[0])]
    seq = [norm(toks[i][0]) for i in idx]
    hit = [False] * len(seq)
    for k in range(len(seq) - n + 1):
        g = tuple(seq[k:k + n])
        if g in ref and g not in excl:
            for j in range(k, k + n):
                hit[j] = True
    k = 0
    count = 0
    while k < len(seq):
        if hit[k]:
            e = k
            while e < len(seq) and hit[e]:
                e += 1
            if e - k >= min_run:
                for j in range(k, e):
                    toks[idx[j]][1] = True
                    count += 1
            k = e
        else:
            k += 1
    return count


def loose(w):
    """A word for finding quotations: without vav and yod, so that full and defective
    spellings match."""
    return re.sub("[וי]", "", norm(w)).replace("מ", "נ") if norm(w) else ""


def loose_grams(words, n):
    seq = [w for w in (loose(x) for x in words) if w]
    return {tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)}


def mark_attributed(toks, ref, is_marker, window=25, n=3, min_run=3, mark_name=True):
    """Make bold what follows a mention of the quoted author (is_marker(word)): the runs,
    within window words after the mention, that are found in ref (loose n-grams)."""
    idx = [i for i, t in enumerate(toks) if loose(t[0])]
    seq = [loose(toks[i][0]) for i in idx]
    count = 0
    for k, i in enumerate(idx):
        if not is_marker(toks[i][0]):
            continue
        if mark_name:
            toks[i][1] = True
            # "ז"ל" after the name goes with it
            if k + 1 < len(idx) and norm(toks[idx[k + 1]][0]) in ("זל", "זצל"):
                toks[idx[k + 1]][1] = True
        # the quotation: from the name to the last run found in ref
        end, q = None, k + 1
        while q < min(len(seq) - n + 1, k + 1 + window):
            e = q
            while e < len(seq) - n + 1 and tuple(seq[e:e + n]) in ref:
                e += 1
            if e - q + n - 1 >= min_run and e > q:
                if end is not None and q - end > 6:
                    break
                end = e + n - 1
                q = e
            else:
                q += 1
        if end is not None:
            for j in range(k + 1, min(end, len(seq))):
                if not toks[idx[j]][1]:
                    count += 1
                toks[idx[j]][1] = True
    return count


def rif_marker(w):
    n = norm(w)
    return n.endswith("ריפ") or "אלפס" in n


def rashi_marker(w):
    n = norm(w)
    return n in ("רשי", "ורשי", "לרשי", "שרשי", "פרשי", "ופרשי", "פירשי", "ופירשי", "שפרשי", "כפרשי", "וכפרשי", "דרשי")


# ---------------------------------------------------------------- linking

def link_comm(comm, rif):
    """Attach each commentary entry to the passage of the Rif it explains: within the
    entry's page of the Rif, the passage where its dibbur hamatchil is found."""
    by_daf = {}
    for j, p in enumerate(rif):
        for _, d in p["dafs"]:
            by_daf.setdefault(d, []).append(j)
    texts = [[norm(w) for w, _ in p["tokens"]] for p in rif]
    last = 0
    for e in comm:
        dh = [norm(w) for w, b in e["tokens"][:12] if b]
        dh = [w for w in dh if w and w not in ("וכו", "כו", "גמ", "מתני", "וגו", "רן", "פי")][:4]
        cands = [j for j in by_daf.get(e["daf"], []) if j >= last] or by_daf.get(e["daf"], [])
        best = None
        for k in (len(dh), 3, 2, 1):
            if k > len(dh) or k == 0:
                continue
            pat = dh[:k]
            for j in cands:
                t = texts[j]
                if any(t[i:i + k] == pat for i in range(len(t) - k + 1)):
                    best = j
                    break
            if best is not None:
                break
        if best is None:
            best = cands[0] if cands else last
        best = max(best, last)
        e["para"] = best
        last = best


def align(rosh, rif, n=3):
    """For every siman of the Rosh, the passage of the Rif with the same material
    (monotonic, by the words they share)."""
    rg = [grams([w for p in s["paras"] for w, _ in p], n) for s in rosh]
    fg = [grams([w for w, _ in p["tokens"]], n) for p in rif]
    S, P = len(rg), len(fg)
    if not P:
        return [0] * S
    score = [[len(a & b) for b in fg] for a in rg]
    dp = [[0.0] * P for _ in range(S)]
    back = [[0] * P for _ in range(S)]
    for i in range(S):
        best, arg = -1.0, 0
        for j in range(P):
            prev = 0.0
            if i:
                if dp[i - 1][j] > best:
                    best, arg = dp[i - 1][j], j
                prev = best
            dp[i][j] = score[i][j] + prev
            back[i][j] = arg
    j = max(range(P), key=lambda x: dp[S - 1][x])
    out = [0] * S
    for i in range(S - 1, -1, -1):
        out[i] = j
        j = back[i][j]
    # where the siman's material begins in the Rif: the first passage after the previous
    # siman's that shares a good part of what the best one does
    for i in range(S):
        lo = out[i - 1] + 1 if i else 0
        best = score[i][out[i]]
        for j in range(min(lo, out[i]), out[i]):
            if best and score[i][j] >= 0.3 * best and score[i][j] >= 3:
                out[i] = j
                break
    return out


# ---------------------------------------------------------------- units of text

@dataclass
class Unit:
    kind: str          # p: paragraph, h: heading, d: day marker
    words: list        # [Word]
    ref: object = None  # siman / passage index
    first: bool = True  # first paragraph of its siman / passage


class Book:
    def __init__(self, name, rosh, rif, comm, comm_name, page=(210, 297), margin=14, rosh_size=12, rif_size=12.5,
                 comm_size=9.3):
        self.name = name
        self.rosh, self.rif, self.comm, self.comm_name = rosh, rif, comm, comm_name
        self.pw, self.ph = page[0] * PT_PER_MM, page[1] * PT_PER_MM
        self.m = margin * PT_PER_MM
        self.W = self.pw - 2 * self.m
        self.head_h = 9 * 1.3 + 5 * PT_PER_MM
        self.H = self.ph - 2 * self.m - self.head_h
        self.gap = 5 * PT_PER_MM
        self.vgap = 2.5 * PT_PER_MM
        self.st_rosh = Style("Frank Ruhl Libre", rosh_size)
        self.st_rif = Style("Frank Ruhl Libre", rif_size)
        self.st_comm = Style("Noto Rashi Hebrew", comm_size)
        self.lh_rosh = rosh_size * 1.45
        self.lh_rif = rif_size * 1.5
        self.lh_comm = comm_size * 1.42
        self.head_style = Style("Frank Ruhl Libre", 9)
        self.cw = self.W * 0.25            # a commentary column beside the Rif
        self.wide = (self.W - self.gap) / 2  # a commentary column under it

    # -------------------------------------------------- words
    def words(self, toks, st):
        b = st.with_bold(True)
        return [Word(w, b if bold else st, width(b if bold else st, w)) for w, bold in toks]

    def marker(self, day, st):
        s = Style(st.family, st.size * 1.25, True)
        t = f"יום {heb(day)}"
        return Unit("d", [Word(t, s, width(s, t))])

    def heading(self, text, st):
        s = Style(st.family, st.size * 1.3, True)
        return Unit("h", [Word(w, s, width(s, w)) for w in text.split()])

    def rosh_units(self, day_at):
        """day_at: siman index -> day number starting there."""
        units, perek = [], None
        for i, s in enumerate(self.rosh):
            if i in day_at:
                units.append(self.marker(day_at[i], self.st_rosh))
            if s["perek"] != perek:
                perek = s["perek"]
                units.append(self.heading(perek, self.st_rosh))
            for k, p in enumerate(s["paras"]):
                toks = ([[f"[{s['num']}]", True]] if k == 0 else []) + p
                units.append(Unit("p", self.words(toks, self.st_rosh), i, k == 0))
        return units

    def rif_units(self, day_at):
        units = []
        for j, p in enumerate(self.rif):
            if j in day_at:
                units.append(self.marker(day_at[j], self.st_rif))
            units.append(Unit("p", self.words(p["tokens"], self.st_rif), j))
        return units

    # -------------------------------------------------- the Rosh: two columns
    def lines_of(self, units, w, st, lh):
        out = []
        for u in units:
            if u.kind == "p":
                ls = break_lines(u.words, st, lh, full_width(w))
            else:
                hl = lh * 1.35
                ls = break_lines(u.words, u.words[0].style, hl, full_width(w), 0.0, "center")
                for l in ls:
                    l.last = True
            for l in ls:
                l.unit = u
            out.extend(ls)
        return out

    def layout_rosh(self, units):
        colw = (self.W - self.gap) / 2
        lines = self.lines_of(units, colw, self.st_rosh, self.lh_rosh)
        pages, i, n = [], 0, len(lines)
        while i < n:
            cols = []
            for _ in range(2):
                col, h = [], 0.0
                while i < n and h + lines[i].h <= self.H + EPS:
                    col.append(lines[i])
                    h += lines[i].h
                    i += 1
                # no heading or day marker alone at the bottom of a column
                while col and col[-1].unit.kind != "p" and i < n:
                    i -= 1
                    col.pop()
                cols.append(col)
            last = i >= n
            for col in cols:
                tot = sum(l.h for l in col)
                spare = self.H - tot
                if col and not last and 0 < spare < self.lh_rosh * 2.5:
                    for l in col:
                        l.h += spare / len(col)
                y = 0.0
                for l in col:
                    l.y = y
                    y += l.h
            pages.append({"kind": "rosh", "cols": cols, "colw": colw})
        return pages

    # -------------------------------------------------- the Rif with the commentary around it
    def rif_flow(self, units):
        """The Rif as a list of words with positions, for cutting pages anywhere."""
        self.units = units
        self.off, t = [], 0
        for u in units:
            self.off.append(t)
            t += len(u.words)
        self.total = t
        # the commentary as one run of words, entry after entry
        self.cwords, self.c_end_of_para = [], {}
        for e in self.comm:
            ws = self.words(e["tokens"], self.st_comm)
            self.cwords.extend(ws)
            self.c_end_of_para[e["para"]] = len(self.cwords)

    def c_upto(self, para):
        """How many commentary words belong to passages up to para (inclusive)."""
        best = 0
        for p, end in self.c_end_of_para.items():
            if p <= para and end > best:
                best = end
        return best

    def unit_at(self, g):
        lo, hi = 0, len(self.off) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.off[mid] <= g:
                lo = mid
            else:
                hi = mid - 1
        return lo

    def text_lines(self, a, b, width_at):
        """Lines of the Rif words a..b laid out with width_at(y)."""
        out, y = [], 0.0
        u0, u1 = self.unit_at(a), self.unit_at(max(a, b - 1))
        for k in range(u0, u1 + 1):
            u = self.units[k]
            s = max(a, self.off[k]) - self.off[k]
            e = min(b, self.off[k] + len(u.words)) - self.off[k]
            ws = u.words[s:e]
            if not ws:
                continue
            if u.kind == "p":
                ls = break_lines(ws, self.st_rif, self.lh_rif, width_at, y)
                if e < len(u.words):
                    ls[-1].last = False
                    ls[-1].cut = True
            else:
                ls = break_lines(ws, ws[0].style, self.lh_rif * 1.35, width_at, y, "center")
            for l in ls:
                l.unit = u
            out.extend(ls)
            y = out[-1].y + out[-1].h
        return out, y

    def take_cols(self, words, width_at, H):
        """Fill the right column and then the left one; width_at(y) -> (right, width)."""
        cols, i, n = [], 0, len(words)
        sp = space(self.st_comm)
        for _ in range(2):
            col, y = [], 0.0
            while i < n and y + self.lh_comm <= H + EPS:
                right, w = width_at(y)
                cur, nat, j = [words[i]], words[i].w, i + 1
                while j < n and nat + sp + words[j].w <= w + 0.01:
                    nat += sp + words[j].w
                    cur.append(words[j])
                    j += 1
                col.append(Line(cur, right, w, nat, self.lh_comm, self.st_comm, "justify", j >= n, y))
                y += self.lh_comm
                i = j
            cols.append(col)
        return cols, i

    def compose(self, a, b, cptr, comm_only=False):
        Wt = self.W - 2 * (self.cw + self.gap)
        narrow = lambda y: (self.cw + self.gap, Wt)
        r = {"a": a, "b": b, "cptr": cptr, "at_end": b >= self.total}
        if b > a and not comm_only:
            last_unit = self.unit_at(b - 1)
            u = self.units[last_unit]
            done_unit = last_unit if self.off[last_unit] + len(u.words) <= b else last_unit - 1
            started = [x.ref for x in self.units[:last_unit + 1] if x.kind == "p"]
            completed = [x.ref for x in self.units[:done_unit + 1] if x.kind == "p"]
            avail = self.c_upto(started[-1]) if started else cptr
            req = self.c_upto(completed[-1]) if completed else cptr
        else:
            avail = req = cptr
            back = [x.ref for x in self.units[:self.unit_at(a) if a < self.total else len(self.units)] if x.kind == "p"]
            if a < self.total and self.off[self.unit_at(a)] < a:
                back = back[:-1]
            avail = req = max(cptr, self.c_upto(back[-1]) if back else cptr)
        if r["at_end"]:
            avail = req = len(self.cwords)
        avail, req = max(avail, cptr), max(req, cptr)
        cws = self.cwords[cptr:avail]
        if comm_only or b <= a:
            text, th = [], 0.0
        else:
            text, th = self.text_lines(a, b, narrow)
        lim = th + self.vgap if th else 0.0
        wide_r = lambda y: (0.0, self.cw if y < lim else self.wide)
        cols, n = self.take_cols(cws, wide_r, self.H)
        mode = "long"
        total = self.H
        if n >= len(cws):
            hcol = max((len(c) for c in cols), default=0) * self.lh_comm
            # the commentary is shorter: can it stay beside the Rif?
            lo_rows = 0
            hi_rows = int(self.H // self.lh_comm)
            fits_beside = None
            for rows in range(0, hi_rows + 1):
                h = rows * self.lh_comm
                if th and h > th + EPS:
                    break
                cs, k = self.take_cols(cws, lambda y: (0.0, self.cw), h)
                if k >= len(cws):
                    fits_beside = (cs, h)
                    break
            if fits_beside is not None and text:
                cols, hc = fits_beside
                mode = "short"
                lim2 = hc + self.vgap if hc else 0.0
                wa = (lambda y: (self.cw + self.gap, Wt) if y < lim2 else (0.0, self.W)) if hc else full_width(self.W)
                text, th = self.text_lines(a, b, wa)
                total = th
                r["hc"] = hc
            else:
                # under the Rif, as far down as it goes: balance the two columns
                best = (cols, hcol)
                for rows in range(1, int(self.H // self.lh_comm) + 1):
                    h = rows * self.lh_comm
                    cs, k = self.take_cols(cws, wide_r, h)
                    if k >= len(cws):
                        best = (cs, h)
                        break
                cols, total = best
                total = max(total, th)
                mode = "under"
        if mode == "long" and text and (th > self.H + EPS or cptr + n < req):
            # the Rif doesn't fit narrow (or the commentary owed doesn't fit around it): keep
            # the commentary owed beside the Rif and let the Rif widen under it; the
            # commentary of the passage that goes on follows it to the next page
            alt = self.short_layout(a, b, self.cwords[cptr:req], th)
            if alt is not None:
                cols, hc, text, th2 = alt
                r.update(text=text, th=th2, cols=cols, n=req - cptr, mode="short", total=th2, req=req, avail=avail,
                         hc=hc)
                r["cnext"] = req
                r["fits"] = th2 <= self.H + EPS
                return r
        r.update(text=text, th=th, cols=cols, n=n if mode == "long" else len(cws), mode=mode, total=total,
                 req=req, avail=avail)
        r["cnext"] = cptr + r["n"]
        r["fits"] = total <= self.H + EPS and th <= self.H + EPS and cptr + r["n"] >= req
        return r

    def short_layout(self, a, b, cws, th):
        """The commentary cws in two columns beside the Rif, as short as they go, and the
        Rif widening under them. -> (cols, hc, text lines, text height) or None."""
        Wt = self.W - 2 * (self.cw + self.gap)
        for rows in range(0, int(self.H // self.lh_comm) + 1):
            h = rows * self.lh_comm
            if h > min(th, self.H) + EPS:
                return None
            cs, k = self.take_cols(cws, lambda y: (0.0, self.cw), h)
            if k >= len(cws):
                lim = h + self.vgap if h else 0.0
                wa = (lambda y: (self.cw + self.gap, Wt) if y < lim else (0.0, self.W)) if h else full_width(self.W)
                text, t = self.text_lines(a, b, wa)
                return cs, h, text, t
        return None

    def backlog(self, a, cptr):
        if a <= 0:
            return False
        k = self.unit_at(a - 1)
        u = self.units[k]
        if self.off[k] + len(u.words) > a:
            k -= 1
        refs = [x.ref for x in self.units[:k + 1] if x.kind == "p"]
        return bool(refs) and self.c_upto(refs[-1]) > cptr

    def layout_rif(self, units):
        self.rif_flow(units)
        pages, a, cptr, guard = [], 0, 0, 0
        min_text = 3 * self.lh_rif
        while (a < self.total or cptr < len(self.cwords)) and guard < 3000:
            guard += 1
            if a >= self.total:
                r = self.compose(a, a, cptr, comm_only=True)
                if r["n"] == 0:
                    break
                pages.append(self.finish(r))
                cptr = r["cnext"]
                continue
            lo, hi, g = a + 1, min(self.total, a + 800), 0
            while lo <= hi:
                mid = (lo + hi) // 2
                if self.compose(a, mid, cptr)["fits"]:
                    g, lo = mid, mid + 1
                else:
                    hi = mid - 1
            if g:
                x, miss = g + 1, 0
                while x <= min(self.total, g + 40) and miss < 8:
                    if self.compose(a, x, cptr)["fits"]:
                        g, miss = x, 0
                    else:
                        miss += 1
                    x += 1
            r = self.compose(a, g, cptr) if g else None
            if r is None or r["th"] < min_text and not r["at_end"]:
                if self.backlog(a, cptr):
                    r2 = self.compose(a, a, cptr, comm_only=True)
                    if r2["n"]:
                        pages.append(self.finish(r2))
                        cptr = r2["cnext"]
                        continue
                # a commentary longer than a page: a few lines of the Rif, the rest runs on
                x = a + 1
                while x < self.total and self.text_lines(a, x, lambda y: (0, self.W - 2 * (self.cw + self.gap)))[1] < min_text:
                    x += 1
                r = self.compose(a, x, cptr)
                r["cnext"] = cptr + r["n"]
            if r["mode"] == "short" and not r["at_end"] and self.H - r["total"] > 1.5 * self.lh_rif:
                # the Rif widened under a short commentary and still leaves a hole: rather a
                # little less of the Rif, with the commentary filling the page around it
                x = r["b"] - 1
                while x > a + 1:
                    q = self.compose(a, x, cptr)
                    if q["fits"] and q["mode"] == "long" and q["th"] >= min_text:
                        r = q
                        break
                    x -= 3
            r = self.end_on_line(r)
            pages.append(self.finish(r))
            a, cptr = r["b"], r["cnext"]
        return pages

    def end_on_line(self, r):
        """End the Rif on a full line when the page stays full without the last line."""
        t = r["text"]
        if r["at_end"] or not t or not getattr(t[-1], "cut", False):
            return r
        last = t[-1]
        if last.natural >= last.width * 0.9 or len(t) < 2:
            return r
        b2 = r["b"] - len(last.words)
        if b2 <= r["a"]:
            return r
        r2 = self.compose(r["a"], b2, r["cptr"])
        if r2["fits"] and (r2["mode"] == "long" or self.H - r2["total"] < self.lh_rif * 1.5):
            return r2
        return r

    def finish(self, r):
        """Stretch the lines so that every column and the text reach the bottom."""
        def stretch(lines, target, cap):
            if not lines:
                return
            h = sum(l.h for l in lines)
            spare = target - h
            if 0 < spare <= cap:
                for l in lines:
                    l.h += spare / len(lines)
            y = lines[0].y if lines else 0.0
            for l in lines:
                l.y = y
                y += l.h

        last = r["at_end"] and r["cnext"] >= len(self.cwords)
        if r["mode"] == "long":
            for c in r["cols"]:
                stretch(c, self.H, self.lh_comm * 1.5)
        elif r["mode"] == "short":
            hc = r.get("hc", 0.0)
            for c in r["cols"]:
                stretch(c, hc, self.lh_comm * 1.5)
            if not last:
                stretch(r["text"], self.H, self.lh_rif * 0.25 * max(1, len(r["text"])))
        else:
            for c in r["cols"]:
                stretch(c, r["total"] if last else self.H, self.lh_comm * 0.3 * max(1, len(c)))
        r["kind"] = "rif"
        return r

    # -------------------------------------------------- pages
    def render(self, rosh_pages, rif_pages, xref, title_rosh, title_rif, first=1):
        out = []
        allp = rosh_pages + rif_pages
        for n, pg in enumerate(allp):
            page = Page(self.pw, self.ph)
            L, R, T = self.m, self.pw - self.m, self.m
            right = f"{self.name} · {title_rosh if pg['kind'] == 'rosh' else title_rif}"
            center = xref[n]
            num = heb(first + n)
            if n % 2 == 1:
                right, num = num, right
            page.head = (right, center, num, self.head_style, T + 9.0 * 1.3 * 0.8)
            page.rules.append((L, T + 9.0 * 1.3 + 1 * PT_PER_MM, R))
            top = T + self.head_h
            if pg["kind"] == "rosh":
                for k, col in enumerate(pg["cols"]):
                    if col:
                        page.frames.append(Frame(col, R - k * (pg["colw"] + self.gap), top))
            else:
                if pg["text"]:
                    page.frames.append(Frame(pg["text"], R, top))
                cols = pg["cols"]
                if cols and cols[0]:
                    page.frames.append(Frame(cols[0], R, top))
                if len(cols) > 1 and cols[1]:
                    # the left column: lines beside the Rif sit at its left edge
                    for l in cols[1]:
                        l.right = (self.wide - l.width) if l.width < self.wide - 0.5 else 0.0
                    page.frames.append(Frame(cols[1], L + self.wide, top))
            out.append(page)
        return out


# ---------------------------------------------------------------- the whole Shas

MASECHTOT = ["ברכות", "שבת", "עירובין", "פסחים", "יומא", "סוכה", "ביצה", "ראש השנה", "תענית", "מגילה", "מועד קטן",
             "יבמות", "כתובות", "נדרים", "גיטין", "קידושין", "בבא קמא", "בבא מציעא", "בבא בתרא", "סנהדרין", "מכות",
             "שבועות", "עבודה זרה", "מנחות", "חולין", "בכורות", "נידה"]
DAYS = 354


def find_file(root, *names):
    for name in names:
        for base, _, files in os.walk(root):
            if name in files:
                return os.path.join(base, name)
    return None


def sources(root, m):
    """The files of masechet m under the Otzaria library folder root."""
    rish = os.path.join(root, "אוצריא", "תלמוד בבלי", "ראשונים")
    comm, comm_name = None, ""
    for fname, nm in ((f"רן על {m}.txt", 'ר"ן'), (f"נימוקי יוסף על {m}.txt", "נימוקי יוסף"),
                      (f"רבינו יונה על {m}.txt", "רבינו יונה")):
        p = find_file(os.path.join(rish, "ריף", "מפרשים"), fname)
        if p:
            comm, comm_name = p, nm
            break
    gem = [find_file(os.path.join(root, "אוצריא", "תלמוד בבלי"), f"{m}.txt"),
           find_file(os.path.join(root, "OraytaToOtzaria"), f"{m}.txt")]
    rashi = [find_file(os.path.join(rish, "רשי"), f"רשי על {m}.txt"),
             find_file(os.path.join(root, "OraytaToOtzaria"), f"תלמוד בבלי - {m} - רשי.txt")]
    return {
        "rosh": find_file(os.path.join(rish, "ראש"), f"פסקי הראש על {m}.txt"),
        "rif": find_file(os.path.join(rish, "ריף"), f"ריף {m}.txt", f"הלכות קטנות לריף ({m}).txt"),
        "comm": comm, "comm_name": comm_name,
        "gemara": [p for p in gem if p], "rashi": [p for p in rashi if p],
    }


def count_words(path):
    if not path:
        return 0
    with open(path, encoding="utf-8") as f:
        return len(re.sub(r"<[^>]+>", " ", f.read()).split())


def day_plan(root):
    """How many days each masechet gets (of DAYS, by the length of its texts), and the
    number of its first day."""
    w = {}
    for m in MASECHTOT:
        s = sources(root, m)
        w[m] = count_words(s["rosh"]) + count_words(s["rif"]) + count_words(s["comm"])
    tot = sum(w.values())
    raw = {m: DAYS * w[m] / tot for m in MASECHTOT}
    days = {m: max(1, int(raw[m])) for m in MASECHTOT}
    left = DAYS - sum(days.values())
    for m in sorted(MASECHTOT, key=lambda x: raw[x] - int(raw[x]), reverse=True)[:max(0, left)]:
        days[m] += 1
    first, n = {}, 1
    for m in MASECHTOT:
        first[m] = n
        n += days[m]
    return days, first


def load_masechet(root, m):
    s = sources(root, m)
    rosh = parse_rosh(read(s["rosh"])) if s["rosh"] else []
    rif = parse_rif(read(s["rif"])) if s["rif"] else []
    comm = parse_comm(read(s["comm"])) if s["comm"] else []
    report = []
    if rif:
        ref = loose_grams([w for p in rif for w, _ in p["tokens"]], 3)
        n = sum(mark_attributed(t, ref, rif_marker) for x in rosh for t in x["paras"])
        report.append(f"ברא\"ש הודגשו {n} מילים מהרי\"ף")
    if comm:
        rsh = set()
        for p in s["rashi"]:
            rsh |= loose_grams(re.sub(r"<[^>]+>", " ", " ".join(read(p))).replace("''", '"').split(), 3)
        n = sum(mark_attributed(e["tokens"], rsh, rashi_marker) for e in comm)
        report.append(f"ב{s['comm_name']} הודגשו {n} מילים מרש\"י")
        link_comm(comm, rif)
    return rosh, rif, comm, s["comm_name"], report


def day_starts(rosh, rif, comm, ndays, al):
    """Where each day begins: (siman index, passage index) pairs, the Rosh at the start of a
    siman and the Rif at the start of a passage, both about the same place."""
    rw = [sum(len(p) for p in s["paras"]) for s in rosh]
    fw = [len(p["tokens"]) for p in rif]
    cw = [0] * len(rif)
    for e in comm:
        cw[e["para"]] += len(e["tokens"])
    total = sum(rw) + sum(fw) + sum(cw)
    cum_r = [0]
    for x in rw:
        cum_r.append(cum_r[-1] + x)
    cum_f = [0]
    for j in range(len(rif)):
        cum_f.append(cum_f[-1] + fw[j] + cw[j])
    starts = [(0, 0)]
    for d in range(1, ndays):
        target = total * d / ndays
        best = None
        for k in range(starts[-1][0] + 1, len(rosh)):
            j = al[k] if rif else 0
            if rif and j <= starts[-1][1]:
                continue
            w = cum_r[k] + (cum_f[j] if rif else 0)
            if best is None or abs(w - target) < abs(best[0] - target):
                best = (w, k, j)
        if best is None:
            break
        starts.append((best[1], best[2]))
    return starts


def build_masechet(root, m, first_day, ndays, page=(210, 297)):
    rosh, rif, comm, comm_name, report = load_masechet(root, m)
    al = align(rosh, rif) if rif and rosh else [0] * len(rosh)
    starts = day_starts(rosh, rif, comm, ndays, al)
    rosh_days = {k: first_day + d for d, (k, _) in enumerate(starts)}
    rif_days = {j: first_day + d for d, (_, j) in enumerate(starts)} if rif else {}
    book = Book(m, rosh, rif, comm, comm_name, page)
    rosh_pages = book.layout_rosh(book.rosh_units(rosh_days)) if rosh else []
    rif_pages = book.layout_rif(book.rif_units(rif_days)) if rif else []
    # where each siman and each passage begins (book page index)
    siman_page, para_page = {}, {}
    for n, pg in enumerate(rosh_pages):
        for col in pg["cols"]:
            for l in col:
                u = l.unit
                if u.kind == "p" and u.first and u.ref not in siman_page:
                    siman_page[u.ref] = n
    off = len(rosh_pages)
    for n, pg in enumerate(rif_pages):
        for l in pg["text"]:
            if l.unit.kind == "p" and l.unit.ref not in para_page:
                para_page[l.unit.ref] = off + n
    xref = []
    for n, pg in enumerate(rosh_pages):
        refs = [l.unit.ref for col in pg["cols"] for l in col if l.unit.kind == "p"]
        perek = rosh[refs[0]]["perek"] if refs else ""
        s = refs[0] if refs else None
        target = para_page.get(al[s]) if (s is not None and rif) else None
        xref.append(f"{perek}" + (f" · ברי\"ף עמ' {heb(target + 1)}" if target is not None else ""))
    for n, pg in enumerate(rif_pages):
        refs = [l.unit.ref for l in pg["text"] if l.unit.kind == "p"]
        if refs:
            j = refs[0]
            daf = rif[j]["daf"]
            ks = [i for i in range(len(rosh)) if al[i] <= j]
            target = siman_page.get(ks[-1]) if ks else None
            xref.append(f"דף {daf}" + (f" · ברא\"ש עמ' {heb(target + 1)}" if target is not None else ""))
        else:
            xref.append(comm_name)
    title_rif = f"רי\"ף ו{comm_name}" if comm_name else "רי\"ף"
    pages = book.render(rosh_pages, rif_pages, xref, "פסקי הרא\"ש", title_rif)
    report.append(f"{m}: {len(rosh_pages)} עמודי רא\"ש, {len(rif_pages)} עמודי רי\"ף, ימים {heb(first_day)}–{heb(first_day + len(starts) - 1)}")
    return pages, report
