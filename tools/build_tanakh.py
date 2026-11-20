"""Make project files for the whole Tanakh from Sefaria's public export (Miqra according to
the Masorah, with ketiv/qere and the open and closed sections; Rashi, Metzudat David and
Metzudat Zion), and from the ready Torah projects (with Onkelos and Rashi).

    python tools/build_tanakh.py SEFARIA_DIR OUT_DIR

SEFARIA_DIR holds the export's merged.json files, named like "Isaiah.json",
"Rashi_on_Isaiah.json", "Metzudat_David_on_Isaiah.json" (see the README of Sefaria-Export).
OUT_DIR gets one project per book, numbered in the order of the Tanakh, and tanakh.json:
the order of the books and the sections (Torah, Nevi'im, Ketuvim) for tools/tanakh_pdf.py.
"""
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "perush-python")
sys.path.insert(0, ROOT)
from perush.sefaria import clean, clean_torah, heb  # noqa: E402

TORAH = ["בראשית", "שמות", "ויקרא", "במדבר", "דברים"]
NEVIIM = [("Joshua", "יהושע"), ("Judges", "שופטים"), ("I Samuel", "שמואל א"), ("II Samuel", "שמואל ב"),
          ("I Kings", "מלכים א"), ("II Kings", "מלכים ב"), ("Isaiah", "ישעיהו"), ("Jeremiah", "ירמיהו"),
          ("Ezekiel", "יחזקאל"), ("Hosea", "הושע"), ("Joel", "יואל"), ("Amos", "עמוס"), ("Obadiah", "עובדיה"),
          ("Jonah", "יונה"), ("Micah", "מיכה"), ("Nahum", "נחום"), ("Habakkuk", "חבקוק"), ("Zephaniah", "צפניה"),
          ("Haggai", "חגי"), ("Zechariah", "זכריה"), ("Malachi", "מלאכי")]
KETUVIM = [("Psalms", "תהלים"), ("Proverbs", "משלי"), ("Job", "איוב"), ("Song of Songs", "שיר השירים"),
           ("Ruth", "רות"), ("Lamentations", "איכה"), ("Ecclesiastes", "קהלת"), ("Esther", "אסתר"),
           ("Daniel", "דניאל"), ("Ezra", "עזרא"), ("Nehemiah", "נחמיה"), ("I Chronicles", "דברי הימים א"),
           ("II Chronicles", "דברי הימים ב")]

SETTINGS = {
    "pageSize": "custom", "pageW": 180, "pageH": 250, "margin": 8, "gutter": 6, "bookMode": True,
    "mainFont": "Taamey Frank CLM", "mainSize": 13, "lineHeight": 1.3, "colGap": 4, "sectionGap": 1.5,
    "minLines": 3, "numbers": True, "header": True, "names": True, "inlineChapters": True, "verseNewLine": False,
    "titlePage": True, "titleBlank": False, "toc": False, "parashaInline": True, "marginMarks": True,
    "dedication": "",
}
COMM = {"font": "Frank Ruehl CLM", "size": 9, "width": 30, "autoW": True, "cols": 1, "side": "left"}
STYLES = {
    "onkelos": dict(COMM, name="אונקלוס", place="side", font="Frank Ruehl CLM", cols=2),
    "rashi": dict(COMM, name="רש\"י", place="bottom"),
    "md": dict(COMM, name="מצודת דוד", place="half"),
    "mz": dict(COMM, name="מצודת ציון", place="half"),
}


def no_notes(s):
    s = re.sub(r'<sup class="footnote-marker">.*?</sup>', "", s, flags=re.S)
    return re.sub(r'<i class="footnote">.*?</i>', "", s, flags=re.S)


def verse_text(s):
    s = no_notes(s)
    s = re.sub(r'<span class="mam-spi-invnun">(.*?)</span>', r"\1", s)        # the inverted nun stays
    s = s.replace("<br>", " ")
    return clean_torah(s)


# the commentaries are set without points, as in the printed Mikraot Gedolot (the Rashi font has
# none of the points and marks some editions give them), and with the marks it does have
MARKS = re.compile(r"[\u0591-\u05c7\u034f\u200b-\u200f\u202a-\u202e]")


