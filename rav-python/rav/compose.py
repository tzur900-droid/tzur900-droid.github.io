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
### הדברים לפרטיהם
כל רעיון, הסבר, חידוש, משל, סיפור, הלכה ומקור (פסוק, גמרא, מדרש, ראשונים) שהרב מביא ושנוגע לבקשה — בפירוט מלא,
בלשון הרב ככל האפשר. משפטים חזקים ואופייניים — ציטוט מדויק במרכאות. שמור על סדר הדברים ועל הקשר ביניהם.
אל תשמיט דברים חשובים ואל תוסיף משלך.
### סגנון
איך הרב מדבר/כותב כאן: ביטויים חוזרים, איך הוא פותח ומסיים, משלים ודוגמאות, פנייה לשומעים, אורך המשפטים.
{transcript_note}
המקור:
<<<
{text}
>>>"""

QUALITY = ("### איכות התמלול: טובה / בינונית / גרועה\n"
           "(גרועה = חלקים גדולים לא מובנים, משפטים משובשים, אי אפשר לדעת בבירור מה הרב אמר)\n")

TRANSCRIPT_NOTE = ("(המקור הוא תמלול אוטומטי של הקלטה: יש בו שגיאות שמיעה, בעיקר בשמות, בציטוטים ובמקורות. "
                   "תקן לפי ההקשר את מה שברור, וכשאינך בטוח — כתוב [לא ברור].)\n")

OUTLINE = """הבקשה: {kind} על פי דברי {rav} ({full}) בנושא: "{request}".

לפניך מה שנאסף מ־{n} מקורות של הרב (כל מקור עם מספר). על פי כל זה:
1. תכנן את ה{kind}: כותרת, ומבנה של פרקים{series} — כך שכל רעיון חשוב מהמקורות ייכנס, בלי חזרות, בסדר הגיוני
   שמתאים לנושא ולדרך של הרב. לכל פרק: כותרת, תכנית של כמה שורות (מה ייכתב בו ובאיזה סדר), ומספרי המקורות שלו.
2. תאר את סגנון הרב לפי המקורות, כדי שאפשר יהיה לכתוב בלשונו: אוצר מילים, ביטויים אופייניים (עם דוגמאות
   מדויקות מהמקורות), מבנה של דבר תורה אצלו, איך הוא מסביר, פונה לשומעים, משתמש במשלים.

