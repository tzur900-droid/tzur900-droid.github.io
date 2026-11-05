"""Step 3: writing — Claude reads every source and takes from it what belongs to the request
(notes/), plans the book with a description of the rabbi's way of speaking (outline.md),
and writes every chapter from the sources of that chapter (chapters/)."""
import json
import os
import re

from .claude_cli import ClaudeError, ask, json_from
from .log import log

CHUNK = 90_000          # characters of a source in one reading
OUTLINE_BUDGET = 350_000
CHAPTER_BUDGET = 160_000

SYSTEM = ("אתה עורך ספרי תורה מנוסה, שמכין ספרים מתוך שיעורים וכתבים של רבנים. אתה נאמן למקורות: "
          "אינך ממציא רעיונות, מקורות או סיפורים שאינם בחומר, ואינך מייחס לרב דבר שלא אמר. "
          "כתוב בעברית תקנית ויפה.")

EXTRACT = """לפניך מקור מס' {id} — {what}.
כותרת: {title}
קישור: {url}
{part}
הבקשה: {kind} על פי דברי {rav} בנושא: "{request}".

קרא את כל המקור, וכתוב בדיוק בצורה הזו:

### של הרב: כן / לא / לא ברור
(האם אלה דברים של {rav} עצמו — כתב שלו, שיעור שלו או סיכום של שיעור שלו)
### רלוונטי: כן / לא
(האם יש כאן משהו לבקשה)
{quality}### תמצית
שלוש־חמש שורות: מה יש במקור הזה לבקשה.
{details}
### סגנון
איך הרב מדבר/כותב כאן: ביטויים חוזרים, איך הוא פותח ומסיים, משלים ודוגמאות, פנייה לשומעים, אורך המשפטים.
{transcript_note}
המקור:
<<<
{text}
>>>"""

QUALITY = ("### איכות התמלול: טובה / בינונית / גרועה\n"
           "(גרועה = חלקים גדולים לא מובנים, משפטים משובשים, אי אפשר לדעת בבירור מה הרב אמר)\n")

DETAILS_FULL = """### הדברים לפרטיהם
כל רעיון, הסבר, חידוש, משל, סיפור, הלכה ומקור (פסוק, גמרא, מדרש, ראשונים) שהרב מביא ושנוגע לבקשה — בפירוט מלא.
**העתק את משפטי הרב עצמם, שלמים ומילה במילה** (בלי לסכם ובלי לנסח מחדש); מותר רק להשמיט חזרות ומילות מילוי
ולתקן שגיאות תמלול ברורות. שמור על סדר הדברים ועל הקשר ביניהם. אל תשמיט דברים חשובים ואל תוסיף משלך."""

# saving: the source itself is given whole to the writing, so here only what the planning needs
DETAILS_LIGHT = """### נושאים
רשימה של הנושאים והרעיונות שהרב מדבר עליהם ושנוגעים לבקשה, לפי הסדר: לכל אחד שורה אחת, ואחריה (אם יש)
משפט אופייני אחד שלו במרכאות. בלי להעתיק את כל הדברים."""

TRANSCRIPT_NOTE = ("(המקור הוא תמלול אוטומטי של הקלטה: יש בו שגיאות שמיעה, בעיקר בשמות, בציטוטים ובמקורות. "
                   "תקן לפי ההקשר את מה שברור, וכשאינך בטוח — כתוב [לא ברור].)\n")

