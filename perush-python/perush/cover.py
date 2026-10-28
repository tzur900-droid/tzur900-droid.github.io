"""The cover of a book: the front, the spine and the back in one spread, as the printer
wants it for a soft (glued) binding. A Hebrew book opens from the right, so laid out flat
the front is on the left, the spine in the middle and the back on the right.

The background goes on past the trim by the bleed; the spine's width is worked out from
the number of pages and the thickness of the paper. All sizes are in points.
"""
import math
import os
from dataclasses import dataclass

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen, QPolygonF

from .model import page_mm
from .textlayout import PT_PER_MM, Style, qfont, width

MM = PT_PER_MM

# (name, background, ink): the ink is the frame, the ornaments and the letters
PALETTES = {
    "bordeaux": ("בורדו וזהב", "#5e1a24", "#d4af5a"),
    "navy": ("כחול כהה וזהב", "#14284b", "#d4af5a"),
    "green": ("ירוק כהה וזהב", "#1e3b2f", "#d4af5a"),
    "black": ("שחור וכסף", "#1a1a1a", "#c8c8c8"),
    "brown": ("חום ושמנת", "#4a2e1f", "#efe3c8"),
    "cream": ("שמנת וחום", "#f2ead8", "#5a3a22"),
    "custom": ("צבעים לבחירה", "", ""),
}

SPINE_DIRS = {
    "down": "מלמעלה למטה (קוראים בהטיית הראש ימינה)",
    "up": "מלמטה למעלה (קוראים בהטיית הראש שמאלה)",
    "across": "שורות לרוחב השדרה (לספר עבה)",
}

SLUG = 8 * MM          # the room for the crop marks outside the bleed
FRAME = 9 * MM         # the outer frame, from the trim (and from the fold of the spine)
FRAME_GAP = 2.5 * MM   # between the outer frame and the inner one


def colors(P):
    """(background, ink) of the project's cover."""
    key = P.get("coverPalette") or "bordeaux"
    if key in PALETTES and key != "custom":
        return PALETTES[key][1], PALETTES[key][2]
    return P.get("coverBg") or "#5e1a24", P.get("coverInk") or "#d4af5a"


def spine_mm(P, n_pages):
    """The width of the spine: as given, or a leaf (two pages) of paper for every two pages."""
    if float(P.get("coverSpineW") or 0) > 0:
        return float(P["coverSpineW"])
    leaves = math.ceil(max(0, n_pages) / 2)
    return round(leaves * float(P.get("coverPaper") or 0.1), 1)


@dataclass
class Cover:
    P: dict
    title: str
    sub: list            # the lines under the name on the front
    n_pages: int
    w: float             # the trimmed page
    h: float
    spine: float
    bleed: float
    slug: float

    @property
    def width(self):
        return 2 * (self.slug + self.bleed + self.w) + self.spine

    @property
    def height(self):
        return 2 * (self.slug + self.bleed) + self.h

    @property
    def x0(self):        # the trim's left edge (the left edge of the front)
        return self.slug + self.bleed

    @property
    def y0(self):
        return self.slug + self.bleed

    def panels(self):
        """The trimmed front, spine and back: (x, y, w, h)."""
        x, y = self.x0, self.y0
        return ((x, y, self.w, self.h), (x + self.w, y, self.spine, self.h),
                (x + self.w + self.spine, y, self.w, self.h))

    def size_mm(self):
        return self.width / MM, self.height / MM


def make_cover(P, n_pages, sub_lines=()):
    """The cover of project P, whose book has n_pages pages. sub_lines: the lines under the
    name on the title page (used when the cover has none of its own)."""
    wmm, hmm = page_mm(P)
    title = (P.get("coverTitle") or "").strip() or (P.get("title") or "").strip()
    own = [l.strip() for l in str(P.get("coverSub") or "").split("\n") if l.strip()]
    return Cover(P, title, own or list(sub_lines), n_pages, wmm * MM, hmm * MM, spine_mm(P, n_pages) * MM,
                 max(0.0, float(P.get("coverBleed") or 0)) * MM, SLUG if P.get("coverMarks") else 0.0)


# ---------------------------------------------------------------- text

def wrap(text, st, w):
    """Words into lines no wider than w (a word wider than w gets a line of its own)."""
    lines, cur = [], []
    for word in text.split():
        trial = " ".join(cur + [word])
        if cur and width(st, trial) > w:
            lines.append(" ".join(cur))
            cur = [word]
        else:
            cur.append(word)
    if cur:
        lines.append(" ".join(cur))
    return lines


