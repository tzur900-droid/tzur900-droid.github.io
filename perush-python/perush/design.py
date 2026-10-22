"""Title pages and covers drawn in lines, as in the old printings.

  * title(pw, ph, lines, style): a title page in the manner of the Vilna Shas, all in
    round lines: a gate of two columns under a round arch with a dome (1) or a medallion
    (2) over its beam, or a rounded frame with garlands (3); the name in the opening.
  * cover(...): a whole cover for printing (back, spine and front, with the bleed): a
    light ground, ornaments in a dark ink and gold (a border of interlaced waves, a
    rounded frame, fleurons, garlands, medallions), the name under a lobed arch, the
    masechtot of the volume in a cartouche and one under another on the spine; the back
    left plain.

Everything is drawn with a QPainter, in points, as a page's paint (see render.draw_page).
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen

from .textlayout import PT_PER_MM, Style, qfont, width

TITLE_FONT = "Drugulin CLM"
PAPER = ["white"]          # the colour inside the drawings (white, or a light one on a cover)
TEXT_FONT = "Frank Ruhl Libre"

# the colours a cover can have: name -> (ground, ink, gold)
COLOURS = {
    "תכלת": ("#cfe4f2", "#1b355c", "#b08433"),
    "תכלת עמוק": ("#a9cfe8", "#13294b", "#a87a22"),
    "תכלת אפרפר": ("#d6e0e8", "#23374d", "#a8802e"),
    "שמנת": ("#f1e8d4", "#3a2a1a", "#a8802e"),
    "מנטה": ("#d3eadf", "#1c3b2e", "#a8802e"),
}


# ------------------------------------------------------------------ drawing helpers
def pen(colour, w):
    p = QPen(QColor(colour))
    p.setWidthF(w)
    p.setCapStyle(Qt.FlatCap)
    p.setJoinStyle(Qt.MiterJoin)
    return p


def text_c(p, x, y, text, st, colour="black"):
    """text centred on x, its baseline at y."""
    p.setPen(QColor(colour))
    p.setFont(qfont(st))
    p.drawText(QPointF(x - width(st, text) / 2, y), text)


def fit(st, text, w):
    """st, smaller if the text is wider than w."""
    tw = width(st, text)
    return st if tw <= w else Style(st.family, st.size * w / tw, st.bold)


def rosette(p, x, y, r, colour, w=0.6, petals=8):
    p.setPen(pen(colour, w))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(x, y), r, r)
    p.drawEllipse(QPointF(x, y), r * 0.28, r * 0.28)
    for k in range(petals):
        a = 2 * math.pi * k / petals
        path = QPainterPath()
        path.moveTo(x + math.cos(a) * r * 0.3, y + math.sin(a) * r * 0.3)
        c1 = (x + math.cos(a - 0.45) * r * 0.85, y + math.sin(a - 0.45) * r * 0.85)
        c2 = (x + math.cos(a + 0.45) * r * 0.85, y + math.sin(a + 0.45) * r * 0.85)
        path.cubicTo(QPointF(*c1), QPointF(*c2), QPointF(x + math.cos(a) * r * 0.3, y + math.sin(a) * r * 0.3))
        p.drawPath(path)


def scroll(p, x, y, s, colour, w=0.6, flip=1):
    """a volute: a spiral of s points, turning to the side flip (1 or -1)."""
    p.setPen(pen(colour, w))
    path = QPainterPath()
    n = 60
    for k in range(n + 1):
        t = k / n * 2.6 * math.pi
        r = s * (1 - k / n * 0.85)
        px, py = x + flip * r * math.cos(t), y + r * math.sin(t)
        if k == 0:
            path.moveTo(px, py)
        else:
            path.lineTo(px, py)
    p.drawPath(path)


def leaf_band(p, x1, x2, y, h, colour, w=0.5):
    """a running band of small leaves between two lines."""
    p.setPen(pen(colour, w))
    p.drawLine(QPointF(x1, y), QPointF(x2, y))
    p.drawLine(QPointF(x1, y + h), QPointF(x2, y + h))
    n = max(1, int((x2 - x1) / (h * 1.3)))
    step = (x2 - x1) / n
    for k in range(n):
        cx = x1 + step * (k + 0.5)
        path = QPainterPath()
        path.moveTo(cx - step * 0.4, y + h / 2)
        path.quadTo(QPointF(cx, y + h * 0.05), QPointF(cx + step * 0.4, y + h / 2))
        path.quadTo(QPointF(cx, y + h * 0.95), QPointF(cx - step * 0.4, y + h / 2))
        p.drawPath(path)


def dentils(p, x1, x2, y, h, colour, w=0.5):
    p.setPen(pen(colour, w))
    p.drawLine(QPointF(x1, y), QPointF(x2, y))
    p.drawLine(QPointF(x1, y + h), QPointF(x2, y + h))
    n = max(1, int((x2 - x1) / (h * 0.9)))
    step = (x2 - x1) / n
    for k in range(n):
        p.drawRect(QRectF(x1 + step * k + step * 0.2, y + h * 0.2, step * 0.6, h * 0.6))


def column(p, x, y1, y2, cwid, colour):
    """a column from y1 (top of the capital) to y2 (foot of the base), centred on x."""
    base_h, cap_h = cwid * 1.5, cwid * 1.1
    lw = 0.7
    p.setPen(pen(colour, lw))
    p.setBrush(Qt.NoBrush)
    # the base: a plinth and two mouldings
    bw = cwid * 1.5
    p.drawRect(QRectF(x - bw / 2, y2 - base_h * 0.55, bw, base_h * 0.55))
    p.drawRect(QRectF(x - bw / 2 + 2, y2 - base_h * 0.55 + 2, bw - 4, base_h * 0.55 - 4))
    p.drawRect(QRectF(x - cwid * 0.65, y2 - base_h * 0.8, cwid * 1.3, base_h * 0.25))
    p.drawRect(QRectF(x - cwid * 0.58, y2 - base_h, cwid * 1.16, base_h * 0.2))
    # the shaft, fluted, with a ring a third of the way up
    top, bot = y1 + cap_h, y2 - base_h
    p.drawRect(QRectF(x - cwid / 2, top, cwid, bot - top))
    for k in range(1, 5):
        fx = x - cwid / 2 + cwid * k / 5
        p.drawLine(QPointF(fx, top + 4), QPointF(fx, bot - 4))
    ring = bot - (bot - top) / 3
    p.setBrush(QBrush(QColor(PAPER[0])))
    p.drawRect(QRectF(x - cwid * 0.56, ring - 4, cwid * 1.12, 8))
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(x - cwid * 0.56, ring), QPointF(x + cwid * 0.56, ring))
    # the capital: an abacus, two volutes and leaves
    p.drawRect(QRectF(x - cwid * 0.8, y1, cwid * 1.6, cap_h * 0.22))
    p.drawRect(QRectF(x - cwid * 0.6, y1 + cap_h * 0.85, cwid * 1.2, cap_h * 0.15))
    scroll(p, x - cwid * 0.5, y1 + cap_h * 0.45, cap_h * 0.28, colour, 0.6, 1)
    scroll(p, x + cwid * 0.5, y1 + cap_h * 0.45, cap_h * 0.28, colour, 0.6, -1)
    for k in (-1, 0, 1):
        path = QPainterPath()
        lx = x + k * cwid * 0.25
        path.moveTo(lx, y1 + cap_h * 0.85)
        path.quadTo(QPointF(lx - cwid * 0.12, y1 + cap_h * 0.5), QPointF(lx, y1 + cap_h * 0.3))
        path.quadTo(QPointF(lx + cwid * 0.12, y1 + cap_h * 0.5), QPointF(lx, y1 + cap_h * 0.85))
        p.drawPath(path)
    return top, bot


def guilloche(p, x1, y1, x2, y2, h, colour, w=0.5):
    """a band of interlaced waves between two lines, from (x1, y1) to (x2, y2) (along a
    side: horizontal or vertical)."""
    horiz = abs(y2 - y1) < abs(x2 - x1)
    L = abs(x2 - x1) if horiz else abs(y2 - y1)
    n = max(2, int(L / (h * 1.6)))
    step = L / n
    p.setPen(pen(colour, w))
    p.setBrush(Qt.NoBrush)

    def pt(u, v):          # u along the band, v across it (0..h)
        return QPointF(x1 + u, y1 + v) if horiz else QPointF(x1 + v, y1 + u)
    p.drawLine(pt(0, 0), pt(L, 0))
    p.drawLine(pt(0, h), pt(L, h))
    for sign in (1, -1):
        path = QPainterPath()
        path.moveTo(pt(0, h / 2))
        for k in range(n):
            u = k * step
            c = h / 2 + sign * h * 0.42
            path.cubicTo(pt(u + step * 0.25, c), pt(u + step * 0.25, c), pt(u + step * 0.5, h / 2))
            c = h / 2 - sign * h * 0.42
            path.cubicTo(pt(u + step * 0.75, c), pt(u + step * 0.75, c), pt(u + step, h / 2))
        p.drawPath(path)
    for k in range(n):
        p.drawEllipse(pt(step * (k + 0.25), h / 2), h * 0.08, h * 0.08)
        p.drawEllipse(pt(step * (k + 0.75), h / 2), h * 0.08, h * 0.08)


def fleuron(p, x, y, s, colour, w=0.6, angle=0.0):
    """a corner ornament: a leaf between two scrolls, pointing at angle (degrees; 0 = up)."""
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.setPen(pen(colour, w))
    p.setBrush(Qt.NoBrush)
    leaf = QPainterPath()
    leaf.moveTo(0, 0)
    leaf.cubicTo(QPointF(-s * 0.35, -s * 0.35), QPointF(-s * 0.2, -s * 0.8), QPointF(0, -s))
    leaf.cubicTo(QPointF(s * 0.2, -s * 0.8), QPointF(s * 0.35, -s * 0.35), QPointF(0, 0))
    p.drawPath(leaf)
    p.drawLine(QPointF(0, -s * 0.1), QPointF(0, -s * 0.85))
    for f in (1, -1):
        path = QPainterPath()
        path.moveTo(0, 0)
        path.cubicTo(QPointF(f * s * 0.5, s * 0.05), QPointF(f * s * 0.9, -s * 0.2), QPointF(f * s * 0.75, -s * 0.5))
        p.drawPath(path)
        scroll(p, f * s * 0.62, -s * 0.5, s * 0.14, colour, w, -f)
    p.restore()


def garland(p, x1, x2, y, sag, colour, w=0.6):
    """a hanging garland of leaves from x1 to x2 at y."""
    p.setPen(pen(colour, w))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(x1, y)
    path.quadTo(QPointF((x1 + x2) / 2, y + sag * 2), QPointF(x2, y))
    p.drawPath(path)
    n = max(4, int(abs(x2 - x1) / 9))
    for k in range(1, n):
        t = k / n
        bx = (1 - t) ** 2 * x1 + 2 * t * (1 - t) * (x1 + x2) / 2 + t * t * x2
        by = (1 - t) ** 2 * y + 2 * t * (1 - t) * (y + sag * 2) + t * t * y
        r = sag * 0.18 * (1 - abs(0.5 - t))
        p.drawEllipse(QPointF(bx, by), r * 1.3, r * 0.8)
    p.drawEllipse(QPointF(x1, y), 2.2, 2.2)
    p.drawEllipse(QPointF(x2, y), 2.2, 2.2)


def round_frame(p, r, rad, colour, w):
    p.setPen(pen(colour, w))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(r, rad, rad)


def lobed_arch(p, x1, x2, spring, rise, colour, w=0.6, lobes=7):
    """the inner edge of an arch made of small round lobes."""
    p.setPen(pen(colour, w))
    rx = (x2 - x1) / 2
    mx = (x1 + x2) / 2
    pts = []
    for k in range(lobes + 1):
        a = math.pi * k / lobes
        pts.append((mx - rx * math.cos(a), spring - rise * math.sin(a)))
    path = QPainterPath()
    path.moveTo(*pts[0])
    for k in range(lobes):
        (ax, ay), (bx, by) = pts[k], pts[k + 1]
        cx, cy = (ax + bx) / 2, (ay + by) / 2
        # bulge towards the centre of the arch
        dx, dy = mx - cx, spring - cy
        d = math.hypot(dx, dy) or 1
        bulge = math.hypot(bx - ax, by - ay) * 0.35
        path.quadTo(QPointF(cx + dx / d * bulge, cy + dy / d * bulge), QPointF(bx, by))
    p.drawPath(path)


# ------------------------------------------------------------------ title page
def title(pw, ph, lines, colour="black", style=1):
    """The paint of a title page: lines = [(text, size, bold)], the first is the name
    (in the arch), the rest under it. style: 1 a gate under a dome, 2 a gate with a
    lobed arch and a medallion, 3 a round frame with garlands."""
    def paint(p):
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing, True)
        m = 30.0
        mid = pw / 2
        # the border: rounded, a thick line and a thin one inside it
        round_frame(p, QRectF(m, m, pw - 2 * m, ph - 2 * m), 14, colour, 1.6)
        round_frame(p, QRectF(m + 4, m + 4, pw - 2 * m - 8, ph - 2 * m - 8), 11, colour, 0.5)
        L, R = m + 18, pw - m - 18
        cw = 30.0
        xl, xr = L + cw * 0.75, R - cw * 0.75
        foot = ph - m - 60
        if style in (1, 2):
            beam = ph * 0.22
            beam_h = 30.0
            cap_top = beam + beam_h
            if style == 1:
                # a dome over the beam, with a rosette and two scrolls at its feet
                dw = (R - L) * 0.62
                for k, lw in ((0, 1.0), (7, 0.45)):
                    path = QPainterPath()
                    path.moveTo(mid - dw / 2 + k, beam)
                    dh = beam - m - 26 - k
                    path.arcTo(QRectF(mid - dw / 2 + k, beam - dh, dw - 2 * k, 2 * dh), 180, -180)
                    p.setPen(pen(colour, lw))
                    p.drawPath(path)
                rosette(p, mid, beam - (beam - m - 26) * 0.5, 15, colour, 0.6, 12)
                for f in (1, -1):
                    scroll(p, mid - f * (dw / 2 + 16), beam - 10, 10, colour, 0.6, f)
                    path = QPainterPath()
                    path.moveTo(mid - f * (dw / 2 + 16), beam - 20)
                    path.quadTo(QPointF(mid - f * (dw / 2 + 4), beam - 22), QPointF(mid - f * dw / 2, beam - 6))
                    p.drawPath(path)
                    p.drawEllipse(QPointF(mid - f * (R - L) * 0.44, beam - 7), 5, 5)
            else:
                # a round medallion over the beam, in a wreath of leaves
                cy = beam - (beam - m - 20) * 0.5
                rr = (beam - m - 26) * 0.5
                p.setPen(pen(colour, 1.0))
                p.drawEllipse(QPointF(mid, cy), rr, rr)
                p.setPen(pen(colour, 0.45))
                p.drawEllipse(QPointF(mid, cy), rr - 5, rr - 5)
                rosette(p, mid, cy, rr - 10, colour, 0.5, 12)
                for f in (1, -1):
                    garland(p, mid - f * (rr + 2), mid - f * (R - L) * 0.45, beam - 14, 7, colour, 0.5)
                    fleuron(p, mid - f * (rr + 22), beam - 2, 14, colour, 0.5, 0)
            # the beam: rounded ends, dentils and a band of leaves
            p.setPen(pen(colour, 1.0))
            p.drawRoundedRect(QRectF(L, beam, R - L, beam_h), 6, 6)
            dentils(p, L + 6, R - 6, beam + 4, 7, colour, 0.45)
            guilloche(p, L + 6, beam + 15, R - 6, beam + 15, 11, colour, 0.45)
            column(p, xl, cap_top, foot, cw, colour)
            column(p, xr, cap_top, foot, cw, colour)
            ix1, ix2 = xl + cw * 0.8, xr - cw * 0.8
            rx = (ix2 - ix1) / 2
            # a round arch: a half circle as wide as the opening (as high as it allows)
            ry = min(rx, (foot - cap_top) * 0.42)
            spring = cap_top + ry + 6
            for k, w in ((0, 1.0), (9, 0.5)):
                path = QPainterPath()
                path.moveTo(ix1 + k, foot - 52)
                path.lineTo(ix1 + k, spring)
                path.arcTo(QRectF(ix1 + k, spring - (ry - k), 2 * (rx - k), 2 * (ry - k)), 180, -180)
                path.lineTo(ix2 - k, foot - 52)
                p.setPen(pen(colour, w))
                p.drawPath(path)
            if style == 2:
                lobed_arch(p, ix1 + 9, ix2 - 9, spring, ry - 9, colour, 0.5, 9)
            else:
                p.setPen(pen(colour, 0.45))
                for k in range(1, 14):
                    a = math.pi * k / 14
                    c, s_ = math.cos(a), math.sin(a)
                    p.drawLine(QPointF(mid - c * rx, spring - s_ * ry), QPointF(mid - c * (rx - 9), spring - s_ * (ry - 9)))
            # the keystone: a small round medallion
            p.setBrush(QBrush(QColor(PAPER[0])))
            p.setPen(pen(colour, 0.8))
            p.drawEllipse(QPointF(mid, spring - ry + 4), 8, 8)
            p.setBrush(Qt.NoBrush)
            rosette(p, mid, spring - ry + 4, 6, colour, 0.4, 6)
            for f in (1, -1):
                fleuron(p, mid - f * (rx - 10), cap_top + 18, 13, colour, 0.5, f * -45)
            top_text = spring - ry * 0.55
        else:
            # a round frame with garlands and fleurons, no columns
            r = QRectF(L, m + 30, R - L, foot - m - 30)
            round_frame(p, r, 40, colour, 1.2)
            round_frame(p, r.adjusted(7, 7, -7, -7), 34, colour, 0.5)
            guilloche(p, r.left() + 40, r.top() + 14, r.right() - 40, r.top() + 14, 10, colour, 0.45)
            # an oval medallion at the head
            p.setBrush(QBrush(QColor(PAPER[0])))
            p.setPen(pen(colour, 1.0))
            p.drawEllipse(QPointF(mid, r.top()), 40, 26)
            p.setBrush(Qt.NoBrush)
            p.setPen(pen(colour, 0.45))
            p.drawEllipse(QPointF(mid, r.top()), 34, 20)
            rosette(p, mid, r.top(), 16, colour, 0.5, 12)
            for f in (1, -1):
                garland(p, mid - f * 44, mid - f * (r.width() / 2 - 30), r.top() + 34, 14, colour, 0.5)
                fleuron(p, mid - f * (r.width() / 2 - 22), r.top() + 50, 16, colour, 0.5, f * -40)
                fleuron(p, mid - f * (r.width() / 2 - 22), r.bottom() - 22, 16, colour, 0.5, 180 + f * 40)
            # a lobed arch inside the frame
            ix1, ix2 = r.left() + 30, r.right() - 30
            lobed_arch(p, ix1, ix2, r.top() + 150, 70, colour, 0.6, 9)
            p.setPen(pen(colour, 0.6))
            p.drawLine(QPointF(ix1, r.top() + 150), QPointF(ix1, r.bottom() - 40))
            p.drawLine(QPointF(ix2, r.top() + 150), QPointF(ix2, r.bottom() - 40))
            top_text = r.top() + 130
        # the step under the gate, with a band across it
        p.setPen(pen(colour, 1.0))
        p.drawRoundedRect(QRectF(L, foot, R - L, ph - m - 18 - foot), 8, 8)
        guilloche(p, L + 10, foot + 6, R - 10, foot + 6, 10, colour, 0.45)
        # the lines: the name, the rest under it, between the columns
        inner = R - L - 2 * cw * 1.6 - 20
        name, *rest = lines
        st = fit(Style(TITLE_FONT, name[1], True), name[0], inner)
        body = list(rest)
        foot_line = body.pop() if body and body[-1][0].startswith("ימי") else None
        body_h = st.size * 0.6 + 16 + sum((size if not text else size * 1.25) for text, size, _ in body)
        y = (top_text + foot - 52) / 2 - (st.size + body_h) / 2 + st.size
        text_c(p, mid, y, name[0], st, colour)
        # a little ornament under the name
        y += st.size * 0.6
        p.setPen(pen(colour, 0.5))
        p.drawLine(QPointF(mid - 50, y), QPointF(mid - 8, y))
        p.drawLine(QPointF(mid + 8, y), QPointF(mid + 50, y))
        rosette(p, mid, y, 5, colour, 0.4, 6)
        y += 16
        for text, size, bold in body:
            if not text:
                y += size
                continue
            st = fit(Style(TITLE_FONT if bold else TEXT_FONT, size, bold), text, inner)
            y += st.size * 1.25
            text_c(p, mid, y, text, st, colour)
        if foot_line:
            st = Style(TEXT_FONT, foot_line[1])
            text_c(p, mid, foot + 6 + 10 + 18 + st.size * 0.4, foot_line[0], st, colour)
        p.restore()
    return paint


# ------------------------------------------------------------------ cover
def spine_width(pages, leaf=0.1):
    """the spine in mm for a book of pages pages (leaf: the paper's thickness, a leaf
    being two pages), and a little for the cover itself."""
    return pages / 2 * leaf + 1.0


def cover(trim, pages, name_lines, masechtot, volume, colours, bleed=3.0, leaf=0.1):
    """-> (width, height, paint) of the whole cover in points: the back on the left, the
    spine, the front on the right (a book read from right to left is opened on its
    right side), with the bleed all round."""
    ground, ink, gold = colours
    tw, th = trim[0] * PT_PER_MM, trim[1] * PT_PER_MM
    sw = spine_width(pages, leaf) * PT_PER_MM
    b = bleed * PT_PER_MM
    W, H = 2 * tw + sw + 2 * b, th + 2 * b

    def paint(p):
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing, True)
        p.fillRect(QRectF(0, 0, W, H), QColor(ground))
        front(p, b + tw + sw, b, tw, th, name_lines, masechtot, volume, ground, ink, gold)
        spine(p, b + tw, b, sw, th, masechtot, volume, ground, ink, gold)
        p.restore()
    return W, H, paint


def front(p, x0, y0, w, h, name_lines, masechtot, volume, ground, ink, gold):
    mid = x0 + w / 2
    # a border of interlaced waves all round, and a rounded frame inside it
    o = QRectF(x0 + 22, y0 + 22, w - 44, h - 44)
    p.setPen(pen(gold, 1.6))
    p.setBrush(Qt.NoBrush)
    p.drawRect(o)
    bh = 13
    guilloche(p, o.left() + 4, o.top() + 4, o.right() - 4, o.top() + 4, bh, ink, 0.55)
    guilloche(p, o.left() + 4, o.bottom() - 4 - bh, o.right() - 4, o.bottom() - 4 - bh, bh, ink, 0.55)
    guilloche(p, o.left() + 4, o.top() + 4 + bh, o.left() + 4, o.bottom() - 4 - bh, bh, ink, 0.55)
    guilloche(p, o.right() - 4 - bh, o.top() + 4 + bh, o.right() - 4 - bh, o.bottom() - 4 - bh, bh, ink, 0.55)
    r = o.adjusted(bh + 12, bh + 12, -bh - 12, -bh - 12)
    round_frame(p, r, 22, gold, 2.0)
    round_frame(p, r.adjusted(5, 5, -5, -5), 18, ink, 0.6)
    for cx, cy, a in ((r.left() + 22, r.top() + 22, -45), (r.right() - 22, r.top() + 22, 45),
                      (r.left() + 22, r.bottom() - 22, -135), (r.right() - 22, r.bottom() - 22, 135)):
        fleuron(p, cx, cy, 18, ink, 0.7, a)
    # a medallion at the head, with garlands to the sides
    cy = r.top() + 50
    p.setBrush(QBrush(QColor(ground)))
    p.setPen(pen(gold, 1.6))
    p.drawEllipse(QPointF(mid, cy), 26, 26)
    p.setBrush(Qt.NoBrush)
    p.setPen(pen(ink, 0.6))
    p.drawEllipse(QPointF(mid, cy), 21, 21)
    rosette(p, mid, cy, 17, ink, 0.6, 12)
    for f in (1, -1):
        garland(p, mid - f * 30, mid - f * (r.width() / 2 - 40), cy - 6, 10, gold, 0.8)
    # a lobed arch over the name
    ax1, ax2 = r.left() + 34, r.right() - 34
    spring = r.top() + 150
    p.setPen(pen(gold, 1.4))
    path = QPainterPath()
    path.moveTo(ax1, spring + 120)
    path.lineTo(ax1, spring)
    path.arcTo(QRectF(ax1, spring - 66, ax2 - ax1, 132), 180, -180)
    path.lineTo(ax2, spring + 120)
    p.drawPath(path)
    lobed_arch(p, ax1 + 7, ax2 - 7, spring, 59, ink, 0.6, 11)
    y = spring - 6
    for text, size in name_lines:
        st = fit(Style(TITLE_FONT, size, True), text, ax2 - ax1 - 30)
        y += st.size * 1.3
        text_c(p, mid, y, text, st, ink)
    y += 20
    p.setPen(pen(gold, 0.9))
    p.drawLine(QPointF(mid - 70, y), QPointF(mid - 12, y))
    p.drawLine(QPointF(mid + 12, y), QPointF(mid + 70, y))
    rosette(p, mid, y, 7, gold, 0.8, 6)
    # the masechtot of the volume, in a rounded cartouche
    rows, row = [], []
    for ms in masechtot:
        if row and width(Style(TITLE_FONT, 17, True), " · ".join(row + [ms])) > r.width() - 90:
            rows.append(row)
            row = []
        row.append(ms)
    rows.append(row)
    if len(masechtot) == 1:
        rows = [["מסכת " + masechtot[0]]]
    ch = 26 * len(rows) + 22
    c = QRectF(r.left() + 30, spring + 150, r.width() - 60, ch)
    p.setBrush(QBrush(QColor(ground)))
    round_frame(p, c, ch / 2, gold, 1.4)
    p.setBrush(Qt.NoBrush)
    round_frame(p, c.adjusted(4, 4, -4, -4), ch / 2 - 4, ink, 0.5)
    yy = c.top() + 11
    for row in rows:
        t = " · ".join(row)
        st = fit(Style(TITLE_FONT, 17, True), t, c.width() - 50)
        yy += 26
        text_c(p, mid, yy - 7, t, st, ink)
    # a great medallion between the cartouche and the foot
    top_m, bot_m = c.bottom() + 16, r.bottom() - 82
    if bot_m - top_m > 60:
        cy = (top_m + bot_m) / 2
        rr = min((bot_m - top_m) / 2, r.width() * 0.3)
        p.setBrush(Qt.NoBrush)
        p.setPen(pen(gold, 1.6))
        p.drawEllipse(QPointF(mid, cy), rr, rr)
        p.setPen(pen(ink, 0.6))
        p.drawEllipse(QPointF(mid, cy), rr - 5, rr - 5)
        p.drawEllipse(QPointF(mid, cy), rr - 16, rr - 16)
        n = int(2 * math.pi * (rr - 10.5) / 9)
        for k in range(n):
            a = 2 * math.pi * k / n
            p.drawEllipse(QPointF(mid + math.cos(a) * (rr - 10.5), cy + math.sin(a) * (rr - 10.5)), 2.2, 2.2)
        rosette(p, mid, cy, rr - 24, gold, 0.8, 16)
        rosette(p, mid, cy, (rr - 24) * 0.45, ink, 0.6, 8)
        for f in (1, -1):
            fleuron(p, mid - f * (rr + 26), cy, 18, gold, 0.8, f * -90)
    # garlands under it and the volume in an oval at the foot
    for f in (1, -1):
        fleuron(p, mid - f * 60, r.bottom() - 52, 16, gold, 0.8, f * -90)
    p.setBrush(QBrush(QColor(ground)))
    p.setPen(pen(gold, 1.4))
    p.drawEllipse(QPointF(mid, r.bottom() - 52), 36, 18)
    p.setBrush(Qt.NoBrush)
    p.setPen(pen(ink, 0.5))
    p.drawEllipse(QPointF(mid, r.bottom() - 52), 32, 14)
    text_c(p, mid, r.bottom() - 47, volume, Style(TITLE_FONT, 14, True), ink)


def spine(p, x0, y0, w, h, masechtot, volume, ground, ink, gold):
    mid = x0 + w / 2
    inner = w - 8
    # bands at the head and the foot, as on a bound book, with panels between them
    for yy in (y0 + 24, y0 + 36, y0 + h - 36, y0 + h - 24):
        p.setPen(pen(gold, 1.6))
        p.drawLine(QPointF(x0 + 2, yy), QPointF(x0 + w - 2, yy))
    for yy in (y0 + 30, y0 + h - 30):
        p.setPen(pen(ink, 0.6))
        p.drawLine(QPointF(x0 + 2, yy), QPointF(x0 + w - 2, yy))
    panel = QRectF(x0 + 4, y0 + 46, w - 8, h - 92)
    p.setPen(pen(ink, 0.6))
    p.drawRoundedRect(panel, 4, 4)
    y = panel.top() + 12
    for text in ("רא\"ש", "ורי\"ף"):
        st = fit(Style(TITLE_FONT, 13, True), text, inner - 4)
        y += st.size * 1.2
        text_c(p, mid, y, text, st, ink)
    y += 12
    rosette(p, mid, y, min(6, inner / 2 - 1), gold, 0.7, 6)
    # the masechtot one under another, in the middle of the spine
    sts = [fit(Style(TITLE_FONT, 11, True), m, inner - 4) for m in masechtot]
    size = min(st.size for st in sts)
    lh = size * 1.6
    top = max(y + 14, y0 + h / 2 - lh * len(masechtot) / 2)
    for k, m in enumerate(masechtot):
        text_c(p, mid, top + lh * (k + 1) - lh * 0.3, m, Style(TITLE_FONT, size, True), ink)
    rosette(p, mid, panel.bottom() - 48, min(6, inner / 2 - 1), gold, 0.7, 6)
    st = fit(Style(TITLE_FONT, 12, True), volume, inner - 4)
    text_c(p, mid, panel.bottom() - 20, volume, st, ink)


# ------------------------------------------------------------------ engraved gates (Vilna)
def outlined(p, x, y, text, st, colour, hatch=1.3, w=0.6):
    """big letters as in an engraving: their outline, and fine lines across them;
    centred on x, the baseline at y."""
    from PySide6.QtGui import QPainterPath as PP
    path = PP()
    path.addText(QPointF(x - width(st, text) / 2, y), qfont(st), text)
    p.save()
    p.setClipPath(path)
    p.setPen(pen(colour, 0.35))
    r = path.boundingRect()
    yy = r.top()
    while yy < r.bottom():
        p.drawLine(QPointF(r.left(), yy), QPointF(r.right(), yy))
        yy += hatch
    p.restore()
    p.setPen(pen(colour, w))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)


def crown(p, x, y, w, colour, lw=0.7):
    """a crown of the Torah, its foot at y, w wide."""
    h = w * 0.62
    p.setPen(pen(colour, lw))
    p.setBrush(QBrush(QColor(PAPER[0])))
    # the band, with jewels
    band = QRectF(x - w / 2, y - h * 0.24, w, h * 0.24)
    p.drawRoundedRect(band, 2, 2)
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(band.left(), band.top() + 2), QPointF(band.right(), band.top() + 2))
    p.drawLine(QPointF(band.left(), band.bottom() - 2), QPointF(band.right(), band.bottom() - 2))
    for k in range(5):
        jx = band.left() + w * (k + 0.5) / 5
        if k % 2:
            p.drawEllipse(QPointF(jx, band.center().y()), h * 0.05, h * 0.05)
        else:
            d = QPainterPath()
            d.moveTo(jx, band.top() + 3.5)
            d.lineTo(jx + h * 0.06, band.center().y())
            d.lineTo(jx, band.bottom() - 3.5)
            d.lineTo(jx - h * 0.06, band.center().y())
            d.closeSubpath()
            p.drawPath(d)
    # the points: five, the middle one highest, with balls, and leaves between them
    top = band.top()
    tips = []
    for k in range(5):
        t = (k - 2) / 2
        tx = x + t * w * 0.42
        ty = top - h * (0.62 - 0.18 * abs(t) ** 1.5)
        tips.append((tx, ty))
    path = QPainterPath()
    path.moveTo(band.left(), top)
    for k, (tx, ty) in enumerate(tips):
        lx = band.left() + w * k / 5 if k else band.left()
        path.quadTo(QPointF(tx - w * 0.06, top - (top - ty) * 0.3), QPointF(tx, ty))
        nx = tips[k + 1][0] if k < 4 else band.right()
        path.quadTo(QPointF(tx + w * 0.06, top - (top - ty) * 0.3), QPointF((tx + nx) / 2 if k < 4 else nx, top - (top - ty) * 0.15 if k < 4 else top))
    p.drawPath(path)
    for tx, ty in tips:
        p.setBrush(QBrush(QColor(PAPER[0])))
        p.drawEllipse(QPointF(tx, ty - h * 0.05), h * 0.05, h * 0.05)
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(tx, ty), QPointF(tx, top - 1))
    # an orb and a little cross of leaves at the top
    cx, cy = tips[2][0], tips[2][1] - h * 0.16
    p.drawEllipse(QPointF(cx, cy), h * 0.07, h * 0.07)
    # hatching inside the band of the crown, as engraved
    p.setPen(pen(colour, 0.3))
    for k in range(1, 4):
        p.drawLine(QPointF(band.left() + 3, top - h * 0.03 * k), QPointF(band.right() - 3, top - h * 0.03 * k))


def twisted_column(p, x, y1, y2, cw, colour, vine=True):
    """a twisted (Solomonic) column with a capital and a base, from y1 to y2."""
    cap_h, base_h = cw * 1.0, cw * 1.3
    p.setPen(pen(colour, 0.7))
    p.setBrush(Qt.NoBrush)
    # base
    bw = cw * 1.5
    p.drawRect(QRectF(x - bw / 2, y2 - base_h * 0.5, bw, base_h * 0.5))
    p.drawRect(QRectF(x - bw / 2 + 2.5, y2 - base_h * 0.5 + 2.5, bw - 5, base_h * 0.5 - 5))
    rosette(p, x, y2 - base_h * 0.25, base_h * 0.17, colour, 0.4, 6)
    p.drawRoundedRect(QRectF(x - cw * 0.68, y2 - base_h * 0.78, cw * 1.36, base_h * 0.28), 4, 4)
    p.drawRect(QRectF(x - cw * 0.6, y2 - base_h, cw * 1.2, base_h * 0.22))
    # capital: abacus, volutes, leaves
    p.drawRect(QRectF(x - cw * 0.85, y1, cw * 1.7, cap_h * 0.22))
    scroll(p, x - cw * 0.55, y1 + cap_h * 0.45, cap_h * 0.25, colour, 0.6, 1)
    scroll(p, x + cw * 0.55, y1 + cap_h * 0.45, cap_h * 0.25, colour, 0.6, -1)
    for k in (-1, 0, 1):
        lx = x + k * cw * 0.27
        path = QPainterPath()
        path.moveTo(lx, y1 + cap_h)
        path.quadTo(QPointF(lx - cw * 0.14, y1 + cap_h * 0.55), QPointF(lx, y1 + cap_h * 0.28))
        path.quadTo(QPointF(lx + cw * 0.14, y1 + cap_h * 0.55), QPointF(lx, y1 + cap_h))
        p.drawPath(path)
    p.drawLine(QPointF(x - cw * 0.55, y1 + cap_h), QPointF(x + cw * 0.55, y1 + cap_h))
    # the shaft: swelling edges and twisting bands
    top, bot = y1 + cap_h, y2 - base_h
    period = cw * 1.25
    n = max(2, int((bot - top) / period))
    period = (bot - top) / n
    amp = cw * 0.06
    for side in (-1, 1):
        path = QPainterPath()
        for k in range(n * 16 + 1):
            yy = top + (bot - top) * k / (n * 16)
            xx = x + side * (cw / 2 + amp * math.sin(2 * math.pi * (yy - top) / period * 2))
            if k:
                path.lineTo(xx, yy)
            else:
                path.moveTo(xx, yy)
        p.drawPath(path)
    p.setPen(pen(colour, 0.55))
    for k in range(n):
        yb = top + k * period
        for off, w_ in ((0, 0.6), (period * 0.18, 0.35), (period * 0.36, 0.35)):
            path = QPainterPath()
            path.moveTo(x - cw / 2, yb + off)
            path.cubicTo(QPointF(x - cw * 0.15, yb + off + period * 0.05), QPointF(x + cw * 0.15, yb + off + period * 0.45),
                         QPointF(x + cw / 2, yb + off + period * 0.5))
            p.setPen(pen(colour, w_))
            p.drawPath(path)
    if vine:
        # a vine winding round it, with leaves and grapes
        p.setPen(pen(colour, 0.5))
        path = QPainterPath()
        for k in range(n * 20 + 1):
            yy = top + (bot - top) * k / (n * 20)
            xx = x + cw * 0.5 * math.sin(2 * math.pi * (yy - top) / period + 1.2)
            if k:
                path.lineTo(xx, yy)
            else:
                path.moveTo(xx, yy)
        p.drawPath(path)
        for k in range(n):
            yy = top + period * (k + 0.3)
            side = 1 if k % 2 else -1
            lx = x + side * cw * 0.55
            leaf = QPainterPath()
            leaf.moveTo(x + side * cw * 0.3, yy)
            leaf.cubicTo(QPointF(lx, yy - cw * 0.35), QPointF(lx + side * cw * 0.3, yy - cw * 0.1), QPointF(lx + side * cw * 0.2, yy + cw * 0.15))
            leaf.cubicTo(QPointF(lx, yy + cw * 0.2), QPointF(x + side * cw * 0.4, yy + cw * 0.1), QPointF(x + side * cw * 0.3, yy))
            p.setBrush(QBrush(QColor(PAPER[0])))
            p.drawPath(leaf)
            p.setBrush(Qt.NoBrush)
            gx, gy = x - side * cw * 0.35, yy + period * 0.45
            for gi, (dx, dy) in enumerate(((0, 0), (-2.4, 2.6), (2.4, 2.6), (0, 5.2), (-2.4, 7.8 - 2.6), (2.4, 7.8 - 2.6), (0, 9.5))):
                p.setBrush(QBrush(QColor(PAPER[0])))
                p.drawEllipse(QPointF(gx + dx, gy + dy), 1.5, 1.5)
            p.setBrush(Qt.NoBrush)


def rope(p, x1, y1, x2, y2, h, colour, w=0.45):
    """a twisted rope along a side (horizontal or vertical)."""
    horiz = abs(y2 - y1) < abs(x2 - x1)
    L = abs(x2 - x1) if horiz else abs(y2 - y1)
    n = max(2, int(L / (h * 0.7)))
    step = L / n
    p.setPen(pen(colour, w))
    p.setBrush(Qt.NoBrush)

    def pt(u, v):
        return QPointF(x1 + u, y1 + v) if horiz else QPointF(x1 + v, y1 + u)
    p.drawLine(pt(0, 0), pt(L, 0))
    p.drawLine(pt(0, h), pt(L, h))
    for k in range(n):
        u = k * step
        path = QPainterPath()
        path.moveTo(pt(u, h))
        path.cubicTo(pt(u + step * 0.1, h * 0.3), pt(u + step * 0.6, 0), pt(u + step * 1.2, 0))
        p.drawPath(path)


def cartouche(p, r, colour, fill="white"):
    """a frame with scrolled ends, for a line of text."""
    p.setPen(pen(colour, 0.9))
    p.setBrush(QBrush(QColor(fill)))
    h = r.height()
    path = QPainterPath()
    path.moveTo(r.left() + h * 0.5, r.top())
    path.lineTo(r.right() - h * 0.5, r.top())
    path.quadTo(QPointF(r.right() - h * 0.15, r.center().y()), QPointF(r.right() - h * 0.5, r.bottom()))
    path.lineTo(r.left() + h * 0.5, r.bottom())
    path.quadTo(QPointF(r.left() + h * 0.15, r.center().y()), QPointF(r.left() + h * 0.5, r.top()))
    p.drawPath(path)
    p.setBrush(Qt.NoBrush)
    p.setPen(pen(colour, 0.4))
    p.drawPath(path.translated(0, 0))
    inner = QRectF(r.left() + 4, r.top() + 3, r.width() - 8, r.height() - 6)
    path2 = QPainterPath()
    path2.moveTo(inner.left() + h * 0.5, inner.top())
    path2.lineTo(inner.right() - h * 0.5, inner.top())
    path2.quadTo(QPointF(inner.right() - h * 0.2, inner.center().y()), QPointF(inner.right() - h * 0.5, inner.bottom()))
    path2.lineTo(inner.left() + h * 0.5, inner.bottom())
    path2.quadTo(QPointF(inner.left() + h * 0.2, inner.center().y()), QPointF(inner.left() + h * 0.5, inner.top()))
    p.drawPath(path2)
    for f in (1, -1):
        cx = r.left() + h * 0.12 if f == 1 else r.right() - h * 0.12
        scroll(p, cx, r.top() + h * 0.28, h * 0.22, colour, 0.6, f)
        scroll(p, cx, r.bottom() - h * 0.28, h * 0.22, colour, 0.6, f)


def gate(pw, ph, name, masechet, sub, foot_text, colour="black", style=4):
    """A title page in the manner of the Vilna Shas and its new printings: a gate of two
    twisted columns, a crown over an arch, the name in the arch, the masechet in great
    engraved letters, a line or two under it, the days in a cartouche at the foot.
    style 4: twisted columns with a vine, a round arch and a crown; 5: fluted columns, a
    rounded broken pediment with scrolls and a crown between them, garlands; 6: a frame of
    rope and leaves, an arched panel with a crown in an oval."""
    def paint(p):
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing, True)
        m = 26.0
        mid = pw / 2
        # the border: a thick line, a rope, a thin line
        p.setPen(pen(colour, 1.8))
        p.drawRect(QRectF(m, m, pw - 2 * m, ph - 2 * m))
        rh = 7
        rope(p, m + 3, m + 3, pw - m - 3, m + 3, rh, colour)
        rope(p, m + 3, ph - m - 3 - rh, pw - m - 3, ph - m - 3 - rh, rh, colour)
        rope(p, m + 3, m + 3 + rh, m + 3, ph - m - 3 - rh, rh, colour)
        rope(p, pw - m - 3 - rh, m + 3 + rh, pw - m - 3 - rh, ph - m - 3 - rh, rh, colour)
        p.setPen(pen(colour, 0.6))
        b = QRectF(m + 3 + rh + 3, m + 3 + rh + 3, pw - 2 * (m + rh + 6), ph - 2 * (m + rh + 6))
        p.drawRect(b)
        for cx, cy in ((b.left(), b.top()), (b.right(), b.top()), (b.left(), b.bottom()), (b.right(), b.bottom())):
            p.setBrush(QBrush(QColor(PAPER[0])))
            p.drawRect(QRectF(cx - 9, cy - 9, 18, 18))
            p.setBrush(Qt.NoBrush)
            rosette(p, cx, cy, 7, colour, 0.45, 8)
        L, R = b.left() + 14, b.right() - 14
        foot = b.bottom() - 66
        cw = 30.0
        xl, xr = L + cw * 0.8, R - cw * 0.8
        if style in (4, 5):
            ent = b.top() + 128          # the entablature's top
            ent_h = 26.0
            cap_top = ent + ent_h
            # entablature
            p.setPen(pen(colour, 1.0))
            p.drawRect(QRectF(L - 4, ent, R - L + 8, ent_h))
            dentils(p, L, R, ent + 3, 7, colour, 0.4)
            leaf_band(p, L, R, ent + 13, 10, colour, 0.4)
            if style == 4:
                twisted_column(p, xl, cap_top, foot, cw, colour)
                twisted_column(p, xr, cap_top, foot, cw, colour)
                # over the entablature: a half round tympanum with a crown above it
                tr = (R - L) * 0.34
                for k, lw in ((0, 1.1), (6, 0.45)):
                    path = QPainterPath()
                    path.moveTo(mid - tr + k, ent)
                    path.arcTo(QRectF(mid - tr + k, ent - tr * 0.62 + k, 2 * (tr - k), 2 * (tr * 0.62 - k)), 180, -180)
                    p.setPen(pen(colour, lw))
                    p.drawPath(path)
                # rays in the tympanum, as engraved
                p.setPen(pen(colour, 0.3))
                for k in range(1, 24):
                    a = math.pi * k / 24
                    p.drawLine(QPointF(mid - math.cos(a) * (tr - 10), ent - math.sin(a) * (tr * 0.62 - 10)),
                               QPointF(mid - math.cos(a) * (tr * 0.45), ent - math.sin(a) * (tr * 0.62 * 0.45)))
                crown(p, mid, ent - tr * 0.62 - 2, 62, colour)
                for f in (1, -1):
                    path = QPainterPath()
                    sx = mid - f * (tr + 6)
                    path.moveTo(sx, ent)
                    path.cubicTo(QPointF(sx - f * 20, ent - 10), QPointF(sx - f * 30, ent - 34), QPointF(sx - f * 52, ent - 28))
                    p.setPen(pen(colour, 0.7))
                    p.drawPath(path)
                    scroll(p, sx - f * 54, ent - 22, 7, colour, 0.6, f)
                    p.drawEllipse(QPointF(mid - f * (R - L) * 0.47, ent - 8), 6, 6)
                    rosette(p, mid - f * (R - L) * 0.47, ent - 8, 5, colour, 0.35, 6)
            else:
                column(p, xl, cap_top, foot, cw, colour)
                column(p, xr, cap_top, foot, cw, colour)
                # a broken pediment of two scrolls rising to a crown on a pedestal
                for f in (1, -1):
                    path = QPainterPath()
                    sx = mid - f * (R - L) * 0.48
                    path.moveTo(sx, ent)
                    path.cubicTo(QPointF(sx + f * 40, ent - 4), QPointF(mid - f * 70, ent - 70), QPointF(mid - f * 32, ent - 58))
                    p.setPen(pen(colour, 1.1))
                    p.drawPath(path)
                    path2 = QPainterPath()
                    path2.moveTo(sx + f * 10, ent)
                    path2.cubicTo(QPointF(sx + f * 46, ent - 2), QPointF(mid - f * 72, ent - 60), QPointF(mid - f * 38, ent - 50))
                    p.setPen(pen(colour, 0.45))
                    p.drawPath(path2)
                    scroll(p, mid - f * 36, ent - 50, 9, colour, 0.8, f)
                    garland(p, mid - f * 22, mid - f * (R - L) * 0.4, ent - 6, 9, colour, 0.5)
                p.setPen(pen(colour, 0.9))
                p.setBrush(QBrush(QColor(PAPER[0])))
                p.drawRect(QRectF(mid - 18, ent - 30, 36, 30))
                p.setBrush(Qt.NoBrush)
                rosette(p, mid, ent - 15, 10, colour, 0.45, 8)
                crown(p, mid, ent - 32, 54, colour)
            # the arch between the columns, round, with a keystone and garlands
            ix1, ix2 = xl + cw * 0.85, xr - cw * 0.85
            rx = (ix2 - ix1) / 2
            ry = rx * 0.5
            spring = cap_top + ry + 4
            for k, lw in ((0, 1.0), (8, 0.45)):
                path = QPainterPath()
                path.moveTo(ix1 + k, foot)
                path.lineTo(ix1 + k, spring)
                path.arcTo(QRectF(ix1 + k, spring - (ry - k), 2 * (rx - k), 2 * (ry - k)), 180, -180)
                path.lineTo(ix2 - k, foot)
                p.setPen(pen(colour, lw))
                p.drawPath(path)
            p.setPen(pen(colour, 0.35))
            for k in range(1, 16):
                a = math.pi * k / 16
                p.drawLine(QPointF(mid - math.cos(a) * rx, spring - math.sin(a) * ry),
                           QPointF(mid - math.cos(a) * (rx - 8), spring - math.sin(a) * (ry - 8)))
            p.setPen(pen(colour, 0.8))
            p.setBrush(QBrush(QColor(PAPER[0])))
            key = QPainterPath()
            key.moveTo(mid - 8, spring - ry - 1)
            key.lineTo(mid + 8, spring - ry - 1)
            key.lineTo(mid + 5, spring - ry + 13)
            key.lineTo(mid - 5, spring - ry + 13)
            key.closeSubpath()
            p.drawPath(key)
            p.setBrush(Qt.NoBrush)
            garland(p, ix1 + 8, mid - 10, spring - ry * 0.25, 12, colour, 0.45)
            garland(p, mid + 10, ix2 - 8, spring - ry * 0.25, 12, colour, 0.45)
            name_y = spring + 14
            inner = ix2 - ix1 - 24
        else:
            # a panel with an arched head, a crown in an oval over it, fleurons in the corners
            panel = QRectF(L + 10, b.top() + 70, R - L - 20, foot - b.top() - 70)
            rr = panel.width() / 2
            for k, lw in ((0, 1.2), (7, 0.45)):
                path = QPainterPath()
                path.moveTo(panel.left() + k, panel.bottom())
                path.lineTo(panel.left() + k, panel.top() + rr * 0.55)
                path.arcTo(QRectF(panel.left() + k, panel.top() + k, panel.width() - 2 * k, rr * 1.1 - 2 * k), 180, -180)
                path.lineTo(panel.right() - k, panel.bottom())
                p.setPen(pen(colour, lw))
                p.drawPath(path)
            lobed_arch(p, panel.left() + 14, panel.right() - 14, panel.top() + rr * 0.55, rr * 0.55 - 14, colour, 0.45, 11)
            # leaves up the sides
            for side in (panel.left() - 7, panel.right() + 7):
                yy = panel.top() + rr * 0.6
                while yy < panel.bottom() - 10:
                    for f in (1, -1):
                        leaf = QPainterPath()
                        leaf.moveTo(side, yy)
                        leaf.quadTo(QPointF(side + f * 7, yy - 4), QPointF(side + f * 3, yy - 11))
                        leaf.quadTo(QPointF(side, yy - 6), QPointF(side, yy))
                        p.setPen(pen(colour, 0.45))
                        p.drawPath(leaf)
                    yy += 12
            oy = b.top() + 40
            p.setPen(pen(colour, 1.0))
            p.setBrush(QBrush(QColor(PAPER[0])))
            p.drawEllipse(QPointF(mid, oy + 10), 46, 30)
            p.setBrush(Qt.NoBrush)
            p.setPen(pen(colour, 0.4))
            p.drawEllipse(QPointF(mid, oy + 10), 41, 25)
            crown(p, mid, oy + 28, 50, colour)
            for f in (1, -1):
                fleuron(p, mid - f * 70, oy + 14, 18, colour, 0.5, f * -90)
                fleuron(p, b.left() + 30 if f == 1 else b.right() - 30, b.top() + 30, 16, colour, 0.5, -45 if f == 1 else 45)
            name_y = panel.top() + rr * 0.55 + 6
            inner = panel.width() - 50
        # the step under the gate, the days in a cartouche
        p.setPen(pen(colour, 1.0))
        p.drawRect(QRectF(L - 4, foot, R - L + 8, b.bottom() - 10 - foot))
        p.setPen(pen(colour, 0.25))
        yy = foot + 3
        while yy < b.bottom() - 13:
            p.drawLine(QPointF(L - 1, yy), QPointF(R + 1, yy))
            yy += 3.2
        cr = QRectF(mid - 110, foot + 12, 220, 32)
        cartouche(p, cr, colour)
        text_c(p, mid, cr.center().y() + 4, foot_text, Style(TEXT_FONT, 11), colour)
        # the lines
        st = fit(Style(TITLE_FONT, 30, True), name, inner)
        y = name_y + st.size
        text_c(p, mid, y, name, st, colour)
        y += 14
        p.setPen(pen(colour, 0.5))
        p.drawLine(QPointF(mid - 60, y), QPointF(mid - 9, y))
        p.drawLine(QPointF(mid + 9, y), QPointF(mid + 60, y))
        rosette(p, mid, y, 5.5, colour, 0.4, 6)
        y += 22
        text_c(p, mid, y + 4, "מסכת", Style(TITLE_FONT, 16, True), colour)
        st = fit(Style(TITLE_FONT, 64, True), masechet, inner)
        y += st.size * 1.05
        outlined(p, mid, y, masechet, st, colour)
        y += 18
        for text in sub:
            st = fit(Style(TEXT_FONT, 12), text, inner)
            y += st.size * 1.45
            text_c(p, mid, y, text, st, colour)
        p.restore()
    return paint


# ------------------------------------------------------------------ the gate of Oz Vehadar
GREY_LINE, GREY_LEAF, GREY_TINT, INK = "#6a6a6a", "#8f8f8f", "#e9e9e9", "#1e1e1e"


def acanthus(p, x, y, s, angle, colour, w=0.5):
    """a curling leaf of s points, from (x, y) towards angle (degrees, 0 = right)."""
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.setPen(pen(colour, w))
    p.setBrush(QBrush(QColor(PAPER[0])))
    path = QPainterPath()
    path.moveTo(0, 0)
    path.cubicTo(QPointF(s * 0.3, -s * 0.45), QPointF(s * 0.8, -s * 0.4), QPointF(s, -s * 0.05))
    path.cubicTo(QPointF(s * 0.75, -s * 0.12), QPointF(s * 0.7, s * 0.02), QPointF(s * 0.55, s * 0.05))
    path.cubicTo(QPointF(s * 0.62, s * 0.18), QPointF(s * 0.45, s * 0.3), QPointF(0, 0))
    p.drawPath(path)
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(s * 0.1, -s * 0.02), QPointF(s * 0.8, -s * 0.08))
    p.restore()


def filigree(p, r, colour=GREY_LEAF, tint=GREY_TINT, seed=1, cell=30.0):
    """the area r filled with a light ground and a pattern of curling stems and leaves,
    the same on both sides of the page's middle (as in an engraved frame)."""
    import random
    rnd = random.Random(seed)
    p.save()
    p.fillRect(r, QColor(tint))
    p.setClipRect(r)
    mid = r.center().x()
    cols = int(r.width() / 2 / cell) + 2
    rows = int(r.height() / cell) + 2
    shapes = []
    for i in range(cols):
        for j in range(rows):
            x = mid + i * cell + rnd.uniform(-4, 4)
            y = r.top() + j * cell + (cell / 2 if i % 2 else 0) + rnd.uniform(-4, 4)
            shapes.append((x - mid, y, rnd.uniform(0, 360), rnd.uniform(0.75, 1.1), rnd.random() < 0.5))
    for f in (1, -1):
        for dx, y, a, sc, curl in shapes:
            x = mid + f * dx
            ang = a if f == 1 else 180 - a
            s = cell * 0.55 * sc
            # a stem curving to a spiral, with leaves on it
            rad = math.radians(ang)
            ex, ey = x + math.cos(rad) * s, y + math.sin(rad) * s
            path = QPainterPath()
            path.moveTo(x, y)
            path.cubicTo(QPointF(x + math.cos(rad + 0.9) * s * 0.6, y + math.sin(rad + 0.9) * s * 0.6),
                         QPointF(ex + math.cos(rad - 1.2) * s * 0.4, ey + math.sin(rad - 1.2) * s * 0.4), QPointF(ex, ey))
            p.setPen(pen(colour, 0.5))
            p.drawPath(path)
            scroll(p, ex, ey, s * 0.22, colour, 0.45, f if curl else -f)
            acanthus(p, x, y, s * 0.55, ang + 60, colour, 0.4)
            acanthus(p, x + math.cos(rad) * s * 0.5, y + math.sin(rad) * s * 0.5, s * 0.4, ang - 70, colour, 0.4)
    p.restore()


