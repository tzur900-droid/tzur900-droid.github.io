"""Measuring words and breaking them into lines.

All sizes are in points. Text is measured on a 72-dpi reference device, so one font
point is one unit everywhere: in the layout, in the PDF and in the preview.
Lines are right-to-left: each line knows its right edge and width, and its words are
drawn from the right.
"""
import os
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


def words_of(tokens, base, ref=None):
    """[(text, bold)] -> [Word] in style base (bold where marked)."""
    out = []
    bold = base.with_bold(True)
    for i, (t, b) in enumerate(tokens):
        st = bold if b else base
        out.append(Word(t, st, width(st, t), ref(i) if ref else None))
    return out


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
        while j < n and nat + sp + words[j].w <= w + 0.01:
            nat += sp + words[j].w
            cur.append(words[j])
            j += 1
        while j < n and len(cur) > 1 and cur[-1].glue:
            # a word that belongs with the next one goes down with it
            j -= 1
            nat -= sp + cur.pop().w
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