def fit(text, family, size, bold, w, max_lines, least=6.0):
    """The largest size (from size down) at which text fits in max_lines lines of width w."""
    while size > least:
        st = Style(family, size, bold)
        lines = wrap(text, st, w)
        if len(lines) <= max_lines and all(width(st, l) <= w for l in lines):
            return st, lines
        size *= 0.94
    st = Style(family, least, bold)
    return st, wrap(text, st, w)


def draw_text(p, text, st, cx, baseline):
    """A line centred on cx."""
    p.setFont(qfont(st))
    p.drawText(QPointF(cx - width(st, text) / 2, baseline), text)


def ascent(st):
    from .textlayout import metrics
    return metrics(st).ascent()


# ---------------------------------------------------------------- drawing

def pen(color, lw, style=Qt.SolidLine):
    pn = QPen(QColor(color))
    pn.setWidthF(lw)
    pn.setStyle(style)
    return pn


def diamond(p, cx, cy, r, color):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawPolygon(QPolygonF([QPointF(cx, cy - r), QPointF(cx + r, cy), QPointF(cx, cy + r), QPointF(cx - r, cy)]))
    p.setBrush(Qt.NoBrush)


# ---------------------------------------------------------------- the ornaments
# Each kind of ornament is a list to choose from; all are drawn in the ink of the cover.

FRAMES = {
    "double": "מסגרת כפולה",
    "single": "מסגרת פשוטה",
    "triple": "מסגרת משולשת (דק-עבה-דק)",
    "notched": "כפולה עם פינות קעורות",
    "dotted": "קו ונקודות",
    "chain": "שרשרת יהלומים",
    "none": "בלי מסגרת",
}
CORNERS = {
    "diamond": "יהלום",
    "circle": "עיגול",
    "rosette": "פרח",
    "star": "מגן דוד",
    "bracket": "זווית",
    "fan": "רבע עיגול",
    "pomegranate": "רימון",
    "scroll": "סלסול",
    "leaves": "עלים",
    "image": "תמונה משלך",
    "none": "בלי",
}
DIVIDERS = {
    "line": "קו ויהלום",
    "diamonds": "שלושה יהלומים",
    "double": "קו כפול",
    "wave": "גל",
    "dots": "שורת נקודות",
    "star": "קווים ומגן דוד",
    "rosette": "קווים ופרח",
    "pomegranate": "קווים ורימון",
    "menorah": "קווים ומנורה",
    "scroll": "סלסולים",
    "vine": "ענף עלים",
    "image": "תמונה משלך",
    "none": "בלי",
}


def dot(p, cx, cy, r, color):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.setBrush(Qt.NoBrush)


def rosette(p, cx, cy, r, ink, bg):
    """Four petals (and four smaller between them), a heart in the background colour."""
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(ink))
    for k, (rr, wide) in enumerate(((r, 0.38), (r * 0.7, 0.3))):
        for a in range(4):
            p.save()
            p.translate(cx, cy)
            p.rotate(a * 90 + k * 45)
            p.drawEllipse(QRectF(0, -rr * wide / 2, rr, rr * wide))
            p.restore()
    p.setBrush(Qt.NoBrush)
    dot(p, cx, cy, r * 0.22, bg)
    dot(p, cx, cy, r * 0.11, ink)


def star(p, cx, cy, r, ink, lw):
    """A Magen David: two triangles."""
    p.setPen(pen(ink, lw))
    p.setBrush(Qt.NoBrush)
    for a0 in (-90, 90):
        pts = [QPointF(cx + r * math.cos(math.radians(a0 + k * 120)), cy + r * math.sin(math.radians(a0 + k * 120)))
               for k in range(3)]
        p.drawPolygon(QPolygonF(pts))


def pomegranate(p, cx, cy, r, ink, bg):
    """A pomegranate, r the radius of its body: the crown on top, a leaf on each side."""
    from PySide6.QtGui import QPainterPath
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(ink))
    by = cy + r * 0.25
    p.drawEllipse(QPointF(cx, by), r, r * 0.95)
    crown = QPainterPath()
    top = by - r * 0.95
    crown.moveTo(cx - r * 0.42, top + r * 0.25)
    for k, dx in enumerate((-0.42, -0.28, -0.14, 0, 0.14, 0.28, 0.42)):
        crown.lineTo(cx + dx * r, top - (r * 0.55 if k % 2 == 0 else r * 0.2))
    crown.lineTo(cx + r * 0.42, top + r * 0.25)
    crown.closeSubpath()
    p.drawPath(crown)
    for sgn in (-1, 1):
        p.save()
        p.translate(cx + sgn * r * 0.55, top + r * 0.05)
        p.rotate(sgn * -35)
        p.drawEllipse(QRectF(0 if sgn > 0 else -r * 0.9, -r * 0.16, r * 0.9, r * 0.32))
        p.restore()
    p.setBrush(Qt.NoBrush)


