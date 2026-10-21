"""A cover for a book: gold on dark leather, with an ornamented frame, a gate (arch) over
the title and a cartouche with a verse; a spine; a back cover; and the same front drawn in
black on white as the title page inside the book.

Everything is drawn with lines and paths (no images), so it prints sharp at any size.
"""
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QLinearGradient, QPainterPath, QPen,
                           QRadialGradient, QTransform)

from .textlayout import PT_PER_MM, ref_device

TITLE_FONT = "Frank Ruhl Libre"
TEXT_FONT = "David Libre"

LEATHER = ("#5c151b", "#3b0c11", "#1f0508")
GOLD = ("#7a5a17", "#e9cf7a", "#a8802a", "#f6e5a3", "#8c6a1e", "#d9b964", "#7a5a17")
INK = "#1a1a1a"

TORAH = {"בראשית", "שמות", "ויקרא", "במדבר", "דברים"}
SILVER = ("#6f7378", "#e6e9ec", "#9da2a8", "#f7f8f9", "#80858b", "#cfd3d7", "#6f7378")

# The covers, each a different design (layout), from the heaviest to the lightest:
#   gate      — leather, an ornate frame and an arch over the title (the classic sefer)
#   medallion — leather, a frame with corners and the title in a great oval
#   label     — cloth with gilt raised bands, the title on a panel of parchment
#   rays      — leather, rays of gold from above and a band across with the title (Art Deco)
#   split     — two fields of colour, the title on the upper, the rest on the lower
#   band      — light paper with a broad band of colour down the spine side
#   letter    — the first letter of the book, huge and faint, behind the title
#   stars     — a night sky full of stars
#   arch      — light paper with one tall arch of colour, the title in it (modern)
#   field     — sky, sun and green hills, light and plain (as on the books of Breslov)
# bg: (material, colours) — leather, cloth or paper. ink: gold, silver or a colour; ink2: the
# colour of a second field (the panel of the label, the lower field of split…).
STYLES = [
    dict(name="שער מעוטר", layout="gate", bg=("leather", LEATHER), ink="gold"),
    dict(name="מדליון", layout="medallion", bg=("leather", ("#2b2a28", "#171615", "#060605")), ink="gold"),
    dict(name="תווית קלף", layout="label", bg=("cloth", ("#2f4f84", "#223b64", "#152846")), ink="gold",
         panel="#efe3c4", ink2="#5a1418"),
    dict(name="קרני זהב", layout="rays", bg=("leather", ("#1f4a33", "#133222", "#07190f")), ink="gold"),
    dict(name="שני שדות", layout="split", bg=("paper", ("#f5eedd", "#ebe0c6")), ink="#f5eedd",
         field="#6b1a1f", ink2="#6b1a1f"),
    dict(name="פס צבע", layout="band", bg=("paper", ("#ffffff", "#f1f1ee")), ink="#14305e", field="#14305e"),
    dict(name="אות גדולה", layout="letter", bg=("leather", ("#45484d", "#2c2e32", "#141517")), ink="silver"),
    dict(name="שמי לילה", layout="stars", bg=("paper", ("#070f26", "#1d356b")), ink="gold"),
    dict(name="קשת מודרנית", layout="arch", bg=("paper", ("#f6f1e7", "#ece3d1")), ink="#f6f1e7",
         field="#1f5c58", ink2="#1f5c58"),
    dict(name="ברסלב", layout="field", bg=("paper", ("#ffffff", "#bcdcf5")), ink="#123a7a", title_font=TEXT_FONT),
]


def style_of(n):
    """Style number n (from 1), or the first."""
    return STYLES[n - 1] if isinstance(n, int) and 1 <= n <= len(STYLES) else STYLES[0]


def book_info(project):
    """The words of the cover from the project: its book and its translations and commentaries."""
    title = (project.get("title") or "").strip()
    names = [c["name"] for c in project.get("comms", [])]
    side = [c["name"] for c in project.get("comms", []) if c["place"] == "side"]
    bases, parts = [], {}
    for n in names:
        if n in side:
            continue
        base, _, part = n.partition(" - ")
        base = base.strip()
        if base not in bases:
            bases.append(base)
        if part:
            parts.setdefault(base, []).append(part.strip())
    lines = []
    if side:
        lines.append("עם " + " ו".join(f"תרגום {s}" if "תרגום" not in s else s for s in side))
    if bases:
        lines.append(("ו" if side else "עם ") + "פירוש " + " ו".join(bases))
    details = []
    for b in bases:
        for p in parts.get(b, []):
            details.append(p)
    haftara = "הפטרת" in project.get("main", "")
    return {
        "top": "חמשה חומשי תורה" if title in TORAH else "",
        "title": f"חומש {title}" if title in TORAH else title,
        "lines": lines,
        "details": " · ".join(d for d in details if d),
        "extra": ("הפטרות עם פירוש " + " ו".join(bases)) if haftara and bases else ("והפטרות" if haftara else ""),
        "verse": "תּוֹרָה צִוָּה לָנוּ מֹשֶׁה מוֹרָשָׁה קְהִלַּת יַעֲקֹב",
        "back": "עֵץ חַיִּים הִיא לַמַּחֲזִיקִים בָּהּ וְתֹמְכֶיהָ מְאֻשָּׁר",
    }


# ---------------------------------------------------------------- materials

def gold(rect):
    g = QLinearGradient(rect.topLeft(), rect.bottomRight())
    for k, c in enumerate(GOLD):
        g.setColorAt(k / (len(GOLD) - 1), QColor(c))
    return QBrush(g)


def metal(rect, stops):
    g = QLinearGradient(rect.topLeft(), rect.bottomRight())
    for k, c in enumerate(stops):
        g.setColorAt(k / (len(stops) - 1), QColor(c))
    return QBrush(g)


