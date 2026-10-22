"""Turning text as it comes (running text, copied from a site or a PDF, with HTML) into the
program's form: the main text with a verse on each line and '#' headings, a commentary with
'@N' before the passages of each verse."""
import html
import re

from .model import heb, parse_main

NIKUD = re.compile("[֑-ׇ]")
NUM = r"[א-ת]{1,3}['׳\"״]?"
MARK = re.compile(r"[\(\[\{]\s*(" + NUM + r")\s*[\)\]\}]")


def plain(s):
    """Letters only, without nikud and te'amim (for recognising headings)."""
    return NIKUD.sub("", s)


def label(s):
    return re.sub(r"['׳\"״]", "", s)


def clean(raw):
    """HTML to text: headings on lines of their own, tags and entities gone, paragraph
    marks ({פ} {ס}) out."""
    s = raw.replace("\r", "")
    s = re.sub(r"<\s*h[1-6][^>]*>(.*?)<\s*/\s*h[1-6]\s*>", lambda m: "\n" + m.group(1) + "\n", s, flags=re.S | re.I)
    s = re.sub(r"<\s*(br|p|div|li)[^>]*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[\{\(\[]\s*[פס]\s*[\}\)\]]", " ", s)          # {פ} {ס}
    s = s.replace("־", "־")                            # keep the maqaf
    s = re.sub(r"[ \t ]+", " ", s)
    return s


def heading(line):
    """'# …' / '## …' for a line that is a heading of the program's kinds, else None."""
    p = plain(line).strip().strip(":.")
    if len(p.split()) > 7:
        return None
    m = re.match(r"^(?:#+\s*)?(פרשת|פרשה)\s+(.+)$", p)
    if m:
        return "# פרשת " + m.group(2).strip()
    m = re.match(r"^(?:#+\s*)?(הפטרת|הפטרה)\b(.*)$", p)
    if m:
        return "## הפטרת" + m.group(2).rstrip()
    m = re.match(r"^(?:#+\s*)?פרק\s+(" + NUM + r")$", p)
    if m:
        return "# פרק " + label(m.group(1))
    return None


def book_title(line):
    """'ספר בראשית' (a short line) -> 'בראשית'"""
    p = plain(line).strip().strip(":.")
    m = re.match(r"^ספר\s+(\S+(?:\s\S+)?)$", p)
    return m.group(1) if m else None


def prepare_main(raw):
    """-> (text for the main box, report, the book's name if the text gives it)"""
    out, verses, heads, title = [], 0, 0, None
    text = clean(raw)
    # a heading inside running text ("… לאמר: פרק ב בראשית …") on a line of its own
    text = re.sub(r"(?<=[:׃.])\s*((?:פרשת|פרק)\s+\S+)\s+", lambda m: "\n" + m.group(1) + "\n", text)
    buf = []

    def flush():
        nonlocal verses
        body = " ".join(buf).strip()
        buf.clear()
        if not body:
            return
        marks = list(MARK.finditer(body))
        if len(marks) >= 1 and marks[0].start() < 3:
            # numbered verses: each number begins a verse
            for k, m in enumerate(marks):
                end = marks[k + 1].start() if k + 1 < len(marks) else len(body)
                t = body[m.end():end].strip()
                if t:
                    out.append(f"[{label(m.group(1))}] {t}")
                    verses += 1
            return
        # running text: a verse ends with : or ׃
        parts = re.split(r"(?<=[:׃])\s+", body)
        for t in parts:
            t = t.strip()
            if t:
                out.append(t)
                verses += 1

    for line in text.split("\n"):
        t = line.strip()
        if not t:
            continue
        if title is None and not out and not buf and book_title(t):
            title = book_title(t)
            continue
        h = heading(t)
        if h:
            flush()
            out.append(h)
            heads += 1
            continue
        if MARK.match(t) and buf:
            flush()          # a numbered verse begins
        buf.append(t)
        if re.search(r"[:׃]$", t):
            flush()          # the line ends a verse
    flush()
    return "\n".join(out), f"{verses} פסוקים, {heads} כותרות", title


def verse_index(main_text):
    """(chapter label, verse label) -> the verse's number in the program (1, 2, …)."""
    items, _ = parse_main(main_text)
    out, by_label = {}, {}
    for it in items:
        if it["type"] != "v" or it["noComm"]:
            continue
        ch = re.sub(r"^פרק\s+", "", plain(it["chapter"])).strip()
        out[(label(ch), label(it["label"]))] = it["idx"] + 1
        by_label.setdefault(label(it["label"]), it["idx"] + 1)
    return out, by_label


def prepare_comm(raw, main_text):
    """-> (text for a commentary box, report). A passage that begins with a verse number
    ('(א)', '{א}', 'פסוק א', after a 'פרק ב' line) gets '@N' of that verse in the main text."""
    index, by_label = verse_index(main_text)
    text = clean(raw)
    out, chapter, found, missing = [], None, 0, []
    for line in text.split("\n"):
        t = line.strip()
        if not t:
            continue
        p = plain(t).strip()
        m = re.match(r"^(?:#+\s*)?פרק\s+(" + NUM + r")[:.]?$", p)
        if m:
            chapter = label(m.group(1))
            continue
        m = re.match(r"^(?:[\(\[\{]\s*(" + NUM + r")\s*[\)\]\}]|פסוק\s+(" + NUM + r")[:.]?|(" + NUM + r")[\).])\s*(.*)$", t)
        if m:
            v = label(m.group(1) or m.group(2) or m.group(3))
            rest = m.group(4)
            n = index.get((chapter, v)) if chapter else None
            if n is None and not chapter:
                n = by_label.get(v)
            if n is not None:
                out.append(f"@{n} {rest}".rstrip())
                found += 1
                continue
            missing.append((chapter or "") + ":" + v)
        out.append(t)
    rep = f"{found} קטעים שויכו לפסוקים"
    if missing:
        rep += f"; לא נמצאו בטקסט העיקרי: {', '.join(missing[:8])}" + ("…" if len(missing) > 8 else "")
    if not found:
        rep = "לא נמצאו מספרי פסוקים — הפירוש יחובר לפי סדר השורות (שורה לכל פסוק)"
    return "\n".join(out), rep