OUTLINE = """הבקשה: {kind} על פי דברי {rav} ({full}) בנושא: "{request}".

{instructions}לפניך מה שנאסף מ־{n} מקורות של הרב (כל מקור עם מספר). על פי כל זה:
1. תכנן את ה{kind}: כותרת, ומבנה של פרקים{series} — כך שכל רעיון חשוב מהמקורות ייכנס, בלי חזרות, בסדר הגיוני
   שמתאים לנושא ולדרך של הרב. לכל פרק: כותרת, תכנית של כמה שורות (מה ייכתב בו ובאיזה סדר), ומספרי המקורות שלו.
2. תאר את סגנון הרב לפי המקורות, כדי שאפשר יהיה לכתוב בלשונו: אוצר מילים, ביטויים אופייניים (עם דוגמאות
   מדויקות מהמקורות), מבנה של דבר תורה אצלו, איך הוא מסביר, פונה לשומעים, משתמש במשלים.

החזר רק JSON:
```json
(כותרת של פרק — רק השם שלו, בלי "פרק" ובלי מספר.)
{{"title": "שם ה{kind}", "subtitle": "שורת משנה", "style": "תיאור הסגנון (פסקאות, עם דוגמאות)",
 "chapters": [{{"title": "...", "plan": "...", "sources": [1, 4]}}]}}
```

החומר:
{notes}"""

CHAPTER = """אתה כותב את {which} של {kind} על פי דברי {rav} ({full}) בנושא: "{request}".

כל ה{kind}:
{toc}

הפרק שאתה כותב עכשיו: "{title}"
התכנית שלו: {plan}

סגנון הרב (לכתוב בלשונו):
{style}

{instructions}כללים:
- **בנה את הפרק כמעט כולו ממשפטים שלמים של הרב, מילה במילה מתוך המקורות שלמטה.** אל תנסח מחדש בלשונך.
  מותר רק: לבחור ולסדר את המשפטים, להשמיט חזרות ומילות מילוי של דיבור, לתקן שגיאות תמלול ודקדוק ברורות,
  ולהוסיף מילות קישור קצרות בין קטע לקטע (כמה מילים, לא משפטים משלך). כשהרב אמר רעיון בכמה מקומות —
  קח את הנוסח המלא והברור שלו.
- רק מה שנמצא במקורות שלמטה. אל תוסיף רעיונות, סיפורים או מקורות משלך. אם יש סתירה בין מקורות — הבא את שני הצדדים.
- בסוף כל פסקה ציין מאיזה מקור היא, כך: {{מקור 12}} או {{מקור 3, 7}}.
- מבנה: כותרות משנה (### כותרת) כשצריך, פסקאות מלאות, ציטוט מפסוק או ממאמר חז"ל בתוך הטקסט כפי שהרב מביא.
  {series_rule}
- אל תחזור על מה ששייך לפרקים אחרים.
{length_rule}
- החזר רק את הפרק עצמו: שורה ראשונה "## {title}" ואחריה הטקסט, בלי הקדמות והסברים שלך ובלי רשימת מקורות
  (הרשימה נוספת אחר כך).

המקורות של הפרק:
{material}"""


