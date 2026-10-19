"""Turn text files exported from Sefaria (a Torah book with te'amim, Onkelos, Rashi,
Ramban) into project files for the program: one per parasha and one for the whole book.

    python main.py --import OUT_DIR torah.txt onkelos.txt rashi.txt ramban.txt

The files are recognised by their first line (<h1>…</h1>), so their order doesn't matter.
Ketiv/qere is written as (ketiv) [qere]; the dibbur hamatchil of Rashi and Ramban, which
Sefaria marks in bold, stays bold.
"""
import html
import json
import os
import re
import sys

PARASHOT = {
    "בראשית": [("בראשית", 1, 1), ("נח", 6, 9), ("לך לך", 12, 1), ("וירא", 18, 1), ("חיי שרה", 23, 1), ("תולדות", 25, 19),
               ("ויצא", 28, 10), ("וישלח", 32, 4), ("וישב", 37, 1), ("מקץ", 41, 1), ("ויגש", 44, 18), ("ויחי", 47, 28)],
    "שמות": [("שמות", 1, 1), ("וארא", 6, 2), ("בא", 10, 1), ("בשלח", 13, 17), ("יתרו", 18, 1), ("משפטים", 21, 1),
             ("תרומה", 25, 1), ("תצוה", 27, 20), ("כי תשא", 30, 11), ("ויקהל", 35, 1), ("פקודי", 38, 21)],
    "ויקרא": [("ויקרא", 1, 1), ("צו", 6, 1), ("שמיני", 9, 1), ("תזריע", 12, 1), ("מצורע", 14, 1), ("אחרי מות", 16, 1),
              ("קדושים", 19, 1), ("אמור", 21, 1), ("בהר", 25, 1), ("בחקתי", 26, 3)],
    "במדבר": [("במדבר", 1, 1), ("נשא", 4, 21), ("בהעלתך", 8, 1), ("שלח", 13, 1), ("קרח", 16, 1), ("חקת", 19, 1),
              ("בלק", 22, 2), ("פינחס", 25, 10), ("מטות", 30, 2), ("מסעי", 33, 1)],
    "דברים": [("דברים", 1, 1), ("ואתחנן", 3, 23), ("עקב", 7, 12), ("ראה", 11, 26), ("שופטים", 16, 18), ("כי תצא", 21, 10),
              ("כי תבוא", 26, 1), ("נצבים", 29, 9), ("וילך", 31, 1), ("האזינו", 32, 1), ("וזאת הברכה", 33, 1)],
}

