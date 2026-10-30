"""Drawing laid-out pages: on screen (preview images) and into a PDF file."""
from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen, QPolygonF

from .textlayout import PT_PER_MM, justify_spacing, metrics, qfont, space, spaced_font


def draw_line(p, line, x_right, top):
    ws = line.words
    if not ws:
        return
    total = sum(w.w for w in ws)
    # the spaces of the line (none after a word that ends with a maqaf)
    gaps = sum(1 for w in ws[:-1] if not getattr(w, "join", False))
    # a line that doesn't end its paragraph reaches the end of the line (unless it holds almost nothing)
    fill = 0.2 if getattr(line, "force", False) else 0.35
    justify = (line.align == "justify" and not line.last and gaps > 0 and total >= line.width * fill)
    gap = (line.width - total) / gaps if justify else space(line.base)
    ls, widths = 0.0, None
    if justify:
        gap, ls, widths = justify_spacing(line, gaps, total)
    if gaps > 0 and total + gap * gaps > line.width:
        gap = (line.width - total) / gaps     # a line set with tighter spaces
    x = x_right
    if line.align == "center":
        x = x_right - (line.width - (total + gap * gaps)) / 2
    m = metrics(line.base)
    nominal = line.base.size * 1.0
    baseline = top + (line.h - (m.ascent() + m.descent())) / 2 + m.ascent()
    if line.h > nominal * 3:  # never float a word in a very tall slot
        baseline = top + m.ascent()
    for k, w in enumerate(ws):
        x -= widths[k] if widths else w.w
        p.setFont(spaced_font(w.style, ls) if ls else qfont(w.style))
        p.drawText(QPointF(x, baseline), w.text)
        if not getattr(w, "join", False):
            x -= gap


def draw_page(p, page):
    p.setPen(QColor("black"))
    p.setLayoutDirection(Qt.RightToLeft)
    if page.head:
        right, center, left, st, base = page.head
        # the head spans the rule under it (the text area, which a binding margin may shift)
        m, R = (page.rules[0][0], page.rules[0][2]) if page.rules else (0, page.width)
        bold = st.with_bold(True)
        from .textlayout import width
        if right:
            p.setFont(qfont(bold))
            p.drawText(QPointF(R - width(bold, right), base), right)
        if center:
            p.setFont(qfont(st))
            p.drawText(QPointF((m + R) / 2 - width(st, center) / 2, base), center)
        if left:
            p.setFont(qfont(bold))
            p.drawText(QPointF(m, base), left)
    for shape in getattr(page, "shapes", []):
        # ornaments (the title page's frame)
        kind = shape[0]
        if kind == "rect":
            _, x, y, w, h, lw = shape
            pen = QPen(QColor("black"))
            pen.setWidthF(lw)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(x, y, w, h))
        elif kind == "line":
            _, x1, y1, x2, y2, lw = shape
            pen = QPen(QColor("black"))
            pen.setWidthF(lw)
            p.setPen(pen)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        elif kind == "diamond":
            _, cx, cy, r = shape
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("black"))
            p.drawPolygon(QPolygonF([QPointF(cx, cy - r), QPointF(cx + r, cy), QPointF(cx, cy + r), QPointF(cx - r, cy)]))
            p.setBrush(Qt.NoBrush)
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
    if hasattr(writer, "setColorModel"):
        # black ink only: black text in RGB is printed with all four inks, and small letters
        # come out blurred if the plates are a hair out of register
        writer.setColorModel(QPdfWriter.ColorModel.Grayscale)
    writer.setTitle(title or "עימוד פירושים")
    writer.setCreator("עימוד פירושים")
    size = QPageSize(QSizeF(w / PT_PER_MM, h / PT_PER_MM), QPageSize.Millimeter, "custom", QPageSize.ExactMatch)
    writer.setPageLayout(QPageLayout(size, QPageLayout.Portrait, QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter))
    p = QPainter(writer)
    for n, page in enumerate(pages):
        if n:
            writer.newPage()
        draw_page(p, page)
    p.end()
