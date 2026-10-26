"""Measuring words and breaking them into lines.

All sizes are in points. Text is measured on a 72-dpi reference device, so one font
point is one unit everywhere: in the layout, in the PDF and in the preview.
Lines are right-to-left: each line knows its right edge and width, and its words are
drawn from the right.
"""
import os
import re
from dataclasses import dataclass, field

from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF, QImage

PT_PER_MM = 72 / 25.4

_ref = None
_qfonts = {}
_metrics = {}
_widths = {}


def load_bundled_fonts(folder):
    """Register the fonts that ship with the program (Frank Ruhl, Rashi script, …)."""
    families = set()
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith((".ttf", ".otf")):
                fid = QFontDatabase.addApplicationFont(os.path.join(folder, name))
                families.update(QFontDatabase.applicationFontFamilies(fid))
    return sorted(families)


def ref_device():
    global _ref
    if _ref is None:
        _ref = QImage(4, 4, QImage.Format_ARGB32)
        dpm = round(72 / 0.0254)
        _ref.setDotsPerMeterX(dpm)
        _ref.setDotsPerMeterY(dpm)
    return _ref


@dataclass(frozen=True)
class Style:
    family: str
    size: float
    bold: bool = False

    def with_bold(self, bold=True):
        return Style(self.family, self.size, bold)

    def scaled(self, k, bold=None):
        return Style(self.family, round(self.size * k, 3), self.bold if bold is None else bold)


def qfont(st):
    f = _qfonts.get(st)
    if f is None:
        f = QFont(st.family)
        f.setPointSizeF(st.size)
        f.setBold(st.bold)
        f.setHintingPreference(QFont.PreferNoHinting)
        f.setKerning(True)
        _qfonts[st] = f
    return f


def metrics(st):
    m = _metrics.get(st)
    if m is None:
        m = QFontMetricsF(qfont(st), ref_device())
        _metrics[st] = m
    return m


def width(st, text):
    key = (st, text)
    w = _widths.get(key)
    if w is None:
        w = metrics(st).horizontalAdvance(text)
        _widths[key] = w
    return w


def space(st):
    return width(st, " ")


@dataclass
class Word:
    text: str
    style: Style
    w: float
    ref: object = None  # where the word comes from (for following positions in the text)
    glue: bool = False  # never the last word of a line (it belongs with the word after it)
    join: bool = False  # ends with a maqaf: no space after it (a line may still end with it)


MAQAF = "\u05be"


def words_of(tokens, base, ref=None, maqaf=False):
    """[(text, bold)] -> [Word] in style base (bold where marked). maqaf: a word joined by
    maqaf is set as its parts (the maqaf ending each but the last, with no space after it),
    so that a line may end after a maqaf; the parts keep the word's ref."""
    out = []
    bold = base.with_bold(True)
    for i, (t, b) in enumerate(tokens):
        st = bold if b else base
        r = ref(i) if ref else None
        parts = [t]
        if maqaf and MAQAF in t.strip(MAQAF):
            parts = [x for x in re.split("(?<=" + MAQAF + ")", t) if x]
        for k, part in enumerate(parts):
            out.append(Word(part, st, width(st, part), r, join=k < len(parts) - 1))
    return out


def split_maqaf(words):
    """The words with each maqaf-joined word as its parts (see words_of), keeping refs."""
    out = []
    for w in words:
        if w.join or MAQAF not in w.text.strip(MAQAF):
            out.append(w)
            continue
        parts = [x for x in re.split("(?<=" + MAQAF + ")", w.text) if x]
        for k, part in enumerate(parts):
            out.append(Word(part, w.style, width(w.style, part), w.ref, w.glue if k == len(parts) - 1 else False,
                            join=k < len(parts) - 1))
    return out


def gap_after(w, sp):
    return 0.0 if w.join else sp


@dataclass
class Line:
    words: list
    right: float      # right edge, measured from the frame's right side (RTL)
    width: float      # width available for the line
    natural: float    # width of the words with normal spaces
    h: float          # line height
    base: Style       # style that sets the spacing and baseline
    align: str = "justify"   # justify | right | center
    last: bool = False       # last line of its paragraph (not stretched unless cut)
    y: float = 0.0

    def fits_more(self, word):
        return self.natural + space(self.base) + word.w <= self.width + 0.01


def break_lines(words, base, lh, width_at, y0=0.0, align="justify", tight=1.0):
    """Greedy line breaking. width_at(y) -> (right offset, width) lets lines beside a
    column be narrower than the lines under it. tight < 1 lets the spaces between the
    words shrink a little."""
    lines = []
    sp = space(base) * tight
    i, n, y = 0, len(words), y0
    while i < n:
        right, w = width_at(y)
        cur = [words[i]]
        nat = words[i].w
        j = i + 1
        while j < n and nat + gap_after(words[j - 1], sp) + words[j].w <= w + 0.01:
            nat += gap_after(words[j - 1], sp) + words[j].w
            cur.append(words[j])
            j += 1
        while j < n and len(cur) > 1 and cur[-1].glue:
            # a word that belongs with the next one goes down with it
            j -= 1
            w_ = cur.pop()
            nat -= gap_after(cur[-1], sp) + w_.w
        lines.append(Line(cur, right, w, nat, lh, base, align, j >= n, y))
        y += lh
        i = j
    return lines


