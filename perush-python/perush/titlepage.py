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
    at the foot of the page."""
    page = Page(pw, ph)
    W = pw - 2 * margin
    R = pw - margin
    block, y = [], 0.0
    big = Style(family, 46, True)
    for l in centred(title, big, 46 * 1.3, W, y):
        block.append(l)
        y = l.y + l.h
    y += 8 * PT_PER_MM
    for k, text in enumerate(lines):
        st = Style(family, 22 if k == 0 and len(lines) > 1 else 16, k == 0 and len(lines) > 1)
        for l in centred(text, st, st.size * 1.5, W, y):
            block.append(l)
            y = l.y + l.h
        y += 2 * PT_PER_MM
    top = ph * 0.36 - y / 2
    page.frames.append(Frame(block, R, top))
    if dedication:
        st = Style(family, 10)
        lh = 10 * 1.5
        ded = []
        for k, text in enumerate(dedication):
            ded.extend(centred(text, st, lh, W, k * lh))
        page.frames.append(Frame(ded, R, ph - margin - len(dedication) * lh))
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
