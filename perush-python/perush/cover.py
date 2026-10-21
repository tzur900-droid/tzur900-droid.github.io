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

# The styles of cover, from the heaviest to the lightest. bg: (material, colours) — leather
# (grain), cloth (a fine weave) or paper (plain, light). ink: gold, silver or a colour.
# frame: ornate (a band of lozenges and rosettes), double, single or none; corners: scrolls
# inside the frame; gate: an arch over the title; cartouche: the verse in an oval frame
# (otherwise in plain letters); divider: scroll or line.
STYLES = [
    dict(name="בורדו מלכותי", bg=("leather", LEATHER), ink="gold", frame="ornate", corners=True, gate=True, cartouche=True),
    dict(name="שחור וזהב", bg=("leather", ("#2b2a28", "#171615", "#060605")), ink="gold", frame="ornate", corners=True, gate=True, cartouche=True),
    dict(name="כחול לילה וזהב", bg=("leather", ("#1e2e5a", "#121d3d", "#070e22")), ink="gold", frame="ornate", corners=True, gate=False, cartouche=True),
    dict(name="ירוק בקבוק", bg=("leather", ("#1f4a33", "#133222", "#07190f")), ink="gold", frame="double", corners=True, gate=True, cartouche=True),
    dict(name="חום עתיק", bg=("leather", ("#6e4624", "#4a2e17", "#25160a")), ink="gold", frame="double", corners=True, gate=False, cartouche=True),
    dict(name="אפור וכסף", bg=("leather", ("#4b4e53", "#2f3236", "#141618")), ink="silver", frame="double", corners=False, gate=False, cartouche=True),
    dict(name="בד כחול קלאסי", bg=("cloth", ("#2f4f84", "#223b64", "#152846")), ink="gold", frame="single", corners=False, gate=False, cartouche=False),
    dict(name="שמנת ובורדו", bg=("paper", ("#f6eedb", "#e6d8b8")), ink="#6b1a1f", frame="double", corners=True, gate=False, cartouche=True),
    dict(name="לבן וכחול", bg=("paper", ("#ffffff", "#e9f0f9")), ink="#1f3c73", frame="single", corners=False, gate=False, cartouche=False, divider="line"),
    dict(name="ברסלב", bg=("paper", ("#ffffff", "#cfe3f6")), ink="#123a7a", frame="none", corners=False, gate=False, cartouche=False, divider="line", title_font=TEXT_FONT),
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

def draw_front(p, rect, info, gilt=True, style=None):
    """The front cover in a style (STYLES), or the title page (gilt=False: the same in black
    on white)."""
    style = style or STYLES[0]
    k = min(rect.width() / 595.0, rect.height() / 842.0)
    if gilt:
        background(p, rect, style)
    else:
        p.fillRect(rect, QColor("white"))
    ink = Ink(rect, gilt, style)
    title_font = style.get("title_font", TITLE_FONT)
    div = style.get("divider", "scroll")
    inner = frame(p, ink, rect, k, style["frame"], style["corners"])
    if style["gate"]:
        box, top, bottom = gate(p, ink, inner, k)
    else:
        # no gate: the title stands in the upper two thirds of the frame
        bottom = inner.top() + inner.height() * 0.7
        box = QRectF(inner.left() + 24 * k, inner.top() + 40 * k, inner.width() - 48 * k, bottom - inner.top() - 40 * k)
    cx = box.center().x()
    # the block of the title, measured first and then set in the middle of the gate:
    # (what, font or width, the room it takes)
    steps = []
    if info.get("top"):
        f = fit_font(title_font, 24 * k, info["top"], box.width() * 0.8)
        steps += [("text", info["top"], f, f.pointSizeF() * 1.0, 0), ("div", 0.5, 16 * k, 14 * k)]
    f = fit_font(title_font, (64 if style["gate"] else 70) * k, info["title"], box.width() * 0.92)
    steps += [("text", info["title"], f, f.pointSizeF() * 0.95, 0), ("div", 0.62, 22 * k, 20 * k)]
    for n, line in enumerate(info.get("lines", [])):
        f = fit_font(title_font, (20 if n == 0 else 23) * k, line, box.width() * 0.95)
        steps.append(("text", line, f, f.pointSizeF() * 1.4, 0))
    if info.get("details"):
        f = fit_font(TEXT_FONT, 14 * k, info["details"], box.width() * 0.95, bold=False)
        steps.append(("text", info["details"], f, f.pointSizeF() * 1.7, 0))
    if info.get("extra"):
        steps.append(("div", 0.3, 16 * k, 4 * k))
        f = fit_font(TEXT_FONT, 15 * k, info["extra"], box.width() * 0.95)
        steps.append(("text", info["extra"], f, f.pointSizeF() * 1.5, 0))
    total = sum(st[3] + (st[2] if st[0] == "div" else 0) for st in steps)
    y = box.top() + max(0.0, (box.height() - total) / 2)
    for st in steps:
        if st[0] == "text":
            y += st[3]
            draw_text(p, ink, st[1], st[2], cx, y)
        else:
            y += st[2]
            divider(p, ink, cx, y, box.width() * st[1], div)
            y += st[3]
    # the verse at the foot, under the gate
    h = 40 * k
    room_top = bottom + 6 * k
    room = inner.bottom() - 34 * k - room_top
    cy = room_top + room / 2
    w = inner.width() * 0.66
    cartouche(p, ink, QRectF(inner.center().x() - w / 2, cy - h / 2, w, h), info.get("verse", ""), k,
              style["cartouche"])


def draw_back(p, rect, info, style=None):
    style = style or STYLES[0]
    k = min(rect.width() / 595.0, rect.height() / 842.0)
    background(p, rect, style, seed=11)
    ink = Ink(rect, True, style)
    inner = frame(p, ink, rect, k, style["frame"], style["corners"])
    c = inner.center()
    if style["frame"] == "ornate" or style["corners"]:
        rosette(p, ink, QPointF(c.x(), c.y() - 70 * k), 22 * k, petals=16)
    w = inner.width() * 0.7
    cartouche(p, ink, QRectF(c.x() - w / 2, c.y() - 20 * k, w, 40 * k), info.get("back", ""), k, style["cartouche"])
    divider(p, ink, c.x(), c.y() + 60 * k, inner.width() * 0.5, style.get("divider", "scroll"))


def draw_spine(p, rect, info, style=None):
    """The spine: bands at head and foot, the title running along it."""
    style = style or STYLES[0]
    background(p, rect, style, seed=3)
    ink = Ink(rect, True, style)
    w = rect.width()
    k = rect.height() / 842.0
    bands = style["frame"] in ("ornate", "double")
    for y0, d in ((rect.top() + 30 * k, 1), (rect.bottom() - 30 * k, -1)) if bands else ():
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
    pw = (rect.width() - spine_w - 2 * bleed) / 2
    front = QRectF(rect.left(), rect.top(), pw + bleed, rect.height())
    spine = QRectF(front.right(), rect.top(), spine_w, rect.height())
    back = QRectF(spine.right(), rect.top(), pw + bleed, rect.height())
    style = style or STYLES[0]
    background(p, rect, style)
    # the ornament is drawn on the trimmed pages: the bleed is the background only
    p.save()
    p.setClipRect(front)
    draw_front(p, QRectF(front.left() + bleed, front.top() + bleed, pw, rect.height() - 2 * bleed), info, style=style)
    p.restore()
    p.save()
    p.setClipRect(back)
    draw_back(p, QRectF(back.left(), back.top() + bleed, pw, rect.height() - 2 * bleed), info, style)
    p.restore()
    draw_spine(p, QRectF(spine.left(), spine.top() + bleed, spine.width(), rect.height() - 2 * bleed), info, style)


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
