"""Step 1: finding the rabbi's material on the request — Claude searches the whole web (sites of
lessons and yeshivot, articles, newspapers, PDFs, recordings), and YouTube is searched too."""
from .claude_cli import ask, json_from
from .log import log

SEARCH_PROMPT = """אתה עוזר מחקר תורני. המשימה: למצוא באינטרנט את כל החומר **של {rav} עצמו** — שנכתב בידו,
או שנאמר בקולו (שיעור מוקלט, סרטון, הרצאה), או סיכום/תמלול של שיעור שלו — שקשור לבקשה הזו:

"{request}"

(המטרה הסופית: {kind} על פי דברי הרב.)
{instructions}

חפש ביסודיות: עשה הרבה חיפושים שונים (לפחות 15), בעברית ובאנגלית, עם ניסוחים שונים של הנושא ושל שם הרב,
ושל תתי־נושאים (למשל לחנוכה: נרות, הלל, על הניסים, מהדרין, יוון, מתתיהו, שמן, חינוך...).
חפש באתרי שיעורים ותורה (כמו yeshiva.org.il, האתר של הרב או של הישיבה שלו, kolhalashon, meirtv, אתרי ישיבות,
גיליונות שבת, עיתונים ומגזינים, ספרים סרוקים או PDF, יוטיוב, ספוטיפיי/פודקאסטים). פתח דפים כדי לוודא
שהם באמת של הרב ובאמת על הנושא, ומצא את הקישור הישיר לכל שיעור או מאמר (לא רק דף רשימה).
אם יש דף רשימה (למשל כל השיעורים של הרב על הנושא באתר מסוים) — היכנס אליו והוצא ממנו את הקישורים לשיעורים עצמם.

אל תכלול: דברים של רבנים אחרים, כתבות על הרב שלא מביאות את דבריו, דפי חנות בלי תוכן.

החזר רק JSON בצורה הזו (בלי שום טקסט אחר):
```json
{{
 "rav_full_name": "השם המלא של הרב ותפקידו",
 "about": "שתיים־שלוש שורות על הרב ועל סגנונו, כפי שעולה מהחיפוש",
 "keywords": ["מילות חיפוש קצרות לנושא, לחיפוש סרטונים: 5–10"],
 "sources": [
  {{"url": "https://...", "title": "שם השיעור/המאמר", "kind": "text|audio|video|pdf",
    "why": "במשפט: מה יש שם ולמה זה רלוונטי"}}
 ]
}}
```
מצא כמה שיותר מקורות (עד {max_sources}). העדף את הקישור הישיר לתוכן עצמו."""


def search_web(project, model=None):
    d = project.data
    from .compose import instructions_block
    prompt = SEARCH_PROMPT.format(rav=d["rav"], request=d["request"], kind=project.kind_name,
                                  instructions=instructions_block(project),
                                  max_sources=d["settings"]["max_sources"])
    log("מחפש באינטרנט (Claude) — זה יכול לקחת כמה דקות…")
    ans = ask(prompt, tools=("WebSearch", "WebFetch"), model=model, timeout=3600)
    data = json_from(ans)
    if isinstance(data, list):
        data = {"sources": data}
    for k in ("rav_full_name", "about"):
        if data.get(k):
            d[k] = data[k]
    d["keywords"] = [k for k in data.get("keywords", []) if isinstance(k, str)][:12]
    n = 0
    for s in data.get("sources", []):
        if isinstance(s, dict) and str(s.get("url", "")).startswith("http"):
            before = len(project.sources)
            project.add_source(s["url"], s.get("title", ""), s.get("kind", ""), s.get("why", ""), "חיפוש")
            n += len(project.sources) - before
    project.save()
    log(f"נמצאו {n} מקורות חדשים באינטרנט")
    return n


def surname(rav):
    """The words of the rabbi's name that a title must contain ("הרב זלמן מלמד" → ["מלמד"])."""
    words = [w for w in rav.replace('"', " ").split() if w not in ("הרב", "רבי", "הגאון", "ר'", "רב", "שליט\"א", "זצ\"ל", "זצל")]
    return words[-1:] if words else []


def search_youtube(project, per_query=15):
    """Videos of the rabbi on YouTube (via yt-dlp, without downloading)."""
    try:
        import yt_dlp
    except ImportError:
        log("yt-dlp לא מותקן — מדלג על חיפוש ביוטיוב")
        return 0
    d = project.data
    must = surname(d["rav"])
    queries = [f"{d['rav']} {d['request']}"] + [f"{d['rav']} {k}" for k in d.get("keywords", [])[:8]]
    n = 0
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": True, "noprogress": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        for q in queries:
            try:
                res = ydl.extract_info(f"ytsearch{per_query}:{q}", download=False)
            except Exception as e:
                log(f"חיפוש ביוטיוב נכשל ({q}): {e}")
                continue
            for e in res.get("entries") or []:
                title = e.get("title") or ""
                hay = title + " " + (e.get("channel") or "") + " " + (e.get("description") or "")
                if must and not all(w in hay for w in must):
                    continue
                url = e.get("url") or ""
                if not url.startswith("http"):
                    url = f"https://www.youtube.com/watch?v={e.get('id')}"
                mins = (e.get("duration") or 0) / 60
                why = f"יוטיוב · {e.get('channel') or ''}" + (f" · {mins:.0f} דקות" if mins else "")
                before = len(project.sources)
                project.add_source(url, title, "video", why, "יוטיוב")
                n += len(project.sources) - before
    project.save()
    log(f"נמצאו {n} סרטונים חדשים ביוטיוב")
    return n
