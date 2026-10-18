"""Drawing laid-out pages: on screen (preview images) and into a PDF file."""
from PySide6.QtCore import QMarginsF, QPointF, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

from .textlayout import PT_PER_MM, metrics, qfont, space


def draw_line(p, line, x_right, top):
    ws = line.words
    if not ws:
        return
    total = sum(w.w for w in ws)
    n = len(ws)
    justify = (line.align == "justify" and not line.last and n > 1 and total >= line.width * 0.6)
    gap = (line.width - total) / (n - 1) if justify else space(line.base)
    x = x_right
    if line.align == "center":
        x = x_right - (line.width - (total + gap * (n - 1))) / 2
    m = metrics(line.base)
    nominal = line.base.size * 1.0
    baseline = top + (line.h - (m.ascent() + m.descent())) / 2 + m.ascent()
    if line.h > nominal * 3:  # never float a word in a very tall slot
        baseline = top + m.ascent()
    for w in ws:
        x -= w.w
        p.setFont(qfont(w.style))
        p.drawText(QPointF(x, baseline), w.text)
        x -= gap


def draw_page(p, page):
    p.setPen(QColor("black"))
    p.setLayoutDirection(Qt.RightToLeft)
    if page.head:
        right, center, left, st, base = page.head
        m = page.rules[0][0] if page.rules else 0
        R = page.width - m
        bold = st.with_bold(True)
        from .textlayout import width
        if right:
            p.setFont(qfont(bold))
            p.drawText(QPointF(R - width(bold, right), base), right)
        if center:
            p.setFont(qfont(st))
            p.drawText(QPointF(page.width / 2 - width(st, center) / 2, base), center)
        if left:
            p.setFont(qfont(bold))
            p.drawText(QPointF(m, base), left)
    pen = QPen(QColor("black"))
    pen.setWidthF(0.6)
    p.setPen(pen)
    for x1, y, x2 in page.rules:
        p.drawLine(QPointF(x1, y), QPointF(x2, y))
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
            writer.newPage()
        draw_page(p, page)
    p.end()