def full_width(w):
    return lambda y: (0.0, w)


def balance_lines(words, base, lh, w, min_ratio=0.6):
    """Break words into the same number of lines as greedy breaking at width w would,
    but spread them evenly, so that every line, the last one too, can be justified to
    the full width (the spaces open a little instead of leaving a short last line)."""
    lines = break_lines(words, base, lh, full_width(w))
    n = len(lines)
    if n < 2:
        for l in lines:
            l.last, l.force = False, True
        return lines
    best = lines
    lo, hi = w * min_ratio, w
    for _ in range(14):
        mid = (lo + hi) / 2
        ls = break_lines(words, base, lh, full_width(mid))
        if len(ls) == n:
            best, hi = ls, mid
        else:
            lo = mid
    for l in best:
        l.width, l.right = w, 0.0
        l.force = True
    best[-1].last = False
    return best


def even_lines(lines, slack=10):
    """Break the words of a paragraph's lines again so that their spaces come out as even as
    possible (the Knuth-Plass method of TeX: the whole paragraph at once, not line by line),
    keeping the number of lines and each line's place and width, so that nothing else on the
    page moves. lines: consecutive lines of one paragraph, all justified. The last line may
    stay short if it ends the paragraph (its .last is set); otherwise it is justified too.
    Each break is looked for within slack words of where line-by-line breaking put it.
    Returns True if the lines were changed."""
    n_lines = len(lines)
    if n_lines < 2 or any(l.align != "justify" for l in lines):
        return False
    words = [w for l in lines for w in l.words]
    n = len(words)
    s = space(lines[0].base)
    pre = [0.0]
    joins = [0]                      # joins[k]: maqaf joins among the first k words
    for w in words:
        pre.append(pre[-1] + w.w)
        joins.append(joins[-1] + (1 if w.join else 0))
    starts = []
    k = 0
    for l in lines:
        starts.append(k)
        k += len(l.words)
    free_last = lines[-1].last
    INF = float("inf")
    # spaces already even (no line wider than twice a normal space): nothing to do
    worst = 0.0
    for k, l in enumerate(lines):
        g = sum(1 for w in l.words[:-1] if not w.join)
        if k == n_lines - 1 and free_last or g < 1:
            continue
        worst = max(worst, (l.width - sum(w.w for w in l.words)) / (g * s))
    if worst <= 2.0:
        return False

    def cost(i, j, line_no):
        """Words i..j-1 on line line_no."""
        m = j - i
        if m <= 0:
            return INF
        total = pre[j] - pre[i]
        gaps = (m - 1) - (joins[j - 1] - joins[i])      # spaces between the words of the line
        width_ = lines[line_no].width
        if line_no == n_lines - 1 and free_last:
            return 0.0 if total + gaps * s * 0.85 <= width_ + 0.01 else INF
        if gaps <= 0:
            return 1e4 if total <= width_ + 0.01 else INF
        r = (width_ - total) / (gaps * s)
        if r < 0.85:
            return INF
        c = (r - 1) ** 2 * 100 if r >= 1 else (1 - r) ** 2 * 400
        if r > 3:
            c += (r - 3) ** 2 * 1000
        return c

    # best[k][j]: the least cost of lines 0..k-1 holding words 0..j-1 (line k begins at j)
    best = [dict() for _ in range(n_lines + 1)]
    back = [dict() for _ in range(n_lines + 1)]
    best[0][0] = 0.0
    for line_no in range(n_lines):
        nxt = starts[line_no + 1] if line_no + 1 < n_lines else n
        if line_no + 1 == n_lines:
            ends = [n]
        else:
            ends = range(max(1, nxt - slack), min(n - 1, nxt + slack) + 1)
        for i, ci in best[line_no].items():
            for j in ends:
                if j <= i or (j < n and words[j - 1].glue):
                    continue
                c = ci + cost(i, j, line_no)
                if c < best[line_no + 1].get(j, INF):
                    best[line_no + 1][j] = c
                    back[line_no + 1][j] = i
    if n not in best[n_lines]:
        return False
    old = sum(cost(starts[k], starts[k + 1] if k + 1 < n_lines else n, k) for k in range(n_lines))
    if best[n_lines][n] >= old - 0.5:
        return False
    cuts = [n]
    j = n
    for line_no in range(n_lines, 0, -1):
        j = back[line_no][j]
        cuts.append(j)
    cuts.reverse()
    for k, l in enumerate(lines):
        ws = words[cuts[k]:cuts[k + 1]]
        l.words = ws
        l.natural = sum(w.w for w in ws) + sum(gap_after(w, s) for w in ws[:-1])
    return True