# Haftarot (Ashkenazi custom): parasha -> [(book, chapter, verse, to chapter, to verse)]
HAFTAROT = {
    # בראשית
    "בראשית": [("ישעיהו", 42, 5, 43, 10)],
    "נח": [("ישעיהו", 54, 1, 55, 5)],
    "לך לך": [("ישעיהו", 40, 27, 41, 16)],
    "וירא": [("מלכים ב", 4, 1, 4, 37)],
    "חיי שרה": [("מלכים א", 1, 1, 1, 31)],
    "תולדות": [("מלאכי", 1, 1, 2, 7)],
    "ויצא": [("הושע", 12, 13, 14, 10)],
    "וישלח": [("עובדיה", 1, 1, 1, 21)],
    "וישב": [("עמוס", 2, 6, 3, 8)],
    "מקץ": [("מלכים א", 3, 15, 4, 1)],
    "ויגש": [("יחזקאל", 37, 15, 37, 28)],
    "ויחי": [("מלכים א", 2, 1, 2, 12)],
    # שמות
    "שמות": [("ישעיהו", 27, 6, 28, 13), ("ישעיהו", 29, 22, 29, 23)],
    "וארא": [("יחזקאל", 28, 25, 29, 21)],
    "בא": [("ירמיהו", 46, 13, 46, 28)],
    "בשלח": [("שופטים", 4, 4, 5, 31)],
    "יתרו": [("ישעיהו", 6, 1, 7, 6), ("ישעיהו", 9, 5, 9, 6)],
    "משפטים": [("ירמיהו", 34, 8, 34, 22), ("ירמיהו", 33, 25, 33, 26)],
    "תרומה": [("מלכים א", 5, 26, 6, 13)],
    "תצוה": [("יחזקאל", 43, 10, 43, 27)],
    "כי תשא": [("מלכים א", 18, 1, 18, 39)],
    "ויקהל": [("מלכים א", 7, 40, 7, 50)],
    "פקודי": [("מלכים א", 7, 51, 8, 21)],
    # ויקרא
    "ויקרא": [("ישעיהו", 43, 21, 44, 23)],
    "צו": [("ירמיהו", 7, 21, 8, 3), ("ירמיהו", 9, 22, 9, 23)],
    "שמיני": [("שמואל ב", 6, 1, 7, 17)],
    "תזריע": [("מלכים ב", 4, 42, 5, 19)],
    "מצורע": [("מלכים ב", 7, 3, 7, 20)],
    "אחרי מות": [("יחזקאל", 22, 1, 22, 19)],
    "קדושים": [("עמוס", 9, 7, 9, 15)],
    "אמור": [("יחזקאל", 44, 15, 44, 31)],
    "בהר": [("ירמיהו", 32, 6, 32, 27)],
    "בחקתי": [("ירמיהו", 16, 19, 17, 14)],
    # במדבר
    "במדבר": [("הושע", 2, 1, 2, 22)],
    "נשא": [("שופטים", 13, 2, 13, 25)],
    "בהעלתך": [("זכריה", 2, 14, 4, 7)],
    "שלח": [("יהושע", 2, 1, 2, 24)],
    "קרח": [("שמואל א", 11, 14, 12, 22)],
    "חקת": [("שופטים", 11, 1, 11, 33)],
    "בלק": [("מיכה", 5, 6, 6, 8)],
    "פינחס": [("מלכים א", 18, 46, 19, 21)],
    "מטות": [("ירמיהו", 1, 1, 2, 3)],
    "מסעי": [("ירמיהו", 2, 4, 2, 28), ("ירמיהו", 3, 4, 3, 4)],
    # דברים
    "דברים": [("ישעיהו", 1, 1, 1, 27)],
    "ואתחנן": [("ישעיהו", 40, 1, 40, 26)],
    "עקב": [("ישעיהו", 49, 14, 51, 3)],
    "ראה": [("ישעיהו", 54, 11, 55, 5)],
    "שופטים": [("ישעיהו", 51, 12, 52, 12)],
    "כי תצא": [("ישעיהו", 54, 1, 54, 10)],
    "כי תבוא": [("ישעיהו", 60, 1, 60, 22)],
    "נצבים": [("ישעיהו", 61, 10, 63, 9)],
    "וילך": [("ישעיהו", 55, 6, 56, 8)],
    "האזינו": [("שמואל ב", 22, 1, 22, 51)],
    "וזאת הברכה": [("יהושע", 1, 1, 1, 18)],
}

# Where the Sephardi custom differs: it ends earlier within the same haftara ("end"),
# starts later within it ("start"), or reads a haftara of its own ("own").
HAFTAROT_SEFARAD = {
    "בראשית": ("end", "ישעיהו", 42, 21),
    "נח": ("end", "ישעיהו", 54, 10),
    "וירא": ("end", "מלכים ב", 4, 23),
    "ויצא": ("own", [("הושע", 11, 7, 12, 12)]),
    "שמות": ("own", [("ירמיהו", 1, 1, 2, 3)]),
    "בשלח": ("start", "שופטים", 5, 1),
    "יתרו": ("end", "ישעיהו", 6, 13),
    "כי תשא": ("start", "מלכים א", 18, 20),
    "ויקהל": ("own", [("מלכים א", 7, 13, 7, 26)]),
    "פקודי": ("own", [("מלכים א", 7, 40, 7, 50)]),
    "שמיני": ("end", "שמואל ב", 6, 19),
    "אחרי מות": ("end", "יחזקאל", 22, 16),
    "קדושים": ("own", [("יחזקאל", 20, 2, 20, 20)]),
    "מסעי": ("own", [("ירמיהו", 2, 4, 2, 28), ("ירמיהו", 4, 1, 4, 2)]),
    "וזאת הברכה": ("end", "יהושע", 1, 9),
}

