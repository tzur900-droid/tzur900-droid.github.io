"""The title page of a book (שער): the name of the book large in the middle, the lines under
it smaller, and the dedication at the foot of the page."""
from .engine import Frame, Page
from .textlayout import PT_PER_MM, Style, break_lines, full_width, words_of


def centred(text, st, lh, width, y=0.0):
    lines = break_lines(words_of([(w, st.bold) for w in text.split()], st), st, lh, full_width(width), y, "center")
    for l in lines:
        l.last = True
    return lines


def title_page(pw, ph, margin, family, title, lines, dedication):
    """title: the name of the book; lines: the smaller lines under it; dedication: lines
    at the foot of the page. The page has a double frame and an ornament under the name."""
    page = Page(pw, ph)
    # a double frame: a heavier line outside, a fine one inside it
    o = margin * 0.7
    page.shapes = [("rect", o, o, pw - 2 * o, ph - 2 * o, 1.6),
                   ("rect", o + 2.2 * PT_PER_MM, o + 2.2 * PT_PER_MM, pw - 2 * o - 4.4 * PT_PER_MM, ph - 2 * o - 4.4 * PT_PER_MM, 0.5)]
    W = pw - 2 * margin
    R = pw - margin
    block, y = [], 0.0
    big = Style(family, 46, True)
    for l in centred(title, big, 46 * 1.3, W, y):
        block.append(l)
        y = l.y + l.h
    y += 3 * PT_PER_MM
    orn_y = y + 2.5 * PT_PER_MM          # the ornament: a line, a diamond, a line
    y += 8 * PT_PER_MM
    for k, text in enumerate(lines):
        st = Style(family, 22 if k == 0 and len(lines) > 1 else 16, k == 0 and len(lines) > 1)
        for l in centred(text, st, st.size * 1.5, W, y):
            block.append(l)
            y = l.y + l.h
        y += 2 * PT_PER_MM
    top = ph * 0.36 - y / 2
    page.frames.append(Frame(block, R, top))
    cx, cy, half = pw / 2, top + orn_y, min(W * 0.22, 50 * PT_PER_MM)
    page.shapes += [("line", cx - half, cy, cx - 4 * PT_PER_MM, cy, 0.8), ("line", cx + 4 * PT_PER_MM, cy, cx + half, cy, 0.8),
                    ("diamond", cx, cy, 2.4 * PT_PER_MM), ("diamond", cx - half - 2 * PT_PER_MM, cy, 1.1 * PT_PER_MM),
                    ("diamond", cx + half + 2 * PT_PER_MM, cy, 1.1 * PT_PER_MM)]
    if dedication:
        st = Style(family, 10)
        lh = 10 * 1.5
        ded = []
        for k, text in enumerate(dedication):
            ded.extend(centred(text, st, lh, W, k * lh))
        page.frames.append(Frame(ded, R, ph - margin - 4 * PT_PER_MM - len(dedication) * lh))
    return page


def blank_page(pw, ph):
    return Page(pw, ph)


def with_list(names):
    """['תרגום אונקלוס', 'רש"י', 'רמב"ן'] -> 'תרגום אונקלוס, רש"י ורמב"ן'"""
    names = [n for n in names if n]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " ו" + names[-1]


def toc_page(pw, ph, margin, family, entries, gutter=0.0):
    """The table of contents: entries are (text, page number, level); level 0 (a parasha)
    bold, level 1 (a haftara) smaller and set in. Dots lead from the name to the number.
    gutter: the binding margin (the page is the back of the title page, a right-hand page:
    its binding side is the left)."""
    from .textlayout import Line, Word, width
    page = Page(pw, ph)
    W = pw - 2 * margin - gutter
    R = pw - margin
    head = Style(family, 20, True)
    frames = [l for l in centred("תוכן העניינים", head, 20 * 1.6, W)]
    y = frames[-1].y + frames[-1].h + 6 * PT_PER_MM
    # a size at which the list fits the page
    for size in (13, 12, 11, 10, 9, 8):
        lh = size * 1.75
        if y + len(entries) * lh <= ph - 2 * margin:
            break
    lines = []
    for text, num, level in entries:
        st = Style(family, size if level == 0 else size * 0.88, level == 0)
        indent = 0.0 if level == 0 else 8 * PT_PER_MM
        avail = W - indent
        words = [Word(w, st, width(st, w)) for w in text.split()]
        nw = Word(num, Style(family, size, level == 0), width(Style(family, size, level == 0), num))
        sp = width(st, " ")
        used = sum(w.w for w in words) + sp * (len(words) - 1) + nw.w + 2 * sp
        dot = Style(family, size * 0.8)
        dots = "." * max(3, int((avail - used) / max(0.1, width(dot, "."))))
        dw = Word(dots, dot, width(dot, dots))
        ws = words + [dw, nw]
        line = Line(ws, indent, avail, sum(w.w for w in ws) + sp * (len(ws) - 1), lh, st, "justify", False, y)
        line.force = True
        lines.append(line)
        y += lh
    page.frames.append(Frame(frames + lines, R, margin))
    return page
