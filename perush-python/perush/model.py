"""Project data: the text, the commentaries and the settings, and how they are parsed.

The project file format is the same JSON the web version saves, so projects move
freely between the two.
"""
import copy
import json
import re

PLACES = {"side": "טור צמוד לטקסט", "bottom": "מתחת לטקסט", "under": "אחרי כל פסוק"}

# Page sizes (name, width mm, height mm): the usual sizes for printing seforim, then paper
# sizes; "custom" takes pageW / pageH from the project.
PAGE_SIZES = {
    "S24": ("ספר גדול 24×34 (מקראות גדולות)", 240, 340),
    "S23": ("ספר 23×32", 230, 320),
    "A4": ("A4 (21×29.7)", 210, 297),
    "S20": ("ספר 20×28", 200, 280),
    "B5": ("B5 (17.6×25)", 176, 250),
    "S17": ("ספר רגיל 17×24", 170, 240),
    "S16": ("ספר 16×23", 160, 230),
    "S15": ("ספר 15×21", 150, 210),
    "A5": ("A5 (14.8×21)", 148, 210),
    "S14": ("ספר קטן 14×20", 140, 200),
    "S12": ("ספר כיס 12×17", 120, 170),
    "A6": ("A6 (10.5×14.8)", 105, 148),
    "Letter": ("Letter (21.6×27.9)", 216, 279),
    "custom": ("גודל אחר (לפי רוחב וגובה)", 0, 0),
}


def page_mm(project):
    """The page's width and height in mm."""
    if project.get("pageSize") == "custom":
        return float(project.get("pageW") or 170), float(project.get("pageH") or 240)
    _, w, h = PAGE_SIZES.get(project.get("pageSize"), PAGE_SIZES["A4"])
    return float(w), float(h)

DEDICATION = "הספר עומד ועוצב בסיוע ובמימון אבנר אליאסיאן\nלימוד התורה יעמוד לזכות לו ולבני משפחתו"

DEFAULTS = {
    "title": "",
    "main": "",
    "comms": [],
    "pageSize": "A4",
    "pageW": 170,
    "pageH": 240,
    "margin": 14,
    "mainFont": "Frank Ruhl Libre",
    "mainSize": 16,
    "lineHeight": 1.45,
    "colGap": 5,
    "sectionGap": 2,
    "minLines": 4,
    "firstPage": 1,
    "verseNewLine": False,
    "numbers": True,
    "header": True,
    "names": True,
    "inlineChapters": False,
    "bookMode": False,
    # printed small at the foot of the first page; a line break ("\n") starts a new line
    "dedication": DEDICATION,
    "titlePage": True,       # a title page at the start: the name of the book, what is in it, the dedication
    "titleSub": "",
    "gutter": 0,             # extra margin on the inner side, for the binding (mm; book form only)          # the line under the name on the title page ("" = made from the commentaries)
}

COMM_DEFAULTS = {
    "name": "פירוש",
    "place": "bottom",
    "side": "left",
    "font": "Noto Rashi Hebrew",
    "size": 10,
    "width": 32,
    "autoW": True,
    "cols": 2,
    "text": "",
}

