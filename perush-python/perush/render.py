"""Drawing laid-out pages: on screen (preview images) and into a PDF file."""
from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

from .textlayout import PT_PER_MM, metrics, qfont, space


def draw_line(p, line, x_right, top):
    ws = line.words
    if not ws:
        return
    total = sum(w.w for w in ws)
    n = len(ws)
    fill = 0.3 if getattr(line, "force", False) else 0.6
    justify = (line.align == "justify" and not line.last and n > 1 and total >= line.width * fill)
    gap = (line.width - total) / (n - 1) if justify else space(line.base)
    if n > 1 and total + gap * (n - 1) > line.width:
        gap = (line.width - total) / (n - 1)     # a line set with tighter spaces
    x = x_right
    if line.align == "center":
        x = x_right - (line.width - (total + gap * (n - 1))) / 2
    m = metrics(line.base)
    if line.align == "center":
        # a line of its own with great letters: placed by them
        m = metrics(max((w.style for w in ws), key=lambda st: st.size))
    nominal = line.base.size * 1.0
    baseline = top + (line.h - (m.ascent() + m.descent())) / 2 + m.ascent()
    if line.h > nominal * 3:  # never float a word in a very tall slot
        baseline = top + m.ascent()
    # where the spaces would open too wide (a narrow column, long words), part of the room
    # goes between the letters instead
    track = 0.0
    if justify and n > 1:
        sp = space(line.base)
        if gap > 1.8 * sp:
            chars = sum(len(w.text) for w in ws)
            track = min(line.base.size * 0.1, (line.width - total - (n - 1) * 1.8 * sp) / max(1, chars))
            gap = (line.width - total - track * chars) / (n - 1)
    for w in ws:
        ww = w.w + track * len(w.text)
        x -= ww
        f = qfont(w.style)
        if track:
            f = QFont(f)
            f.setLetterSpacing(QFont.AbsoluteSpacing, track)
        p.setFont(f)
        p.drawText(QPointF(x, baseline), w.text)
        x -= gap


def draw_oz_head(p, page, h):
    """The head of a page as in Oz Vehadar: the perek great in the middle and the amudim
    under it in square brackets; the name of the work in two, one word on each side of
    the perek (רבינו ... אשר); the page's number at the outer edge (in a grey box where a
    day begins). No rule under it."""
    from .textlayout import width
    m, R = page.head_span
    st, big, sub = h["st"], h["big"], h["subst"]
    base = h["base"]
    mid = (m + R) / 2
    p.setPen(QColor("black"))
    tw = width(big, h["title"]) if h["title"] else 0.0
    if h["title"]:
        p.setFont(qfont(big))
        p.drawText(QPointF(mid - tw / 2, base), h["title"])
    if h["sub"]:
        p.setFont(qfont(sub))
        p.drawText(QPointF(mid - width(sub, h["sub"]) / 2, h["sub_base"]), h["sub"])
    bold = st.with_bold(True)
    num = h["num"]
    nw = width(bold, num)
    right_word, left_word = h["work"]
    # the number at the outer edge; each word of the name midway between the perek and
    # the edge on its side (on the outer side: between the perek and the number)
    if h["outer"] == "right":
        xn = R - nw
        right_end, left_end = xn - st.size, m
    else:
        xn = m
        right_end, left_end = R, m + nw + st.size
    p.setFont(qfont(st))
    for word, a, c in ((right_word, mid + tw / 2, right_end), (left_word, left_end, mid - tw / 2)):
        if word:
            ww = width(st, word)
            p.drawText(QPointF((a + c) / 2 - ww / 2, base), word)
    if h["box"]:
        p.fillRect(QRectF(xn - 3, base - st.size * 0.95, nw + 6, st.size * 1.35), QColor("#d6d6d6"))
    p.setPen(QColor("black"))
    p.setFont(qfont(bold))
    p.drawText(QPointF(xn, base), num)


