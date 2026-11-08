"""Typesets a book.md of 'ספר מהרב' as a designed Word file, in the style of 'להודות ולהלל'
(Beit El): title page, table of contents by parasha with dotted leaders, a page for every
parasha, every talk on a new page with a large title, bold sub-headings, justified Frank Ruehl
text, a '*' footnote with the talk's sources on its first page, running heads
'page | book' / 'parasha | page'.

    python design_book.py book.md out.docx [--title "..."] [--subtitle "..."] [--by "..."]
"""
import copy
import re
import sys

import docx
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt

FONT = "FrankRuehl"
BODY_PT = 12.5


# ---------- reading the book ----------
def parse(md):
    """{title, subtitle, foreword, parts: [{name, talks: [{title, blocks, sources}]}], all_sources}"""
    book = {"title": "", "subtitle": "", "foreword": [], "parts": [], "all_sources": []}
    part, talk, mode = None, None, "head"
    sources_block = False
    for raw in md.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# "):
            name = line[2:].strip()
            if not book["title"]:
                book["title"] = name
                continue
            part = {"name": name, "talks": []}
            book["parts"].append(part)
            talk, mode, sources_block = None, "part", False
            continue
        if line.startswith("## "):
            name = line[3:].strip()
            sources_block = False
            if name.startswith("פתח דבר"):
                mode = "foreword"
                continue
            if name.startswith("רשימת המקורות"):
                mode = "all_sources"
                continue
            if part is None:
                part = {"name": "", "talks": []}
                book["parts"].append(part)
            # names only, as asked ("פרק א: …" of books written before that was fixed)
            name = re.sub(r"^\s*(?:פרק|שיחה|שיעור|חלק)\s+[\u05d0-\u05ea\d]{1,4}['׳\"]?\s*[:.\-–—]\s*", "", name) or name
            talk = {"title": name, "blocks": [], "sources": []}
            part["talks"].append(talk)
            mode = "talk"
            continue
        if line.startswith("### "):
            name = line[4:].strip()
            if mode == "talk" and name == "מקורות":
                sources_block = True
                continue
            if mode == "talk":
                talk["blocks"].append(("h", name))
            continue
        if mode == "head":
            if not book["subtitle"] and not line.startswith("על פי דברי"):
                book["subtitle"] = line
            continue
        if mode == "foreword":
            book["foreword"].append(line)
        elif mode == "all_sources":
            if line.startswith("- "):
                book["all_sources"].append(clean_source(line[2:]))
        elif mode == "talk":
            if sources_block and line.startswith("- "):
                talk["sources"].append(clean_source(line[2:]))
            elif re.fullmatch(r"[-*_]{3,}", line):
                continue
            else:
                talk["blocks"].append(("p", line))
                talk.setdefault("marks", []).extend(
                    int(x) for m in re.finditer(r"\{מקור(?:ות)?\s*([\d,\s]+)\}", line) for x in re.findall(r"\d+", m.group(1)))
    # a book whose talks have no list of sources of their own: from the marks and the end list
    numbered = {}
    for src in book["all_sources"]:
        m = re.match(r"^(\d+)\.\s*(.*)", src)
        if m:
            numbered[int(m.group(1))] = m.group(2)
    book["all_sources"] = [re.sub(r"^\d+\.\s*", "", x) for x in book["all_sources"]]
    for part in book["parts"]:
        for t in part["talks"]:
            if not t["sources"] and numbered:
                seen = []
                for x in t.get("marks", []):
                    if x in numbered and x not in seen:
                        seen.append(x)
                t["sources"] = [numbered[x] for x in seen]
    return book


def clean_source(s):
    s = re.sub(r"^\((\d+)\)\s*", r"\1. ", s)
    s = re.sub(r"\s*←\s*בפרקים:.*$", "", s)
    s = re.sub(r"\s*\((?:תומלל|כתוביות|הדף לא|הועתק|נקרא|הקלטה)[^)]*\)\s*$", "", s)
    return s.strip()


LIST_PAGE = re.compile(r"^(רשימה:|כל שיעורי|עמוד \d+ ברשימת|שיעורי הרב בנושא)")