def _split(text, n=CHUNK):
    if len(text) <= n:
        return [text]
    parts, i = [], 0
    while i < len(text):
        j = min(len(text), i + n)
        k = text.rfind("\n", i + n // 2, j) if j < len(text) else j
        j = k if k > i else j
        parts.append(text[i:j])
        i = j
    return parts


def extract_one(project, s, model=None):
    d = project.data
    text = project.read("sources", f"{s['id']:03d}.txt")
    if not text:
        return
    heard = "תומלל" in (s.get("note") or "") or "כתוביות" in (s.get("note") or "")
    what = "תמלול של שיעור מוקלט" if heard else "טקסט"
    parts = _split(text)
    outs = []
    st = d["settings"]
    light = st.get("light_reading", True)
    read_model = (st.get("read_model", "sonnet") if light else model) or model
    for i, part in enumerate(parts):
        prompt = EXTRACT.format(id=s["id"], what=what, title=s["title"], url=s["url"],
                                part=f"(חלק {i + 1} מתוך {len(parts)})" if len(parts) > 1 else "",
                                kind=project.kind_name, rav=d["rav"], request=source_request(project, s),
                                transcript_note=TRANSCRIPT_NOTE if heard else "", text=part,
                                quality=QUALITY if heard else "", details=DETAILS_LIGHT if light else DETAILS_FULL)
        outs.append(ask(prompt, model=read_model, system=SYSTEM, timeout=1800))
    note = "\n\n".join(outs)
    project.write(note, "notes", f"{s['id']:03d}.md")
    mine = re.findall(r"של הרב:\s*\**\s*(כן|לא ברור|לא)", note)
    rel = re.findall(r"רלוונטי:\s*\**\s*(כן|לא)", note)
    not_his = bool(mine) and all(m == "לא" for m in mine)
    unrelated = bool(rel) and all(r == "לא" for r in rel)
    if not_his or unrelated:
        s["state"] = "irrelevant"
        s["note"] = "לא של הרב" if not_his else "לא קשור לבקשה"
        log(f"– {s['title'][:60]} — {s['note']}")
    elif heard and poor_transcript(note) and redo_accurately(project, s):
        return
    else:
        s["state"] = "read"
        if heard and poor_transcript(note):
            s["note"] = (s.get("note") or "") + " · ההקלטה לא ברורה גם בתמלול המדויק"
        log(f"✓ נקרא: {s['title'][:60]}")
    project.save()


def poor_transcript(note):
    q = re.findall(r"איכות התמלול:\s*\**\s*(טובה|בינונית|גרועה)", note)
    return bool(q) and q.count("גרועה") * 2 >= len(q)      # most parts of the recording were poor


def redo_accurately(project, s):
    """A poor transcript that was not made with the accurate model: back to waiting, to be
    transcribed again with it (the recording is kept, nothing is downloaded again)."""
    how = s.get("how") or ""
    if not how:      # sources from before "how" was kept
        note = s.get("note") or ""
        how = "auto_subs" if "אוטומטיות" in note else ("human_subs" if "כתוביות" in note else
                                                          "whisper:" + project.data["settings"].get("whisper_model", "ivrit-ai"))
    if s.get("accurate") or how == "whisper:ivrit-ai":
        return False
    for path in (project.source_text_path(s), project.note_path(s)):
        if os.path.isfile(path):
            os.remove(path)
    s.update(accurate=True, state="new", chars=0,
             note="התמלול לא היה ברור — יתומלל שוב במודל המדויק")
    project.save()
    log(f"↻ {s['title'][:60]} — התמלול לא ברור ({how}); יתומלל שוב במודל המדויק")
    return True


def source_request(project, s):
    """What a source is read for: the book's request, or its parasha in a book of talks on a chumash."""
    if s.get("parasha"):
        return f"שיחות על פרשת {s['parasha']} (ספר {project.data.get('parasha_mode', {}).get('book', '')})"
    return project.data["request"]


def plan_model(project, model):
    """Planning (and the search) with the thrifty model unless the settings say otherwise; the
    writing keeps the model chosen in the settings."""
    st = project.data["settings"]
    return (st.get("plan_model", "sonnet") if st.get("light_reading", True) else model) or model


def instructions_block(project):
    t = (project.data.get("instructions") or "").strip()
    return f"הנחיות המבקש לספר (חובה לקיים אותן):\n{t}\n\n" if t else ""


REVISE = """לפניך תכנית של {kind} על פי דברי {rav} בנושא: "{request}", והערות של המבקש עליה.
{instructions}תקן את התכנית לפי ההערות. מה שההערות לא מבקשות לשנות — השאר כמו שהוא (כולל תיאור הסגנון).
כל פרק צריך מקורות מתוך רשימת המקורות שלמטה (לפי המספר).

התכנית:
{outline}

ההערות:
{comments}

המקורות (מספר, כותרת ותמצית):
{summaries}

החזר רק JSON כמו קודם:
```json
{{"title": "...", "subtitle": "...", "style": "...", "chapters": [{{"title": "...", "plan": "...", "sources": [1, 4]}}]}}
```"""


def revise_outline(project, comments, model=None):
    """The plan corrected by the user's comments."""
    d = project.data
    used = [s for s in project.sources if s["state"] == "read"]
    summaries = "\n".join(f"{s['id']}. {s['title']}: {_summary(project.read('notes', '%03d.md' % s['id']))[:600]}"
                          for s in used)
    prompt = REVISE.format(kind=project.kind_name, rav=d["rav"], request=d["request"],
                           instructions=instructions_block(project), outline=project.read("outline.md"),
                           comments=comments, summaries=summaries)
    log("מתקן את התכנית לפי ההערות…")
    plan = json_from(ask(prompt, model=plan_model(project, model), system=SYSTEM, timeout=1800))
    project.write(outline_to_md(plan), "outline.md")
    d["title"] = plan.get("title") or d.get("title") or ""
    project.save()
    log(f"התכנית תוקנה: {len(plan.get('chapters', []))} פרקים")
    return plan


def _summary(note):
    m = re.search(r"### תמצית\s*(.*?)(?=###|\Z)", note, re.S)
    return (m.group(1) if m else note[:1200]).strip()


def make_outline(project, model=None):
    d = project.data
    used = [s for s in project.sources if s["state"] == "read"]
    if not used:
        raise ClaudeError("אין מקורות שנקראו ונמצאו קשורים לבקשה — אין ממה לכתוב.")
    notes = {s["id"]: project.read("notes", "%03d.md" % s["id"]) for s in used}
    full = "\n\n".join(f"=== מקור {s['id']}: {s['title']} ===\n{notes[s['id']]}" for s in used)
    if len(full) > OUTLINE_BUDGET:
        log("החומר ארוך — לתכנון נשלחת התמצית של כל מקור")
        full = "\n\n".join(f"=== מקור {s['id']}: {s['title']} ===\n{_summary(notes[s['id']])}" for s in used)
    series = " (כל פרק = שיעור אחד בסדרה)" if d["kind"] == "series" else ""
    prompt = OUTLINE.format(kind=project.kind_name, rav=d["rav"], full=d.get("rav_full_name") or d["rav"],
                            request=d["request"], n=len(used), series=series, notes=full,
                            instructions=instructions_block(project))
    log("מתכנן את הספר ומנתח את סגנון הרב…")
    plan = json_from(ask(prompt, model=plan_model(project, model), system=SYSTEM, timeout=2400))
    project.write(outline_to_md(plan), "outline.md")
    d["title"] = plan.get("title") or d.get("title") or ""
    project.save()
    log(f"התכנית מוכנה: {len(plan.get('chapters', []))} פרקים")
    return plan


NUMBERED = re.compile(r"^\s*(?:פרק|שיחה|שיעור|חלק)\s+[\u05d0-\u05ea\d]{1,4}['׳\"]?\s*[:.\-–—]\s*")


def bare_title(t):
    """A chapter's name without "פרק א:" before it (the book's chapters have names only)."""
    return NUMBERED.sub("", t or "").strip() or (t or "").strip()


def outline_to_md(plan):
    out = [f"# {plan.get('title', '')}", plan.get("subtitle", ""), "", "## סגנון הרב", plan.get("style", ""), ""]
    for i, c in enumerate(plan.get("chapters", []), 1):
        out += [f"## פרק {i}: {bare_title(c.get('title', ''))}"]
        if c.get("part"):
            out.append(f"פרשה: {c['part']}")
        out += ["מקורות: " + ", ".join(str(x) for x in c.get("sources", [])), c.get("plan", ""), ""]
    return "\n".join(out).strip() + "\n"


def md_to_outline(md):
    """The plan back from outline.md (as the user may have edited it)."""
    plan = {"title": "", "subtitle": "", "style": "", "chapters": []}
    cur, mode = None, "head"
    for line in md.splitlines():
        if line.startswith("# ") and not plan["title"]:
            plan["title"] = line[2:].strip()
            continue
        m = re.match(r"^##\s*פרק\s*[^:]*:\s*(.*)", line)
        if m:
            cur = {"title": bare_title(m.group(1)), "plan": "", "sources": []}
            plan["chapters"].append(cur)
            mode = "chap"
            continue
        if line.startswith("## סגנון"):
            mode = "style"
            continue
        if mode == "head" and line.strip() and not plan["subtitle"]:
            plan["subtitle"] = line.strip()
        elif mode == "style":
            plan["style"] += line + "\n"
        elif mode == "chap":
            mp = re.match(r"^פרשה:\s*(.*)", line)
            mm = re.match(r"^מקורות:\s*(.*)", line)
            if mp:
                cur["part"] = mp.group(1).strip()
            elif mm:
                cur["sources"] = [int(x) for x in re.findall(r"\d+", mm.group(1))]
            else:
                cur["plan"] += line + "\n"
    plan["style"] = plan["style"].strip()
    for c in plan["chapters"]:
        c["plan"] = c["plan"].strip()
    return plan


LENGTH_RULE = ("- אורך: כמה שיותר מהחומר של השיחה, אבל לא יותר מכ־10 עמודי ספר (עד כ־3,500 מילים). "
               "אל תמתח ואל תחזור כדי להאריך.")


def write_chapter(project, plan, i, model=None):
    d = project.data
    c = plan["chapters"][i]
    by_id = {s["id"]: s for s in project.sources}
    ids = [x for x in c["sources"] if x in by_id] or [s["id"] for s in project.sources if s["state"] == "read"]
    # the sources themselves when they fit (the rabbi's own words); otherwise what was taken from them
    texts = [(x, project.read("sources", "%03d.txt" % x)) for x in ids]
    if sum(len(t) for _, t in texts) > CHAPTER_BUDGET and not d["settings"].get("light_reading", True):
        texts = [(x, project.read("notes", "%03d.md" % x)) for x in ids]   # (short notes are no use here)
    if sum(len(t) for _, t in texts) > CHAPTER_BUDGET:
        per = CHAPTER_BUDGET // max(1, len(texts))
        texts = [(x, t[:per]) for x, t in texts]
    material = "\n\n".join(f"=== מקור {x}: {by_id[x]['title']} ===\n{t}" for x, t in texts)
    toc = "\n".join(f"{n}. {ch['title']}" + ("   ← הפרק הזה" if n - 1 == i else "")
                    for n, ch in enumerate(plan["chapters"], 1))
    series = d["kind"] == "series"
    prompt = CHAPTER.format(
        which=(f"שיחה לפרשת {c['part']}" if c.get("part") else f"שיעור {i + 1}" if series else f"פרק {i + 1}"),
        kind=project.kind_name, rav=d["rav"],
        full=d.get("rav_full_name") or d["rav"], request=d["request"], toc=toc, title=c["title"],
        plan=c["plan"], style=plan.get("style", ""), material=material, instructions=instructions_block(project),
        length_rule=LENGTH_RULE if d["kind"] == "parasha" else "",
        series_rule=("- זה שיעור בסדרה: פתיחה שמחברת לשיעור הקודם (אם יש), גוף השיעור, וסיכום קצר בסוף."
                     if series else ""))
    log(f"כותב פרק {i + 1}/{len(plan['chapters'])}: {c['title']}")
    text = ask(prompt, model=model, system=SYSTEM, timeout=2400).strip()
    if not text.startswith("##"):
        text = f"## {c['title']}\n\n" + text
    project.write(text + "\n", "chapters", f"{i + 1:02d}.md")
    return text


THIS = {"book": "הספר הזה", "series": "סדרת השיעורים הזו", "article": "הקונטרס הזה", "summary": "הסיכום הזה"}


def editor_note(project):
    d = project.data
    used = [s for s in project.sources if s["state"] == "read"]
    heard = sum(1 for s in used if "תומלל" in (s.get("note") or "") or "כתוביות" in (s.get("note") or ""))
    return ("## פתח דבר\n\n"
            f"{THIS.get(d['kind'], 'החיבור הזה')} נערך מתוך {len(used)} מקורות של {d.get('rav_full_name') or d['rav']} — "
            f"שיעורים, מאמרים וכתבים שפורסמו ברשת{f', מהם {heard} שיעורים מוקלטים שתומללו' if heard else ''}. "
            "העריכה נעשתה בעזרת בינה מלאכותית (Claude), ככל האפשר במשפטיו של הרב עצמו; בסוף כל פסקה מצוין "
            "המקור שלה, בסוף כל פרק — המקורות שמהם נערך, ובסוף הספר — רשימת כל המקורות. ייתכנו בו טעויות של תמלול ושל עריכה, והאחריות עליהן על העורך ולא על הרב; "
            "כל דבר הלכה יש לברר במקור. לפני הפצה או הדפסה ראוי לבקש את הסכמת הרב או מוסדותיו.\n")


SRC_MARK = re.compile(r"\{מקור(?:ות)?\s*([\d,\s]+)\}")


def chapter_sources(text):
    """The numbers of the sources a chapter's paragraphs are marked with, in order."""
    seen = []
    for m in SRC_MARK.finditer(text):
        for x in re.findall(r"\d+", m.group(1)):
            if int(x) not in seen:
                seen.append(int(x))
    return seen


def _src_line(s):
    return f"{s['title']} — {s['url']}"


def chapter_with_sources(project, text):
    """The chapter, with the list of the lessons it was edited from at its end."""
    by_id = {s["id"]: s for s in project.sources}
    ids = [x for x in chapter_sources(text) if x in by_id]
    if not ids:
        return text
    lines = ["", "### מקורות", ""] + [f"- ({x}) {_src_line(by_id[x])}" for x in ids]
    return text.rstrip() + "\n" + "\n".join(lines) + "\n"


def sources_list(project, chapters=()):
    """All the sources of the book, and in which chapters each one was used."""
    by_id = {s["id"]: s for s in project.sources}
    used_in = {}
    for title, text in chapters:
        for x in chapter_sources(text):
            used_in.setdefault(x, []).append(title)
    ids = [s["id"] for s in project.sources if s["id"] in used_in] or \
        [s["id"] for s in project.sources if s["state"] == "read"]
    lines = ["## רשימת המקורות", "", "המקורות שמהם נערך הספר, ובאילו פרקים נעשה שימוש בכל אחד:", ""]
    for x in ids:
        s = by_id[x]
        where = "; ".join(used_in.get(x, []))
        lines.append(f"- ({x}) {_src_line(s)}" + (f" ({s['note']})" if s.get("note") else "") +
                     (f"  ← בפרקים: {where}" if where else ""))
    return "\n".join(lines) + "\n"


def assemble(project, plan):
    n = len(plan["chapters"])
    by = f"על פי דברי {project.data.get('rav_full_name') or project.data['rav']}"
    sub = plan.get("subtitle", "")
    parts = [f"# {plan.get('title') or project.label()}", sub, "", "" if project.data["rav"] in sub else by, "",
             editor_note(project)]
    chapters = []
    for i in range(n):
        text = project.read("chapters", f"{i + 1:02d}.md")
        if not text:
            continue
        c = plan["chapters"][i]
        title = c["title"] + (f" (פרשת {c['part']})" if c.get("part") else "")
        if c.get("part") and (i == 0 or plan["chapters"][i - 1].get("part") != c["part"]):
            parts.append(f"# פרשת {c['part']}")
        chapters.append((title, text))
        parts.append(chapter_with_sources(project, text))
    parts.append(sources_list(project, chapters))
    md = "\n\n".join(p.strip("\n") for p in parts) + "\n"
    project.write(md, "book.md")
    return md


def load_plan(project):
    md = project.read("outline.md")
    return md_to_outline(md) if md else None


def plan_json(plan):
    return json.dumps(plan, ensure_ascii=False, indent=1)
