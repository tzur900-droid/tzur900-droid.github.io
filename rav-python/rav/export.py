"""The book out of book.md: a Word file (right to left, to go on editing) and a PDF."""
import html
import re

FONT = "David"


def blocks(md):
    """(kind, text) for every block: h1, h2, h3, p, quote, li."""
    out, para = [], []

    def flush():
        if para:
            out.append(("p", " ".join(para)))
            para.clear()
    for line in md.splitlines():
        s = line.strip()
        if not s:
            flush()
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", s)
        if m:
            flush()
            out.append(("h%d" % min(3, len(m.group(1))), m.group(2)))
        elif re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            flush()
            out.append(("hr", ""))
        elif s.startswith(">"):
            flush()
            out.append(("quote", s.lstrip("> ")))
        elif re.match(r"^[-*•]\s+", s):
            flush()
            out.append(("li", re.sub(r"^[-*•]\s+", "", s)))
        else:
            para.append(s)
    flush()
    return out


SRC = re.compile(r"\s*\{מקור(?:ות)?\s*([\d,\s]+)\}")


def runs(text):
    """(text, bold, superscript) pieces of a line: **bold** and the {מקור 12} marks."""
    pieces = []
    for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        bold = i % 2 == 1
        pos = 0
        for m in SRC.finditer(part):
            if m.start() > pos:
                pieces.append((part[pos:m.start()], bold, False))
            nums = ", ".join(re.findall(r"\d+", m.group(1)))
            pieces.append((f"({nums})", False, True))
            pos = m.end()
        if pos < len(part):
            pieces.append((part[pos:], bold, False))
    return pieces


def to_docx(md, path):
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    from docx.shared import Pt

    d = docx.Document()
    st = d.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(13)
    rpr = st.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs"):
        fonts.set(qn(a), FONT)
    sz = OxmlElement("w:szCs")
    sz.set(qn("w:val"), "26")
    rpr.append(sz)
    for sec in d.sections:
        bidi = OxmlElement("w:bidi")
        sec._sectPr.append(bidi)

    def rtl(p):
        ppr = p._p.get_or_add_pPr()
        b = OxmlElement("w:bidi")
        ppr.insert(0, b)

    def add(kind, text):
        if kind.startswith("h"):
            p = d.add_heading(level=int(kind[1]))
        elif kind == "li":
            p = d.add_paragraph(style="List Bullet")
        else:
            p = d.add_paragraph()
        rtl(p)
        if kind in ("p", "quote", "li"):
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.line_spacing = 1.25
        if kind == "h2":
            p.paragraph_format.page_break_before = True
        if kind == "h1":
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if kind == "quote":
            p.paragraph_format.right_indent = Pt(24)
        for t, bold, sup in runs(text):
            r = p.add_run(t)
            r.bold = bold or None
            r.font.rtl = True
            r.font.name = FONT
            r._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:cs"), FONT)
            if bold:
                r._element.get_or_add_rPr().append(OxmlElement("w:bCs"))
            if sup:
                r.font.superscript = True
                r.font.size = Pt(8)
            if kind == "quote":
                r.italic = True
    for kind, text in blocks(md):
        if kind == "hr":
            p = d.add_paragraph("* * *")
            rtl(p)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            continue
        add(kind, text)
    d.save(path)


def to_html(md):
    out = []
    for kind, text in blocks(md):
        if kind == "hr":
            out.append("<p align='center'>* * *</p>")
            continue
        inner = ""
        for t, bold, sup in runs(text):
            t = html.escape(t)
            if sup:
                t = f"<sup>{t}</sup>"
            elif bold:
                t = f"<b>{t}</b>"
            inner += t
        tag = {"quote": "blockquote", "li": "p"}.get(kind, kind)
        if kind == "li":
            inner = "• " + inner
        out.append(f"<{tag}>{inner}</{tag}>")
    return ("<html dir='rtl'><head><meta charset='utf-8'><style>"
            "body{font-family:'David','Frank Ruehl CLM','Noto Serif Hebrew','Times New Roman';font-size:10.5pt;line-height:140%;}"
            "h1{text-align:center;font-size:20pt;margin-top:30pt;} h2{font-size:14pt;page-break-before:always;margin-top:22pt;}"
            "h3{font-size:11.5pt;} p{text-align:justify;margin:0 0 7pt 0;} sup{font-size:7pt;}"
            "blockquote{margin-right:24pt;font-style:italic;}"
            "</style></head><body>" + "\n".join(out) + "</body></html>")


def to_pdf(md, path):
    """A PDF of the book, A5, through Qt (needs a QApplication)."""
    from PySide6.QtCore import QMarginsF, Qt
    from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument, QTextOption
    from PySide6.QtPrintSupport import QPrinter
    pr = QPrinter(QPrinter.HighResolution)
    pr.setOutputFormat(QPrinter.PdfFormat)
    pr.setOutputFileName(path)
    pr.setPageLayout(QPageLayout(QPageSize(QPageSize.A5), QPageLayout.Portrait,
                                 QMarginsF(16, 18, 16, 18), QPageLayout.Millimeter))
    doc = QTextDocument()
    opt = QTextOption()
    opt.setTextDirection(Qt.RightToLeft)
    opt.setAlignment(Qt.AlignJustify)
    doc.setDefaultTextOption(opt)
    doc.setHtml(to_html(md))
    doc.print_(pr)