def source_title(x):
    """A source's name as a book cites it: without its link, the rabbi's name, the site, '(PDF מלא)'."""
    t = re.split(r"\s+—\s+https?://", x)[0]
    t = re.sub(r"\s*\((?:דף רשימה|הועתק|נקרא|PDF)[^)]*\)", "", t)
    t = re.sub(r"\s*\|?\s*(?:מו\"?ר\s+)?(?:ה?רה\"ג|הרב|ראש הישיבה)\s+זלמן(?:\s+ברוך)?\s+מלמד(?:\s+שליט\"א)?\s*", " ", t)
    t = re.sub(r"\s*(?:-|–)?\s*(?:מאת\s+)?(?:ה?רה\"ג|הרב)\s+זלמן(?:\s+ברוך)?\s+מלמד(?:\s+שליט\"א)?", "", t)
    t = re.sub(r"\|\s*(?:אתר ישיבה|דבר תורה לחנוכה|שיעור כללי)\s*", "", t)
    t = re.sub(r"\s*מאת\s+ראש הישיבה", "", t)
    t = re.sub(r"\s*מאת\s*[-–]\s*", " – ", t)
    t = re.sub(r"\s*[-–]\s*\)", ")", t)
    t = re.sub(r"\s*\|\s*", ", ", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,–-|")
    return t


def note_titles(sources):
    """The names for a talk's footnote: list pages left out (unless there is nothing else), each
    lesson once."""
    names = [source_title(x) for x in sources]
    real = [n for n in names if not LIST_PAGE.match(n)] or names
    out, keys = [], []
    for n in real:
        key = re.sub(r"[^\u05d0-\u05ea]", "", re.sub(r"\([^)]*\)", "", n))     # (the series in brackets aside)
        if key and key not in keys:
            keys.append(key)
            out.append(n)
    return out


def strip_marks(t):
    t = re.sub(r"\s*\{מקור(?:ות)?\s*[\d,\s]+\}", "", t)
    t = re.sub(r"[¹²³⁴⁵⁶⁷⁸⁹⁰]+", "", t)
    return t.strip()


# ---------- low-level Word helpers ----------
def rtl_par(p):
    ppr = p._p.get_or_add_pPr()
    if ppr.find(qn("w:bidi")) is None:
        ppr.insert(0, OxmlElement("w:bidi"))


def font_run(r, size=None, bold=None, font=FONT):
    r.font.name = font
    rpr = r._element.get_or_add_rPr()
    fonts = rpr.get_or_add_rFonts()
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(a), font)
    rtl = OxmlElement("w:rtl")
    rpr.append(rtl)
    if size:
        r.font.size = Pt(size)
        szcs = OxmlElement("w:szCs")
        szcs.set(qn("w:val"), str(int(size * 2)))
        rpr.append(szcs)
    if bold:
        r.font.bold = True
        rpr.append(OxmlElement("w:bCs"))
    return r


def add_text(p, text, size=None, bold=None):
    """Text with **bold** pieces."""
    for i, piece in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        if piece:
            font_run(p.add_run(piece), size, bold or (i % 2 == 1))
    return p


def field(p, instr, placeholder="1", size=None, bold=None):
    def fc(t):
        r = p.add_run()
        e = OxmlElement("w:fldChar")
        e.set(qn("w:fldCharType"), t)
        r._r.append(e)
        return r
    fc("begin")
    r = p.add_run()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instr} "
    r._r.append(it)
    fc("separate")
    font_run(p.add_run(placeholder), size, bold)
    fc("end")


def style_font(st, size, bold=False):
    st.font.name = FONT
    st.font.size = Pt(size)
    st.font.bold = bold
    rpr = st.element.get_or_add_rPr()
    f = rpr.get_or_add_rFonts()
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        f.set(qn(a), FONT)
    for tag, val in (("w:szCs", str(int(size * 2))),):
        e = rpr.find(qn(tag))
        if e is None:
            e = OxmlElement(tag)
            rpr.append(e)
        e.set(qn("w:val"), val)
    if bold and rpr.find(qn("w:bCs")) is None:
        rpr.append(OxmlElement("w:bCs"))
    ppr = st.element.get_or_add_pPr()
    if ppr.find(qn("w:bidi")) is None:
        ppr.append(OxmlElement("w:bidi"))