def text_path(x, y, text, st, maxw=None):
    """the outline of text, centred on x with its baseline at y, no wider than maxw."""
    from PySide6.QtGui import QTransform
    path = QPainterPath()
    path.addText(QPointF(0, 0), qfont(st), text)
    r = path.boundingRect()
    k = min(1.0, maxw / r.width()) if maxw else 1.0
    t = QTransform()
    t.translate(x - (r.left() + r.width() / 2) * k, y)
    t.scale(k, k)
    return t.map(path)


def shaded(p, x, y, text, st, line=GREY_LINE, maxw=None, shade=("#f6f6f6", "#c4c4c4"), shadow="#9a9a9a"):
    """great letters as in the gate of Oz Vehadar: shaded light grey within a dark outline,
    with a shadow; centred on x, the baseline at y."""
    from PySide6.QtGui import QLinearGradient
    path = text_path(x, y, text, st, maxw)
    p.save()
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(shadow)))
    p.drawPath(path.translated(1.6, 1.6))
    r = path.boundingRect()
    g = QLinearGradient(QPointF(0, r.top()), QPointF(0, r.bottom()))
    g.setColorAt(0, QColor(shade[0]))
    g.setColorAt(1, QColor(shade[1]))
    p.setBrush(QBrush(g))
    p.setPen(pen(line, 0.8))
    p.drawPath(path)
    p.restore()


