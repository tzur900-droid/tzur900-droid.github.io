"""Title pages and covers drawn in lines, as in the old printings.

  * title(pw, ph, lines): a title page in the manner of the Vilna Shas: a gate of two
    columns on their bases under an arch, the beam across their capitals and a crown above
    it; the name in the arch, the rest of the lines under it, between the columns.
  * cover(...): a whole cover for printing (back, spine and front, with the bleed): a
    ground of one colour, gold lines and ornaments, the name on the front and the
    masechtot of the volume one under another on the spine; the back left plain.

Everything is drawn with a QPainter, in points, as a page's paint (see render.draw_page).
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen

from .textlayout import PT_PER_MM, Style, qfont, width

TITLE_FONT = "Drugulin CLM"
TEXT_FONT = "Frank Ruhl Libre"

# the colours a cover can have: (name, ground, gold)
COLOURS = {
    "כחול": ("#13233f", "#c9a54c"),
    "בורדו": ("#4a1420", "#c9a54c"),
    "שחור": ("#151515", "#c9a54c"),
    "חום": ("#3b2416", "#c9a54c"),
    "ירוק": ("#14301f", "#c9a54c"),
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


# ------------------------------------------------------------------ title page
def title(pw, ph, lines, colour="black"):
    """The paint of a title page: lines = [(text, size, bold)], the first is the name
    (in the arch), the rest under it."""
    def paint(p):
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing, True)
        m = 30.0
        # the border: a thick line and a thin one inside it
        p.setPen(pen(colour, 1.6))
        p.drawRect(QRectF(m, m, pw - 2 * m, ph - 2 * m))
        p.setPen(pen(colour, 0.5))
        p.drawRect(QRectF(m + 4, m + 4, pw - 2 * m - 8, ph - 2 * m - 8))
        for cx, cy in ((m + 4, m + 4), (pw - m - 4, m + 4), (m + 4, ph - m - 4), (pw - m - 4, ph - m - 4)):
            rosette(p, cx, cy, 7, colour, 0.5)
        L, R = m + 18, pw - m - 18
        cw = 30.0
        xl, xr = L + cw * 0.75, R - cw * 0.75
        beam = ph * 0.2            # the beam's top
        beam_h = 34.0
        cap_top = beam + beam_h
        foot = ph - m - 60
        # the crown above the beam: a pediment with a rosette, and scrolls at its ends
        p.setPen(pen(colour, 0.9))
        mid = pw / 2
        ped = QPainterPath()
        ped.moveTo(L + 10, beam)
        ped.lineTo(mid, m + 30)
        ped.lineTo(R - 10, beam)
        p.drawPath(ped)
        ped2 = QPainterPath()
        ped2.moveTo(L + 26, beam - 4)
        ped2.lineTo(mid, m + 38)
        ped2.lineTo(R - 26, beam - 4)
        p.setPen(pen(colour, 0.45))
        p.drawPath(ped2)
        rosette(p, mid, beam - (beam - m - 30) * 0.45, 13, colour, 0.6, 10)
        scroll(p, L + 22, beam - 12, 9, colour, 0.6, -1)
        scroll(p, R - 22, beam - 12, 9, colour, 0.6, 1)
        # the beam: mouldings, dentils and a band of leaves
        p.setPen(pen(colour, 1.0))
        p.drawRect(QRectF(L, beam, R - L, beam_h))
        p.setPen(pen(colour, 0.5))
        p.drawLine(QPointF(L, beam + 4), QPointF(R, beam + 4))
        dentils(p, L, R, beam + 7, 8, colour, 0.45)
        leaf_band(p, L + 4, R - 4, beam + 19, 11, colour, 0.45)
        # the columns
        column(p, xl, cap_top, foot, cw, colour)
        column(p, xr, cap_top, foot, cw, colour)
        # the arch between them, its keystone and its stones
        ix1, ix2 = xl + cw * 0.8, xr - cw * 0.8
        rx = (ix2 - ix1) / 2
        spring = cap_top + 70
        ry = min(rx * 0.55, spring - cap_top - 6)
        for k, w in ((0, 1.0), (9, 0.5)):
            path = QPainterPath()
            path.moveTo(ix1 + k, foot - 52)
            path.lineTo(ix1 + k, spring)
            path.arcTo(QRectF(ix1 + k, spring - (ry - k), 2 * (rx - k), 2 * (ry - k)), 180, -180)
            path.lineTo(ix2 - k, foot - 52)
            p.setPen(pen(colour, w))
            p.drawPath(path)
        p.setPen(pen(colour, 0.45))
        for k in range(1, 12):
            a = math.pi * k / 12
            c, s = math.cos(a), math.sin(a)
            x1_, y1_ = mid - c * rx, spring - s * ry
            x2_, y2_ = mid - c * (rx - 9), spring - s * (ry - 9)
            p.drawLine(QPointF(x1_, y1_), QPointF(x2_, y2_))
        kw = 14
        key = QPainterPath()
        key.moveTo(mid - kw / 2, spring - ry - 3)
        key.lineTo(mid + kw / 2, spring - ry - 3)
        key.lineTo(mid + kw * 0.35, spring - ry + 12)
        key.lineTo(mid - kw * 0.35, spring - ry + 12)
        key.closeSubpath()
        p.setBrush(QBrush(QColor("white")))
        p.setPen(pen(colour, 0.8))
        p.drawPath(key)
        p.setBrush(Qt.NoBrush)
        # spandrels: a rosette in each corner between the arch and the beam
        rosette(p, ix1 + 14, cap_top + 16, 9, colour, 0.5)
        rosette(p, ix2 - 14, cap_top + 16, 9, colour, 0.5)
        # the step under the gate, with a band across it
        p.setPen(pen(colour, 1.0))
        p.drawRect(QRectF(L, foot, R - L, ph - m - 18 - foot))
        leaf_band(p, L + 4, R - 4, foot + 6, 10, colour, 0.45)
        # the lines: the name in the arch, the rest under it, between the columns
        inner = ix2 - ix1 - 30
        name, *rest = lines
        st = fit(Style(TITLE_FONT, name[1], True), name[0], inner)
        # the block of lines, its height, centred in the opening of the gate
        body_h = st.size * 0.6 + 16 + sum((size if not text else size * 1.25)
                                          for text, size, _ in rest if not text.startswith("ימי"))
        y = (spring - ry * 0.4 + foot - 52) / 2 - (st.size + body_h) / 2 + st.size
        text_c(p, mid, y, name[0], st, colour)
        # a little ornament under the name
        y += st.size * 0.6
        p.setPen(pen(colour, 0.5))
        p.drawLine(QPointF(mid - 50, y), QPointF(mid - 8, y))
        p.drawLine(QPointF(mid + 8, y), QPointF(mid + 50, y))
        rosette(p, mid, y, 5, colour, 0.4, 6)
        y += 16
        body = [x for x in rest]
        foot_line = None
        if body and body[-1][0].startswith("ימי"):
            foot_line = body.pop()
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
    ground, gold = colours
    tw, th = trim[0] * PT_PER_MM, trim[1] * PT_PER_MM
    sw = spine_width(pages, leaf) * PT_PER_MM
    b = bleed * PT_PER_MM
    W, H = 2 * tw + sw + 2 * b, th + 2 * b

    def paint(p):
        p.save()
        p.setRenderHint(p.RenderHint.Antialiasing, True)
        p.fillRect(QRectF(0, 0, W, H), QColor(ground))
        # the front: on the right
        fx = b + tw + sw
        front(p, fx, b, tw, th, name_lines, masechtot, volume, gold)
        # the spine
        spine(p, b + tw, b, sw, th, masechtot, volume, gold)
        p.restore()
    return W, H, paint


def front(p, x0, y0, w, h, name_lines, masechtot, volume, gold):
    m = 14 * PT_PER_MM
    r = QRectF(x0 + m, y0 + m, w - 2 * m, h - 2 * m)
    p.setPen(pen(gold, 2.2))
    p.setBrush(Qt.NoBrush)
    p.drawRect(r)
    p.setPen(pen(gold, 0.7))
    p.drawRect(r.adjusted(6, 6, -6, -6))
    for cx, cy in ((r.left(), r.top()), (r.right(), r.top()), (r.left(), r.bottom()), (r.right(), r.bottom())):
        rosette(p, cx, cy, 11, gold, 0.8, 8)
    mid = x0 + w / 2
    # a gate: an arch on two thin pillars, the name under the arch
    aw = r.width() - 70
    top = r.top() + 40
    ah = 90
    gx1, gx2 = mid - aw / 2, mid + aw / 2
    gy2 = r.top() + r.height() * 0.62
    for k, lw in ((0, 1.4), (6, 0.6)):
        path = QPainterPath()
        path.moveTo(gx1 + k, gy2)
        path.lineTo(gx1 + k, top + ah / 2)
        path.arcTo(QRectF(gx1 + k, top + k, aw - 2 * k, ah - 2 * k), 180, -180)
        path.lineTo(gx2 - k, gy2)
        p.setPen(pen(gold, lw))
        p.drawPath(path)
    p.setPen(pen(gold, 1.0))
    p.drawLine(QPointF(gx1 - 8, gy2), QPointF(gx2 + 8, gy2))
    p.drawLine(QPointF(gx1 - 8, gy2 + 4), QPointF(gx2 + 8, gy2 + 4))
    rosette(p, mid, top - 14, 10, gold, 0.8, 10)
    scroll(p, gx1 + 20, top + ah * 0.55, 8, gold, 0.7, 1)
    scroll(p, gx2 - 20, top + ah * 0.55, 8, gold, 0.7, -1)
    y = top + ah * 0.75
    for text, size in name_lines:
        st = fit(Style(TITLE_FONT, size, True), text, aw - 40)
        y += st.size * 1.35
        text_c(p, mid, y, text, st, gold)
    y += 26
    p.setPen(pen(gold, 0.8))
    p.drawLine(QPointF(mid - 70, y), QPointF(mid - 12, y))
    p.drawLine(QPointF(mid + 12, y), QPointF(mid + 70, y))
    rosette(p, mid, y, 7, gold, 0.7, 6)
    # the masechtot of the volume, under the gate
    y = gy2 + 20
    rows, row = [], []
    for ms in masechtot:
        if row and width(Style(TITLE_FONT, 18, True), " · ".join(row + [ms])) > r.width() - 60:
            rows.append(row)
            row = []
        row.append(ms)
    rows.append(row)
    if len(masechtot) == 1:
        rows = [["מסכת " + masechtot[0]]]
    for row in rows:
        t = " · ".join(row)
        st = fit(Style(TITLE_FONT, 18, True), t, r.width() - 60)
        y += st.size * 1.45
        text_c(p, mid, y, t, st, gold)
    # a band and the volume at the foot
    leaf_band(p, r.left() + 20, r.right() - 20, r.bottom() - 62, 12, gold, 0.7)
    text_c(p, mid, r.bottom() - 24, volume, Style(TITLE_FONT, 16, True), gold)


def spine(p, x0, y0, w, h, masechtot, volume, gold):
    mid = x0 + w / 2
    # bands at the head and the foot, as on a bound book
    for yy in (y0 + 28, y0 + 40, y0 + h - 40, y0 + h - 28):
        p.setPen(pen(gold, 1.2))
        p.drawLine(QPointF(x0 + 3, yy), QPointF(x0 + w - 3, yy))
    p.setPen(pen(gold, 0.5))
    p.drawLine(QPointF(x0 + 3, y0 + 34), QPointF(x0 + w - 3, y0 + 34))
    p.drawLine(QPointF(x0 + 3, y0 + h - 34), QPointF(x0 + w - 3, y0 + h - 34))
    inner = w - 8
    y = y0 + 70
    for text, size in (("רא\"ש", 13), ("ורי\"ף", 13)):
        st = fit(Style(TITLE_FONT, size, True), text, inner)
        y += st.size * 1.2
        text_c(p, mid, y, text, st, gold)
    y += 10
    rosette(p, mid, y, min(6, inner / 2), gold, 0.6, 6)
    y += 14
    # the masechtot one under another, in the middle of the spine
    sts = [fit(Style(TITLE_FONT, 11, True), m, inner) for m in masechtot]
    size = min(st.size for st in sts)
    lh = size * 1.55
    top = max(y + 10, y0 + h / 2 - lh * len(masechtot) / 2)
    for k, m in enumerate(masechtot):
        text_c(p, mid, top + lh * (k + 1) - lh * 0.3, m, Style(TITLE_FONT, size, True), gold)
    rosette(p, mid, y0 + h - 70, min(6, inner / 2), gold, 0.6, 6)
    st = fit(Style(TITLE_FONT, 12, True), volume, inner)
    text_c(p, mid, y0 + h - 50, volume, st, gold)