# ---------- footnotes (python-docx has none: the part is made here) ----------
FOOTNOTES_XML = (
    f'<w:footnotes {nsdecls("w")}>'
    '<w:footnote w:type="separator" w:id="-1"><w:p><w:pPr><w:bidi/><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
    '<w:r><w:separator/></w:r></w:p></w:footnote>'
    '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:pPr><w:bidi/><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
    '<w:r><w:continuationSeparator/></w:r></w:p></w:footnote>'
    '</w:footnotes>')


class Footnotes:
    def __init__(self, document):
        self.doc = document
        part = Part(PackURI("/word/footnotes.xml"),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml",
                    FOOTNOTES_XML.encode("utf-8"), document.part.package)
        document.part.relate_to(part, RT.FOOTNOTES)
        self.part = part
        self.root = parse_xml(FOOTNOTES_XML)
        self.next = 1

    def add(self, p, text):
        """A footnote; its mark is '*' (the section numbers notes as * † ‡, again on every page)."""
        fid = self.next
        self.next += 1
        r = p.add_run()
        r._r.get_or_add_rPr().append(parse_xml(f'<w:rStyle {nsdecls("w")} w:val="FootnoteReference"/>'))
        r._r.get_or_add_rPr().append(parse_xml(f'<w:vertAlign {nsdecls("w")} w:val="superscript"/>'))
        ref = OxmlElement("w:footnoteReference")
        ref.set(qn("w:id"), str(fid))
        r._r.append(ref)
        esc = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        note = parse_xml(
            f'<w:footnote {nsdecls("w")} w:id="{fid}"><w:p><w:pPr><w:bidi/><w:jc w:val="both"/>'
            f'<w:spacing w:after="40" w:line="240" w:lineRule="auto"/></w:pPr>'
            f'<w:r><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}"/><w:vertAlign w:val="superscript"/>'
            f'<w:sz w:val="20"/><w:szCs w:val="20"/><w:rtl/></w:rPr><w:footnoteRef/></w:r>'
            f'<w:r><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}"/><w:sz w:val="19"/><w:szCs w:val="19"/><w:rtl/></w:rPr>'
            f'<w:t xml:space="preserve"> {esc}</w:t></w:r></w:p></w:footnote>')
        self.root.append(note)

    def save(self):
        self.part._blob = self.root.xml.encode("utf-8") if hasattr(self.root, "xml") else \
            __import__("lxml.etree", fromlist=["x"]).tostring(self.root, xml_declaration=True, encoding="UTF-8", standalone=True)