def arc_text(p, cx, cy, rad, text, st, colour=INK):
    """text along the top of a circle (centre cx, cy; rad to the baseline), read from
    right to left, centred on the top."""
    total = width(st, text)
    a = math.pi / 2 - (total / 2) / rad       # the angle of the right end (y up)
    p.save()
    p.setPen(QColor(colour))
    p.setFont(qfont(st))
    for ch in text:
        w = width(st, ch)
        mid_a = a + (w / 2) / rad
        x = cx + rad * math.cos(mid_a)
        y = cy - rad * math.sin(mid_a)
        p.save()
        p.translate(x, y)
        p.rotate(90 - math.degrees(mid_a))
        p.drawText(QPointF(-w / 2, 0), ch)
        p.restore()
        a += w / rad
    p.restore()


def divider(p, x, y, half, colour=GREY_LINE):
    p.setPen(pen(colour, 0.6))
    p.drawLine(QPointF(x - half, y), QPointF(x - 8, y))
    p.drawLine(QPointF(x + 8, y), QPointF(x + half, y))
    d = QPainterPath()
    d.moveTo(x - 6, y)
    d.lineTo(x, y - 3)
    d.lineTo(x + 6, y)
    d.lineTo(x, y + 3)
    d.closeSubpath()
    p.setBrush(QBrush(QColor(colour)))
    p.drawPath(d)
    p.setBrush(Qt.NoBrush)
    for f in (1, -1):
        scroll(p, x + f * (half + 4), y - 2, 3.5, colour, 0.5, -f)