def menorah(p, cx, cy, h, ink):
    """The menorah of seven branches, h high, standing on its foot at cy + h / 2."""
    top = cy - h / 2 + h * 0.16           # where the branches end (under the lights)
    foot = cy + h / 2
    arm = h * 0.5
    lw = max(0.6, h * 0.045)
    p.setBrush(Qt.NoBrush)
    p.setPen(pen(ink, lw))
    p.drawLine(QPointF(cx, top), QPointF(cx, foot - h * 0.08))
    for k in (1, 2, 3):
        r = arm * k / 3
        p.drawArc(QRectF(cx - r, top - r, 2 * r, 2 * r), 180 * 16, 180 * 16)
    p.setPen(pen(ink, lw * 1.4))
    p.drawLine(QPointF(cx - h * 0.18, foot), QPointF(cx + h * 0.18, foot))
    p.drawLine(QPointF(cx - h * 0.1, foot - h * 0.08), QPointF(cx + h * 0.1, foot - h * 0.08))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(ink))
    for k in range(-3, 4):
        x = cx + arm * k / 3
        p.drawEllipse(QRectF(x - h * 0.035, top - h * 0.15, h * 0.07, h * 0.12))
    p.setBrush(Qt.NoBrush)


def spiral(x, y, r, turns, sgn_x, sgn_y, start=0.0):
    """The points of a curl winding in from radius r around (x, y)."""
    pts = []
    n = int(40 * turns)
    for k in range(n + 1):
        t = k / n
        a = start + t * turns * 2 * math.pi
        rr = r * (1 - 0.8 * t)
        pts.append(QPointF(x + sgn_x * rr * math.cos(a), y + sgn_y * rr * math.sin(a)))
    return pts