# ---------- the document ----------
def build(book, out, title=None, subtitle=None, by=None, toc_pages=None):
    d = docx.Document()
    title = title or book["title"]
    subtitle = subtitle or book["subtitle"]
    by = by or "על פי דברי מו\"ר ראש הישיבה הרב זלמן ברוך מלמד שליט\"א"

    sec = d.sections[0]
    sec.page_width, sec.page_height = Cm(17), Cm(24)
    sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.0)
    sec.left_margin, sec.right_margin = Cm(1.9), Cm(2.3)          # (mirrored: inner wider)
    sec.header_distance, sec.footer_distance = Cm(1.2), Cm(1.0)
    sectpr = sec._sectPr
    sectpr.append(OxmlElement("w:bidi"))
    settings = d.settings.element
    settings.append(parse_xml(f'<w:mirrorMargins {nsdecls("w")}/>'))
    settings.append(parse_xml(f'<w:evenAndOddHeaders {nsdecls("w")}/>'))
    if toc_pages is None:
        settings.append(parse_xml(f'<w:updateFields {nsdecls("w")} w:val="true"/>'))

    normal = d.styles["Normal"]
    style_font(normal, BODY_PT)
    pf = normal.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.space_after = Pt(6)
    pf.line_spacing = 1.18
    h1, h2, h3 = d.styles["Heading 1"], d.styles["Heading 2"], d.styles["Heading 3"]
    for st, size in ((h1, 30), (h2, 24), (h3, 14)):
        style_font(st, size, bold=(st is h3))
        st.font.color.rgb = None
        st.paragraph_format.keep_with_next = True
        rpr = st.element.get_or_add_rPr()
        for c in rpr.findall(qn("w:color")):
            rpr.remove(c)
    h1.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h1.paragraph_format.space_before = Pt(160)
    h2.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    h2.paragraph_format.space_before = Pt(30)
    h2.paragraph_format.space_after = Pt(26)
    h3.paragraph_format.space_before = Pt(14)
    h3.paragraph_format.space_after = Pt(6)
    for name, size, bold in (("TOC 1", 14, True), ("TOC 2", 13, True)):
        st = d.styles.add_style(name, 1) if name not in [s.name for s in d.styles] else d.styles[name]
        style_font(st, size, bold)
    d.styles["TOC 1"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    d.styles["TOC 1"].paragraph_format.space_before = Pt(16)
    d.styles["TOC 1"].paragraph_format.space_after = Pt(10)
    t2 = d.styles["TOC 2"].paragraph_format
    t2.space_after = Pt(9)
    tabw = sec.page_width - sec.left_margin - sec.right_margin
    t2.tab_stops.add_tab_stop(tabw, alignment=2, leader=1)   # left (in RTL: the far end), dots

    notes = Footnotes(d)

    def para(text="", style=None, align=None, size=None, bold=None, before=None, after=None):
        p = d.add_paragraph(style=style)
        rtl_par(p)
        if align is not None:
            p.alignment = align
        if before is not None:
            p.paragraph_format.space_before = Pt(before)
        if after is not None:
            p.paragraph_format.space_after = Pt(after)
        if text:
            add_text(p, text, size, bold)
        return p

    def page_break():
        p = d.add_paragraph()
        p.add_run().add_break(WD_BREAK.PAGE)
        return p

    # title page
    para(title, align=WD_ALIGN_PARAGRAPH.CENTER, size=40, bold=True, before=150, after=24)
    if subtitle:
        para(subtitle, align=WD_ALIGN_PARAGRAPH.CENTER, size=18, after=6)
    para(by, align=WD_ALIGN_PARAGRAPH.CENTER, size=16, before=110)
    page_break()
    # the back of the title page: the foreword
    if book["foreword"]:
        para("פתח דבר", align=WD_ALIGN_PARAGRAPH.CENTER, size=18, bold=True, before=40, after=14)
        for t in book["foreword"]:
            para(strip_marks(t), size=11)
        page_break()
    # table of contents
    para("תוכן עניינים", align=WD_ALIGN_PARAGRAPH.CENTER, size=26, bold=True, before=20, after=20)
    p = para()
    if toc_pages:       # the entries with their pages (found by laying the book out once)
        for kind, text, page in toc_pages:
            q = para(style="TOC 1" if kind == 1 else "TOC 2")
            if kind == 1 and ":" in text:
                first, rest = text.split(":", 1)
                font_run(q.add_run(first.strip()), 13)
                q.add_run().add_break()
                font_run(q.add_run(rest.strip()), 16, True)
            else:
                add_text(q, text)
            if kind == 2:
                font_run(q.add_run("\t" + str(page)), bold=True)
    else:
        field(p, 'TOC \\o "1-2" \\h \\z', "(לחצו F9 לעדכון תוכן העניינים)")

    # the parts and the talks
    blank_sections = set()
    for part in book["parts"]:
        if part["name"]:
            d.add_section(WD_SECTION.ODD_PAGE)
            blank_sections.add(len(d.sections) - 1)
            hp = para(style="Heading 1")
            if ":" in part["name"]:
                first, rest = part["name"].split(":", 1)
                font_run(hp.add_run(first.strip()), 20)
                hp.add_run().add_break()
                font_run(hp.add_run(rest.strip()))
            else:
                add_text(hp, part["name"])
        for ti, talk in enumerate(part["talks"]):
            if ti == 0:
                d.add_section(WD_SECTION.NEW_PAGE)
            else:
                page_break()
            h = para(talk["title"], style="Heading 2")
            if talk["sources"]:
                names = note_titles(talk["sources"])
                notes.add(h, f"נערך מתוך {'השיעור' if len(names) == 1 else 'השיעורים'}: {'; '.join(names)}.")
            for kind, text in talk["blocks"]:
                if kind == "h":
                    para(strip_marks(text), style="Heading 3")
                else:
                    t = strip_marks(text)
                    if t:
                        para(t)
    # all the sources
    if book["all_sources"]:
        d.add_section(WD_SECTION.ODD_PAGE)
        blank_sections.add(len(d.sections) - 1)
        para("רשימת המקורות", style="Heading 1")
        d.add_section(WD_SECTION.NEW_PAGE)
        for s in book["all_sources"]:
            para("• " + s, size=10.5, after=3)

    # running heads: even 'page | book', odd 'parasha | page'; none on the first pages
    for i, s in enumerate(d.sections):
        s.different_first_page_header_footer = (i == 0)
        fp = s._sectPr.find(qn("w:footnotePr"))
        if fp is None:
            s._sectPr.append(parse_xml(f'<w:footnotePr {nsdecls("w")}><w:numFmt w:val="chicago"/>'
                                       f'<w:numRestart w:val="eachPage"/></w:footnotePr>'))
        if i == 0 or i in blank_sections:     # the title pages and the parasha pages: no running head
            s.header.is_linked_to_previous = False
            s.even_page_header.is_linked_to_previous = False
            continue
        s.header.is_linked_to_previous = False
        s.even_page_header.is_linked_to_previous = False
        hp = s.even_page_header.paragraphs[0]
        rtl_par(hp)
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        field(hp, "PAGE", "1", 11, True)
        font_run(hp.add_run("  |  " + title), 11)
        op = s.header.paragraphs[0]
        rtl_par(op)
        op.alignment = WD_ALIGN_PARAGRAPH.LEFT
        # a book in parts: the part's name; a book of talks only: the talk's name
        field(op, 'STYLEREF "Heading 2"', "", 11)
        font_run(op.add_run("  |  "), 11)
        field(op, "PAGE", "1", 11, True)
        s._sectPr.append(OxmlElement("w:bidi")) if s._sectPr.find(qn("w:bidi")) is None else None
    notes.save()
    d.save(out)


def toc_from_pdf(book, pdf):
    """(kind, text, page) for the parts and talks, by the page their heading is on (page = the
    printed number = the place in the PDF)."""
    from pypdf import PdfReader
    pages = [(pg.extract_text() or "") for pg in PdfReader(pdf).pages]
    norm = lambda t: re.sub(r"[\s\u0591-\u05C7״\"'׳]+", "", t)     # (also without nikud and quote marks)
    flat = [norm(t) for t in pages]
    out = []
    start = next((i + 1 for i, t in enumerate(flat) if "תוכןעניינים" in t or "םיניינעןכות" in t), 0)
    for part in book["parts"]:
        items = ([(1, part["name"])] if part["name"] else []) + [(2, t["title"]) for t in part["talks"]]
        for kind, text in items:
            # the words after a colon (before it there are often quotes and nikud, which come out
            # of the PDF in a jumbled order)
            key = norm(text.split(":", 1)[-1] if (kind == 1 or ":" in text) else text)[:25]
            # pdf text of RTL may come reversed: try both
            found = next((i for i in range(start, len(flat)) if key in flat[i] or key[::-1] in flat[i]), None)
            if found is None:
                found = start
            out.append((kind, text, found + 1))
            start = found
    return out


def main():
    a = sys.argv[1:]
    opts = {}
    for k in ("--title", "--subtitle", "--by"):
        if k in a:
            i = a.index(k)
            opts[k[2:]] = a[i + 1]
            del a[i:i + 2]
    pdf = "--pdf" in a
    a = [x for x in a if x != "--pdf"]
    md = open(a[0], encoding="utf-8").read()
    book = parse(md)
    out = a[1]
    build(book, out, **opts)
    print(f"{len(book['parts'])} פרשות, {sum(len(p['talks']) for p in book['parts'])} שיחות → {out}")
    if pdf:
        import os
        import subprocess
        base = os.path.splitext(out)[0]
        tmp = base + ".toc.docx"
        toc = None
        for _ in range(3):      # the table of contents with its pages; again, until the pages stay
            build(book, tmp, toc_pages=toc, **opts)
            # blank pages kept (a parasha starts on a right-hand page), so a PDF page is a book page
            fmt = 'pdf:writer_pdf_Export:{"IsSkipEmptyPages":{"type":"boolean","value":"false"}}'
            subprocess.run(["soffice", "--headless", "--convert-to", fmt, "--outdir", os.path.dirname(out) or ".", tmp],
                           capture_output=True, timeout=600)
            new = toc_from_pdf(book, base + ".toc.pdf")
            if new == toc:
                break
            toc = new
        os.replace(base + ".toc.pdf", base + ".pdf")
        os.remove(tmp)
        print("PDF:", base + ".pdf")


if __name__ == "__main__":
    main()
