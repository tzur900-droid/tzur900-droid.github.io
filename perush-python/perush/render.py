"""Drawing laid-out pages: on screen (preview images) and into a PDF file."""
import re

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

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


def new_writer(path, w, h, title):
    writer = QPdfWriter(path)
    writer.setResolution(72)
    writer.setTitle(title or "עימוד פירושים")
    writer.setCreator("עימוד פירושים")
    size = QPageSize(QSizeF(w / PT_PER_MM, h / PT_PER_MM), QPageSize.Millimeter, "custom", QPageSize.ExactMatch)
    writer.setPageLayout(QPageLayout(size, QPageLayout.Portrait, QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter))
    return writer


def export_pdf(pages, path, title="", book=False, cover=None):
    """book: the PDF opens as a book bound on the right (pages side by side from right to
    left, the first alone), so the inner side of each page faces the spine.
    cover: the cover's words (cover.book_info): the PDF begins with the front cover, its
    blank inside, a title page and its blank back, and ends with the back cover, so the
    first page of the text is still a left-hand page."""
    if not pages:
        raise ValueError("אין עמודים לייצוא")
    w, h = pages[0].width, pages[0].height
    writer = new_writer(path, w, h, title)
    p = QPainter(writer)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
    rect = QRectF(0, 0, w, h)
    first = [True]

    def new_page():
        if not first[0]:
            writer.newPage()
        first[0] = False

    if cover:
        from .cover import draw_front
        new_page()
        draw_front(p, rect, cover)
        new_page()
        new_page()
        draw_front(p, rect, cover, gilt=False)
        new_page()
    for page in pages:
        new_page()
        draw_page(p, page)
    if cover:
        from .cover import draw_back
        if len(pages) % 2:
            new_page()          # the inside of the back cover
        new_page()
        draw_back(p, rect, cover)
    p.end()
    if book or cover:
        right_to_left(path)


def export_cover(path, w, h, n_pages, cover):
    """The whole cover for printing, laid flat: front, spine (as thick as n_pages make it)
    and back, with bleed all round."""
    from .cover import BLEED_MM, draw_wrap, spine_mm
    bleed = BLEED_MM * PT_PER_MM
    spine = spine_mm(n_pages) * PT_PER_MM
    W, H = 2 * w + spine + 2 * bleed, h + 2 * bleed
    writer = new_writer(path, W, H, cover.get("title", ""))
    p = QPainter(writer)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
    draw_wrap(p, QRectF(0, 0, W, H), cover, spine, bleed)
    p.end()
    return spine / PT_PER_MM


def right_to_left(path):
    """Tell PDF viewers that the pages are a book read from right to left, shown two by two
    with the first page alone: an incremental update that adds this to the catalog."""
    with open(path, "rb") as f:
        data = f.read()
    at = data.find(b"/Type /Catalog")
    start = max(data.rfind(b"\nendobj", 0, at), 0)
    m = re.compile(rb"\s*(\d+) 0 obj\s*<<(.*?)>>\s*endobj", re.S).match(data, start + len(b"\nendobj") if start else 0)
    if at < 0 or not m or b"/Type /Catalog" not in m.group(2) or b"<<" in m.group(2):
        return
    t = re.search(rb"trailer\s*<<(.*?)>>\s*startxref\s*(\d+)", data[data.rfind(b"trailer"):], re.S)
    if not m or not t or b"/ViewerPreferences" in m.group(2):
        return
    num, body = int(m.group(1)), m.group(2)
    trailer, prev = t.group(1), int(t.group(2))
    size = re.search(rb"/Size\s+(\d+)", trailer)
    info = re.search(rb"/Info\s+\d+\s+0\s+R", trailer)
    if not size:
        return
    obj = (b"%d 0 obj\n<<" % num + body.rstrip() +
           b"\n/ViewerPreferences << /Direction /R2L >>\n/PageLayout /TwoPageRight\n>>\nendobj\n")
    if not data.endswith(b"\n"):
        data += b"\n"
    off = len(data)
    xref = off + len(obj)
    tail = (b"xref\n0 1\n0000000000 65535 f \n%d 1\n%010d 00000 n \n" % (num, off) +
            b"trailer\n<<\n/Size " + size.group(1) + b"\n" + (info.group(0) + b"\n" if info else b"") +
            b"/Root %d 0 R\n/Prev %d\n>>\nstartxref\n%d\n%%%%EOF\n" % (num, prev, xref))
    with open(path, "wb") as f:
        f.write(data + obj + tail)