def flame(p, x, y, s, colour=GREY_LINE, fill="#d8d8d8"):
    path = QPainterPath()
    path.moveTo(x, y)
    path.cubicTo(QPointF(x - s * 0.6, y - s * 0.3), QPointF(x - s * 0.2, y - s * 0.8), QPointF(x, y - s * 1.2))
    path.cubicTo(QPointF(x + s * 0.25, y - s * 0.75), QPointF(x + s * 0.6, y - s * 0.3), QPointF(x, y))
    p.setPen(pen(colour, 0.6))
    p.setBrush(QBrush(QColor(fill)))
    p.drawPath(path)
    p.setBrush(Qt.NoBrush)


SEDARIM_SIDES = (("אמונת", "עתיך", "חוסן"), ("ישועות", "חכמת", "ודעת"))


# the colours of a gate: lines, leaves, the ground of the filigree, ink, the inside of the
# panels, the shading of the great letters, their shadow, the ground of a cover
GREY = dict(line=GREY_LINE, leaf=GREY_LEAF, tint=GREY_TINT, ink=INK, paper="white",
            shade=("#f6f6f6", "#c4c4c4"), shadow="#9a9a9a", ground=None)
PALETTES = {
    "תכלת": dict(line="#1f3d66", leaf="#6d90b8", tint="#cfe2f1", ink="#14284a", paper="#f1f7fc",
                 shade=("#ffffff", "#b3cbe3"), shadow="#7e9bb9", ground="#cfe2f1"),
    "תכלת עמוק": dict(line="#173156", leaf="#5a82ae", tint="#a9cbe6", ink="#0f2242", paper="#e6f0f9",
                      shade=("#ffffff", "#a3c0de"), shadow="#6b8bb0", ground="#a9cbe6"),
    "שמנת": dict(line="#5b4123", leaf="#a88a5c", tint="#efe3c8", ink="#3a2814", paper="#fbf6ea",
                 shade=("#fffaf0", "#e0c99a"), shadow="#b39a6e", ground="#efe3c8"),
}