def leaf(p, x, y, length, angle, ink):
    """An almond-shaped leaf from (x, y), pointing at angle (degrees)."""
    from PySide6.QtGui import QPainterPath
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    path = QPainterPath()
    path.moveTo(0, 0)
    path.quadTo(QPointF(length / 2, -length * 0.4), QPointF(length, 0))
    path.quadTo(QPointF(length / 2, length * 0.4), QPointF(0, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(ink))
    p.drawPath(path)
    p.setBrush(Qt.NoBrush)
    p.restore()


def scroll_arm(p, x0, y0, x1, sgn, ink, lw=0.9):
    """A gentle curve from x0 out to x1 (on the side sgn) that ends in a curl, and a smaller
    curl hanging from its middle: the scrollwork of old title pages."""
    from PySide6.QtGui import QPainterPath
    r, r2 = 2.4 * MM, 1.4 * MM
    ex = x1 - sgn * r
    path = QPainterPath()
    path.moveTo(x0, y0)
    path.cubicTo(QPointF(x0 + (ex - x0) * 0.3, y0 - r * 0.6), QPointF(x0 + (ex - x0) * 0.7, y0 - r * 0.6), QPointF(ex, y0))
    p.setPen(pen(ink, lw))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.drawPolyline(spiral(ex, y0 + r, r, 1.25, sgn, 1, -math.pi / 2))
    mx, my = (x0 + ex) / 2, y0 - r * 0.45
    p.drawPolyline(spiral(mx, my + r2, r2, 1.1, -sgn, 1, -math.pi / 2))


def own_image(P, key):
    return image(P.get(key))


def corner(p, cx, cy, sx, sy, ink, bg, kind, P=None):
    """The ornament of a corner of the frame at (cx, cy); (sx, sy) points into the panel."""
    if kind == "diamond":
        diamond(p, cx, cy, 1.6 * MM, ink)
    elif kind == "circle":
        dot(p, cx, cy, 1.5 * MM, ink)
        dot(p, cx, cy, 0.6 * MM, bg)
    elif kind == "rosette":
        rosette(p, cx, cy, 3 * MM, ink, bg)
    elif kind == "star":
        star(p, cx, cy, 2.6 * MM, ink, 0.7)
    elif kind == "bracket":
        # an angle inside the corner, its arms ending in small diamonds
        d, L = 2.2 * MM, 11 * MM
        p.setPen(pen(ink, 1.0))
        p.drawLine(QPointF(cx + sx * d, cy + sy * d), QPointF(cx + sx * L, cy + sy * d))
        p.drawLine(QPointF(cx + sx * d, cy + sy * d), QPointF(cx + sx * d, cy + sy * L))
        diamond(p, cx + sx * L + sx * 1.2 * MM, cy + sy * d, 0.9 * MM, ink)
        diamond(p, cx + sx * d, cy + sy * L + sy * 1.2 * MM, 0.9 * MM, ink)
        diamond(p, cx, cy, 1.2 * MM, ink)
    elif kind == "fan":
        # quarter circles from the corner, into the panel
        p.setBrush(Qt.NoBrush)
        start = {(1, 1): 270, (-1, 1): 180, (-1, -1): 90, (1, -1): 0}[(sx, sy)]
        for r, lw in ((7 * MM, 1.0), (5 * MM, 0.5)):
            p.setPen(pen(ink, lw))
            p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), int(start * 16), 90 * 16)
        dot(p, cx + sx * 2.2 * MM, cy + sy * 2.2 * MM, 0.8 * MM, ink)
    elif kind == "pomegranate":
        pomegranate(p, cx + sx * 3.2 * MM, cy + sy * 3.2 * MM, 2.0 * MM, ink, bg)
        diamond(p, cx, cy, 1.0 * MM, ink)
    elif kind == "scroll":
        # a curl in the corner, its arms running along the two sides
        p.setPen(pen(ink, 0.9))
        p.setBrush(Qt.NoBrush)
        d = 2.4 * MM
        p.drawLine(QPointF(cx + sx * d * 2, cy + sy * d), QPointF(cx + sx * 14 * MM, cy + sy * d))
        p.drawLine(QPointF(cx + sx * d, cy + sy * d * 2), QPointF(cx + sx * d, cy + sy * 14 * MM))
        p.drawPolyline(spiral(cx + sx * 4.6 * MM, cy + sy * 4.6 * MM, 2.4 * MM, 1.3, sx, sy, math.pi))
        dot(p, cx + sx * 15 * MM, cy + sy * d, 0.6 * MM, ink)
        dot(p, cx + sx * d, cy + sy * 15 * MM, 0.6 * MM, ink)
    elif kind == "leaves":
        # leaves along the two sides from the corner, a berry in it
        for k in range(3):
            o = (3.5 + k * 3.6) * MM
            ln = (3.4 - k * 0.6) * MM
            leaf(p, cx + sx * o, cy + sy * 2.2 * MM, ln, math.degrees(math.atan2(sy * 0.5, sx)), ink)
            leaf(p, cx + sx * 2.2 * MM, cy + sy * o, ln, math.degrees(math.atan2(sy, sx * 0.5)), ink)
        dot(p, cx + sx * 2 * MM, cy + sy * 2 * MM, 1.3 * MM, ink)
    elif kind == "image":
        img = own_image(P or {}, "coverCornerImg")
        if img:
            # drawn as for the top right corner; turned over for the others
            S = 16 * MM
            k = min(S / img.width(), S / img.height())
            p.save()
            p.translate(cx, cy)
            p.scale(sx, sy)
            p.translate(img.width() * k, 0)
            p.scale(-1, 1)
            p.drawImage(QRectF(0, 0, img.width() * k, img.height() * k), img)
            p.restore()


def notched_rect(x1, y1, x2, y2, r):
    """A rectangle whose corners are cut inward in quarter circles."""
    from PySide6.QtGui import QPainterPath
    path = QPainterPath()
    box = lambda cx, cy: QRectF(cx - r, cy - r, 2 * r, 2 * r)
    path.moveTo(x1 + r, y1)
    path.arcTo(box(x2, y1), 180, 90)
    path.arcTo(box(x2, y2), 90, 90)
    path.arcTo(box(x1, y2), 0, 90)
    path.arcTo(box(x1, y1), 270, 90)
    path.closeSubpath()
    return path