class Ink:
    """What the ornaments and letters are drawn with: gold or silver (pressed into the
    cover, with a shadow), or a plain colour. ground: the colour under them, for the
    squares the rosettes of the frame sit in."""

    def __init__(self, rect, gilt, style=None):
        style = style or STYLES[0]
        kind = style["ink"] if gilt else INK
        self.gilt = gilt and kind in ("gold", "silver")
        if kind == "gold":
            self.brush = gold(rect)
        elif kind == "silver":
            self.brush = metal(rect, SILVER)
        else:
            self.brush = QBrush(QColor(kind))
        material, colours = style["bg"]
        self.ground = QColor(colours[1] if material != "paper" else colours[0]) if gilt else QColor("white")

    def pen(self, w):
        pen = QPen(self.brush, w)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen


def background(p, rect, style, seed=7):
    material, colours = style["bg"]
    if material == "leather":
        leather(p, rect, seed, colours)
    elif material == "cloth":
        cloth(p, rect, colours)
    else:
        g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        g.setColorAt(0.0, QColor(colours[0]))
        g.setColorAt(1.0, QColor(colours[1]))
        p.fillRect(rect, QBrush(g))


def cloth(p, rect, colours):
    """Book cloth: an even colour, a little lighter in the middle, with a fine weave."""
    g = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.8)
    for k, c in enumerate(colours):
        g.setColorAt(k / (len(colours) - 1), QColor(c))
    p.fillRect(rect, QBrush(g))
    pen = QPen(QColor(255, 255, 255, 6), 0.3)
    p.setPen(pen)
    y = rect.top()
    while y < rect.bottom():
        p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        y += 0.9
    p.setPen(QPen(QColor(0, 0, 0, 8), 0.3))
    x = rect.left()
    while x < rect.right():
        p.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        x += 0.9


def leather(p, rect, seed=7, colours=LEATHER):
    g = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.75)
    g.setColorAt(0.0, QColor(colours[0]))
    g.setColorAt(0.6, QColor(colours[1]))
    g.setColorAt(1.0, QColor(colours[2]))
    p.fillRect(rect, QBrush(g))
    # the grain of the leather: fine specks, a little lighter and a little darker
    rnd = random.Random(seed)
    p.setPen(Qt.NoPen)
    n = int(rect.width() * rect.height() / 60)
    for _ in range(n):
        x = rect.left() + rnd.random() * rect.width()
        y = rect.top() + rnd.random() * rect.height()
        r = 0.25 + rnd.random() * 0.7
        light = rnd.random() < 0.5
        p.setBrush(QColor(255, 220, 200, 10) if light else QColor(0, 0, 0, 22))
        p.drawEllipse(QPointF(x, y), r, r)


# ---------------------------------------------------------------- text

def qf(family, size, bold=True):
    f = QFont(family)
    f.setPointSizeF(size)
    f.setBold(bold)
    return f


def text_width(font, text):
    return QFontMetricsF(font, ref_device()).horizontalAdvance(text)


def fit_font(family, size, text, max_w, bold=True):
    f = qf(family, size, bold)
    w = text_width(f, text)
    if w > max_w:
        f = qf(family, size * max_w / w, bold)
    return f


def draw_text(p, ink, text, font, cx, baseline, emboss=True):
    """Text centred on cx. Gilt letters get a dark shadow under them, as if pressed into
    the leather."""
    path = QPainterPath()
    path.addText(QPointF(0, 0), font, text)
    br = path.boundingRect()
    path.translate(cx - br.center().x(), baseline)
    p.setPen(Qt.NoPen)
    if ink.gilt and emboss:
        shadow = QPainterPath(path)
        shadow.translate(0.6, 0.8)
        p.setBrush(QColor(0, 0, 0, 150))
        p.drawPath(shadow)
    p.setBrush(ink.brush)
    p.drawPath(path)
    return br.height()


# ---------------------------------------------------------------- ornaments

def rosette(p, ink, c, r, petals=8):
    path = QPainterPath()
    for k in range(petals):
        a = 2 * math.pi * k / petals
        tip = QPointF(c.x() + r * math.cos(a), c.y() + r * math.sin(a))
        l = QPointF(c.x() + r * 0.45 * math.cos(a - 0.5), c.y() + r * 0.45 * math.sin(a - 0.5))
        rr = QPointF(c.x() + r * 0.45 * math.cos(a + 0.5), c.y() + r * 0.45 * math.sin(a + 0.5))
        path.moveTo(c)
        path.quadTo(l, tip)
        path.quadTo(rr, c)
    p.setPen(ink.pen(0.5))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.setPen(Qt.NoPen)
    p.setBrush(ink.brush)
    p.drawEllipse(c, r * 0.18, r * 0.18)
    p.setPen(ink.pen(0.6))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(c, r * 1.08, r * 1.08)