NAVI = {"ישעיהו", "ירמיהו", "יחזקאל", "שמואל א", "שמואל ב", "מלכים א", "מלכים ב", "יהושע", "שופטים", "הושע", "יואל",
        "עמוס", "עובדיה", "יונה", "מיכה", "נחום", "חבקוק", "צפניה", "חגי", "זכריה", "מלאכי"}

LETTERS = {"א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5, "ו": 6, "ז": 7, "ח": 8, "ט": 9, "י": 10, "כ": 20, "ך": 20,
           "ל": 30, "מ": 40, "ם": 40, "נ": 50, "ן": 50, "ס": 60, "ע": 70, "פ": 80, "ף": 80, "צ": 90, "ץ": 90,
           "ק": 100, "ר": 200, "ש": 300, "ת": 400}


def gematria(s):
    return sum(LETTERS.get(ch, 0) for ch in s)


def bold_marks(s):
    """<b>…</b> -> **…** (spaces kept outside the stars so words stay whole)."""
    def rep(m):
        inner = m.group(1).strip()
        return f" **{inner}** " if inner else " "
    s = re.sub(r"<b>(.*?)</b>", rep, s, flags=re.S)
    return s


def clean(s, keep_bold=False):
    s = s.replace("&nbsp;", " ").replace("&thinsp;", " ")
    if keep_bold:
        s = bold_marks(s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\*\*\s*\*\*", " ", s)
    return s


def clean_torah(s):
    s = re.sub(r'<span class="mam-spi-[a-z]+">.*?</span>', " ", s)      # {פ} {ס} paragraph marks
    s = re.sub(r"<sup[^>]*>.*?</sup>", "", s)                             # editorial notes
    s = re.sub(r'<span class="mam-kq"><span class="mam-kq-q">\[(.*?)\]</span>\s*<span class="mam-kq-k">\((.*?)\)</span></span>',
               lambda m: f"({m.group(2)}) [{m.group(1)}]", s)              # ketiv/qere
    s = re.sub(r'<span class="mam-kq"><span class="mam-kq-k">\((.*?)\)</span>\s*<span class="mam-kq-q">\[(.*?)\]</span></span>',
               lambda m: f"({m.group(1)}) [{m.group(2)}]", s)
    s = s.replace("&thinsp;", " ")
    return clean(s)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read().replace("\r", "").split("\n")


TORAH = {"בראשית", "שמות", "ויקרא", "במדבר", "דברים"}


def kind_of(lines):
    h1 = clean(lines[0]) if lines else ""
    if h1 in NAVI:
        return "navi:" + h1
    if h1 in TORAH and any(re.match(r"\s*<h3>\{", l) for l in lines[:20]):
        return "otz_torah"
    if "אונקלוס" in h1:
        return "onkelos"
    if "רש" in h1 and "על" in h1:
        return "rashi"
    if "רמב" in h1:
        return "ramban"
    return "torah"


OTZ_NAMES = {"אונקלוס": "onkelos", "רש\"י": "rashi", "רמב\"ן": "ramban"}


def parse_otzaria_torah(lines):
    """A Torah book from Otzaria ('תורה לפי פרקים (פרשנים)'): under '<h3>{X}</h3>' the
    verse (with te'amim, ketiv/qere as '(ketiv) [qere]'), then each commentator's lines,
    the first marked '<b style="color: gray;">name</b>'. Onkelos, Rashi and Ramban are kept."""
    book = clean(lines[0])
    verses, comms = [], {k: {} for k in OTZ_NAMES.values()}
    ch = v = 0
    label = ""
    expect = False
    cur = None
    for l in lines[1:]:
        m = re.match(r"\s*<h2>.*?פרק[-\s]+(\S+?)\s*</h2>", l)
        if m:
            ch, cur = gematria(m.group(1)), None
            continue
        m = re.match(r"\s*<h3>\{(\S+?)\}</h3>", l)
        if m:
            label = m.group(1)
            v, expect, cur = gematria(label), True, None
            continue
        if not l.strip():
            continue
        if expect:
            verses.append((ch, v, label, clean(l)))
            expect = False
            continue
        m = re.match(r'\s*<b style="color: gray;">(.*?)</b>\s*(.*)$', l)
        if m:
            cur = OTZ_NAMES.get(clean(m.group(1)))
            l = m.group(2)
        if cur:
            t = clean(l, keep_bold=cur != "onkelos")
            if t:
                comms[cur].setdefault((ch, v), []).append(t)
    # verses Otzaria splits where the commentaries (and the usual numbering) have one
    for (bk, ch, v1, v2) in MERGE_VERSES:
        if bk != book:
            continue
        keep = [x for x in verses if not (x[0] == ch and v1 < x[1] <= v2)]
        joined = " ".join(x[3] for x in verses if x[0] == ch and v1 <= x[1] <= v2)
        out = []
        for c, v, l, t in keep:
            if c == ch and v == v1:
                t = joined
            elif c == ch and v > v2:
                v -= v2 - v1
                l = heb(v)
            out.append((c, v, l, t))
        verses = out
    return book, verses, comms


# (book, chapter, first verse, last verse) to join into the first
MERGE_VERSES = [("דברים", 5, 17, 20)]


def parse_navi(lines):
    """A book of Nevi'im from Otzaria: '<h2>… פרק-X</h2>', '<h3>{Y}</h3>', then the verse
    (with te'amim, ketiv/qere as '(ketiv) [qere]') and commentaries, which are skipped."""
    out = {}
    ch = 0
    k = 0
    while k < len(lines):
        l = lines[k]
        m = re.match(r"\s*<h2>.*?פרק[-\s]+(\S+?)\s*</h2>", l)
        if m:
            ch = gematria(m.group(1))
        m = re.match(r"\s*<h3>\{(\S+?)\}</h3>", l)
        if m and ch:
            j = k + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                out[(ch, gematria(m.group(1)))] = clean(lines[j])
            k = j
        k += 1
    return out


def haftara_part(title, parts, navi, end_mark=None, start_mark=None):
    book0, c0 = parts[0][0], parts[0][1]
    out = [f"## {title} ({book0} {heb(c0)})"]
    cur = c0
    for book, c1, v1, c2, v2 in parts:
        verses = sorted(k for k in navi[book] if (c1, v1) <= k <= (c2, v2))
        for ch, v in verses:
            if ch != cur:
                out.append(f"### פרק {heb(ch)}")
                cur = ch
            text = navi[book][(ch, v)]
            if end_mark and (book, ch, v) == end_mark:
                text += " **(כאן מסיימים הספרדים)**"
            if start_mark and (book, ch, v) == start_mark:
                text = "**(כאן מתחילים הספרדים)** " + text
            out.append(f"[{heb(v)}] {text}")
    return out


def haftara_lines(name, navi):
    """The haftara of a parasha as main-text lines ('## הפטרת …', verses, '### פרק' when
    the chapter changes): the Ashkenazi custom, with the Sephardi custom where it differs.
    [] when a book it needs isn't loaded."""
    parts = HAFTAROT.get(name)
    if not parts or any(b not in navi for b, *_ in parts):
        return []
    sef = HAFTAROT_SEFARAD.get(name)
    if sef and sef[0] == "own" and all(b in navi for b, *_ in sef[1]):
        return (haftara_part(f"הפטרת {name} לאשכנזים", parts, navi)
                + haftara_part(f"הפטרת {name} לספרדים", sef[1], navi))
    end_mark = tuple(sef[1:]) if sef and sef[0] == "end" else None
    start_mark = tuple(sef[1:]) if sef and sef[0] == "start" else None
    return haftara_part(f"הפטרת {name}", parts, navi, end_mark, start_mark)


def parse_torah(lines):
    book = clean(lines[0])
    verses = []   # (chapter, verse, label, text)
    ch = 0
    for l in lines[1:]:
        m = re.match(r"\s*<h2>\s*פרק\s+(\S+)\s*</h2>", l)
        if m:
            ch = gematria(m.group(1))
            continue
        m = re.match(r"\s*\(([א-ת]+)\)\s*(.*)$", l)
        if m and ch:
            verses.append((ch, gematria(m.group(1)), m.group(1), clean_torah(m.group(2))))
    return book, verses


def parse_by_verse(lines, keep_bold=True):
    """Onkelos: '(א) text' lines under '<h2>פרק'. Rashi / Ramban: paragraphs under
    '<h3>פסוק'. Text before chapter 1 (an introduction) goes to (1, 1)."""
    out = {}
    ch = v = 0
    intro = []
    for l in lines[1:]:
        m = re.match(r"\s*<h2>\s*(.*?)\s*</h2>", l)
        if m:
            t = m.group(1)
            mm = re.match(r"פרק\s+(\S+)", t)
            ch, v = (gematria(mm.group(1)), 0) if mm else (0, 0)
            continue
        m = re.match(r"\s*<h3>\s*פסוק\s+(\S+)\s*</h3>", l)
        if m:
            v = gematria(m.group(1))
            continue
        if not l.strip() or l.strip().startswith("<h1>"):
            continue
        m = re.match(r"\s*\(([א-ת]+)\)\s*(.*)$", l)
        if m and ch and not v:     # Onkelos style
            out.setdefault((ch, gematria(m.group(1))), []).append(clean(m.group(2), keep_bold))
            continue
        text = clean(l, keep_bold)
        if not text:
            continue
        if ch and v:
            out.setdefault((ch, v), []).append(text)
        elif not ch and re.search(r"[֑-ׇ]", text):
            intro.append(text)     # the commentator's introduction
    if intro:
        out.setdefault((1, 1), [])[:0] = ["**הקדמה:** " + intro[0]] + intro[1:]
    return out


def heb(n):
    ones = ["", "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט"]
    tens = ["", "י", "כ", "ל", "מ", "נ", "ס", "ע", "פ", "צ"]
    hund = ["", "ק", "ר", "ש", "ת"]
    s = ""
    while n >= 400:
        s += "ת"
        n -= 400
    if n >= 100:
        s += hund[n // 100]
        n %= 100
    s += "טו" if n == 15 else "טז" if n == 16 else tens[n // 10] + ones[n % 10]
    return s


def comm_lines(entries, verses):
    lines = []
    for n, (ch, v, _, _) in enumerate(verses, 1):
        for t in entries.get((ch, v), []):
            lines.append(f"@{n} {t}")
    return "\n".join(lines)


def build(book, verses, comms, parashot, navi=None):
    """parashot: [(name, first index, end index)] within verses. Each parasha is followed
    by its haftara when the books of Nevi'im are given."""
    main = []
    cur_ch = None
    starts = {a: name for name, a, _ in parashot}
    ends = {b: name for name, _, b in parashot}
    for n, (ch, v, label, text) in enumerate(verses):
        if n in ends and navi:
            main.extend(haftara_lines(ends[n], navi))
        if n in starts:
            main.append(f"# פרשת {starts[n]}")
            cur_ch = None
        if ch != cur_ch:
            main.append(f"# פרק {heb(ch)}")
            cur_ch = ch
        main.append(f"[{label}] {text}")
    if len(verses) in ends and navi:
        main.extend(haftara_lines(ends[len(verses)], navi))
    project = {
        "title": book,
        "main": "\n".join(main),
        "comms": [],
        "pageSize": "A4", "margin": 14, "mainFont": "Noto Serif Hebrew", "mainSize": 15, "lineHeight": 1.6,
        "colGap": 5, "sectionGap": 2, "minLines": 4, "firstPage": 1,
        "verseNewLine": False, "numbers": True, "header": True, "names": True, "inlineChapters": True,
    }
    styles = {
        "onkelos": {"name": "אונקלוס", "place": "side", "side": "left", "font": "Noto Serif Hebrew", "size": 10.5, "width": 34, "autoW": True, "cols": 2},
        "rashi": {"name": "רש\"י", "place": "bottom", "side": "left", "font": "Noto Rashi Hebrew", "size": 9.5, "width": 30, "autoW": True, "cols": 2},
        "ramban": {"name": "רמב\"ן", "place": "bottom", "side": "left", "font": "Noto Rashi Hebrew", "size": 9, "width": 30, "autoW": True, "cols": 2},
    }
    for kind in ("onkelos", "rashi", "ramban"):
        if kind in comms:
            project["comms"].append(dict(styles[kind], text=comm_lines(comms[kind], verses)))
    return project


def convert(paths, out_dir):
    """Returns (written file paths, report lines)."""
    os.makedirs(out_dir, exist_ok=True)
    files = {}
    for p in paths:
        lines = read(p)
        files[kind_of(lines)] = lines
    navi = {k[5:]: parse_navi(v) for k, v in files.items() if k.startswith("navi:")}
    if "otz_torah" in files:
        book, verses, comms = parse_otzaria_torah(files["otz_torah"])
        return write_book(book, verses, comms, navi, out_dir)
    if "torah" not in files:
        raise ValueError("לא נמצא קובץ של הפסוקים (קובץ שהשורה הראשונה שלו היא שם הספר).")
    book, verses = parse_torah(files["torah"])
    comms = {}
    if "onkelos" in files:
        comms["onkelos"] = parse_by_verse(files["onkelos"], keep_bold=False)
    for k in ("rashi", "ramban"):
        if k in files:
            comms[k] = parse_by_verse(files[k], keep_bold=True)
    return write_book(book, verses, comms, navi, out_dir)


def write_book(book, verses, comms, navi, out_dir):
    if not verses:
        raise ValueError("לא נמצאו פסוקים בקובץ הפסוקים.")
    index = {(ch, v): n for n, (ch, v, _, _) in enumerate(verses)}
    table = PARASHOT.get(book, [(book, verses[0][0], verses[0][1])])
    starts = [(name, index[(ch, v)]) for name, ch, v in table if (ch, v) in index] or [(book, 0)]
    parashot = [(name, a, starts[k + 1][1] if k + 1 < len(starts) else len(verses)) for k, (name, a) in enumerate(starts)]
    written = []

    def dump(proj, name):
        p = os.path.join(out_dir, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(proj, f, ensure_ascii=False, indent=1)
        written.append(p)

    for k, (name, a, b) in enumerate(parashot, 1):
        part = verses[a:b]
        dump(build(book, part, comms, [(name, 0, len(part))], navi), f"{book} {k:02d} - פרשת {name}.json")
    dump(build(book, verses, comms, parashot, navi), f"{book} - כל הספר.json")
    names = {"onkelos": "אונקלוס", "rashi": "רש\"י", "ramban": "רמב\"ן"}
    report = [f"{book}: {len(verses)} פסוקים, {len(parashot)} פרשות."]
    for k, c in comms.items():
        lost = sum(1 for key in c if key not in index)
        report.append(f"{names[k]}: {sum(len(x) for x in c.values())} קטעים על {len(c)} פסוקים"
                      + (f" — {lost} לא שויכו לפסוק!" if lost else "."))
    if navi:
        got = [name for name, _, _ in parashot if haftara_lines(name, navi)]
        missing = [name for name, _, _ in parashot if not haftara_lines(name, navi)]
        report.append(f"הפטרות: {len(got)} מתוך {len(parashot)} פרשות" + (f" (חסר ספר עבור: {', '.join(missing)})" if missing else "."))
    return written, report