def frames(p, P, x, y, w, h, ink, bg):
    """The frame of a panel (front or back), and the ornaments in the corners of its inner line."""
    kind = P.get("coverFrame") or "double"
    o, i = FRAME, FRAME + FRAME_GAP
    p.setBrush(Qt.NoBrush)
    rect = lambda d: QRectF(x + d, y + d, w - 2 * d, h - 2 * d)
    if kind == "single":
        p.setPen(pen(ink, 1.2))
        p.drawRect(rect(i))
    elif kind == "triple":
        p.setPen(pen(ink, 0.5))
        p.drawRect(rect(o - 1.2 * MM))
        p.setPen(pen(ink, 2.2))
        p.drawRect(rect(o + 0.4 * MM))
        p.setPen(pen(ink, 0.5))
        p.drawRect(rect(i))
    elif kind == "notched":
        p.setPen(pen(ink, 1.8))
        p.drawRect(rect(o))
        p.setPen(pen(ink, 0.7))
        p.drawPath(notched_rect(x + i, y + i, x + w - i, y + h - i, 5 * MM))
    elif kind == "dotted":
        p.setPen(pen(ink, 1.4))
        p.drawRect(rect(o))
        dots = QPen(QColor(ink))
        dots.setWidthF(1.3)
        dots.setCapStyle(Qt.RoundCap)
        dots.setDashPattern([0.01, 3.2])      # round dots, in units of the line's width
        p.setPen(dots)
        p.drawRect(rect(i))
    elif kind == "chain":
        p.setPen(pen(ink, 1.4))
        p.drawRect(rect(o))
        x1, y1, x2, y2 = x + i, y + i, x + w - i, y + h - i
        for a, b, horiz in (((x1, y1), (x2, y1), True), ((x1, y2), (x2, y2), True),
                            ((x1, y1), (x1, y2), False), ((x2, y1), (x2, y2), False)):
            length = (b[0] - a[0]) if horiz else (b[1] - a[1])
            n = max(1, round(length / (3.2 * MM)))
            for k in range(n + 1):
                t = a[0] + length * k / n if horiz else a[1] + length * k / n
                diamond(p, t if horiz else a[0], a[1] if horiz else t, 0.8 * MM, ink)
    elif kind != "none":
        p.setPen(pen(ink, 1.8))
        p.drawRect(rect(o))
        p.setPen(pen(ink, 0.6))
        p.drawRect(rect(i))
    kind = P.get("coverCorner") or "diamond"
    if kind != "none":
        for cx, sx in ((x + i, 1), (x + w - i, -1)):
            for cy, sy in ((y + i, 1), (y + h - i, -1)):
                corner(p, cx, cy, sx, sy, ink, bg, kind, P)


def ornament(p, P, cx, cy, half, ink, bg):
    """The divider under the name on the front, half as wide as half on each side."""
    kind = P.get("coverDivider") or "line"
    if kind == "none":
        return

    def lines(gap, lw=0.9):
        p.setPen(pen(ink, lw))
        p.drawLine(QPointF(cx - half, cy), QPointF(cx - gap, cy))
        p.drawLine(QPointF(cx + gap, cy), QPointF(cx + half, cy))

    if kind == "diamonds":
        lines(10 * MM, 0.6)
        for dx, r in ((-6 * MM, 1.3 * MM), (0, 2.4 * MM), (6 * MM, 1.3 * MM)):
            diamond(p, cx + dx, cy, r, ink)
    elif kind == "double":
        p.setPen(pen(ink, 1.2))
        p.drawLine(QPointF(cx - half, cy - 0.8 * MM), QPointF(cx + half, cy - 0.8 * MM))
        p.setPen(pen(ink, 0.5))
        p.drawLine(QPointF(cx - half * 0.8, cy + 0.8 * MM), QPointF(cx + half * 0.8, cy + 0.8 * MM))
    elif kind == "wave":
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        n = max(2, int(2 * half / (6 * MM)))
        step = 2 * half / n
        path.moveTo(cx - half, cy)
        for k in range(n):
            x0 = cx - half + k * step
            amp = 1.3 * MM if k % 2 == 0 else -1.3 * MM
            path.quadTo(QPointF(x0 + step / 2, cy - 2 * amp), QPointF(x0 + step, cy))
        p.setPen(pen(ink, 0.9))
        p.drawPath(path)
        diamond(p, cx - half - 2 * MM, cy, 1.0 * MM, ink)
        diamond(p, cx + half + 2 * MM, cy, 1.0 * MM, ink)
    elif kind == "dots":
        k, x = 0, 0.0
        while x <= half:
            r = max(0.35 * MM, 1.5 * MM * (1 - x / half * 0.75))
            for sgn in ((1,) if k == 0 else (1, -1)):
                dot(p, cx + sgn * x, cy, r, ink)
            k += 1
            x += 3.6 * MM
    elif kind == "star":
        lines(5 * MM)
        star(p, cx, cy, 3.4 * MM, ink, 0.8)
        diamond(p, cx - half - 2 * MM, cy, 1.1 * MM, ink)
        diamond(p, cx + half + 2 * MM, cy, 1.1 * MM, ink)
    elif kind == "pomegranate":
        lines(5 * MM)
        pomegranate(p, cx, cy, 2.6 * MM, ink, bg)
        diamond(p, cx - half - 2 * MM, cy, 1.1 * MM, ink)
        diamond(p, cx + half + 2 * MM, cy, 1.1 * MM, ink)
    elif kind == "menorah":
        lines(6.5 * MM)
        menorah(p, cx, cy - 1 * MM, 11 * MM, ink)
        diamond(p, cx - half - 2 * MM, cy, 1.1 * MM, ink)
        diamond(p, cx + half + 2 * MM, cy, 1.1 * MM, ink)
    elif kind == "scroll":
        diamond(p, cx, cy, 1.8 * MM, ink)
        for sgn in (-1, 1):
            scroll_arm(p, cx + sgn * 3 * MM, cy, cx + sgn * half, sgn, ink)
    elif kind == "vine":
        p.setPen(pen(ink, 0.8))
        p.drawLine(QPointF(cx - half, cy), QPointF(cx + half, cy))
        dot(p, cx, cy, 1.4 * MM, ink)
        for sgn in (-1, 1):
            x, k = 3.2 * MM, 0
            while x < half - 2 * MM:
                up = -1 if k % 2 == 0 else 1
                size = 3.6 * MM * (1 - 0.45 * x / half)
                leaf(p, cx + sgn * x, cy, size, (180 if sgn < 0 else 0) + sgn * up * 40, ink)
                x += 3.4 * MM
                k += 1
            dot(p, cx + sgn * half, cy, 0.7 * MM, ink)
    elif kind == "image":
        img = own_image(P, "coverDividerImg")
        if img:
            draw_image(p, img, cx - half - 3 * MM, cy - 7 * MM, 2 * half + 6 * MM, 14 * MM)
    elif kind == "rosette":
        lines(5.5 * MM)
        rosette(p, cx, cy, 4 * MM, ink, bg)
        diamond(p, cx - half - 2 * MM, cy, 1.1 * MM, ink)
        diamond(p, cx + half + 2 * MM, cy, 1.1 * MM, ink)
    else:
        lines(4 * MM)
        diamond(p, cx, cy, 2.4 * MM, ink)
        diamond(p, cx - half - 2 * MM, cy, 1.1 * MM, ink)
        diamond(p, cx + half + 2 * MM, cy, 1.1 * MM, ink)


