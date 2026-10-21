"""More cover designs (11-50): each a layout of its own — Jewish motifs (a Torah scroll,
the tablets, a menorah, a crown, pillars), scenes (Jerusalem, dunes, the sea, Sinai),
ornament (mosaic, lattice, papercut, a vine) and modern type — and some of the layouts
on other grounds (stars, marble, a night field).

A layout draws the front cover over its ground; the back and the spine take the ground and
the ink of the style (cover.draw_back, cover.draw_spine). Extras of the ground (stars,
waves, a skyline…) are drawn by ground() on the front, the back and the spine alike, so the
cover laid flat runs on across them.
"""
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainterPath, QPen, QRadialGradient

from . import cover as C


# ---------------------------------------------------------------- helpers

def fill(p, path_or_rect, brush):
    p.setPen(Qt.NoPen)
    p.setBrush(brush if isinstance(brush, QBrush) else QBrush(QColor(brush)))
    if isinstance(path_or_rect, QPainterPath):
        p.drawPath(path_or_rect)
    else:
        p.drawRect(path_or_rect)


def vgrad(rect, *colours):
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    for i, c in enumerate(colours):
        g.setColorAt(i / max(1, len(colours) - 1), QColor(c))
    return QBrush(g)


def hgrad(rect, *colours):
    g = QLinearGradient(rect.topLeft(), rect.topRight())
    for i, c in enumerate(colours):
        g.setColorAt(i / max(1, len(colours) - 1), QColor(c))
    return QBrush(g)


def box(rect, x, y, w, h):
    """A part of rect, in fractions of it."""
    return QRectF(rect.left() + rect.width() * x, rect.top() + rect.height() * y, rect.width() * w, rect.height() * h)


def words(p, rect, info, k, ink, style, part, scale=1.0, ink2=None, top=True):
    C.title_block(p, box(rect, *part), info, k, ink, style, ink2=ink2, scale=scale, top_in_box=top)


def verse(p, rect, info, k, ink, y, w=0.66, size=14):
    C.plain_text(p, ink, info.get("verse", ""), rect.center().x(), rect.top() + rect.height() * y, k,
                 rect.width() * w, size)


def rounded_top(l, t, w, b):
    """A shape with a round top (an arch, a tablet)."""
    path = QPainterPath()
    path.moveTo(l, b)
    path.lineTo(l, t + w / 2)
    path.arcTo(QRectF(l, t, w, w), 180, -180)
    path.lineTo(l + w, b)
    path.closeSubpath()
    return path


def outline(p, ink, path, w):
    p.setBrush(Qt.NoBrush)
    p.setPen(ink.pen(w))
    p.drawPath(path)


def text_right(p, ink, text, font, right, baseline):
    C.draw_text(p, ink, text, font, right - C.text_width(font, text) / 2, baseline)


# ---------------------------------------------------------------- extras of the ground

def ex_waves(p, rect, k, style, front):
    cols = style.get("waves", ("#7fb2d9", "#4f8fc0", "#2c6aa0", "#1b4d7c"))
    for i, col in enumerate(cols):
        y0 = rect.top() + rect.height() * (0.66 + i * 0.075)
        path = QPainterPath()
        path.moveTo(rect.left(), rect.bottom())
        path.lineTo(rect.left(), y0)
        n = 60
        for j in range(n + 1):
            x = rect.left() + rect.width() * j / n
            y = y0 + math.sin(j / n * math.pi * (5 + i) + i) * 7 * k
            path.lineTo(x, y)
        path.lineTo(rect.right(), rect.bottom())
        path.closeSubpath()
        fill(p, path, col)


def ex_dunes(p, rect, k, style, front):
    if front:
        c = QPointF(rect.center().x(), rect.top() + rect.height() * 0.66)
        g = QRadialGradient(c, rect.width() * 0.5)
        g.setColorAt(0, QColor(255, 236, 170, 230))
        g.setColorAt(1, QColor(255, 236, 170, 0))
        fill(p, QRectF(rect.left(), rect.top(), rect.width(), rect.height() * 0.7), QBrush(g))
        p.setBrush(QColor("#ffd27a"))
        p.drawEllipse(c, rect.width() * 0.13, rect.width() * 0.13)
    for i, (top, col) in enumerate(((0.64, "#d99a5b"), (0.72, "#c47f42"), (0.82, "#a8632f"), (0.9, "#874b22"))):
        y = rect.top() + rect.height() * top
        path = QPainterPath()
        path.moveTo(rect.left(), rect.bottom())
        path.lineTo(rect.left(), y + 12 * k)
        path.cubicTo(rect.left() + rect.width() * (0.3 + 0.1 * i), y - 26 * k,
                     rect.left() + rect.width() * (0.55 - 0.08 * i), y + 30 * k, rect.right(), y - 6 * k)
        path.lineTo(rect.right(), rect.bottom())
        path.closeSubpath()
        fill(p, path, col)


def ex_skyline(p, rect, k, style, front):
    """The walls and towers of Jerusalem, dark against the sky."""
    col = QColor(style.get("skyline", "#2a1a2e"))
    base = rect.top() + rect.height() * 0.8
    fill(p, QRectF(rect.left(), base, rect.width(), rect.bottom() - base), col)
    rnd = random.Random(3)
    x = rect.left()
    while x < rect.right():
        w = (14 + rnd.random() * 26) * k
        h = (10 + rnd.random() * 40) * k
        kind = rnd.random()
        path = QPainterPath()
        path.addRect(QRectF(x, base - h, w, h + 1))
        if kind < 0.18:     # a dome
            path.addEllipse(QPointF(x + w / 2, base - h), w * 0.45, w * 0.45)
        elif kind < 0.5:    # battlements
            for j in range(int(w // (5 * k))):
                path.addRect(QRectF(x + j * 5 * k, base - h - 4 * k, 2.6 * k, 4 * k))
        fill(p, path, col)
        x += w
    if front:
        # the dome of a great building in the middle
        cx = rect.center().x()
        path = QPainterPath()
        path.addRect(QRectF(cx - 34 * k, base - 52 * k, 68 * k, 53 * k))
        path.addEllipse(QPointF(cx, base - 52 * k), 26 * k, 26 * k)
        fill(p, path, col)
        p.setBrush(C.gold(rect))
        p.drawEllipse(QPointF(cx, base - 56 * k), 24 * k, 22 * k)


def ex_mountain(p, rect, k, style, front):
    base = rect.bottom()
    peak = QPointF(rect.center().x() + rect.width() * 0.05, rect.top() + rect.height() * 0.58)
    if front:
        for i in range(-10, 11):
            a = -math.pi / 2 + i * 0.12
            end = QPointF(peak.x() + math.cos(a) * rect.height() * 0.6, peak.y() + math.sin(a) * rect.height() * 0.6)
            p.setPen(QPen(QColor(255, 240, 190, 70), (2.5 if i % 2 else 1.2) * k))
            p.drawLine(peak, end)
    path = QPainterPath()
    path.moveTo(rect.left(), base)
    path.lineTo(rect.left(), rect.top() + rect.height() * 0.8)
    path.lineTo(rect.left() + rect.width() * 0.25, rect.top() + rect.height() * 0.7)
    path.lineTo(peak)
    path.lineTo(rect.left() + rect.width() * 0.8, rect.top() + rect.height() * 0.74)
    path.lineTo(rect.right(), rect.top() + rect.height() * 0.78)
    path.lineTo(rect.right(), base)
    path.closeSubpath()
    fill(p, path, vgrad(rect, "#6d5a4b", "#3b2e25"))


def ex_rainbow(p, rect, k, style, front):
    if not front:
        return
    c = QPointF(rect.center().x(), rect.top() + rect.height() * 0.62)
    r0 = rect.width() * 0.62
    for i, col in enumerate(("#e5484d", "#f08c3a", "#f2c94c", "#5cb85c", "#3b8fd9", "#5b5bd6", "#8e5bd6")):
        r = r0 - i * 7 * k
        pen = QPen(QColor(col), 7 * k)
        pen.setColor(QColor(QColor(col).red(), QColor(col).green(), QColor(col).blue(), 120))
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), 0, 180 * 16)
    for (x, y, s) in ((0.15, 0.62, 1.0), (0.85, 0.6, 1.2), (0.5, 0.86, 1.4)):
        cx, cy = rect.left() + rect.width() * x, rect.top() + rect.height() * y
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 235))
        for dx, dy, r in ((-18, 4, 14), (0, -6, 18), (18, 4, 14), (6, 8, 14)):
            p.drawEllipse(QPointF(cx + dx * k * s, cy + dy * k * s), r * k * s, r * k * s)