def lozenge_band(p, ink, a, b, size, step):
    """A row of small lozenges with dots between them, from point a to point b."""
    dx, dy = b.x() - a.x(), b.y() - a.y()
    length = math.hypot(dx, dy)
    n = max(1, int(length // step))
    ux, uy = dx / length, dy / length
    vx, vy = -uy, ux
    real = length / n
    for k in range(n):
        t = (k + 0.5) * real
        cx, cy = a.x() + ux * t, a.y() + uy * t
        path = QPainterPath()
        path.moveTo(cx + ux * size, cy + uy * size)
        path.lineTo(cx + vx * size * 0.55, cy + vy * size * 0.55)
        path.lineTo(cx - ux * size, cy - uy * size)
        path.lineTo(cx - vx * size * 0.55, cy - vy * size * 0.55)
        path.closeSubpath()
        p.setPen(ink.pen(0.5))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(ink.brush)
        p.drawEllipse(QPointF(cx, cy), size * 0.18, size * 0.18)
        if k:
            dx0, dy0 = a.x() + ux * k * real, a.y() + uy * k * real
            p.drawEllipse(QPointF(dx0, dy0), size * 0.14, size * 0.14)


def scroll(p, ink, c, w, flip=1, up=1):
    """A curl of acanthus: a long S from the centre outwards, ending in a spiral."""
    path = QPainterPath()
    x0, y0 = c.x(), c.y()
    path.moveTo(x0, y0)
    path.cubicTo(x0 + flip * w * 0.25, y0 - up * w * 0.28, x0 + flip * w * 0.55, y0 + up * w * 0.22,
                 x0 + flip * w * 0.8, y0 - up * w * 0.05)
    # the spiral at the end
    cx, cy = x0 + flip * w * 0.86, y0 - up * w * 0.02
    r = w * 0.09
    for k in range(10):
        a = math.pi * (1 + k * 0.35)
        rr = r * (1 - k * 0.08)
        path.lineTo(cx + flip * rr * math.cos(a), cy - up * rr * math.sin(a))
    p.setPen(ink.pen(0.9))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    # small leaves along the stem
    for t, s in ((0.3, 1), (0.55, -1)):
        lx = x0 + flip * w * t
        ly = y0 + up * w * (0.02 if s > 0 else 0.0)
        leaf = QPainterPath()
        leaf.moveTo(lx, ly)
        leaf.quadTo(lx + flip * w * 0.05, ly - up * s * w * 0.12, lx + flip * w * 0.12, ly - up * s * w * 0.1)
        leaf.quadTo(lx + flip * w * 0.06, ly - up * s * w * 0.03, lx, ly)
        p.setPen(Qt.NoPen)
        p.setBrush(ink.brush)
        p.drawPath(leaf)


def divider(p, ink, cx, y, w, kind="scroll"):
    """A line of ornament under a title: two scrolls from a lozenge in the middle, or (line)
    a thin line broken by a small lozenge."""
    if kind == "line":
        s = max(2.0, w * 0.03)
        p.setPen(ink.pen(max(0.5, w * 0.004)))
        p.drawLine(QPointF(cx - w / 2, y), QPointF(cx - s * 2, y))
        p.drawLine(QPointF(cx + s * 2, y), QPointF(cx + w / 2, y))
        path = QPainterPath()
        path.moveTo(cx, y - s)
        path.lineTo(cx + s, y)
        path.lineTo(cx, y + s)
        path.lineTo(cx - s, y)
        path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(ink.brush)
        p.drawPath(path)
        return
    scroll(p, ink, QPointF(cx - w * 0.06, y), w * 0.44, flip=-1)
    scroll(p, ink, QPointF(cx + w * 0.06, y), w * 0.44, flip=1)
    path = QPainterPath()
    s = w * 0.05
    path.moveTo(cx, y - s)
    path.lineTo(cx + s * 0.7, y)
    path.lineTo(cx, y + s)
    path.lineTo(cx - s * 0.7, y)
    path.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(ink.brush)
    p.drawPath(path)


def corner(p, ink, c, size, sx, sy):
    """The ornament in a corner of the frame: a rosette with two scrolls along the sides."""
    rosette(p, ink, c, size * 0.42)
    scroll(p, ink, QPointF(c.x() + sx * size * 0.5, c.y()), size * 2.2, flip=sx, up=-sy)
    p.save()
    p.translate(c)
    p.rotate(90 if sx * sy > 0 else -90)
    p.translate(-c.x(), -c.y())
    scroll(p, ink, QPointF(c.x() + sx * size * 0.5, c.y()), size * 2.2, flip=sx, up=sy)
    p.restore()


def frame(p, ink, rect, k, kind="ornate", corners=True):
    """The frame of the cover. ornate: a heavy outer line, a band of lozenges between double
    lines, rosettes in its corners; double: a heavy line and a thin one; single: a thin line;
    none: nothing. corners: scrolls in the inner corners. k scales the ornament to the page.
    Returns the room inside the frame."""
    if kind != "ornate":
        inner = rect.adjusted(26 * k, 26 * k, -26 * k, -26 * k)
        p.setBrush(Qt.NoBrush)
        if kind == "double":
            p.setPen(ink.pen(2.0 * k))
            p.drawRect(rect.adjusted(18 * k, 18 * k, -18 * k, -18 * k))
            p.setPen(ink.pen(0.7 * k))
            p.drawRect(inner)
        elif kind == "single":
            p.setPen(ink.pen(0.9 * k))
            p.drawRect(inner)
        else:
            return rect.adjusted(34 * k, 34 * k, -34 * k, -34 * k)
        if corners:
            corner_scrolls(p, ink, inner, k)
        return inner
    m1 = rect.adjusted(14 * k, 14 * k, -14 * k, -14 * k)
    p.setBrush(Qt.NoBrush)
    p.setPen(ink.pen(2.4 * k))
    p.drawRect(m1)
    m2 = m1.adjusted(5 * k, 5 * k, -5 * k, -5 * k)
    p.setPen(ink.pen(0.7 * k))
    p.drawRect(m2)
    band = 15 * k
    m3 = m2.adjusted(band, band, -band, -band)
    p.drawRect(m3)
    mid = m2.adjusted(band / 2, band / 2, -band / 2, -band / 2)
    pts = [mid.topLeft(), mid.topRight(), mid.bottomRight(), mid.bottomLeft()]
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        # leave the corners for the rosettes
        ux = (b.x() - a.x()) / max(1e-6, math.hypot(b.x() - a.x(), b.y() - a.y()))
        uy = (b.y() - a.y()) / max(1e-6, math.hypot(b.x() - a.x(), b.y() - a.y()))
        lozenge_band(p, ink, QPointF(a.x() + ux * band, a.y() + uy * band),
                     QPointF(b.x() - ux * band, b.y() - uy * band), band * 0.36, band * 1.1)
    for pt in pts:
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(ink.ground))
        p.drawRect(QRectF(pt.x() - band / 2, pt.y() - band / 2, band, band))
        rosette(p, ink, pt, band * 0.42)
    m4 = m3.adjusted(4 * k, 4 * k, -4 * k, -4 * k)
    p.setBrush(Qt.NoBrush)
    p.setPen(ink.pen(1.3 * k))
    p.drawRect(m4)
    if corners:
        corner_scrolls(p, ink, m4, k)
    return m4


def corner_scrolls(p, ink, box, k):
    s = 26 * k
    for (cx, cy, sx, sy) in ((box.left(), box.top(), 1, 1), (box.right(), box.top(), -1, 1),
                             (box.right(), box.bottom(), -1, -1), (box.left(), box.bottom(), 1, -1)):
        c = QPointF(cx + sx * s * 0.55, cy + sy * s * 0.55)
        corner(p, ink, c, s, sx, sy)


def gate(p, ink, inner, k):
    """An arch over the title, standing on two pillars, the inner one doubled."""
    left, right = inner.left() + 30 * k, inner.right() - 30 * k
    top = inner.top() + 44 * k
    spring = top + (right - left) * 0.32
    bottom = inner.top() + inner.height() * 0.66
    for off, w in ((0, 1.6), (6 * k, 0.6)):
        path = QPainterPath()
        l, r = left + off, right - off
        path.moveTo(l, bottom)
        path.lineTo(l, spring)
        mid = (l + r) / 2
        path.cubicTo(l, spring - (r - l) * 0.26, mid - (r - l) * 0.18, top + off, mid, top + off)
        path.cubicTo(mid + (r - l) * 0.18, top + off, r, spring - (r - l) * 0.26, r, spring)
        path.lineTo(r, bottom)
        p.setPen(ink.pen(w * k))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
    # the bases and capitals of the pillars
    for x in (left, right):
        for y in (spring, bottom):
            p.setPen(ink.pen(1.0 * k))
            p.drawLine(QPointF(x - 9 * k, y), QPointF(x + 9 * k, y))
            p.drawLine(QPointF(x - 6 * k, y + (3 if y == spring else -3) * k),
                       QPointF(x + 6 * k, y + (3 if y == spring else -3) * k))
    p.setPen(ink.pen(0.7 * k))
    p.drawLine(QPointF(left - 2 * k, bottom + 4 * k), QPointF(right + 2 * k, bottom + 4 * k))
    # a crown of rays at the head of the arch
    cx = (left + right) / 2
    rosette(p, ink, QPointF(cx, top - 1 * k), 9 * k, petals=12)
    return QRectF(left + 14 * k, spring - 20 * k, right - left - 28 * k, bottom - spring), top, bottom


def cartouche(p, ink, rect, text, k, framed=True):
    """An oval frame with a verse in it (framed=False: the verse alone)."""
    if not framed:
        f = fit_font(TEXT_FONT, 14 * k, text, rect.width())
        draw_text(p, ink, text, f, rect.center().x(), rect.center().y() + f.pointSizeF() * 0.35)
        return
    p.setBrush(Qt.NoBrush)
    p.setPen(ink.pen(1.2 * k))
    p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
    p.setPen(ink.pen(0.5 * k))
    p.drawRoundedRect(rect.adjusted(3 * k, 3 * k, -3 * k, -3 * k), rect.height() / 2 - 3 * k, rect.height() / 2 - 3 * k)
    for x, s in ((rect.left(), -1), (rect.right(), 1)):
        scroll(p, ink, QPointF(x, rect.center().y()), 38 * k, flip=s)
    f = fit_font(TEXT_FONT, 13.5 * k, text, rect.width() - 34 * k)
    draw_text(p, ink, text, f, rect.center().x(), rect.center().y() + f.pointSizeF() * 0.35)


# ---------------------------------------------------------------- pages

def title_block(p, box, info, k, ink, style, ink2=None, scale=1.0, top_in_box=True):
    """The words of the cover in the middle of box: the series, the title, a divider, the
    translation and commentaries, and the haftarot. ink2 (if given) for the lines under
    the title."""
    title_font = style.get("title_font", TITLE_FONT)
    div = style.get("divider", "scroll")
    ink2 = ink2 or ink
    steps = []
    if info.get("top") and top_in_box:
        f = fit_font(title_font, 24 * k * scale, info["top"], box.width() * 0.8)
        steps += [("text", info["top"], f, f.pointSizeF() * 1.0, ink), ("div", 0.5, 16 * k, 14 * k, ink)]
    if info.get("title"):
        f = fit_font(title_font, 66 * k * scale, info["title"], box.width() * 0.94)
        steps += [("text", info["title"], f, f.pointSizeF() * 0.95, ink), ("div", 0.62, 22 * k, 20 * k, ink)]
    for n, line in enumerate(info.get("lines", [])):
        f = fit_font(title_font, (20 if n == 0 else 23) * k * scale, line, box.width() * 0.95)
        steps.append(("text", line, f, f.pointSizeF() * 1.4, ink2))
    if info.get("details"):
        f = fit_font(TEXT_FONT, 14 * k * scale, info["details"], box.width() * 0.95, bold=False)
        steps.append(("text", info["details"], f, f.pointSizeF() * 1.7, ink2))
    if info.get("extra"):
        steps.append(("div", 0.3, 16 * k, 4 * k, ink2))
        f = fit_font(TEXT_FONT, 15 * k * scale, info["extra"], box.width() * 0.95)
        steps.append(("text", info["extra"], f, f.pointSizeF() * 1.5, ink2))
    total = sum(st[3] + (st[2] if st[0] == "div" else 0) for st in steps)
    y = box.top() + max(0.0, (box.height() - total) / 2)
    cx = box.center().x()
    for st in steps:
        if st[0] == "text":
            y += st[3]
            draw_text(p, st[4], st[1], st[2], cx, y)
        else:
            y += st[2]
            divider(p, st[4], cx, y, box.width() * st[1], div)
            y += st[3]


def plain_text(p, ink, text, cx, cy, k, w, size=14, family=None):
    f = fit_font(family or TEXT_FONT, size * k, text, w)
    draw_text(p, ink, text, f, cx, cy + f.pointSizeF() * 0.35)


def solid(color):
    return Ink(QRectF(0, 0, 1, 1), True, {"ink": color, "bg": ("paper", ("#ffffff", "#ffffff"))})


def hills(p, rect, k):
    """Green hills at the foot of a page, three ridges, the nearest the darkest."""
    x0, x1, b = rect.left(), rect.right(), rect.bottom()
    w = rect.width()
    for top, colours, phase in ((0.70, ("#a9d18e", "#8cc06e"), 0.0), (0.78, ("#7fb85e", "#5f9c43"), 0.35),
                                (0.86, ("#4f8a37", "#3a6e27"), 0.7)):
        y = rect.top() + rect.height() * top
        path = QPainterPath()
        path.moveTo(x0, b)
        path.lineTo(x0, y + 10 * k * math.sin(phase * 7))
        n = 4
        for i in range(n):
            xa = x0 + w * (i + 0.5) / n
            xb = x0 + w * (i + 1) / n
            ya = y - (18 + 10 * math.sin(i * 2.1 + phase * 5)) * k
            yb = y + 8 * k * math.sin(i * 1.7 + phase * 3)
            path.quadTo(xa, ya, xb, yb)
        path.lineTo(x1, b)
        path.closeSubpath()
        g = QLinearGradient(QPointF(0, y - 30 * k), QPointF(0, b))
        g.setColorAt(0, QColor(colours[0]))
        g.setColorAt(1, QColor(colours[1]))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawPath(path)


def sun(p, c, r):
    g = QRadialGradient(c, r * 3)
    g.setColorAt(0.0, QColor(255, 236, 160, 255))
    g.setColorAt(0.3, QColor(255, 228, 140, 180))
    g.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(c, r * 3, r * 3)
    p.setBrush(QColor("#ffe58a"))
    p.drawEllipse(c, r, r)


def stars(p, rect, k, seed=5):
    rnd = random.Random(seed)
    p.setPen(Qt.NoPen)
    n = int(rect.width() * rect.height() / 420)
    for _ in range(n):
        x = rect.left() + rnd.random() * rect.width()
        y = rect.top() + rnd.random() * rect.height()
        r = (0.25 + rnd.random() ** 3 * 1.2) * k
        p.setBrush(QColor(255, 250, 230, int(90 + rnd.random() * 165)))
        p.drawEllipse(QPointF(x, y), r, r)
    for _ in range(14):
        x = rect.left() + rnd.random() * rect.width()
        y = rect.top() + rnd.random() * rect.height()
        r = (3 + rnd.random() * 4) * k
        path = QPainterPath()
        path.moveTo(x, y - r)
        path.quadTo(x, y, x + r, y)
        path.quadTo(x, y, x, y + r)
        path.quadTo(x, y, x - r, y)
        path.quadTo(x, y, x, y - r)
        p.setBrush(QColor(255, 248, 220, 230))
        p.drawPath(path)


def ground(p, rect, style, k, seed=7, front=True):
    """The background of a cover in its style, over rect (with the bleed). The sun of the
    field is on the front only."""
    background(p, rect, style, seed)
    lay = style["layout"]
    if lay == "stars":
        stars(p, rect, k, seed)
    elif lay == "field":
        if front:
            sun(p, QPointF(rect.left() + rect.width() * 0.78, rect.top() + rect.height() * 0.16), 16 * k)
        hills(p, rect, k)


def raised_bands(p, ink, rect, k, ys):
    for y in ys:
        for off, w in ((-4, 0.6), (-1.5, 1.6), (1.5, 1.6), (4, 0.6)):
            p.setPen(ink.pen(w * k))
            p.drawLine(QPointF(rect.left(), y + off * k), QPointF(rect.right(), y + off * k))


def draw_front(p, rect, info, gilt=True, style=None, bleed=0.0):
    """The front cover in a style (STYLES). gilt=False: the title page inside the book —
    the same words in black on white, in a plain frame (the gate's ornate one for the gate).
    bleed: how far the background goes on past rect (on a cover laid flat for printing)."""
    style = style or STYLES[0]
    k = min(rect.width() / 595.0, rect.height() / 842.0)
    lay = style["layout"]
    if not gilt:
        p.fillRect(rect, QColor("white"))
        ink = Ink(rect, False, style)
        if lay == "gate":
            inner = frame(p, ink, rect, k)
            box, top, bottom = gate(p, ink, inner, k)
        else:
            inner = frame(p, ink, rect, k, "double", True)
            bottom = inner.top() + inner.height() * 0.72
            box = QRectF(inner.left() + 24 * k, inner.top() + 40 * k, inner.width() - 48 * k, bottom - inner.top() - 40 * k)
        title_block(p, box, info, k, ink, style)
        cartouche(p, ink, QRectF(inner.center().x() - inner.width() * 0.33, (bottom + inner.bottom()) / 2 - 20 * k,
                                 inner.width() * 0.66, 40 * k), info.get("verse", ""), k, lay == "gate")
        return
    ground(p, rect.adjusted(-bleed, -bleed, bleed, bleed), style, k)
    ink = Ink(rect, True, style)
    verse = info.get("verse", "")
    cx = rect.center().x()

    if lay == "gate":
        inner = frame(p, ink, rect, k)
        box, top, bottom = gate(p, ink, inner, k)
        title_block(p, box, info, k, ink, style)
        cartouche(p, ink, QRectF(cx - inner.width() * 0.33, (bottom + inner.bottom() - 28 * k) / 2 - 20 * k,
                                 inner.width() * 0.66, 40 * k), verse, k)

    elif lay == "medallion":
        inner = frame(p, ink, rect, k, "double", True)
        ow, oh = inner.width() * 0.86, inner.height() * 0.56
        oval = QRectF(cx - ow / 2, inner.top() + inner.height() * 0.15, ow, oh)
        p.setBrush(Qt.NoBrush)
        p.setPen(ink.pen(2.0 * k))
        p.drawEllipse(oval)
        p.setPen(ink.pen(0.7 * k))
        p.drawEllipse(oval.adjusted(6 * k, 6 * k, -6 * k, -6 * k))
        for y in (oval.top(), oval.bottom()):
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(ink.ground))
            p.drawEllipse(QPointF(cx, y), 13 * k, 13 * k)
            rosette(p, ink, QPointF(cx, y), 11 * k, petals=12)
        for x, s in ((oval.left(), -1), (oval.right(), 1)):
            scroll(p, ink, QPointF(x, oval.center().y()), 30 * k, flip=s)
        if info.get("top"):
            plain_text(p, ink, info["top"], cx, (inner.top() + oval.top()) / 2, k, inner.width() * 0.8, 22, TITLE_FONT)
        title_block(p, oval.adjusted(ow * 0.12, oh * 0.1, -ow * 0.12, -oh * 0.1), info, k, ink, style,
                    scale=0.85, top_in_box=False)
        plain_text(p, ink, verse, cx, (oval.bottom() + inner.bottom()) / 2, k, inner.width() * 0.7)

    elif lay == "label":
        H = rect.height()
        raised_bands(p, ink, rect.adjusted(-bleed, 0, bleed, 0), k,
                     [rect.top() + H * f for f in (0.07, 0.12, 0.88, 0.93)])
        lw, lh = rect.width() * 0.74, H * 0.5
        lab = QRectF(cx - lw / 2, rect.top() + H * 0.21, lw, lh)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRect(lab.translated(2.5 * k, 3 * k))
        g = QLinearGradient(lab.topLeft(), lab.bottomRight())
        g.setColorAt(0, QColor(style["panel"]).lighter(104))
        g.setColorAt(1, QColor(style["panel"]).darker(106))
        p.setBrush(QBrush(g))
        p.drawRect(lab)
        p.setBrush(Qt.NoBrush)
        p.setPen(ink.pen(1.6 * k))
        p.drawRect(lab.adjusted(5 * k, 5 * k, -5 * k, -5 * k))
        dark = solid(style["ink2"])
        p.setPen(dark.pen(0.6 * k))
        p.drawRect(lab.adjusted(9 * k, 9 * k, -9 * k, -9 * k))
        title_block(p, lab.adjusted(22 * k, 18 * k, -22 * k, -18 * k), info, k, dark, style, scale=0.9)
        plain_text(p, ink, verse, cx, rect.top() + H * 0.79, k, rect.width() * 0.66)

    elif lay == "rays":
        H, W = rect.height(), rect.width()
        o = QPointF(cx, rect.top() - H * 0.15)
        p.save()
        p.setClipRect(rect.adjusted(-bleed, -bleed, bleed, bleed))
        for i in range(-24, 25):
            a = math.pi / 2 + i * 0.035
            end = QPointF(o.x() + math.cos(a) * H * 1.6, o.y() + math.sin(a) * H * 1.6)
            pen = ink.pen((0.9 if i % 3 == 0 else 0.4) * k)
            p.setPen(pen)
            p.setOpacity(0.55)
            p.drawLine(o, end)
        p.setOpacity(1.0)
        p.restore()
        band = QRectF(rect.left() - bleed, rect.top() + H * 0.25, W + 2 * bleed, H * 0.48)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(style["bg"][1][2]))
        p.drawRect(band)
        p.setPen(ink.pen(2.2 * k))
        for y in (band.top() + 4 * k, band.bottom() - 4 * k):
            p.drawLine(QPointF(band.left(), y), QPointF(band.right(), y))
        p.setPen(ink.pen(0.6 * k))
        for y in (band.top() + 9 * k, band.bottom() - 9 * k):
            p.drawLine(QPointF(band.left(), y), QPointF(band.right(), y))
        m = 22 * k
        for (x, y, sx, sy) in ((rect.left() + m, rect.top() + m, 1, 1), (rect.right() - m, rect.top() + m, -1, 1),
                               (rect.left() + m, rect.bottom() - m, 1, -1), (rect.right() - m, rect.bottom() - m, -1, -1)):
            for step in range(3):
                d = step * 7 * k
                L = (60 - step * 14) * k
                p.setPen(ink.pen((1.6 if step == 0 else 0.7) * k))
                p.drawLine(QPointF(x + sx * d, y + sy * d), QPointF(x + sx * (d + L), y + sy * d))
                p.drawLine(QPointF(x + sx * d, y + sy * d), QPointF(x + sx * d, y + sy * (d + L)))
        title_block(p, band.adjusted(W * 0.08 + bleed, 16 * k, -W * 0.08 - bleed, -16 * k), info, k, ink, style)
        plain_text(p, ink, verse, cx, rect.top() + H * 0.82, k, W * 0.66)

    elif lay == "split":
        H, W = rect.height(), rect.width()
        cut = rect.top() + H * 0.58
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(style["field"]))
        p.drawRect(QRectF(rect.left() - bleed, rect.top() - bleed, W + 2 * bleed, cut - rect.top() + bleed))
        gl = Ink(rect, True, dict(style, ink="gold"))
        p.setPen(gl.pen(2.0 * k))
        p.drawLine(QPointF(rect.left() - bleed, cut), QPointF(rect.right() + bleed, cut))
        upper = QRectF(rect.left() + W * 0.1, rect.top() + H * 0.12, W * 0.8, cut - rect.top() - H * 0.16)
        info_top = dict(info, lines=[], details="", extra="")
        title_block(p, upper, info_top, k, ink, style, scale=1.1)
        low = solid(style["ink2"])
        lower = QRectF(rect.left() + W * 0.1, cut + H * 0.01, W * 0.8, H * 0.26)
        title_block(p, lower, dict(info, top="", title=""), k, low, dict(style, divider="line"), scale=0.92,
                    top_in_box=False)
        plain_text(p, low, verse, cx, rect.top() + H * 0.93, k, W * 0.6, 13)

    elif lay == "band":
        H, W = rect.height(), rect.width()
        bw = W * 0.2
        bandr = QRectF(rect.right() - bw, rect.top() - bleed, bw + bleed, H + 2 * bleed)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(style["field"]))
        p.drawRect(bandr)
        gl = Ink(rect, True, dict(style, ink="gold"))
        p.setPen(gl.pen(1.4 * k))
        p.drawLine(QPointF(bandr.left() + 6 * k, bandr.top()), QPointF(bandr.left() + 6 * k, bandr.bottom()))
        p.setPen(gl.pen(0.5 * k))
        p.drawLine(QPointF(bandr.left() + 10 * k, bandr.top()), QPointF(bandr.left() + 10 * k, bandr.bottom()))
        if info.get("top"):
            f = fit_font(TITLE_FONT, 26 * k, info["top"], H * 0.6)
            p.save()
            p.translate(QPointF(rect.right() - bw / 2 + 4 * k, rect.center().y()))
            p.rotate(90)
            draw_text(p, gl, info["top"], f, 0, f.pointSizeF() * 0.35)
            p.restore()
        area = QRectF(rect.left() + W * 0.07, rect.top() + H * 0.18, W * 0.66, H * 0.5)
        title_block(p, area, info, k, ink, dict(style, divider="line"), top_in_box=False)
        plain_text(p, ink, verse, area.center().x(), rect.top() + H * 0.86, k, area.width())

    elif lay == "letter":
        H, W = rect.height(), rect.width()
        letter = info.get("letter") or (info.get("title", " ").split()[-1][:1])
        f = qf(TITLE_FONT, H * 0.62)
        path = QPainterPath()
        path.addText(QPointF(0, 0), f, letter)
        br = path.boundingRect()
        path.translate(cx - br.center().x(), rect.top() + H * 0.47 - br.center().y())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 30))
        p.drawPath(path)
        p.setBrush(Qt.NoBrush)
        p.setPen(ink.pen(0.8 * k))
        p.drawRect(rect.adjusted(20 * k, 20 * k, -20 * k, -20 * k))
        title_block(p, QRectF(rect.left() + W * 0.08, rect.top() + H * 0.2, W * 0.84, H * 0.52), info, k, ink,
                    dict(style, divider="line"))
        plain_text(p, ink, verse, cx, rect.top() + H * 0.85, k, W * 0.66)

    elif lay == "stars":
        H, W = rect.height(), rect.width()
        title_block(p, QRectF(rect.left() + W * 0.08, rect.top() + H * 0.18, W * 0.84, H * 0.5), info, k, ink, style)
        p.setPen(ink.pen(0.6 * k))
        p.drawLine(QPointF(cx - W * 0.25, rect.top() + H * 0.78), QPointF(cx + W * 0.25, rect.top() + H * 0.78))
        plain_text(p, ink, verse, cx, rect.top() + H * 0.83, k, W * 0.66)

    elif lay == "arch":
        H, W = rect.height(), rect.width()
        aw, top, bot = W * 0.7, rect.top() + H * 0.1, rect.top() + H * 0.8
        path = QPainterPath()
        l, r = cx - aw / 2, cx + aw / 2
        path.moveTo(l, bot)
        path.lineTo(l, top + aw / 2)
        path.arcTo(QRectF(l, top, aw, aw), 180, -180)
        path.lineTo(r, bot)
        path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(style["field"]))
        p.drawPath(path)
        gl = Ink(rect, True, dict(style, ink="gold"))
        outline = QPainterPath()
        l2, r2, t2 = l - 7 * k, r + 7 * k, top - 7 * k
        outline.moveTo(l2, bot + 7 * k)
        outline.lineTo(l2, t2 + (aw + 14 * k) / 2)
        outline.arcTo(QRectF(l2, t2, aw + 14 * k, aw + 14 * k), 180, -180)
        outline.lineTo(r2, bot + 7 * k)
        outline.closeSubpath()
        p.setBrush(Qt.NoBrush)
        p.setPen(gl.pen(1.0 * k))
        p.drawPath(outline)
        title_block(p, QRectF(l + aw * 0.08, top + aw * 0.22, aw * 0.84, bot - top - aw * 0.3), info, k, ink,
                    dict(style, divider="line"), scale=0.92)
        plain_text(p, solid(style["ink2"]), verse, cx, rect.top() + H * 0.89, k, W * 0.7)

    elif lay == "field":
        H, W = rect.height(), rect.width()
        title_block(p, QRectF(rect.left() + W * 0.08, rect.top() + H * 0.14, W * 0.84, H * 0.48), info, k, ink,
                    dict(style, divider="line"), scale=1.05)
        plain_text(p, solid("#ffffff"), verse, cx, rect.top() + H * 0.93, k, W * 0.7)


