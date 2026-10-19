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


def kind_of(lines):
    h1 = clean(lines[0]) if lines else ""
    if "אונקלוס" in h1:
        return "onkelos"
    if "רש" in h1 and "על" in h1:
        return "rashi"
    if "רמב" in h1:
        return "ramban"
    return "torah"


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


def build(book, verses, comms, parashot):
    """parashot: [(name, first index, end index)] within verses."""
    main = []
    cur_ch = None
    starts = {a: name for name, a, _ in parashot}
    for n, (ch, v, label, text) in enumerate(verses):
        if n in starts:
            main.append(f"# פרשת {starts[n]}")
            cur_ch = None
        if ch != cur_ch:
            main.append(f"# פרק {heb(ch)}")
            cur_ch = ch
        main.append(f"[{label}] {text}")
    project = {
        "title": book,
        "main": "\n".join(main),
        "comms": [],
        "pageSize": "A4", "margin": 14, "mainFont": "Noto Serif Hebrew", "mainSize": 15, "lineHeight": 1.6,
        "colGap": 5, "sectionGap": 2, "minLines": 4, "firstPage": 1,
        "verseNewLine": False, "numbers": True, "header": True, "names": True,
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
    if "torah" not in files:
        raise ValueError("לא נמצא קובץ של הפסוקים (קובץ שהשורה הראשונה שלו היא שם הספר).")
    book, verses = parse_torah(files["torah"])
    if not verses:
        raise ValueError("לא נמצאו פסוקים בקובץ הפסוקים.")
    comms = {}
    if "onkelos" in files:
        comms["onkelos"] = parse_by_verse(files["onkelos"], keep_bold=False)
    for k in ("rashi", "ramban"):
        if k in files:
            comms[k] = parse_by_verse(files[k], keep_bold=True)
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
        dump(build(book, part, comms, [(name, 0, len(part))]), f"{book} {k:02d} - פרשת {name}.json")
    dump(build(book, verses, comms, parashot), f"{book} - כל הספר.json")
    names = {"onkelos": "אונקלוס", "rashi": "רש\"י", "ramban": "רמב\"ן"}
    report = [f"{book}: {len(verses)} פסוקים, {len(parashot)} פרשות."]
    for k, c in comms.items():
        lost = sum(1 for key in c if key not in index)
        report.append(f"{names[k]}: {sum(len(x) for x in c.values())} קטעים על {len(c)} פסוקים"
                      + (f" — {lost} לא שויכו לפסוק!" if lost else "."))
    return written, report