EXAMPLE = {
    "title": "בראשית",
    "main": "\n".join([
        "# פרשת בראשית",
        "# פרק א",
        "בראשית ברא אלהים את השמים ואת הארץ.",
        "והארץ היתה תהו ובהו וחשך על פני תהום ורוח אלהים מרחפת על פני המים.",
        "ויאמר אלהים יהי אור ויהי אור.",
        "וירא אלהים את האור כי טוב ויבדל אלהים בין האור ובין החשך.",
        "ויקרא אלהים לאור יום ולחשך קרא לילה ויהי ערב ויהי בקר יום אחד.",
        "## הפטרת בראשית",
        "[ה] כה אמר האל ה' בורא השמים ונוטיהם רקע הארץ וצאצאיה נתן נשמה לעם עליה ורוח להלכים בה.",
        "[ו] אני ה' קראתיך בצדק ואחזק בידך ואצרך ואתנך לברית עם לאור גוים.",
        "[ז] לפקח עינים עורות להוציא ממסגר אסיר מבית כלא ישבי חשך.",
    ]),
    "comms": [
        {
            "name": "אונקלוס", "place": "side", "side": "left", "font": "Noto Serif Hebrew",
            "size": 11, "width": 34, "autoW": True, "cols": 2,
            "text": "\n".join([
                "בקדמין ברא יי ית שמיא וית ארעא.",
                "וארעא הות צדיא וריקניא וחשוכא על אפי תהומא ורוחא מן קדם יי מנשבא על אפי מיא.",
                "ואמר יי יהי נהורא והוה נהורא.",
                "וחזא יי ית נהורא ארי טב ואפריש יי בין נהורא ובין חשוכא.",
                "וקרא יי לנהורא יממא ולחשוכא קרא ליליא והוה רמש והוה צפר יום חד.",
            ]),
        },
        {
            "name": "רש\"י", "place": "bottom", "side": "left", "font": "Noto Rashi Hebrew",
            "size": 10, "width": 30, "autoW": True, "cols": 2,
            "text": "\n".join([
                "@1 בראשית - אמר רבי יצחק לא היה צריך להתחיל את התורה אלא מהחדש הזה לכם, שהיא מצוה ראשונה שנצטוו בה ישראל. ומה טעם פתח בבראשית, משום כח מעשיו הגיד לעמו לתת להם נחלת גוים.",
                "@2 תהו ובהו - תהו לשון תמה ושממון, שאדם תוהא ומשתומם על בהו שבו.",
                "@2 ורוח אלהים מרחפת - כסא הכבוד עומד באויר ומרחף על פני המים ברוח פיו של הקב\"ה ובמאמרו, כיונה המרחפת על הקן.",
                "@4 וירא אלהים את האור כי טוב ויבדל - אף בזה אנו צריכים לדברי אגדה, ראהו שאינו כדאי להשתמש בו רשעים, והבדילו לצדיקים לעתיד לבא.",
                "@5 יום אחד - לפי סדר לשון הפרשה היה לו לכתוב יום ראשון, כמו שכתוב בשאר הימים שני שלישי רביעי. למה כתב אחד, לפי שהיה הקב\"ה יחיד בעולמו.",
            ]),
        },
    ],
}


def normalize(project):
    """Fill in missing settings so older or hand-written project files still load."""
    p = copy.deepcopy(DEFAULTS)
    p.update({k: v for k, v in project.items() if k in DEFAULTS})
    comms = []
    for c in project.get("comms", []):
        cc = dict(COMM_DEFAULTS)
        cc.update({k: v for k, v in c.items() if k in COMM_DEFAULTS})
        if cc["place"] not in PLACES:
            cc["place"] = "bottom"
        comms.append(cc)
    p["comms"] = comms
    if p["pageSize"] not in PAGE_SIZES:
        p["pageSize"] = "A4"
    return p


def example_project():
    p = normalize(EXAMPLE)
    return p


def load_project(path):
    with open(path, encoding="utf-8") as f:
        return normalize(json.load(f))


def save_project(project, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)