def draw_back(p, rect, info, style=None, bleed=0.0):
    style = style or STYLES[0]
    k = min(rect.width() / 595.0, rect.height() / 842.0)
    lay = style["layout"]
    ground(p, rect.adjusted(-bleed, -bleed, bleed, bleed), style, k, seed=11, front=False)
    ink = Ink(rect, True, style)
    cx, H, W = rect.center().x(), rect.height(), rect.width()
    text = info.get("back", "")
    if lay == "gate":
        inner = frame(p, ink, rect, k)
        rosette(p, ink, QPointF(cx, rect.center().y() - 70 * k), 22 * k, petals=16)
        cartouche(p, ink, QRectF(cx - inner.width() * 0.35, rect.center().y() - 20 * k, inner.width() * 0.7, 40 * k), text, k)
        divider(p, ink, cx, rect.center().y() + 60 * k, inner.width() * 0.5)
    elif lay == "medallion":
        inner = frame(p, ink, rect, k, "double", True)
        rosette(p, ink, QPointF(cx, rect.center().y() - 50 * k), 26 * k, petals=16)
        plain_text(p, ink, text, cx, rect.center().y() + 10 * k, k, inner.width() * 0.75)
    elif lay == "label":
        raised_bands(p, ink, rect.adjusted(-bleed, 0, bleed, 0), k,
                     [rect.top() + H * f for f in (0.07, 0.12, 0.88, 0.93)])
        plain_text(p, ink, text, cx, rect.center().y(), k, W * 0.7)
    elif lay == "rays":
        band = QRectF(rect.left() - bleed, rect.top() + H * 0.44, W + 2 * bleed, H * 0.12)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(style["bg"][1][2]))
        p.drawRect(band)
        p.setPen(ink.pen(1.6 * k))
        for y in (band.top() + 3 * k, band.bottom() - 3 * k):
            p.drawLine(QPointF(band.left(), y), QPointF(band.right(), y))
        plain_text(p, ink, text, cx, band.center().y(), k, W * 0.7)
    elif lay == "split":
        cut = rect.top() + H * 0.58
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(style["field"]))
        p.drawRect(QRectF(rect.left() - bleed, rect.top() - bleed, W + 2 * bleed, cut - rect.top() + bleed))
        gl = Ink(rect, True, dict(style, ink="gold"))
        p.setPen(gl.pen(2.0 * k))
        p.drawLine(QPointF(rect.left() - bleed, cut), QPointF(rect.right() + bleed, cut))
        plain_text(p, ink, text, cx, rect.top() + H * 0.4, k, W * 0.7)
    elif lay == "band":
        bandr = QRectF(rect.left() - bleed, rect.top() - bleed, W * 0.2 + bleed, H + 2 * bleed)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(style["field"]))
        p.drawRect(bandr)
        plain_text(p, ink, text, rect.left() + W * 0.6, rect.center().y(), k, W * 0.66)
    elif lay == "arch":
        plain_text(p, solid(style["ink2"]), text, cx, rect.center().y(), k, W * 0.7)
    elif lay == "field":
        plain_text(p, ink, text, cx, rect.top() + H * 0.35, k, W * 0.7)
    else:
        p.setPen(ink.pen(0.6 * k))
        if lay == "letter":
            p.setBrush(Qt.NoBrush)
            p.drawRect(rect.adjusted(20 * k, 20 * k, -20 * k, -20 * k))
        plain_text(p, ink, text, cx, rect.center().y(), k, W * 0.7)