def plain_comm(t):
    t = unicodedata.normalize("NFKD", t)          # (letters with a point as one character: apart)
    t = t.replace("\u05be", " ").replace("\u05c3", ":").replace("\u05f4", '"').replace("\u05f3", "'")
    t = t.replace("\u2014", "-").replace("\u2013", "-").replace("\u2026", "...")
    return re.sub(r"  +", " ", MARKS.sub("", t))


def load(sef, name):
    path = os.path.join(sef, name.replace(" ", "_") + ".json")
    return json.load(open(path, encoding="utf-8"))["text"] if os.path.exists(path) else None


def comm_text(text, verses):
    """'@N passage' lines (N: the verse's number in the book, from 1) of a commentary given as
    [chapter][verse][passage]."""
    out = []
    for n, (c, v) in enumerate(verses, 1):
        if c < len(text) and v < len(text[c]):
            for p in text[c][v] or []:
                t = plain_comm(clean(no_notes(p), keep_bold=True))
                if t:
                    out.append(f"@{n} {t}")
    return "\n".join(out)


def nach_book(sef, en, he):
    text = load(sef, en)
    # a verse the Masorah edition leaves out (Joshua 21:36-37): from the Ta'amei Hamikra edition
    other = load(sef, en + "__Tanach_with_Taamei_Hamikra")
    for c, chapter in enumerate(text):
        for v, s in enumerate(chapter):
            if len(re.sub(r"<[^>]+>|[^\u05d0-\u05ea]", "", s)) < 2 and other and c < len(other) and v < len(other[c]):
                chapter[v] = other[c][v]
    main, verses = [], []
    for c, chapter in enumerate(text):
        main.append(f"# פרק {heb(c + 1)}")
        for v, s in enumerate(chapter):
            if not s.strip():
                continue
            main.append(f"[{heb(v + 1)}] {verse_text(s)}")
            verses.append((c, v))
    p = dict(SETTINGS, title=he, main="\n".join(main), comms=[])
    for kind, prefix in (("rashi", "Rashi on "), ("md", "Metzudat David on "), ("mz", "Metzudat Zion on ")):
        t = load(sef, prefix + en)
        if t:
            p["comms"].append(dict(STYLES[kind], text=comm_text(t, verses)))
    return p


def torah_book(he):
    """The ready Torah project of the book: its text without the haftarot, Onkelos and Rashi."""
    src = json.load(open(os.path.join(ROOT, "projects", he, f"{he} - כל הספר.json"), encoding="utf-8"))
    main, skip = [], False
    for line in src["main"].split("\n"):
        if line.startswith("#"):
            skip = line.startswith("##") or (skip and line.startswith("###"))
        if not skip:
            main.append(line)
    p = dict(SETTINGS, title=he, main="\n".join(main), comms=[])
    for c in src["comms"]:
        kind = {"אונקלוס": "onkelos", "רש\"י": "rashi"}.get(c["name"])
        if kind:
            text = c["text"] if kind == "onkelos" else "\n".join(plain_comm(l) for l in c["text"].split("\n"))
            p["comms"].append(dict(STYLES[kind], text=text))
    return p


def main(sef, out):
    os.makedirs(out, exist_ok=True)
    order = []
    sections = [("תורה", [(None, he) for he in TORAH]), ("נביאים", NEVIIM), ("כתובים", KETUVIM)]
    k = 0
    for sec, books in sections:
        for en, he in books:
            k += 1
            p = torah_book(he) if en is None else nach_book(sef, en, he)
            name = f"{k:02d} {he}.json"
            with open(os.path.join(out, name), "w", encoding="utf-8") as f:
                json.dump(p, f, ensure_ascii=False, indent=1)
            order.append({"section": sec, "file": name, "title": he})
            print(name, len(p["main"].split("\n")), "lines;", ", ".join(c["name"] for c in p["comms"]))
    with open(os.path.join(out, "tanakh.json"), "w", encoding="utf-8") as f:
        json.dump(order, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