def gate_page(w, h, items, foot_title, foot_lines, pal=GREY, sides=(("אמונת", "עתיך", "חוסן"), ("ישועות", "חכמת", "ודעת")),
              feet=(("זרעים", "מועד", "נשים"), ("נזיקין", "קדשים", "טהרות")), margin=24.0):
    """The gate of the Oz Vehadar Shas, w by h points from (0, 0): a frame of filigree, a
    great round arch, pillars on both sides with the words of the verse at the head, a
    vine down them and the sedarim at the foot, and a little gate of twisted columns and
    flames at the foot with foot_title along its arch and foot_lines in it. items, in the
    arch, one block in its middle: ("shaded", text, size) great shaded letters, ("text",
    text, size), ("div",) an ornament."""
    def paint(p):
        PAPER[0] = pal["paper"]
        line, leaf, tint, ink = pal["line"], pal["leaf"], pal["tint"], pal["ink"]
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing, True)
        m = margin
        O = QRectF(m, m, w - 2 * m, h - 2 * m)
        I = O.adjusted(7, 7, -7, -7)
        filigree(p, I, leaf, tint, seed=7, cell=22)
        p.setPen(pen(line, 1.6))
        p.setBrush(Qt.NoBrush)
        p.drawRect(O)
        p.setPen(pen(line, 0.6))
        p.drawRect(O.adjusted(3, 3, -3, -3))
        p.drawRect(I)
        mid = w / 2
        pil = 74.0
        xr1, xl1 = I.right() - pil, I.left() + pil
        panel_bot = I.top() + I.height() * 0.80
        ax1, ax2 = xl1 + 4, xr1 - 4
        rx = (ax2 - ax1) / 2
        spring = I.top() + 22 + rx
        band = 13.0
        outer = QPainterPath()
        outer.moveTo(ax1, panel_bot)
        outer.lineTo(ax1, spring)
        outer.arcTo(QRectF(ax1, spring - rx, 2 * rx, 2 * rx), 180, -180)
        outer.lineTo(ax2, panel_bot)
        outer.closeSubpath()
        inner = QPainterPath()
        inner.moveTo(ax1 + band, panel_bot)
        inner.lineTo(ax1 + band, spring)
        inner.arcTo(QRectF(ax1 + band, spring - rx + band, 2 * (rx - band), 2 * (rx - band)), 180, -180)
        inner.lineTo(ax2 - band, panel_bot)
        inner.closeSubpath()
        p.save()
        p.setClipPath(outer.subtracted(inner))
        filigree(p, QRectF(ax1, spring - rx, 2 * rx, panel_bot - spring + rx), leaf, tint, seed=3, cell=11)
        p.restore()
        p.setBrush(QBrush(QColor(pal["paper"])))
        p.setPen(pen(line, 0.8))
        p.drawPath(inner)
        p.setBrush(Qt.NoBrush)
        p.setPen(pen(line, 1.0))
        p.drawPath(outer)
        # the pillars
        for x0, words, foot in ((xr1, sides[0], feet[0]), (I.left(), sides[1], feet[1])):
            px1, px2 = x0 + 7, x0 + pil - 7
            pc = (px1 + px2) / 2
            top_r = QRectF(px1, spring - 6, px2 - px1, 66)
            mid_r = QRectF(px1 + 6, top_r.bottom() + 16, px2 - px1 - 12, panel_bot - top_r.bottom() - 30)
            foot_r = QRectF(px1, panel_bot + 10, px2 - px1, I.bottom() - panel_bot - 18)
            for rr in (top_r, mid_r, foot_r):
                p.setBrush(QBrush(QColor(pal["paper"])))
                p.setPen(pen(line, 0.9))
                p.drawRect(rr)
                p.setBrush(Qt.NoBrush)
                p.setPen(pen(line, 0.4))
                p.drawRect(rr.adjusted(2.5, 2.5, -2.5, -2.5))
            for yy in (top_r.bottom() + 4, mid_r.bottom() + 3):
                p.setPen(pen(line, 0.8))
                p.setBrush(QBrush(QColor(pal["paper"])))
                p.drawRect(QRectF(px1 - 4, yy, px2 - px1 + 8, 6))
                p.setBrush(Qt.NoBrush)
            # down the pillar: a vine, its leaves and rosettes
            vt, vb = mid_r.top() + 14, mid_r.bottom() - 14
            path = QPainterPath()
            n = 120
            for k in range(n + 1):
                yy = vt + (vb - vt) * k / n
                xx = pc + 8 * math.sin((yy - vt) / 26 * math.pi)
                if k:
                    path.lineTo(xx, yy)
                else:
                    path.moveTo(xx, yy)
            p.setPen(pen(leaf, 0.7))
            p.drawPath(path)
            yy, k = vt + 13, 0
            while yy < vb - 6:
                f = 1 if k % 2 else -1
                acanthus(p, pc + 8 * math.sin((yy - vt) / 26 * math.pi), yy, 13, 90 + f * 70, line, 0.45)
                yy += 13
                k += 1
            rosette(p, pc, mid_r.top() + 9, 5, line, 0.45, 6)
            rosette(p, pc, mid_r.bottom() - 9, 5, line, 0.45, 6)
            st = Style(TITLE_FONT, 13, True)
            for k, wd in enumerate(words):
                text_c(p, pc, top_r.top() + 20 + k * 17, wd, st, line)
            for k, wd in enumerate(foot):
                text_c(p, pc, foot_r.top() + foot_r.height() / 2 - 13 + k * 19, wd, st, line)
        # the little gate at the foot
        gw, gt = 132.0, panel_bot + 8
        gb = I.bottom() - 4
        gx1, gx2 = mid - gw / 2, mid + gw / 2
        p.setBrush(QBrush(QColor(pal["paper"])))
        p.setPen(pen(line, 0.8))
        gp = QPainterPath()
        gp.moveTo(gx1 + 12, gb)
        gp.lineTo(gx1 + 12, gt + 34)
        gp.quadTo(QPointF(mid, gt - 6), QPointF(gx2 - 12, gt + 34))
        gp.lineTo(gx2 - 12, gb)
        gp.closeSubpath()
        p.drawPath(gp)
        p.setBrush(Qt.NoBrush)
        for cx in (gx1 + 6, gx2 - 6):
            twisted_column(p, cx, gt + 26, gb, 9, line, vine=False)
            p.setPen(pen(line, 0.7))
            p.setBrush(QBrush(QColor(pal["paper"])))
            p.drawRect(QRectF(cx - 7, gt + 18, 14, 8))
            p.setBrush(Qt.NoBrush)
            flame(p, cx, gt + 17, 12, line, pal["shade"][1])
        if foot_title:
            arc_text(p, mid, gt + 64, 38, foot_title, Style(TEXT_FONT, 9.5), ink)
        box = QRectF(mid - 34, gt + 44, 68, gb - gt - 52)
        p.setPen(pen(line, 1.0))
        p.drawRect(box)
        p.setPen(pen(line, 0.4))
        p.drawRect(box.adjusted(2.5, 2.5, -2.5, -2.5))
        yy = box.top() + 4
        for text, size in foot_lines:
            st = fit(Style(TITLE_FONT, size, True), text, box.width() - 10)
            yy += st.size * 1.25
            text_c(p, mid, yy, text, st, ink)
        # the block of lines in the arch
        w_in = 2 * (rx - band) - 30
        ops, y = [], 0.0
        for it in items:
            if it[0] == "shaded":
                st = Style(TITLE_FONT, it[2], True)
                y += st.size * (0.75 if not ops else 1.0)
                ops.append(("shaded", y, it[1], st))
                y += st.size * 0.25
            elif it[0] == "text":
                st = fit(Style(TITLE_FONT, it[2], True), it[1], w_in)
                y += st.size * 1.4
                ops.append(("text", y, it[1], st))
            else:
                y += 18
                ops.append(("div", y - 4, None, None))
                y += 4
        top, bot = spring - rx * 0.45, panel_bot - 16
        y0 = top + max(0.0, (bot - top - y) / 2) - 10
        for kind, yy, text, st in ops:
            if kind == "shaded":
                shaded(p, mid, y0 + yy, text, st, line, maxw=w_in - 10, shade=pal["shade"], shadow=pal["shadow"])
            elif kind == "text":
                text_c(p, mid, y0 + yy, text, st, ink)
            else:
                divider(p, mid, y0 + yy, 40, line)
        p.restore()
        PAPER[0] = "white"
    return paint