def ex_lattice(p, rect, k, style, front):
    ink = C.Ink(rect, True, style)
    step = 26 * k
    p.setOpacity(0.35)
    n = int((rect.width() + rect.height()) / step) + 2
    for i in range(-n, n):
        x = rect.left() + i * step
        p.setPen(ink.pen(0.6 * k))
        p.drawLine(QPointF(x, rect.top()), QPointF(x + rect.height(), rect.bottom()))
        p.drawLine(QPointF(x, rect.bottom()), QPointF(x + rect.height(), rect.top()))
    p.setOpacity(1.0)


def ex_mosaic(p, rect, k, style, front):
    a, b = style.get("tiles", ("#1c3c6b", "#244b84"))
    s = 18 * k
    rows = int(rect.height() / s) + 2
    cols = int(rect.width() / s) + 2
    for r in range(rows):
        for c in range(cols):
            cx = rect.left() + c * s + (s / 2 if r % 2 else 0)
            cy = rect.top() + r * s * 0.5
            path = QPainterPath()
            path.moveTo(cx, cy - s / 2)
            path.lineTo(cx + s / 2, cy)
            path.lineTo(cx, cy + s / 2)
            path.lineTo(cx - s / 2, cy)
            path.closeSubpath()
            fill(p, path, a if (r + c) % 3 else b)
    ink = C.Ink(rect, True, style)
    p.setOpacity(0.5)
    for r in range(rows):
        y = rect.top() + r * s * 0.5
        for c in range(cols):
            cx = rect.left() + c * s + (s / 2 if r % 2 else 0)
            p.setPen(Qt.NoPen)
            p.setBrush(ink.brush)
            p.drawEllipse(QPointF(cx, y), 0.9 * k, 0.9 * k)
    p.setOpacity(1.0)


def ex_letters(p, rect, k, style, front):
    rnd = random.Random(9)
    letters = "אבגדהוזחטיכלמנסעפצקרשת"
    col = QColor(style.get("letters", "#ffffff"))
    for _ in range(int(rect.width() * rect.height() / 900)):
        f = C.qf(C.TITLE_FONT, (10 + rnd.random() * 34) * k)
        x = rect.left() + rnd.random() * rect.width()
        y = rect.top() + rnd.random() * rect.height()
        path = QPainterPath()
        path.addText(QPointF(x, y), f, rnd.choice(letters))
        fill(p, path, QColor(col.red(), col.green(), col.blue(), int(14 + rnd.random() * 26)))


def ex_tallit(p, rect, k, style, front):
    col = QColor(style.get("stripes", "#1b2a4a"))
    for y0 in (rect.top() + rect.height() * 0.08, rect.bottom() - rect.height() * 0.08 - 46 * k):
        y = y0
        for w in (12, 3, 3, 3, 12):
            fill(p, QRectF(rect.left(), y, rect.width(), w * k), col)
            y += (w + 4) * k


def ex_marble(p, rect, k, style, front):
    rnd = random.Random(21)
    for _ in range(40):
        path = QPainterPath()
        x = rect.left() + rnd.random() * rect.width()
        y = rect.top() + rnd.random() * rect.height()
        path.moveTo(x, y)
        for _ in range(4):
            x2 = x + (rnd.random() - 0.3) * 160 * k
            y2 = y + (rnd.random() - 0.5) * 120 * k
            path.cubicTo(x + (rnd.random() - 0.5) * 80 * k, y + (rnd.random() - 0.5) * 80 * k,
                         x2 + (rnd.random() - 0.5) * 60 * k, y2 + (rnd.random() - 0.5) * 60 * k, x2, y2)
            x, y = x2, y2
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(90, 90, 100, int(15 + rnd.random() * 40)), (0.3 + rnd.random() * 1.4) * k))
        p.drawPath(path)