def sample(kind, key, bg, ink, w=96, h=40):
    """A small picture of one ornament, for the list to choose it from."""
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor(bg))
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing)
    k = h / (16 * MM)         # 16 mm of the cover in the height of the picture
    p.scale(k, k)
    W, H = w / k, h / k
    if key == "image":
        # a picture of a picture: a frame with a mountain and a sun
        p.setPen(pen(ink, 0.5, Qt.DashLine))
        r = QRectF(W / 2 - 7 * MM, H / 2 - 5 * MM, 14 * MM, 10 * MM)
        p.drawRect(r)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(ink))
        p.drawPolygon(QPolygonF([QPointF(r.left() + 2 * MM, r.bottom() - 1.5 * MM), QPointF(r.center().x() - 1 * MM, r.top() + 4 * MM),
                                 QPointF(r.right() - 2 * MM, r.bottom() - 1.5 * MM)]))
        dot(p, r.right() - 3.2 * MM, r.top() + 2.6 * MM, 1.1 * MM, ink)
        p.end()
        return img
    if kind == "divider":
        ornament(p, {"coverDivider": key}, W / 2, H / 2, W * 0.36, ink, bg)
    elif kind == "corner":
        k0 = H / 2 - FRAME - FRAME_GAP - 1.5 * MM     # the corner a little above the middle, room round it
        frames(p, {"coverFrame": "double", "coverCorner": key}, W / 2 - 7 * MM - FRAME - FRAME_GAP, k0, W * 3, H * 3, ink, bg)
    else:
        frames(p, {"coverFrame": key, "coverCorner": "none"}, -FRAME + 1.5 * MM, -FRAME + 1.5 * MM,
               W + 2 * FRAME - 3 * MM, H * 3, ink, bg)
    p.end()
    return img


def image(path):
    if not path or not os.path.isfile(path):
        return None
    img = QImage(path)
    return None if img.isNull() else img


def draw_image(p, img, x, y, w, h, align="center"):
    """img inside the box (x, y, w, h), keeping its shape; returns the rect it took."""
    k = min(w / img.width(), h / img.height())
    iw, ih = img.width() * k, img.height() * k
    ix = x + (w - iw) / 2 if align == "center" else (x if align == "left" else x + w - iw)
    r = QRectF(ix, y + (h - ih) / 2, iw, ih)
    p.drawImage(r, img)
    return r