def heb(n):
    """A number in Hebrew letters (15 and 16 as ט"ו / ט"ז)."""
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
    if n == 15:
        s += "טו"
    elif n == 16:
        s += "טז"
    else:
        s += tens[n // 10] + ones[n % 10]
    return s


def tokenize(text):
    """Split text into words; **…** marks bold. Returns [(word, bold)]."""
    out = []
    bold = False
    for raw in text.split():
        parts = raw.split("**")
        word = "".join(parts)
        if not word:
            if len(parts) > 1:
                bold = not bold if len(parts) % 2 == 0 else bold
            continue
        # a word is bold if it starts inside a bold stretch or opens one
        b = bold or (len(parts) > 1 and parts[0] == "")
        out.append((word, b))
        if len(parts) % 2 == 0:
            bold = not bold
    return out


_DH = re.compile(r"^(.{1,90}?)\s+[-–—]\s+(.*)$", re.S)


def entry_tokens(raw):
    """A commentary entry: the words before ' - ' (the dibbur hamatchil) are bold."""
    raw = raw.strip()
    if "**" in raw:
        return tokenize(raw)
    m = _DH.match(raw)
    if m:
        return [(w, True) for w in m.group(1).split()] + [(w, False) for w in m.group(2).split()]
    return [(w, False) for w in raw.split()]


def parse_main(text):
    """Turn the main text into items: headings and verses.

    '# …' is a heading; a heading starting with פרשת/פרשה names the parasha for the
    running head. '## …' opens a section with no commentary (a haftara) until the next
    '# …'. '[label] text' gives a verse its own label.
    """
    items = []
    verses = 0
    in_chap = 0
    chapter = ""
    parasha = ""
    no_comm = False
    for line in text.replace("\r", "").split("\n"):
        t = line.strip()
        if not t:
            continue
        if t.startswith("#"):
            # '###' is a heading inside the current section (a chapter within a haftara)
            if not t.startswith("###"):
                no_comm = t.startswith("##")
            chapter = t.lstrip("#").strip()
            if not no_comm and re.match(r"^פרש(ת|ה)\s", chapter):
                parasha = chapter
            in_chap = 0
            items.append({"type": "h", "text": chapter, "chapter": chapter, "parasha": parasha, "noComm": no_comm})
            continue
        in_chap += 1
        label = heb(in_chap)
        body = t
        m = re.match(r"^\[([^\]]{1,12})\]\s*(.*)$", t)
        if m:
            label, body = m.group(1), m.group(2)
        items.append({
            "type": "v", "idx": -1 if no_comm else verses, "label": label, "words": tokenize(body),
            "plain": body, "chapter": chapter, "parasha": parasha, "noComm": no_comm,
        })
        if not no_comm:
            verses += 1
    return items, verses


def parse_comm(comm, n):
    """Link a commentary's lines to verses.

    By order: line N belongs to verse N (an empty line = no commentary).
    By reference: a line starting '@N' belongs to verse N; lines after it, until the
    next '@', belong to the same verse.
    Returns (entries per verse, problem text, info text).
    """
    entries = [[] for _ in range(n)]
    lines = comm["text"].replace("\r", "").split("\n")
    by_ref = any(re.match(r"^\s*@\s*\d+", l) for l in lines)
    problem = info = ""
    if by_ref:
        cur = -1
        bad = []
        for l in lines:
            m = re.match(r"^\s*@\s*(\d+)\s*(.*)$", l, re.S)
            if m:
                cur = int(m.group(1)) - 1
                if cur < 0 or cur >= n:
                    bad.append(m.group(1))
                    cur = -2
                    continue
                if m.group(2).strip():
                    entries[cur].append(m.group(2))
            elif l.strip():
                if cur >= 0:
                    entries[cur].append(l)
                elif cur == -1:
                    bad.append("שורה ללא @")
        covered = sum(1 for e in entries if e)
        info = f"לפי הפניה · {covered} מתוך {n} פסוקים עם פירוש"
        if bad:
            uniq = list(dict.fromkeys(bad))
            problem = f"הפניה לפסוק שלא קיים: {', '.join(uniq)} (יש {n} פסוקים)"
    else:
        rows = [l for l in lines if not l.strip().startswith("#")]
        while rows and not rows[-1].strip():
            rows.pop()
        for i, l in enumerate(rows):
            if i < n and l.strip():
                entries[i].append(l)
        if not rows:
            info = "ריק"
        elif len(rows) != n:
            problem = f"{len(rows)} שורות מול {n} פסוקים — הפירוש לא יתאים לפסוקים!"
        else:
            info = f"לפי סדר · {n} שורות = {n} פסוקים ✓"
    return entries, problem, info