def ex_moon(p, rect, k, style, front):
    if not front:
        return
    c = QPointF(rect.left() + rect.width() * 0.78, rect.top() + rect.height() * 0.13)
    r = 18 * k
    g = QRadialGradient(c, r * 3)
    g.setColorAt(0, QColor(255, 250, 220, 90))
    g.setColorAt(1, QColor(255, 250, 220, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(c, r * 3, r * 3)
    path = QPainterPath()
    path.addEllipse(c, r, r)
    cut = QPainterPath()
    cut.addEllipse(QPointF(c.x() + r * 0.45, c.y() - r * 0.2), r * 0.9, r * 0.9)
    fill(p, path.subtracted(cut), "#fff6d5")


def ex_night_hills(p, rect, k, style, front):
    for top, col in ((0.72, "#1d3b3a"), (0.8, "#15302d"), (0.88, "#0d211f")):
        y = rect.top() + rect.height() * top
        path = QPainterPath()
        path.moveTo(rect.left(), rect.bottom())
        path.lineTo(rect.left(), y)
        n = 4
        for i in range(n):
            path.quadTo(rect.left() + rect.width() * (i + 0.5) / n, y - (16 + 8 * math.sin(i * 2 + top * 9)) * k,
                        rect.left() + rect.width() * (i + 1) / n, y + 6 * k * math.sin(i + top * 7))
        path.lineTo(rect.right(), rect.bottom())
        path.closeSubpath()
        fill(p, path, col)


def ex_stars(p, rect, k, style, front):
    C.stars(p, rect, k, 5)


def ex_glow(p, rect, k, style, front):
    """Light breaking out from above the middle: 'ויהי אור'."""
    c = QPointF(rect.center().x(), rect.top() + rect.height() * 0.3)
    p.setPen(Qt.NoPen)
    for i in range(36):
        a = i * math.pi * 2 / 36
        path = QPainterPath()
        path.moveTo(c)
        L = rect.height()
        path.lineTo(c.x() + math.cos(a - 0.03) * L, c.y() + math.sin(a - 0.03) * L)
        path.lineTo(c.x() + math.cos(a + 0.03) * L, c.y() + math.sin(a + 0.03) * L)
        path.closeSubpath()
        fill(p, path, QColor(255, 236, 180, 22 if i % 2 else 12))
    g = QRadialGradient(c, rect.width() * 0.5)
    g.setColorAt(0, QColor(255, 246, 210, 220))
    g.setColorAt(0.35, QColor(255, 220, 140, 90))
    g.setColorAt(1, QColor(255, 220, 140, 0))
    fill(p, QRectF(rect), QBrush(g))


EXTRAS = {"waves": ex_waves, "dunes": ex_dunes, "skyline": ex_skyline, "mountain": ex_mountain,
          "rainbow": ex_rainbow, "lattice": ex_lattice, "mosaic": ex_mosaic, "letters": ex_letters,
          "tallit": ex_tallit, "marble": ex_marble, "moon": ex_moon, "night_hills": ex_night_hills,
          "stars": ex_stars, "glow": ex_glow}


def extras(p, rect, style, k, front):
    for name in style.get("extras", ()):
        EXTRAS[name](p, rect, k, style, front)


# ---------------------------------------------------------------- the layouts

def lay_panel(p, rect, info, k, ink, style):
    inner = C.frame(p, ink, rect, k, style.get("frame", "ornate"), False)
    pan = inner.adjusted(inner.width() * 0.08, inner.height() * 0.1, -inner.width() * 0.08, -inner.height() * 0.24)
    fill(p, pan, style["field"])
    p.setBrush(Qt.NoBrush)
    p.setPen(ink.pen(1.8 * k))
    p.drawRect(pan)
    p.setPen(ink.pen(0.6 * k))
    p.drawRect(pan.adjusted(5 * k, 5 * k, -5 * k, -5 * k))
    for pt in (pan.topLeft(), pan.topRight(), pan.bottomLeft(), pan.bottomRight()):
        C.rosette(p, ink, pt, 9 * k)
    C.title_block(p, pan.adjusted(18 * k, 18 * k, -18 * k, -18 * k), info, k, ink, style, scale=0.92)
    C.cartouche(p, ink, QRectF(rect.center().x() - inner.width() * 0.33, (pan.bottom() + inner.bottom()) / 2 - 18 * k,
                               inner.width() * 0.66, 36 * k), info.get("verse", ""), k)


def lay_scroll(p, rect, info, k, ink, style):
    """A Torah scroll: parchment between two rollers (atzei chaim)."""
    W, H = rect.width(), rect.height()
    par = box(rect, 0.2, 0.17, 0.6, 0.6)
    fill(p, par.translated(3 * k, 4 * k), QColor(0, 0, 0, 80))
    fill(p, par, hgrad(par, "#e2d2a8", "#f3e7c8", "#f6ecd2", "#f3e7c8", "#e2d2a8"))
    for x in (par.left(), par.right()):
        rod = QRectF(x - 12 * k, par.top() - 6 * k, 24 * k, par.height() + 12 * k)
        fill(p, rod, hgrad(rod, "#4a2c17", "#8a5a33", "#5b371d"))
        for y, d in ((par.top() - 6 * k, -1), (par.bottom() + 6 * k, 1)):
            handle = QRectF(x - 4 * k, min(y, y + d * 34 * k), 8 * k, 34 * k)
            fill(p, handle, hgrad(handle, "#4a2c17", "#9a6a3e", "#4a2c17"))
            p.setBrush(ink.brush)
            p.drawEllipse(QPointF(x, y + d * 8 * k), 15 * k, 5 * k)
            p.drawEllipse(QPointF(x, y + d * 36 * k), 7 * k, 7 * k)
    dark = C.solid(style.get("ink2", "#3a2412"))
    p.setPen(dark.pen(0.5 * k))
    for y in (par.top() + 10 * k, par.bottom() - 10 * k):
        p.drawLine(QPointF(par.left() + 22 * k, y), QPointF(par.right() - 22 * k, y))
    C.title_block(p, par.adjusted(30 * k, 20 * k, -30 * k, -20 * k), info, k, dark, dict({"divider": "line"}, **style), scale=0.82)
    verse(p, rect, info, k, ink, 0.88)


def lay_luchot(p, rect, info, k, ink, style):
    """The tablets of the covenant, the title above and the rest below."""
    W, H = rect.width(), rect.height()
    words(p, rect, dict(info, lines=[], details="", extra=""), k, ink, style, (0.08, 0.05, 0.84, 0.3))
    tw, top, bot = W * 0.26, rect.top() + H * 0.37, rect.top() + H * 0.68
    rows = ("א ב ג ד ה", "ו ז ח ט י")
    for i, x in enumerate((rect.center().x() - tw - 4 * k, rect.center().x() + 4 * k)):
        shape = rounded_top(x, top, tw, bot)
        fill(p, shape, vgrad(QRectF(x, top, tw, bot - top), "#e9e4d6", "#cfc6b1"))
        outline(p, ink, shape, 1.6 * k)
        letters = rows[1 - i].split()
        f = C.qf(C.TITLE_FONT, 17 * k)
        for j, L in enumerate(letters):
            y = top + tw * 0.45 + j * (bot - top - tw * 0.45) / 5.4 + 16 * k
            C.draw_text(p, C.solid("#3b3326"), L, f, x + tw / 2, y, emboss=False)
    words(p, rect, dict(info, top="", title=""), k, ink, dict({"divider": "line"}, **style), (0.08, 0.69, 0.84, 0.19), top=False)
    verse(p, rect, info, k, ink, 0.93, size=12)


def menorah(p, ink, c, w, k):
    """A menorah of seven branches standing on c (the foot of its stem), w wide."""
    h = w * 0.62
    top = c.y() - h
    p.setBrush(Qt.NoBrush)
    for i in range(1, 4):
        r = w / 2 * i / 3
        p.setPen(ink.pen(3.2 * k))
        p.drawArc(QRectF(c.x() - r, top + h * 0.15 - r, 2 * r, 2 * r), 180 * 16, 180 * 16)
    p.drawLine(QPointF(c.x(), top), QPointF(c.x(), c.y()))
    for i in range(-3, 4):
        x = c.x() + w / 2 * i / 3
        p.setPen(Qt.NoPen)
        p.setBrush(ink.brush)
        p.drawRect(QRectF(x - 4 * k, top - 3 * k, 8 * k, 4 * k))
        flame = QPainterPath()
        flame.moveTo(x, top - 18 * k)
        flame.quadTo(x + 5 * k, top - 9 * k, x, top - 4 * k)
        flame.quadTo(x - 5 * k, top - 9 * k, x, top - 18 * k)
        fill(p, flame, QColor("#ffcf5a"))
    base = QPainterPath()
    base.moveTo(c.x() - w * 0.16, c.y())
    base.lineTo(c.x() + w * 0.16, c.y())
    base.lineTo(c.x() + w * 0.04, c.y() - h * 0.12)
    base.lineTo(c.x() - w * 0.04, c.y() - h * 0.12)
    base.closeSubpath()
    fill(p, base, ink.brush)


def lay_menorah(p, rect, info, k, ink, style):
    inner = C.frame(p, ink, rect, k, style.get("frame", "double"), False)
    words(p, rect, info, k, ink, style, (0.1, 0.06, 0.8, 0.5), scale=0.9)
    menorah(p, ink, QPointF(rect.center().x(), rect.top() + rect.height() * 0.84), rect.width() * 0.5, k)
    verse(p, rect, info, k, ink, 0.9, size=12)


def crown(p, ink, c, w, k):
    h = w * 0.55
    path = QPainterPath()
    l, r, b = c.x() - w / 2, c.x() + w / 2, c.y()
    path.moveTo(l, b)
    pts = 5
    for i in range(pts + 1):
        x = l + w * i / pts
        y_peak = b - h if i % 1 == 0 else b
        if i == 0:
            path.lineTo(x, b - h * 0.8)
        else:
            path.lineTo(x - w / pts / 2, b - h * 0.42)
            path.lineTo(x, b - h * (0.8 if i in (0, pts) else 1.0))
    path.lineTo(r, b)
    path.closeSubpath()
    fill(p, path, ink.brush)
    for i in range(pts + 1):
        x = l + w * i / pts
        y = b - h * (0.8 if i in (0, pts) else 1.0)
        p.setBrush(ink.brush)
        p.drawEllipse(QPointF(x, y - 5 * k), 5 * k, 5 * k)
    band = QRectF(l - 4 * k, b - 4 * k, w + 8 * k, 14 * k)
    fill(p, band, ink.brush)
    for i in range(5):
        p.setBrush(QColor("#7a0f1c") if i % 2 else QColor("#1e3f8a"))
        p.drawEllipse(QPointF(l + w * (i + 0.5) / 5, b + 3 * k), 3.5 * k, 3.5 * k)


def lay_crown(p, rect, info, k, ink, style):
    C.frame(p, ink, rect, k, style.get("frame", "single"), True)
    crown(p, ink, QPointF(rect.center().x(), rect.top() + rect.height() * 0.24), rect.width() * 0.3, k)
    words(p, rect, info, k, ink, style, (0.08, 0.28, 0.84, 0.48))
    verse(p, rect, info, k, ink, 0.86)


def lay_skyline(p, rect, info, k, ink, style):
    words(p, rect, info, k, ink, style, (0.08, 0.08, 0.84, 0.5))
    verse(p, rect, info, k, C.solid("#f3d9a6"), 0.91)


def lay_waves(p, rect, info, k, ink, style):
    words(p, rect, info, k, ink, style, (0.08, 0.1, 0.84, 0.5))
    verse(p, rect, info, k, C.solid("#ffffff"), 0.93)


def lay_mosaic(p, rect, info, k, ink, style):
    pan = box(rect, 0.12, 0.14, 0.76, 0.64)
    fill(p, pan.translated(3 * k, 4 * k), QColor(0, 0, 0, 90))
    fill(p, pan, style["field"])
    p.setBrush(Qt.NoBrush)
    p.setPen(ink.pen(1.4 * k))
    p.drawRect(pan.adjusted(6 * k, 6 * k, -6 * k, -6 * k))
    C.title_block(p, pan.adjusted(20 * k, 20 * k, -20 * k, -20 * k), info, k, ink, style, scale=0.9)
    vb = box(rect, 0.2, 0.84, 0.6, 0.07)
    fill(p, vb, style["field"])
    C.plain_text(p, ink, info.get("verse", ""), vb.center().x(), vb.center().y(), k, vb.width() * 0.92, 12)


def hexagram(p, ink, c, r, k, w=1.6):
    for rot in (-90, 90):
        path = QPainterPath()
        for i in range(3):
            a = math.radians(rot + i * 120)
            pt = QPointF(c.x() + r * math.cos(a), c.y() + r * math.sin(a))
            path.moveTo(pt) if i == 0 else path.lineTo(pt)
        path.closeSubpath()
        outline(p, ink, path, w * k)


def lay_hexagram(p, rect, info, k, ink, style):
    c = QPointF(rect.center().x(), rect.top() + rect.height() * 0.42)
    p.setOpacity(0.55)
    hexagram(p, ink, c, rect.width() * 0.44, k, 2.4)
    hexagram(p, ink, c, rect.width() * 0.44 - 8 * k, k, 0.7)
    p.setOpacity(1.0)
    words(p, rect, info, k, ink, style, (0.12, 0.22, 0.76, 0.42), scale=0.85)
    verse(p, rect, info, k, ink, 0.86)


def vine(p, ink, x, top, bottom, k, side):
    path = QPainterPath()
    n = 120
    for i in range(n + 1):
        y = top + (bottom - top) * i / n
        xx = x + side * 8 * k * math.sin(i / n * math.pi * 9)
        path.moveTo(xx, y) if i == 0 else path.lineTo(xx, y)
    outline(p, ink, path, 1.2 * k)
    for i in range(18):
        y = top + (bottom - top) * (i + 0.5) / 18
        xx = x + side * 8 * k * math.sin((i + 0.5) / 18 * math.pi * 9)
        s = 1 if i % 2 else -1
        leaf = QPainterPath()
        leaf.moveTo(xx, y)
        leaf.quadTo(xx + s * 9 * k, y - 10 * k, xx + s * 16 * k, y - 4 * k)
        leaf.quadTo(xx + s * 8 * k, y + 2 * k, xx, y)
        fill(p, leaf, ink.brush)
        if i % 3 == 1:
            for gx, gy in ((0, 0), (4, 0), (2, 3.5), (6, 3.5), (4, 7), (3, 10.5)):
                p.setBrush(ink.brush)
                p.drawEllipse(QPointF(xx - s * (6 + gx) * k, y + (4 + gy) * k), 2.1 * k, 2.1 * k)


def lay_vine(p, rect, info, k, ink, style):
    m = rect.width() * 0.08
    for x, side in ((rect.left() + m, 1), (rect.right() - m, -1)):
        vine(p, ink, x, rect.top() + 30 * k, rect.bottom() - 30 * k, k, side)
    words(p, rect, info, k, ink, style, (0.16, 0.14, 0.68, 0.56), scale=0.88)
    verse(p, rect, info, k, ink, 0.84, w=0.6)


def lay_diagonal(p, rect, info, k, ink, style):
    W, H = rect.width(), rect.height()
    path = QPainterPath()
    path.moveTo(rect.left() - 20, rect.top() + H * 0.72)
    path.lineTo(rect.right() + 20, rect.top() + H * 0.5)
    path.lineTo(rect.right() + 20, rect.top() + H * 0.66)
    path.lineTo(rect.left() - 20, rect.top() + H * 0.88)
    path.closeSubpath()
    fill(p, path, style["field"])
    gl = C.Ink(rect, True, dict(style, ink="gold"))
    p.setPen(gl.pen(1.4 * k))
    p.drawLine(QPointF(rect.left() - 20, rect.top() + H * 0.70), QPointF(rect.right() + 20, rect.top() + H * 0.48))
    words(p, rect, info, k, ink, dict({"divider": "line"}, **style), (0.08, 0.06, 0.84, 0.42))
    p.save()
    p.translate(rect.center().x(), rect.top() + H * 0.69)
    p.rotate(-math.degrees(math.atan2(H * 0.22, W)))
    f = C.fit_font(C.TEXT_FONT, 15 * k, info.get("verse", ""), W * 0.8)
    C.draw_text(p, C.solid(style.get("ink2", "#ffffff")), info.get("verse", ""), f, 0, f.pointSizeF() * 0.35)
    p.restore()


def lay_circle(p, rect, info, k, ink, style):
    c = QPointF(rect.center().x(), rect.top() + rect.height() * 0.42)
    r = rect.width() * 0.42
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(style["field"]))
    p.drawEllipse(c, r, r)
    gl = C.Ink(rect, True, dict(style, ink="gold"))
    p.setBrush(Qt.NoBrush)
    p.setPen(gl.pen(1.0 * k))
    p.drawEllipse(c, r + 7 * k, r + 7 * k)
    C.title_block(p, QRectF(c.x() - r * 0.8, c.y() - r * 0.7, r * 1.6, r * 1.4), info, k, ink,
                  dict({"divider": "line"}, **style), scale=0.8)
    verse(p, rect, info, k, C.solid(style.get("ink2", "#333333")), 0.88)


def lay_border_text(p, rect, info, k, ink, style):
    """The verse runs round the frame on all four sides."""
    m = 26 * k
    inner = rect.adjusted(m, m, -m, -m)
    p.setBrush(Qt.NoBrush)
    p.setPen(ink.pen(1.0 * k))
    p.drawRect(inner)
    p.drawRect(inner.adjusted(22 * k, 22 * k, -22 * k, -22 * k))
    text = info.get("verse", "")
    f = C.qf(C.TEXT_FONT, 11 * k)
    for (cx, cy, rot, length) in ((inner.center().x(), inner.top() + 11 * k, 0, inner.width()),
                                  (inner.right() - 11 * k, inner.center().y(), 90, inner.height()),
                                  (inner.center().x(), inner.bottom() - 11 * k, 180, inner.width()),
                                  (inner.left() + 11 * k, inner.center().y(), 270, inner.height())):
        p.save()
        p.translate(cx, cy)
        p.rotate(rot)
        tw = C.text_width(f, text + "  ·  ")
        reps = max(1, int((length - 40 * k) // tw))
        C.draw_text(p, ink, "  ·  ".join([text] * reps), f, 0, 4 * k, emboss=False)
        p.restore()
    words(p, rect, info, k, ink, style, (0.12, 0.16, 0.76, 0.66))


def pillar(p, ink, x, top, bottom, w, k, brush):
    shaft = QRectF(x - w / 2, top + 26 * k, w, bottom - top - 44 * k)
    fill(p, shaft, brush)
    p.setPen(QPen(QColor(0, 0, 0, 50), 0.8 * k))
    for i in range(1, 5):
        xx = shaft.left() + shaft.width() * i / 5
        p.drawLine(QPointF(xx, shaft.top()), QPointF(xx, shaft.bottom()))
    fill(p, QRectF(x - w * 0.75, top + 14 * k, w * 1.5, 12 * k), brush)
    fill(p, QRectF(x - w * 0.62, top, w * 1.24, 14 * k), brush)
    for s in (-1, 1):
        C.scroll(p, ink, QPointF(x + s * w * 0.4, top + 20 * k), w * 0.6, flip=s)
    fill(p, QRectF(x - w * 0.7, bottom - 18 * k, w * 1.4, 8 * k), brush)
    fill(p, QRectF(x - w * 0.85, bottom - 10 * k, w * 1.7, 10 * k), brush)
    p.setBrush(Qt.NoBrush)
    p.setPen(ink.pen(0.8 * k))
    p.drawRect(shaft)


def lay_columns(p, rect, info, k, ink, style):
    W, H = rect.width(), rect.height()
    top, bottom = rect.top() + H * 0.12, rect.top() + H * 0.9
    brush = vgrad(rect, *style.get("stone", ("#e8e2d3", "#cfc5b0")))
    for x in (rect.left() + W * 0.13, rect.right() - W * 0.13):
        pillar(p, ink, x, top, bottom, W * 0.09, k, brush)
    lint = QRectF(rect.left() + W * 0.05, top - 26 * k, W * 0.9, 22 * k)
    fill(p, lint, brush)
    p.setBrush(Qt.NoBrush)
    p.setPen(ink.pen(0.9 * k))
    p.drawRect(lint)
    for i in range(5):
        C.rosette(p, ink, QPointF(lint.left() + lint.width() * (i + 0.5) / 5, lint.center().y()), 7 * k)
    words(p, rect, info, k, C.solid(style.get("ink2", "#2b2418")), style, (0.24, 0.2, 0.52, 0.56), scale=0.78)
    verse(p, rect, info, k, C.solid(style.get("ink2", "#2b2418")), 0.86, w=0.5, size=11)


def lay_light(p, rect, info, k, ink, style):
    words(p, rect, info, k, ink, style, (0.08, 0.36, 0.84, 0.46))
    verse(p, rect, info, k, ink, 0.89)


def lay_dunes(p, rect, info, k, ink, style):
    words(p, rect, info, k, ink, style, (0.08, 0.06, 0.84, 0.46))
    verse(p, rect, info, k, C.solid("#fff1d6"), 0.95, size=12)


def tree(p, ink, base, h, k):
    """A tree of life: a trunk, branches curling out, leaves at their ends."""
    rnd = random.Random(4)

    def branch(x, y, a, length, width, depth):
        x2 = x + math.cos(a) * length
        y2 = y + math.sin(a) * length
        path = QPainterPath()
        path.moveTo(x, y)
        path.quadTo(x + math.cos(a + 0.3) * length * 0.5, y + math.sin(a + 0.3) * length * 0.5, x2, y2)
        p.setBrush(Qt.NoBrush)
        p.setPen(ink.pen(width))
        p.drawPath(path)
        if depth == 0:
            for _ in range(5):
                lx = x2 + (rnd.random() - 0.5) * 18 * k
                ly = y2 + (rnd.random() - 0.5) * 18 * k
                leaf = QPainterPath()
                la = rnd.random() * math.pi * 2
                leaf.moveTo(lx, ly)
                leaf.quadTo(lx + math.cos(la + 0.6) * 9 * k, ly + math.sin(la + 0.6) * 9 * k,
                            lx + math.cos(la) * 14 * k, ly + math.sin(la) * 14 * k)
                leaf.quadTo(lx + math.cos(la - 0.6) * 9 * k, ly + math.sin(la - 0.6) * 9 * k, lx, ly)
                fill(p, leaf, ink.brush)
            return
        for d in (-0.5, 0.45):
            branch(x2, y2, a + d + (rnd.random() - 0.5) * 0.2, length * 0.72, width * 0.66, depth - 1)

    branch(base.x(), base.y(), -math.pi / 2, h * 0.34, 7 * k, 5)


def lay_tree(p, rect, info, k, ink, style):
    C.frame(p, ink, rect, k, style.get("frame", "double"), False)
    p.setOpacity(0.9)
    tree(p, ink, QPointF(rect.center().x(), rect.top() + rect.height() * 0.9), rect.height() * 0.95, k)
    p.setOpacity(1.0)
    pan = box(rect, 0.14, 0.12, 0.72, 0.4)
    under = QColor(style["bg"][1][1])
    under.setAlpha(215)
    fill(p, pan, under)
    C.title_block(p, pan.adjusted(10 * k, 10 * k, -10 * k, -10 * k), info, k, ink, style, scale=0.85)
    verse(p, rect, info, k, ink, 0.95, size=11)


def scallop(rect, r):
    """A rectangle with a scalloped edge (papercut)."""
    path = QPainterPath()
    path.addRect(rect)
    holes = QPainterPath()
    for edge in ("t", "b", "l", "r"):
        length = rect.width() if edge in "tb" else rect.height()
        n = int(length // (2 * r))
        for i in range(n):
            t = (i + 0.5) * length / n
            if edge == "t":
                c = QPointF(rect.left() + t, rect.top())
            elif edge == "b":
                c = QPointF(rect.left() + t, rect.bottom())
            elif edge == "l":
                c = QPointF(rect.left(), rect.top() + t)
            else:
                c = QPointF(rect.right(), rect.top() + t)
            holes.addEllipse(c, r * 0.9, r * 0.9)
    return path.subtracted(holes)


def lay_papercut(p, rect, info, k, ink, style):
    pan = box(rect, 0.09, 0.07, 0.82, 0.86)
    shape = scallop(pan, 8 * k)
    fill(p, shape.translated(2 * k, 3 * k), QColor(0, 0, 0, 60))
    fill(p, shape, style.get("panel", "#ffffff"))
    inner = pan.adjusted(20 * k, 20 * k, -20 * k, -20 * k)
    holes = QPainterPath()
    for i in range(int(inner.width() // (14 * k))):
        x = inner.left() + (i + 0.5) * inner.width() / int(inner.width() // (14 * k))
        for y in (inner.top() + 4 * k, inner.bottom() - 4 * k):
            path = QPainterPath()
            path.moveTo(x, y - 4 * k)
            path.lineTo(x + 4 * k, y)
            path.lineTo(x, y + 4 * k)
            path.lineTo(x - 4 * k, y)
            path.closeSubpath()
            holes.addPath(path)
    fill(p, holes, style["bg"][1][1])
    dark = C.solid(style["ink2"])
    C.title_block(p, inner.adjusted(10 * k, 30 * k, -10 * k, -inner.height() * 0.22), info, k, dark,
                  dict({"divider": "line"}, **style), scale=0.9)
    C.plain_text(p, dark, info.get("verse", ""), rect.center().x(), inner.bottom() - inner.height() * 0.09, k,
                 inner.width() * 0.8, 12)


def lay_tallit(p, rect, info, k, ink, style):
    words(p, rect, info, k, ink, dict({"divider": "line"}, **style), (0.08, 0.24, 0.84, 0.46))
    verse(p, rect, info, k, ink, 0.76)


def lay_editorial(p, rect, info, k, ink, style):
    """Large type set to the right, a rule, and the rest under it — as a magazine."""
    W, H = rect.width(), rect.height()
    right = rect.right() - W * 0.1
    y = rect.top() + H * 0.12
    if info.get("top"):
        f = C.qf(C.TEXT_FONT, 16 * k)
        text_right(p, ink, info["top"], f, right, y)
    parts = info["title"].split()
    y += 20 * k
    for t in parts:
        f = C.fit_font(style.get("title_font", C.TITLE_FONT), 92 * k, t, W * 0.8)
        y += f.pointSizeF() * 0.95
        text_right(p, ink, t, f, right, y)
    y += 18 * k
    accent = C.solid(style.get("ink2", "#b23a2e"))
    p.setPen(accent.pen(3 * k))
    p.drawLine(QPointF(right, y), QPointF(right - W * 0.3, y))
    y += 12 * k
    for line in info.get("lines", []) + [info.get("details", ""), info.get("extra", "")]:
        if not line:
            continue
        f = C.fit_font(C.TEXT_FONT, 15 * k, line, W * 0.8)
        y += f.pointSizeF() * 1.6
        text_right(p, ink, line, f, right, y)
    f = C.fit_font(C.TEXT_FONT, 12 * k, info.get("verse", ""), W * 0.8)
    text_right(p, accent, info.get("verse", ""), f, right, rect.bottom() - H * 0.07)


def lay_stacked(p, rect, info, k, ink, style):
    """The title as large as the page allows, one word to a line."""
    W, H = rect.width(), rect.height()
    y = rect.top() + H * 0.14
    if info.get("top"):
        C.plain_text(p, ink, info["top"], rect.center().x(), y, k, W * 0.8, 18, C.TITLE_FONT)
    y += 20 * k
    for t in info["title"].split():
        f = C.fit_font(style.get("title_font", C.TITLE_FONT), 300 * k, t, W * 0.86)
        y += f.pointSizeF() * 0.9
        C.draw_text(p, ink, t, f, rect.center().x(), y)
    words(p, rect, dict(info, top="", title=""), k, C.solid(style.get("ink2", "#ffffff")),
          dict({"divider": "line"}, **style), (0.1, (y - rect.top()) / H + 0.02, 0.8, 0.24), top=False)
    verse(p, rect, info, k, ink, 0.93, size=12)


def lay_shield(p, rect, info, k, ink, style):
    W, H = rect.width(), rect.height()
    l, r, t, b = rect.left() + W * 0.14, rect.right() - W * 0.14, rect.top() + H * 0.1, rect.top() + H * 0.78
    path = QPainterPath()
    path.moveTo(l, t)
    path.lineTo(r, t)
    path.lineTo(r, t + (b - t) * 0.55)
    path.cubicTo(r, t + (b - t) * 0.85, rect.center().x() + W * 0.1, b - 10 * k, rect.center().x(), b)
    path.cubicTo(rect.center().x() - W * 0.1, b - 10 * k, l, t + (b - t) * 0.85, l, t + (b - t) * 0.55)
    path.closeSubpath()
    fill(p, path, style["field"])
    outline(p, ink, path, 2.2 * k)
    inner = QPainterPath(path)
    p.save()
    p.translate(rect.center().x(), (t + b) / 2)
    p.scale(0.94, 0.95)
    p.translate(-rect.center().x(), -(t + b) / 2)
    outline(p, ink, inner, 0.8 * k)
    p.restore()
    words(p, rect, info, k, ink, style, (0.2, 0.14, 0.6, 0.48), scale=0.8)
    verse(p, rect, info, k, ink, 0.88)


def lay_seal(p, rect, info, k, ink, style):
    C.frame(p, ink, rect, k, style.get("frame", "single"), False)
    words(p, rect, info, k, ink, style, (0.1, 0.08, 0.8, 0.52))
    c = QPointF(rect.center().x(), rect.top() + rect.height() * 0.76)
    rnd = random.Random(2)
    path = QPainterPath()
    n = 28
    for i in range(n + 1):
        a = i * math.pi * 2 / n
        rr = (38 + rnd.random() * 5) * k
        pt = QPointF(c.x() + math.cos(a) * rr, c.y() + math.sin(a) * rr)
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
    path.closeSubpath()
    g = QRadialGradient(QPointF(c.x() - 10 * k, c.y() - 10 * k), 50 * k)
    g.setColorAt(0, QColor("#c8343b"))
    g.setColorAt(1, QColor("#6e1015"))
    fill(p, path, QBrush(g))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(0, 0, 0, 70), 1.4 * k))
    p.drawEllipse(c, 27 * k, 27 * k)
    letter = info.get("title", " ").split()[-1][:1]
    f = C.qf(C.TITLE_FONT, 36 * k)
    C.draw_text(p, C.solid("#4a0a0e"), letter, f, c.x() + 0.8 * k, c.y() + 13 * k, emboss=False)
    C.draw_text(p, C.solid("#e1666c"), letter, f, c.x(), c.y() + 12 * k, emboss=False)
    verse(p, rect, info, k, ink, 0.91, size=12)


def lay_sinai(p, rect, info, k, ink, style):
    words(p, rect, info, k, ink, style, (0.08, 0.07, 0.84, 0.44))
    verse(p, rect, info, k, C.solid("#f3e3c3"), 0.93)


def lay_lattice(p, rect, info, k, ink, style):
    c = QPointF(rect.center().x(), rect.top() + rect.height() * 0.45)
    rx, ry = rect.width() * 0.4, rect.height() * 0.32
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(style["bg"][1][1]))
    p.drawEllipse(c, rx, ry)
    p.setBrush(Qt.NoBrush)
    p.setPen(ink.pen(2.0 * k))
    p.drawEllipse(c, rx, ry)
    p.setPen(ink.pen(0.7 * k))
    p.drawEllipse(c, rx - 6 * k, ry - 6 * k)
    C.title_block(p, QRectF(c.x() - rx * 0.78, c.y() - ry * 0.72, rx * 1.56, ry * 1.44), info, k, ink, style, scale=0.82)
    vb = box(rect, 0.18, 0.84, 0.64, 0.06)
    fill(p, vb, style["bg"][1][1])
    C.plain_text(p, ink, info.get("verse", ""), vb.center().x(), vb.center().y(), k, vb.width() * 0.9, 12)


def lay_corners(p, rect, info, k, ink, style):
    s = 46 * k
    m = 28 * k
    for (cx, cy, sx, sy) in ((rect.left() + m, rect.top() + m, 1, 1), (rect.right() - m, rect.top() + m, -1, 1),
                             (rect.right() - m, rect.bottom() - m, -1, -1), (rect.left() + m, rect.bottom() - m, 1, -1)):
        c = QPointF(cx + sx * s * 0.4, cy + sy * s * 0.4)
        C.rosette(p, ink, c, s * 0.42, petals=12)
        C.corner(p, ink, c, s, sx, sy)
        p.setPen(ink.pen(1.0 * k))
        p.drawLine(QPointF(cx, cy), QPointF(cx + sx * s * 2.6, cy))
        p.drawLine(QPointF(cx, cy), QPointF(cx, cy + sy * s * 2.6))
    words(p, rect, info, k, ink, style, (0.1, 0.2, 0.8, 0.54))
    verse(p, rect, info, k, ink, 0.82)


def lay_parchment(p, rect, info, k, ink, style):
    rnd = random.Random(8)
    pan = box(rect, 0.1, 0.1, 0.8, 0.76)
    path = QPainterPath()
    pts = []
    n = 24
    for i in range(n):
        pts.append(QPointF(pan.left() + pan.width() * i / n, pan.top() + (rnd.random() - 0.5) * 6 * k))
    for i in range(n):
        pts.append(QPointF(pan.right() + (rnd.random() - 0.5) * 6 * k, pan.top() + pan.height() * i / n))
    for i in range(n):
        pts.append(QPointF(pan.right() - pan.width() * i / n, pan.bottom() + (rnd.random() - 0.5) * 6 * k))
    for i in range(n):
        pts.append(QPointF(pan.left() + (rnd.random() - 0.5) * 6 * k, pan.bottom() - pan.height() * i / n))
    path.moveTo(pts[0])
    for pt in pts[1:]:
        path.lineTo(pt)
    path.closeSubpath()
    fill(p, path.translated(3 * k, 4 * k), QColor(0, 0, 0, 110))
    g = QRadialGradient(pan.center(), pan.width() * 0.75)
    g.setColorAt(0, QColor("#f4e8c8"))
    g.setColorAt(0.75, QColor("#e5d09f"))
    g.setColorAt(1, QColor("#c9a868"))
    fill(p, path, QBrush(g))
    dark = C.solid(style.get("ink2", "#3d2412"))
    C.title_block(p, pan.adjusted(26 * k, 30 * k, -26 * k, -pan.height() * 0.2), info, k, dark, style, scale=0.88)
    C.plain_text(p, dark, info.get("verse", ""), pan.center().x(), pan.bottom() - pan.height() * 0.1, k,
                 pan.width() * 0.8, 12)


def lay_rainbow(p, rect, info, k, ink, style):
    words(p, rect, info, k, ink, style, (0.08, 0.06, 0.84, 0.32), scale=0.85)
    verse(p, rect, info, k, ink, 0.95, size=12)


def lay_letters(p, rect, info, k, ink, style):
    pan = box(rect, 0.12, 0.2, 0.76, 0.52)
    fill(p, pan, style["field"])
    p.setBrush(Qt.NoBrush)
    p.setPen(ink.pen(1.2 * k))
    p.drawRect(pan.adjusted(-5 * k, -5 * k, 5 * k, 5 * k))
    C.title_block(p, pan.adjusted(16 * k, 16 * k, -16 * k, -16 * k), info, k, ink, dict({"divider": "line"}, **style), scale=0.88)
    verse(p, rect, info, k, ink, 0.84)


def lay_twin_arch(p, rect, info, k, ink, style):
    W, H = rect.width(), rect.height()
    aw = W * 0.3
    top, bot = rect.top() + H * 0.08, rect.top() + H * 0.5
    for x in (rect.center().x() - aw - 6 * k, rect.center().x() + 6 * k):
        shape = rounded_top(x, top, aw, bot)
        fill(p, shape, style["field"])
        outline(p, ink, shape, 1.6 * k)
        outline(p, ink, rounded_top(x + 6 * k, top + 6 * k, aw - 12 * k, bot - 6 * k), 0.6 * k)
        p.setPen(ink.pen(0.6 * k))
        p.drawLine(QPointF(x + aw / 2, top + aw * 0.5), QPointF(x + aw / 2, bot - 6 * k))
        p.drawLine(QPointF(x + 6 * k, top + aw * 0.95), QPointF(x + aw - 6 * k, top + aw * 0.95))
    hexagram(p, ink, QPointF(rect.center().x(), top + 10 * k), 12 * k, k, 1.0)
    p.setPen(ink.pen(1.4 * k))
    p.drawLine(QPointF(rect.left() + W * 0.12, bot + 4 * k), QPointF(rect.right() - W * 0.12, bot + 4 * k))
    words(p, rect, info, k, ink, style, (0.08, 0.52, 0.84, 0.36), scale=0.82)
    verse(p, rect, info, k, ink, 0.92, size=12)


LAYOUTS = {
    "panel": lay_panel, "scroll": lay_scroll, "luchot": lay_luchot, "menorah": lay_menorah, "crown": lay_crown,
    "skyline": lay_skyline, "waves": lay_waves, "mosaic": lay_mosaic, "hexagram": lay_hexagram, "vine": lay_vine,
    "diagonal": lay_diagonal, "circle": lay_circle, "border_text": lay_border_text, "columns": lay_columns,
    "light": lay_light, "dunes": lay_dunes, "tree": lay_tree, "papercut": lay_papercut, "tallit": lay_tallit,
    "editorial": lay_editorial, "stacked": lay_stacked, "shield": lay_shield, "seal": lay_seal, "sinai": lay_sinai,
    "lattice": lay_lattice, "corners": lay_corners, "parchment": lay_parchment, "rainbow": lay_rainbow,
    "letters": lay_letters, "twin_arch": lay_twin_arch,
}

D = C.TEXT_FONT
L1 = ("#5c151b", "#3b0c11", "#1f0508")
BLACK = ("#2b2a28", "#171615", "#060605")
NAVY = ("#1e2e5a", "#121d3d", "#070e22")
GREEN = ("#1f4a33", "#133222", "#07190f")
BROWN = ("#6e4624", "#4a2e17", "#25160a")

MORE_STYLES = [
    # 11-20: Jewish motifs
    dict(name="לוח מוזהב", layout="panel", bg=("leather", BROWN), ink="gold", field="#1e2e5a"),
    dict(name="ספר תורה", layout="scroll", bg=("leather", L1), ink="gold", ink2="#3a2412"),
    dict(name="לוחות הברית", layout="luchot", bg=("cloth", ("#2f4f84", "#223b64", "#152846")), ink="gold"),
    dict(name="מנורה", layout="menorah", bg=("leather", NAVY), ink="gold"),
    dict(name="כתר תורה", layout="crown", bg=("leather", L1), ink="gold"),
    dict(name="עמודי המקדש", layout="columns", bg=("paper", ("#f4efe4", "#e4dccb")), ink="gold", ink2="#2b2418",
         stone=("#ece6d8", "#cfc4ad")),
    dict(name="מגן דוד", layout="hexagram", bg=("leather", NAVY), ink="silver"),
    dict(name="מגן", layout="shield", bg=("leather", BLACK), ink="gold", field="#5c151b"),
    dict(name="חותם", layout="seal", bg=("paper", ("#f5efe2", "#e8dfcc")), ink="#2a2a2a"),
    dict(name="קלף", layout="parchment", bg=("leather", BROWN), ink="gold", ink2="#3d2412"),
    # 21-30: scenes
    dict(name="ירושלים", layout="skyline", bg=("paper", ("#f7c66b", "#d9774a")), ink="#3b1c2c", extras=("skyline",),
         skyline="#3b1c2c"),
    dict(name="ים", layout="waves", bg=("paper", ("#fdfbf4", "#d9ecf7")), ink="#18406e", extras=("waves",)),
    dict(name="מדבר", layout="dunes", bg=("paper", ("#f6c27a", "#d26f45")), ink="#5a2310", extras=("dunes",)),
    dict(name="הר סיני", layout="sinai", bg=("paper", ("#1a2238", "#5a4a6a")), ink="gold", extras=("mountain",)),
    dict(name="ויהי אור", layout="light", bg=("paper", ("#0c1022", "#2a2240")), ink="gold", extras=("glow",)),
    dict(name="קשת בענן", layout="rainbow", bg=("paper", ("#e8f3fd", "#b9daf3")), ink="#1d3b70", extras=("rainbow",)),
    dict(name="עץ החיים", layout="tree", bg=("leather", GREEN), ink="gold"),
    dict(name="גפן", layout="vine", bg=("leather", L1), ink="gold"),
    dict(name="לילה בשדה", layout="field", bg=("paper", ("#0a1530", "#27406e")), ink="gold",
         extras=("stars", "moon", "night_hills"), title_font=C.TITLE_FONT),
    dict(name="שמש עולה", layout="circle", bg=("paper", ("#fbf4e6", "#f1e2c4")), ink="#fdf6e8", field="#c2552d",
         ink2="#7a2f16"),
    # 31-40: ornament and pattern
    dict(name="פסיפס", layout="mosaic", bg=("paper", ("#1c3c6b", "#1c3c6b")), ink="gold", field="#0f2445",
         extras=("mosaic",), tiles=("#1c3c6b", "#24508c")),
    dict(name="סבכה", layout="lattice", bg=("leather", BLACK), ink="gold", extras=("lattice",)),
    dict(name="חיתוך נייר", layout="papercut", bg=("paper", ("#8c1d2b", "#6b1420")), ink="#ffffff", panel="#fffaf0",
         ink2="#6b1420"),
    dict(name="פסי טלית", layout="tallit", bg=("paper", ("#fbf8f1", "#efe8da")), ink="#1b2a4a", extras=("tallit",),
         stripes="#1b2a4a"),
    dict(name="אותיות", layout="letters", bg=("leather", NAVY), ink="gold", field="#0c1633", extras=("letters",)),
    dict(name="פינות מעוטרות", layout="corners", bg=("leather", GREEN), ink="gold"),
    dict(name="פסוק מסביב", layout="border_text", bg=("leather", L1), ink="gold"),
    dict(name="חלונות בית הכנסת", layout="twin_arch", bg=("paper", ("#f6f1e7", "#e9dfcb")), ink="gold",
         field="#1f3c73"),
    dict(name="שיש", layout="columns", bg=("paper", ("#fbfbfa", "#e9e9e7")), ink="silver", ink2="#2e2e33",
         extras=("marble",), stone=("#ffffff", "#dcdcdc")),
    dict(name="פס אלכסוני", layout="diagonal", bg=("paper", ("#ffffff", "#f1efea")), ink="#1a1a1a", field="#14305e",
         ink2="#ffffff"),
    # 41-50: modern type, and layouts on other grounds
    dict(name="מגזין", layout="editorial", bg=("paper", ("#f7f4ee", "#efe9de")), ink="#141414", ink2="#b23a2e"),
    dict(name="כותרת ענקית", layout="stacked", bg=("paper", ("#14305e", "#0d2146")), ink="#f4e7c4", ink2="#ffffff",
         title_font=D),
    dict(name="מדליון בכוכבים", layout="medallion", bg=("paper", ("#070f26", "#1d356b")), ink="gold", extras=("stars",)),
    dict(name="לוחות בכוכבים", layout="luchot", bg=("paper", ("#070f26", "#1d356b")), ink="gold", extras=("stars",)),
    dict(name="מנורה על בד", layout="menorah", bg=("cloth", ("#7a1d27", "#5c151b", "#3b0c11")), ink="gold"),
    dict(name="ספר תורה בלילה", layout="scroll", bg=("paper", ("#070f26", "#1d356b")), ink="gold", ink2="#3a2412",
         extras=("stars",)),
    dict(name="שמש מעל הים", layout="circle", bg=("paper", ("#fdf3e3", "#f6d9b4")), ink="#fff8ec", field="#e08a3c",
         ink2="#ffffff", extras=("waves",)),
    dict(name="ירושלים בלילה", layout="skyline", bg=("paper", ("#0a1530", "#3b3a6e")), ink="gold",
         extras=("stars", "moon", "skyline"), skyline="#05070f"),
    dict(name="מגן דוד בפסיפס", layout="hexagram", bg=("paper", ("#123a3a", "#123a3a")), ink="gold",
         extras=("mosaic",), tiles=("#123a3a", "#1a4d4d")),
    dict(name="כתר על שיש", layout="crown", bg=("paper", ("#fbfbfa", "#e9e9e7")), ink="gold", extras=("marble",)),
]