def gate_cover(trim, pages, items, spine_lines, masechtot, volume, pal, bleed=3.0, leaf=0.1):
    """-> (width, height, paint): a whole cover in the manner of the gate: the front on
    the left (a Hebrew book: its spine is on the right of the front), the spine, the back
    on the right, left plain; with the bleed all round."""
    tw, th = trim[0] * PT_PER_MM, trim[1] * PT_PER_MM
    sw = spine_width(pages, leaf) * PT_PER_MM
    b = bleed * PT_PER_MM
    W, H = 2 * tw + sw + 2 * b, th + 2 * b
    front = gate_page(tw, th, items, "", [(volume, 15)], pal, margin=20.0)

    def paint(p):
        p.save()
        p.fillRect(QRectF(0, 0, W, H), QColor(pal["ground"]))
        p.translate(b, b)
        front(p)
        p.restore()
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing, True)
        gate_spine(p, b + tw, b, sw, th, spine_lines, masechtot, volume, pal)
        p.restore()
    return W, H, paint


def gate_spine(p, x0, y0, w, h, spine_lines, masechtot, volume, pal):
    line, ink = pal["line"], pal["ink"]
    mid = x0 + w / 2
    inner = w - 10
    PAPER[0] = pal["paper"]
    # filigree down the spine, a frame, panels for the name and the masechtot
    r = QRectF(x0 + 2, y0 + 20, w - 4, h - 40)
    filigree(p, r, pal["leaf"], pal["tint"], seed=11, cell=14)
    p.setPen(pen(line, 1.2))
    p.drawRect(r)
    p.setPen(pen(line, 0.5))
    p.drawRect(r.adjusted(2.5, 2.5, -2.5, -2.5))
    top = QRectF(x0 + 6, y0 + 40, w - 12, 118)
    p.setBrush(QBrush(QColor(pal["paper"])))
    p.setPen(pen(line, 0.9))
    p.drawRoundedRect(top, (w - 12) / 2, (w - 12) / 2)
    p.setBrush(Qt.NoBrush)
    y = top.top() + 30
    for k, it in enumerate(spine_lines):
        if it == "div":
            y += 6
            p.setPen(pen(line, 0.6))
            p.drawLine(QPointF(mid - inner / 2 + 4, y), QPointF(mid - 4, y))
            p.drawLine(QPointF(mid + 4, y), QPointF(mid + inner / 2 - 4, y))
            p.setBrush(QBrush(QColor(line)))
            d = QPainterPath()
            d.moveTo(mid - 3, y)
            d.lineTo(mid, y - 2)
            d.lineTo(mid + 3, y)
            d.lineTo(mid, y + 2)
            d.closeSubpath()
            p.drawPath(d)
            p.setBrush(Qt.NoBrush)
            y += 8
            continue
        st = fit(Style(TITLE_FONT, 13, True), it, inner - 6)
        y += st.size * 1.2
        text_c(p, mid, y, it, st, ink)
    n = len(masechtot)
    sts = [fit(Style(TITLE_FONT, 11, True), m, inner - 8) for m in masechtot]
    size = min(st.size for st in sts)
    lh = size * 1.7
    box = QRectF(x0 + 6, y0 + h / 2 - lh * n / 2 - 12, w - 12, lh * n + 24)
    p.setBrush(QBrush(QColor(pal["paper"])))
    p.setPen(pen(line, 0.9))
    p.drawRect(box)
    p.setBrush(Qt.NoBrush)
    p.setPen(pen(line, 0.4))
    p.drawRect(box.adjusted(2.5, 2.5, -2.5, -2.5))
    for k, m in enumerate(masechtot):
        text_c(p, mid, box.top() + 12 + lh * (k + 1) - lh * 0.3, m, Style(TITLE_FONT, size, True), ink)
    vb = QRectF(x0 + 6, y0 + h - 100, w - 12, 50)
    p.setBrush(QBrush(QColor(pal["paper"])))
    p.setPen(pen(line, 0.9))
    p.drawRoundedRect(vb, 8, 8)
    p.setBrush(Qt.NoBrush)
    st = fit(Style(TITLE_FONT, 12, True), volume, inner - 6)
    text_c(p, mid, vb.center().y() + 4, volume, st, ink)
    PAPER[0] = "white"