החזר רק JSON:
```json
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

כללים:
- כתוב את הפרק במלואו, בלשון הרב ובקולו — כאילו הרב עצמו כותב או מדבר (כמו ספר שנערך מתוך שיעוריו),
  עם הביטויים והדרך שלו. דברים מתומללים — ערוך ללשון כתובה נקייה, אבל השאר את החיות ואת האופי של הרב.
- רק מה שנמצא במקורות שלמטה. אל תוסיף רעיונות, סיפורים או מקורות משלך. אם יש סתירה בין מקורות — הבא את שני הצדדים.
- בסוף כל פסקה ציין מאיזה מקור היא, כך: {{מקור 12}} או {{מקור 3, 7}}.
- מבנה: כותרות משנה (### כותרת) כשצריך, פסקאות מלאות, ציטוט מפסוק או ממאמר חז"ל בתוך הטקסט כפי שהרב מביא.
  {series_rule}
- אל תחזור על מה ששייך לפרקים אחרים.
- החזר רק את הפרק עצמו: שורה ראשונה "## {title}" ואחריה הטקסט, בלי הקדמות והסברים שלך.

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
    for i, part in enumerate(parts):
        prompt = EXTRACT.format(id=s["id"], what=what, title=s["title"], url=s["url"],
                                part=f"(חלק {i + 1} מתוך {len(parts)})" if len(parts) > 1 else "",
                                kind=project.kind_name, rav=d["rav"], request=d["request"],
                                transcript_note=TRANSCRIPT_NOTE if heard else "", text=part,
                                quality=QUALITY if heard else "")
        outs.append(ask(prompt, model=model, system=SYSTEM, timeout=1800))
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
                            request=d["request"], n=len(used), series=series, notes=full)
    log("מתכנן את הספר ומנתח את סגנון הרב…")
    plan = json_from(ask(prompt, model=model, system=SYSTEM, timeout=2400))
    project.write(outline_to_md(plan), "outline.md")
    d["title"] = plan.get("title") or d.get("title") or ""
    project.save()
    log(f"התכנית מוכנה: {len(plan.get('chapters', []))} פרקים")
    return plan


def outline_to_md(plan):
    out = [f"# {plan.get('title', '')}", plan.get("subtitle", ""), "", "## סגנון הרב", plan.get("style", ""), ""]
    for i, c in enumerate(plan.get("chapters", []), 1):
        out += [f"## פרק {i}: {c.get('title', '')}",
                "מקורות: " + ", ".join(str(x) for x in c.get("sources", [])),
                c.get("plan", ""), ""]
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
            cur = {"title": m.group(1).strip(), "plan": "", "sources": []}
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
            mm = re.match(r"^מקורות:\s*(.*)", line)
            if mm:
                cur["sources"] = [int(x) for x in re.findall(r"\d+", mm.group(1))]
            else:
                cur["plan"] += line + "\n"
    plan["style"] = plan["style"].strip()
    for c in plan["chapters"]:
        c["plan"] = c["plan"].strip()
    return plan


def write_chapter(project, plan, i, model=None):
    d = project.data
    c = plan["chapters"][i]
    by_id = {s["id"]: s for s in project.sources}
    ids = [x for x in c["sources"] if x in by_id] or [s["id"] for s in project.sources if s["state"] == "read"]
    # the sources themselves when they fit (the rabbi's own words); otherwise what was taken from them
    texts = [(x, project.read("sources", "%03d.txt" % x)) for x in ids]
    if sum(len(t) for _, t in texts) > CHAPTER_BUDGET:
        texts = [(x, project.read("notes", "%03d.md" % x)) for x in ids]
    if sum(len(t) for _, t in texts) > CHAPTER_BUDGET:
        per = CHAPTER_BUDGET // max(1, len(texts))
        texts = [(x, t[:per]) for x, t in texts]
    material = "\n\n".join(f"=== מקור {x}: {by_id[x]['title']} ===\n{t}" for x, t in texts)
    toc = "\n".join(f"{n}. {ch['title']}" + ("   ← הפרק הזה" if n - 1 == i else "")
                    for n, ch in enumerate(plan["chapters"], 1))
    series = d["kind"] == "series"
    prompt = CHAPTER.format(
        which=f"שיעור {i + 1}" if series else f"פרק {i + 1}", kind=project.kind_name, rav=d["rav"],
        full=d.get("rav_full_name") or d["rav"], request=d["request"], toc=toc, title=c["title"],
        plan=c["plan"], style=plan.get("style", ""), material=material,
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
            "העריכה נעשתה בעזרת בינה מלאכותית (Claude), על פי לשונו ודרכו של הרב, ובסוף כל פסקה מצוין "
            "המקור שלה (הרשימה בסוף). ייתכנו בו טעויות של תמלול ושל עריכה, והאחריות עליהן על העורך ולא על הרב; "
            "כל דבר הלכה יש לברר במקור. לפני הפצה או הדפסה ראוי לבקש את הסכמת הרב או מוסדותיו.\n")


def sources_list(project):
    used = [s for s in project.sources if s["state"] == "read"]
    lines = ["## רשימת המקורות", ""]
    for s in used:
        lines.append(f"- {s['id']}. {s['title']} — {s['url']}" + (f" ({s['note']})" if s.get("note") else ""))
    return "\n".join(lines) + "\n"


def assemble(project, plan):
    n = len(plan["chapters"])
    by = f"על פי דברי {project.data.get('rav_full_name') or project.data['rav']}"
    sub = plan.get("subtitle", "")
    parts = [f"# {plan.get('title') or project.label()}", sub, "", "" if project.data["rav"] in sub else by, "",
             editor_note(project)]
    for i in range(n):
        parts.append(project.read("chapters", f"{i + 1:02d}.md"))
    parts.append(sources_list(project))
    md = "\n\n".join(p.strip("\n") for p in parts) + "\n"
    project.write(md, "book.md")
    return md


def load_plan(project):
    md = project.read("outline.md")
    return md_to_outline(md) if md else None


def plan_json(plan):
    return json.dumps(plan, ensure_ascii=False, indent=1)
