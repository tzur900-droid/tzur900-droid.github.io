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
    p.setBrush(QBrush(QColor("white")))
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
            p.setBrush(QBrush(QColor("white")))
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
            p.setBrush(QBrush(QColor("white")))
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