def draw_spine(p, rect, info, style=None):
    """The spine: the background of the style, bands at head and foot on leather and
    cloth, the title running along it."""
    style = style or STYLES[0]
    lay = style["layout"]
    k = rect.height() / 842.0
    if lay in ("split", "band", "arch"):
        p.fillRect(rect, QColor(style["field"]))
        ink = Ink(rect, True, dict(style, ink="gold" if lay != "split" else style["ink"]))
    else:
        ground(p, rect, style, k, seed=3, front=False)
        ink = Ink(rect, True, style)
    w = rect.width()
    if style["bg"][0] in ("leather", "cloth"):
        for y0, d in ((rect.top() + 30 * k, 1), (rect.bottom() - 30 * k, -1)):
            for off, lw in ((0, 1.6), (4 * k, 0.6), (40 * k, 0.6), (44 * k, 1.6)):
                y = y0 + d * off
                p.setPen(ink.pen(lw))
                p.drawLine(QPointF(rect.left() + w * 0.08, y), QPointF(rect.right() - w * 0.08, y))
            if w > 14:
                rosette(p, ink, QPointF(rect.center().x(), y0 + d * 22 * k), min(w * 0.3, 12 * k))
    text = " · ".join(t for t in (info.get("top"), info.get("title")) if t)
    size = min(w * 0.55, 20 * k)
    if size < 4:
        return
    f = fit_font(style.get("title_font", TITLE_FONT), size, text, rect.height() - 200 * k)
    p.save()
    p.translate(rect.center())
    p.rotate(90)
    draw_text(p, ink, text, f, 0, f.pointSizeF() * 0.35)
    p.restore()