def draw_front(p, c, x, y, w, h, ink, bg, family):
    frames(p, c.P, x, y, w, h, ink, bg)
    p.setPen(QColor(ink))
    inner = w - 2 * (FRAME + FRAME_GAP + 9 * MM)
    cx = x + w / 2
    big, tlines = fit(c.title or " ", family, w * 0.15, True, inner, 3)
    t_lh = big.size * 1.25
    subs = []
    for k, text in enumerate(c.sub):
        first = k == 0 and len(c.sub) > 1
        st, ls = fit(text, family, big.size * (0.42 if first else 0.34), first, inner, 3)
        subs.append((st, ls))
    # the block: the name, the ornament, the lines under it; centred a little above the middle
    gap = 7 * MM
    total = len(tlines) * t_lh + gap * 2 + sum(len(ls) * st.size * 1.45 + 2 * MM for st, ls in subs)
    top = y + h * 0.42 - total / 2
    yy = top
    for l in tlines:
        draw_text(p, l, big, cx, yy + ascent(big) + (t_lh - big.size * 1.1) / 2)
        yy += t_lh
    ornament(p, c.P, cx, yy + gap, min(inner * 0.32, 45 * MM), ink, bg)
    yy += gap * 2
    p.setPen(QColor(ink))
    for st, ls in subs:
        for l in ls:
            draw_text(p, l, st, cx, yy + ascent(st))
            yy += st.size * 1.45
        yy += 2 * MM
    foot = (c.P.get("coverFoot") or "").strip()
    if foot:
        st, ls = fit(foot, family, big.size * 0.3, False, inner, 2)
        lh = st.size * 1.4
        yy = y + h - FRAME - FRAME_GAP - 9 * MM - len(ls) * lh
        p.setPen(QColor(ink))
        for l in ls:
            draw_text(p, l, st, cx, yy + ascent(st))
            yy += lh


def draw_back(p, c, x, y, w, h, ink, bg, family):
    frames(p, c.P, x, y, w, h, ink, bg)
    pad = FRAME + FRAME_GAP + 9 * MM
    inner = w - 2 * pad
    bottom = y + h - pad
    code = image(c.P.get("coverBarcode"))
    if code:
        # at the foot, on the side of the spine, on white (a barcode needs its quiet zone)
        bw, bh = min(42 * MM, inner * 0.45), 26 * MM
        k = min(bw / code.width(), bh / code.height())
        iw, ih = code.width() * k, code.height() * k
        r = QRectF(x + pad, bottom - ih, iw, ih)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("white"))
        p.drawRect(r.adjusted(-1.5 * MM, -1.5 * MM, 1.5 * MM, 1.5 * MM))
        p.setBrush(Qt.NoBrush)
        p.drawImage(r, code)
        bottom = r.top() - 8 * MM
    text = str(c.P.get("coverBack") or "").strip()
    if not text:
        return
    paras = [t.strip() for t in text.split("\n")]
    room = bottom - (y + pad)
    size = max(9.0, w / MM * 0.085)
    while True:
        st = Style(family, size)
        lh = size * 1.6
        lines = []
        for t in paras:
            lines.extend(wrap(t, st, inner) if t else [""])
        if len(lines) * lh <= room or size <= 7:
            break
        size *= 0.95
    total = len(lines) * lh
    # in the upper part of the room, but no higher than its top
    yy = y + pad + max(0.0, (room - total) * 0.35)
    p.setPen(QColor(ink))
    for l in lines:
        if l:
            draw_text(p, l, st, x + w / 2, yy + ascent(st) + (lh - size * 1.1) / 2)
        yy += lh


def draw_spine(p, c, x, y, w, h, ink, family):
    if w < 3 * MM:
        return
    band = 13 * MM
    logo = image(c.P.get("coverLogo"))
    logo_h = min(16 * MM, max(6 * MM, w * 1.2)) if logo else 0.0
    p.setBrush(Qt.NoBrush)
    tops = (y + band, y + h - band - logo_h)
    for k, by in enumerate(tops):
        d = 1.6 * MM if k == 0 else -1.6 * MM
        p.setPen(pen(ink, 1.4))
        p.drawLine(QPointF(x, by), QPointF(x + w, by))
        p.setPen(pen(ink, 0.5))
        p.drawLine(QPointF(x, by + d), QPointF(x + w, by + d))
    if logo:
        draw_image(p, logo, x + 1.5 * MM, y + h - band - logo_h + 3 * MM, w - 3 * MM, logo_h - 3 * MM)
    title = (c.P.get("coverSpine") or "").strip() or c.title
    sub = (c.P.get("coverSpineSub") or "").strip()
    a, b = tops[0] + 6 * MM, tops[1] - 6 * MM          # the room for the text, down the spine
    p.setPen(QColor(ink))
    if c.P.get("coverSpineDir") == "across":
        inner = w - 3 * MM
        yy = a + 4 * MM
        size = min(w * 0.5, 34.0)
        for text, bold in ((title, True), (sub, False)):
            if not text:
                continue
            st, ls = fit(text, family, size, bold, inner, 4)
            for l in ls:
                draw_text(p, l, st, x + w / 2, yy + ascent(st))
                yy += st.size * 1.3
            yy += 3 * MM
            size = st.size * 0.55          # the line after the name, smaller than it
        return
    length = b - a
    size = min(w * 0.55, 40.0)          # the letters across the spine: about half its width
    while size > 4:
        st, sst = Style(family, size, True), Style(family, size * 0.62)
        gap = size * 1.2 if sub else 0
        total = width(st, title) + (gap + width(sst, sub) if sub else 0)
        if total <= length:
            break
        size *= 0.95
    p.save()
    p.translate(x + w / 2, (a + b) / 2)
    p.rotate(-90 if c.P.get("coverSpineDir", "down") != "up" else 90)
    # one line along the spine: the name, then (smaller) the line after it; the text begins
    # at the right of the rotated line, as Hebrew does
    from .textlayout import metrics
    base = metrics(st).tightBoundingRect("אבגדהמש").height() / 2   # the letters centred across the spine
    xr = total / 2
    p.setFont(qfont(st))
    p.drawText(QPointF(xr - width(st, title), base), title)
    if sub:
        p.setFont(qfont(sst))
        p.drawText(QPointF(xr - width(st, title) - gap - width(sst, sub), base * sst.size / st.size), sub)
        diamond(p, xr - width(st, title) - gap / 2, 0, st.size * 0.12, ink)
    p.restore()


