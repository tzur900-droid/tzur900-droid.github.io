"""Talks on a book of the Torah: for every parasha, a few of the rabbi's talks on YouTube are
transcribed, and up to three talks are written from them, each on a different subject.

Everything runs by itself: search per parasha → download and transcribe → reading → a plan for
every parasha → writing → the book (a heading for every parasha, its talks, their sources)."""
import re

from . import collect, compose, pipeline
from .claude_cli import json_from, ask
from .log import log
from .search import PARASHOT


def name_words(rav):
    """The first name and the family name ("הרב זלמן ברוך מלמד" → זלמן, מלמד): titles often leave out
    the middle name."""
    w = collect.rav_words(rav)
    return [w[0], w[-1]] if len(w) > 2 else w


def mentions(title, parasha):
    """Whether a video's title speaks of this parasha (the name as a whole word)."""
    t = re.sub(r"[\"'׳״|\-–—:,.()\[\]]", " ", title or "")
    return re.search(rf"(^|\s)(ל?פרשת\s+)?{re.escape(parasha)}(\s|$)", t) is not None


def find_videos(project, parasha, want, stop=lambda: False):
    """Up to want of the rabbi's talks on the parasha (title has the rabbi's name and the parasha's)."""
    import yt_dlp
    rav = project.data["rav"]
    names = name_words(rav)
    queries = [f"{rav} שיחת מוצאי שבת {parasha}", f"{rav} פרשת {parasha}", f"{' '.join(names)} {parasha}"]
    found, seen = [], set()
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        for q in queries:
            if stop() or len(found) >= want:
                break
            try:
                res = ydl.extract_info(f"ytsearch30:{q}", download=False)
            except Exception as e:
                log(f"חיפוש ביוטיוב נכשל ({q}): {type(e).__name__}")
                continue
            for e in res.get("entries") or []:
                vid = e.get("id")
                title = e.get("title") or ""
                hay = title + " " + (e.get("channel") or "")
                mins = (e.get("duration") or 0) / 60
                if not vid or vid in seen or not all(w in hay for w in names) or not mentions(title, parasha):
                    continue
                if mins and (mins < 8 or mins > 120):        # not a short clip, not a whole day of lessons
                    continue
                seen.add(vid)
                found.append((f"https://www.youtube.com/watch?v={vid}", title, mins, e.get("channel") or ""))
                if len(found) >= want:
                    break
    return found


def step_search(project, stop=lambda: False):
    mode = project.data["parasha_mode"]
    for p in PARASHOT[mode["book"]]:
        if stop():
            return
        have = [s for s in project.sources if s.get("parasha") == p]
        if len(have) >= mode["videos"]:
            continue
        vids = find_videos(project, p, mode["videos"] - len(have), stop)
        for url, title, mins, channel in vids:
            s = project.add_source(url, title, "video", f"יוטיוב · {channel}" + (f" · {mins:.0f} דקות" if mins else ""),
                                   "יוטיוב")
            s["parasha"] = p
        log(f"פרשת {p}: {len(have) + len(vids)} שיחות ביוטיוב")
        project.save()


PLAN = """הבקשה: שיחות על פרשת {parasha} (ספר {book}) על פי דברי {rav}, לספר שבו לכל פרשה עד {talks} שיחות.
{instructions}לפניך מה שנאסף מ־{n} שיחות של הרב על הפרשה (כל מקור עם מספר).
תכנן עד {talks} שיחות לפרשה. **כל שיחה בנושא אחר**, בלי חזרות ביניהן. אם אין מספיק חומר ל־{talks} שיחות שונות —
תכנן פחות (עדיף שתי שיחות מלאות משלוש חוזרות). כל שיחה צריכה להישען על חומר רב מהמקורות.
לכל שיחה: כותרת (רק השם, בלי "שיחה" ובלי מספר), תכנית של כמה שורות, ומספרי המקורות שלה.
{style_ask}
החזר רק JSON:
```json
{{"style": "{style_field}", "chapters": [{{"title": "...", "plan": "...", "sources": [1, 4]}}]}}
```

החומר:
{notes}"""


def plan_parasha(project, parasha, style, model=None):
    d, mode = project.data, project.data["parasha_mode"]
    used = [s for s in project.sources if s.get("parasha") == parasha and s["state"] == "read"]
    if not used:
        log(f"פרשת {parasha}: אין שיחות שנקראו — מדלג")
        return [], style
    notes = "\n\n".join(f"=== מקור {s['id']}: {s['title']} ===\n{project.read('notes', '%03d.md' % s['id'])}"
                        for s in used)
    if len(notes) > compose.OUTLINE_BUDGET:
        notes = "\n\n".join(f"=== מקור {s['id']}: {s['title']} ===\n"
                            f"{compose._summary(project.read('notes', '%03d.md' % s['id']))}" for s in used)
    prompt = PLAN.format(parasha=parasha, book=mode["book"], rav=d.get("rav_full_name") or d["rav"], talks=mode["talks"],
                         instructions=compose.instructions_block(project), n=len(used), notes=notes,
                         style_ask="" if style else "וגם: תאר את סגנון הרב לפי המקורות (ביטויים אופייניים עם דוגמאות, "
                                                    "מבנה של שיחה אצלו, איך הוא פותח ומסיים), כדי לכתוב בלשונו.",
                         style_field="" if style else "תיאור הסגנון")
    log(f"מתכנן את השיחות לפרשת {parasha}…")
    res = json_from(ask(prompt, model=model, system=compose.SYSTEM, timeout=1800))
    chapters = []
    for c in res.get("chapters", [])[:mode["talks"]]:
        ids = [x for x in c.get("sources", []) if any(s["id"] == x for s in used)] or [s["id"] for s in used]
        chapters.append({"title": compose.bare_title(c.get("title", "")), "plan": c.get("plan", ""),
                         "sources": ids, "part": parasha})
    log(f"פרשת {parasha}: {len(chapters)} שיחות")
    return chapters, style or (res.get("style") or "")


def step_outline(project, model=None):
    d, mode = project.data, project.data["parasha_mode"]
    chapters, style = [], ""
    for p in PARASHOT[mode["book"]]:
        ch, style = plan_parasha(project, p, style, model)
        chapters += ch
    plan = {"title": f"שיחות על ספר {mode['book']}", "subtitle": f"על פי דברי {d.get('rav_full_name') or d['rav']}",
            "style": style, "chapters": chapters}
    project.write(compose.outline_to_md(plan), "outline.md")
    d["title"] = plan["title"]
    project.save()
    log(f"התכנית מוכנה: {len(chapters)} שיחות ב־{len({c['part'] for c in chapters})} פרשות")
    return plan


def run(project, stop=lambda: False):
    """All of it, going on from where it stopped."""
    if not project.sources or any(len([s for s in project.sources if s.get("parasha") == p]) == 0
                                  for p in PARASHOT[project.data["parasha_mode"]["book"]]):
        step_search(project, stop)
    for step in (pipeline.step_collect, pipeline.step_read):
        if stop():
            return None
        step(project, stop)
    if stop():
        return None
    if not project.read("outline.md"):
        step_outline(project, pipeline.model_of(project))
    return pipeline.step_write(project, stop)