def draw_page(p, page):
    p.setPen(QColor("black"))
    p.setLayoutDirection(Qt.RightToLeft)
    for paint in getattr(page, "paint", []):
        # a page drawn in lines (a title page, a cover)
        paint(p)
    oz = getattr(page, "oz_head", None)
    if oz:
        draw_oz_head(p, page, oz)
    if page.head and not oz:
        right, center, left, st, base = page.head
        # the head spans the text block (its rule): the margins differ on the two sides
        m = page.rules[0][0] if page.rules else 0
        R = page.rules[0][2] if page.rules else page.width - m
        bold = st.with_bold(True)
        from .textlayout import width
        box = getattr(page, "head_box", None)
        if box:
            # a day begins on this page: its number (with the day) in a grey box
            t = right if box == "right" else left
            tw = width(bold, t)
            x0 = R - tw if box == "right" else m
            p.fillRect(QRectF(x0 - 3, base - st.size * 0.95, tw + 6, st.size * 1.35), QColor("#d6d6d6"))
            p.setPen(QColor("black"))
        if right:
            p.setFont(qfont(bold))
            p.drawText(QPointF(R - width(bold, right), base), right)
        if center:
            p.setFont(qfont(st))
            p.drawText(QPointF((m + R) / 2 - width(st, center) / 2, base), center)
        if left:
            p.setFont(qfont(bold))
            p.drawText(QPointF(m, base), left)
    pen = QPen(QColor("black"))
    pen.setWidthF(0.6)
    p.setPen(pen)
    for x1, y, x2 in page.rules:
        p.drawLine(QPointF(x1, y), QPointF(x2, y))
    p.setPen(QColor("black"))
    for x, y, text, st in getattr(page, "marks", []):
        # a note in the margin, centred on x
        from .textlayout import width as _w
        p.setFont(qfont(st))
        p.drawText(QPointF(x - _w(st, text) / 2, y), text)
    for x, yc, word, num, st in getattr(page, "boxes", []):
        # a day: a light grey box, "יום" over its number, centred on x and yc
        from .textlayout import width as _w
        small = st.__class__(st.family, st.size * 0.82, st.bold)
        w = max(_w(small, word), _w(st, num)) + st.size * 0.9
        h = small.size + st.size + st.size * 0.75
        p.fillRect(QRectF(x - w / 2, yc - h / 2, w, h), QColor("#d6d6d6"))
        p.setPen(QColor("black"))
        p.setFont(qfont(small))
        p.drawText(QPointF(x - _w(small, word) / 2, yc - h / 2 + st.size * 0.3 + small.size * 0.85), word)
        p.setFont(qfont(st))
        p.drawText(QPointF(x - _w(st, num) / 2, yc + h / 2 - st.size * 0.45), num)
    for x, y, w, h in getattr(page, "deco", []):
        # a frame for a great opening word: a double line, little scrolls at its sides
        pen2 = QPen(QColor("black"))
        pen2.setWidthF(1.1)
        p.setPen(pen2)
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(x, y, w, h))
        pen2.setWidthF(0.45)
        p.setPen(pen2)
        p.drawRect(QRectF(x + 2.5, y + 2.5, w - 5, h - 5))
        from .design import rosette
        for cx, cy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
            p.setBrush(QColor("white"))
            p.drawEllipse(QPointF(cx, cy), 3.2, 3.2)
            rosette(p, cx, cy, 3, "black", 0.35, 6)
        p.setPen(QColor("black"))
    for fr in page.frames:
        for line in fr.lines:
            draw_line(p, line, fr.x_right - line.right, fr.top + line.y)


def page_image(page, zoom=1.0):
    """The page as an image, zoom = pixels per point."""
    img = QImage(max(1, int(page.width * zoom)), max(1, int(page.height * zoom)), QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor("white"))
    dpm = round(72 / 0.0254)
    img.setDotsPerMeterX(dpm)
    img.setDotsPerMeterY(dpm)
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
    p.scale(zoom, zoom)
    draw_page(p, page)
    if page.overfull:
        pen = QPen(QColor("#dc2626"))
        pen.setWidthF(2)
        p.setPen(pen)
        p.drawRect(1, 1, page.width - 2, page.height - 2)
    p.end()
    return img


def export_pdf(pages, path, title=""):
    if not pages:
        raise ValueError("אין עמודים לייצוא")
    w, h = pages[0].width, pages[0].height
    writer = QPdfWriter(path)
    writer.setResolution(72)
    writer.setTitle(title or "עימוד פירושים")
    writer.setCreator("עימוד פירושים")
    size = QPageSize(QSizeF(w / PT_PER_MM, h / PT_PER_MM), QPageSize.Millimeter, "custom", QPageSize.ExactMatch)
    writer.setPageLayout(QPageLayout(size, QPageLayout.Portrait, QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter))
    p = QPainter(writer)
    for n, page in enumerate(pages):
        if n:
            if (page.width, page.height) != (w, h):
                w, h = page.width, page.height
                size = QPageSize(QSizeF(w / PT_PER_MM, h / PT_PER_MM), QPageSize.Millimeter, "custom", QPageSize.ExactMatch)
                writer.setPageLayout(QPageLayout(size, QPageLayout.Portrait, QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter))
            writer.newPage()
        draw_page(p, page)
    p.end()