def draw_marks(p, c):
    """Crop marks at the corners of the trim, and the folds of the spine at its top and foot."""
    p.setPen(pen("black", 0.3))
    L, R = c.x0, c.x0 + 2 * c.w + c.spine
    T, B = c.y0, c.y0 + c.h
    near, far = c.bleed + 1 * MM, c.bleed + c.slug
    for x in (L, R):
        for yy, s in ((T, -1), (B, 1)):
            p.drawLine(QPointF(x, yy + s * near), QPointF(x, yy + s * far))
    for yy in (T, B):
        for x, s in ((L, -1), (R, 1)):
            p.drawLine(QPointF(x + s * near, yy), QPointF(x + s * far, yy))
    for x in (c.x0 + c.w, c.x0 + c.w + c.spine):
        p.drawLine(QPointF(x, T - near), QPointF(x, T - far))
        p.drawLine(QPointF(x, B + near), QPointF(x, B + far))


def draw_guides(p, c):
    """On screen only: the trim and the folds of the spine, dashed."""
    p.setBrush(Qt.NoBrush)
    p.setPen(pen("#22d3ee", 0.8, Qt.DashLine))
    p.drawRect(QRectF(c.x0, c.y0, 2 * c.w + c.spine, c.h))
    for x in (c.x0 + c.w, c.x0 + c.w + c.spine):
        p.drawLine(QPointF(x, c.y0), QPointF(x, c.y0 + c.h))


def draw_cover(p, c, guides=False):
    bg, ink = colors(c.P)
    family = c.P.get("coverFont") or c.P.get("mainFont") or "Frank Ruhl Libre"
    p.setLayoutDirection(Qt.RightToLeft)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(bg))
    p.drawRect(QRectF(c.slug, c.slug, c.width - 2 * c.slug, c.height - 2 * c.slug))
    p.setBrush(Qt.NoBrush)
    front, spine, back = c.panels()
    draw_front(p, c, *front, ink, bg, family)
    draw_spine(p, c, *spine, ink, family)
    draw_back(p, c, *back, ink, bg, family)
    if c.slug:
        draw_marks(p, c)
    if guides:
        draw_guides(p, c)


def cover_image(c, zoom=1.0):
    """The cover as an image (zoom = pixels per point), with the trim and folds marked."""
    img = QImage(max(1, int(c.width * zoom)), max(1, int(c.height * zoom)), QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor("white"))
    dpm = round(72 / 0.0254)      # a point of type is a point of the page, as in the layout
    img.setDotsPerMeterX(dpm)
    img.setDotsPerMeterY(dpm)
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
    p.scale(zoom, zoom)
    draw_cover(p, c, guides=True)
    p.end()
    return img


def export_cover(c, path, title=""):
    """The cover as a PDF of one page, its size the whole spread with the bleed (in colour)."""
    writer = QPdfWriter(path)
    writer.setResolution(72)
    writer.setTitle((title or "עימוד פירושים") + " — כריכה")
    writer.setCreator("עימוד פירושים")
    size = QPageSize(QSizeF(c.width / MM, c.height / MM), QPageSize.Millimeter, "cover", QPageSize.ExactMatch)
    writer.setPageLayout(QPageLayout(size, QPageLayout.Portrait, QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter))
    p = QPainter(writer)
    draw_cover(p, c)
    p.end()