def draw_wrap(p, rect, info, spine_w, bleed, style=None):
    """The whole cover laid flat, outside up, for a book bound on the right: the front on
    the left, then the spine, then the back. bleed: extra all round, to be trimmed."""
    style = style or STYLES[0]
    pw = (rect.width() - spine_w - 2 * bleed) / 2
    front = QRectF(rect.left(), rect.top(), pw + bleed, rect.height())
    spine = QRectF(front.right(), rect.top(), spine_w, rect.height())
    back = QRectF(spine.right(), rect.top(), pw + bleed, rect.height())
    # each part draws its own background into the bleed beside it
    p.save()
    p.setClipRect(front)
    draw_front(p, QRectF(front.left() + bleed, front.top() + bleed, pw, rect.height() - 2 * bleed), info,
               style=style, bleed=bleed)
    p.restore()
    p.save()
    p.setClipRect(back)
    draw_back(p, QRectF(back.left(), back.top() + bleed, pw, rect.height() - 2 * bleed), info, style, bleed)
    p.restore()
    p.save()
    p.setClipRect(spine)
    draw_spine(p, spine, info, style)
    p.restore()


# the thickness of a sheet of ordinary uncoated book paper, by its weight (g/m²), in mm
PAPER_MM = {60: 0.075, 70: 0.09, 80: 0.1, 90: 0.11, 100: 0.125, 120: 0.15}


# the soft cover itself (card of about 250-300g) adds to the spine where it wraps the block
COVER_MM = 0.5


def spine_mm(n_pages, grams=80):
    """The width of the spine of a soft cover: the book block (one sheet for every two
    pages) and the card of the cover around it."""
    sheet = PAPER_MM.get(grams, grams / 800)
    return max(3.0, math.ceil(n_pages / 2) * sheet + COVER_MM)


BLEED_MM = 3.0
