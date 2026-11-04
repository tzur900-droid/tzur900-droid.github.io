"""Step 2: getting the text of every source — a web page, a PDF, a Word file, YouTube subtitles,
or a recording transcribed on this computer. Every source's text is kept in sources/NNN.txt."""
import os
import re
import urllib.parse

from .claude_cli import ClaudeError, ask
from .log import log
from . import transcribe as tr

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
MEDIA_EXT = (".mp3", ".m4a", ".wav", ".ogg", ".opus", ".aac", ".wma", ".flac", ".mp4", ".webm", ".mkv", ".mov", ".avi")
DOC_EXT = (".pdf", ".docx", ".txt", ".md", ".rtf", ".html", ".htm")
VIDEO_HOSTS = ("youtube.com", "youtu.be", "vimeo.com", "spotify.com", "soundcloud.com", "facebook.com",
               "rumble.com", "dailymotion.com", "podcasts.apple.com")


class Skip(Exception):
    """The source has nothing to use (the reason is the message)."""


class Listed(Skip):
    """A page that lists lessons: the lessons were added as sources of their own."""


LIST_WORDS = ("רשימ", "ארכיון", "תגית", "כל השיעורים", "עמוד ", "קטגורי", "סדרת")


def looks_like_list(s, url):
    hay = (s.get("title") or "") + " " + (s.get("why") or "")
    low = url.lower()
    return any(w in hay for w in LIST_WORDS) or any(w in low for w in ("/tags/", "filter", "catid=", "/rabbis/", "/category/", "/series/"))


def is_list_page(s, url, text, links):
    """A page that lists lessons (and is not a lesson itself): many lesson links, and most of
    its text is their titles. A lesson with a few related lessons under it is not a list."""
    if len(links) < 5:
        return False
    titles = sum(len(t) for _, t in links)
    mostly_links = titles >= 0.4 * max(1, len(text))
    return mostly_links or (looks_like_list({"title": s.get("title", "")}, url) and len(text) < 3000)


def lesson_links(html, base):
    """(url, title) of the links on a page that look like single lessons on the same site."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["nav", "header", "footer", "script", "style"]):
        t.decompose()
    h = host(base)
    out, seen = [], {base.rstrip("/")}
    for a in soup.find_all("a", href=True):
        u = urllib.parse.urljoin(base, a["href"]).split("#")[0]
        title = re.sub(r"\s+", " ", a.get_text(" ")).strip()
        if host(u) != h or len(title) < 8 or u.rstrip("/") in seen:
            continue
        if looks_like_list({"title": title}, u) or re.search(r"(login|register|share|print|mailto|javascript)", u, re.I):
            continue
        if h.endswith("yeshiva.org.il") and not re.search(r"/midrash/\d+/?$", urllib.parse.urlparse(u).path):
            continue        # on the yeshiva site a lesson is /midrash/<number>; the rest is the site's menus
        seen.add(u.rstrip("/"))
        out.append((u, title[:150]))
    return out


class ShortPage(Exception):
    """The program could not get the text of a page by itself (then Claude tries)."""


# ---------- pages built in the browser (JavaScript): opened in Edge/Chrome without a window ----------
def find_browser():
    import shutil
    cands = []
    for base in (os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                 os.environ.get("PROGRAMFILES", r"C:\Program Files"), os.environ.get("LOCALAPPDATA", "")):
        if base:
            cands += [os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                      os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")]
    for c in cands:
        if os.path.isfile(c):
            return c
    for name in ("msedge", "google-chrome", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    import glob
    found = glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome")
    return found[0] if found else None


# ways of reading a page that failed again and again on this computer are not tried any more
# (in this run of the program): each failed try costs a minute or two
_failures = {"builtin": 0, "edge": 0, "claude": 0}
GIVE_UP = 2


def _gave_up(way):
    return _failures[way] >= GIVE_UP


def _result(way, ok):
    if ok:
        _failures[way] = 0
        return
    _failures[way] += 1
    if _failures[way] == GIVE_UP:
        names = {"builtin": "הדפדפן המובנה", "edge": "Edge", "claude": "Claude (קריאת דפים)"}
        log(f"{names[way]} לא מצליח לפתוח דפים במחשב הזה — לא מנסה אותו יותר בהרצה הזו "
            "(הסרטונים וההקלטות ממשיכים כרגיל)")


def render(url, wait_ms=15000):
    """The page's HTML after its scripts ran, or "": first in the browser inside the program,
    then in Edge/Chrome without a window."""
    from . import webview
    if webview.available() and not _gave_up("builtin"):
        html = webview.render(url)
        ok = len(text_of_html(html)) >= 300
        _result("builtin", ok)
        if ok:
            log("הדף נפתח בדפדפן המובנה")
            return html
        log(f"הדפדפן המובנה החזיר {len(html)} תווים")
    if _gave_up("edge"):
        return ""
    html = render_external(url, wait_ms)
    _result("edge", len(text_of_html(html)) >= 300 if html else False)
    return html


def render_external(url, wait_ms=15000):
    """The page through Edge/Chrome without a window."""
    import shutil
    import subprocess
    import sys
    import tempfile
    exe = find_browser()
    if not exe:
        return ""
    base = [exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
            "--disable-extensions", "--mute-audio", "--disable-background-networking",
            "--disable-component-update", "--disable-sync", f"--virtual-time-budget={wait_ms}",
            f"--user-agent={UA}"]
    if sys.platform != "win32" and hasattr(os, "geteuid") and os.geteuid() == 0:
        base.insert(1, "--no-sandbox")
    flags = 0x08000000 if sys.platform == "win32" else 0
    # first with a profile of its own (an open Edge does not take the page over), then without
    for own in (True, False):
        profile = tempfile.mkdtemp(prefix="rav-browser-") if own else None
        cmd = base + ([f"--user-data-dir={profile}"] if own else []) + ["--dump-dom", url]
        try:
            # stdin from nowhere: a program without a console has no stdin to hand on
            r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=90,
                               creationflags=flags)
            html = r.stdout.decode("utf-8", "replace")
            if len(html) > 200:
                return html
            err = r.stderr.decode("utf-8", "replace").strip().splitlines()[-3:]
            log(f"הדפדפן ({os.path.basename(exe)}, {'פרופיל נפרד' if own else 'רגיל'}) החזיר {len(html)} תווים, "
                f"קוד {r.returncode}: {' / '.join(err)[:300]}")
        except Exception as e:
            log(f"הדפדפן לא פתח את הדף ({type(e).__name__})")
        finally:
            if profile:
                shutil.rmtree(profile, ignore_errors=True)
    return ""


def is_local(url):
    return not re.match(r"^https?://", url)


def host(url):
    return urllib.parse.urlparse(url).netloc.lower()


def is_recording_link(url, page_url=""):
    """Whether a copied link is a recording (a video site, or a media file), and not a web page
    (like the address of the lesson page itself, which is blocked like the page)."""
    low = url.lower().split("?")[0]
    if is_video_host(url) or low.endswith(MEDIA_EXT) or ".m3u8" in url.lower():
        return True
    if page_url and host(url) == host(page_url):
        return False
    return bool(re.search(r"(media|video|audio|stream|cdn|vod)", host(url)))


def is_video_host(url):
    h = host(url)
    return any(h == v or h.endswith("." + v) for v in VIDEO_HOSTS)


# ---------- text from files ----------
def fix_visual_hebrew(text):
    """Hebrew taken out of some PDFs comes out backwards (visual order): every word starting
    with a final letter (ם ן ץ ף ך) gives it away. Then every line is turned around."""
    words = re.findall(r"[א-ת]{2,}", text)
    if not words:
        return text
    starts = sum(1 for w in words if w[0] in "םןץףך")
    ends = sum(1 for w in words if w[-1] in "םןץףך")
    if starts > ends and starts > len(words) * 0.02:
        log("הטקסט ב־PDF הפוך (סדר חזותי) — הופך את השורות")
        return "\n".join(line[::-1] for line in text.split("\n"))
    return text


def text_of_pdf(path):
    from pypdf import PdfReader
    r = PdfReader(path)
    pages = []
    for p in r.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception:
            pages.append("")
    text = "\n\n".join(pages)
    if len(text.strip()) < 200 and len(r.pages) > 1:
        raise Skip("PDF סרוק (תמונות בלי טקסט) — אי אפשר לקרוא אותו כרגע")
    return fix_visual_hebrew(text)


def text_of_docx(path):
    import docx
    d = docx.Document(path)
    return "\n\n".join(p.text for p in d.paragraphs if p.text.strip())


def text_of_html(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "iframe"]):
        t.decompose()
    cands = soup.find_all(["article", "main"]) or []
    best = max(cands, key=lambda t: len(t.get_text()), default=None)
    body = best if best is not None and len(best.get_text()) > 800 else (soup.body or soup)
    lines, seen = [], set()
    for line in body.get_text("\n").split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if len(line) < 2:
            continue
        if len(line) < 60 and line in seen:     # menus and buttons repeat
            continue
        seen.add(line)
        lines.append(line)
    return "\n".join(lines)


def media_links(html, base):
    """Recordings on a page: <audio>/<video>/<source>, links to media files, YouTube frames."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for t in soup.find_all(["audio", "video", "source", "a", "iframe", "embed"]):
        u = t.get("src") or t.get("href") or t.get("data-src") or ""
        if not u:
            continue
        u = urllib.parse.urljoin(base, u)
        low = u.lower().split("?")[0]
        if low.endswith(MEDIA_EXT) or (t.name in ("iframe", "embed") and is_video_host(u)):
            if "youtube.com/embed/" in u:
                u = "https://www.youtube.com/watch?v=" + u.split("/embed/")[1][:11]
            if u not in found:
                found.append(u)
    for m in re.finditer(r"https?://[^\s\"'<>]+?\.(?:mp3|m4a)", html):   # players that hide the link in a script
        if m.group(0) not in found:
            found.append(m.group(0))
    return found


# ---------- subtitles and recordings ----------
def vtt_to_text(vtt):
    out, prev = [], ""
    for line in vtt.splitlines():
        line = line.strip()
        if not line or "-->" in line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line and line != prev:
            out.append(line)
            prev = line
    return " ".join(out)


def _sub_url(tracks):
    for lang in ("he", "iw", "he-IL", "iw-IL"):
        for f in tracks.get(lang) or []:
            if f.get("ext") == "vtt":
                return f["url"]
        if tracks.get(lang):
            return tracks[lang][0]["url"]
    return None


BOT_CHECK = ("confirm you", "not a bot", "Sign in to confirm")


def ytdl(opts, url, download=False):
    """yt-dlp, and when YouTube asks to confirm a person: wait a little and try again, then with
    the sign-in of the user's own browser (its cookies), as yt-dlp itself advises."""
    import time
    import yt_dlp
    tries = [None, None] + [(b,) for b in ("edge", "firefox", "chrome")]
    last = None
    for i, browser in enumerate(tries):
        o = dict(opts)
        if browser:
            o["cookiesfrombrowser"] = browser
        try:
            with yt_dlp.YoutubeDL(o) as ydl:
                info = ydl.extract_info(url, download=download)
                return info, (ydl.prepare_filename(info) if download and info else None)
        except Exception as e:
            last = e
            if not any(m in str(e) for m in BOT_CHECK):
                if browser:          # this browser's cookies could not be read: the next one
                    continue
                raise
            if i == 0:
                log("יוטיוב ביקש לוודא שמדובר באדם — מחכה דקה ומנסה שוב")
                time.sleep(60)
            elif browser is None:
                log("יוטיוב עדיין מבקש אימות — מנסה עם ההתחברות של הדפדפן שלכם")
            else:
                log(f"גם עם {browser[0]} יוטיוב ביקש אימות")
    raise last


def from_media_site(project, s, settings, progress, should_stop):
    """YouTube and the like: subtitles written by people if there are; otherwise the recording,
    transcribed here (or YouTube's automatic subtitles, if chosen in the settings)."""
    import yt_dlp
    import requests
    info, _ = ytdl({"quiet": True, "no_warnings": True, "skip_download": True, "noprogress": True}, s["url"])
    if info.get("_type") == "playlist":
        entries = [e for e in info.get("entries") or [] if e]
        raise Skip(f"זו רשימת השמעה של {len(entries)} סרטונים — הוסיפו את הסרטונים עצמם")
    mins = (info.get("duration") or 0) / 60
    if s.get("title") in ("", s["url"]):
        s["title"] = info.get("title") or s["url"]
    if mins > settings.get("max_video_minutes", 120):
        raise Skip(f"ארוך מדי ({mins:.0f} דקות; אפשר לשנות בהגדרות)")
    header = f"{info.get('title', '')}\n{info.get('channel') or info.get('uploader') or ''} · {info.get('upload_date', '')}\n\n"
    desc = (info.get("description") or "").strip()
    url = _sub_url(info.get("subtitles") or {})
    how, kind = "כתוביות שנכתבו בידי אדם", "human_subs"
    if not url and settings.get("auto_subs"):
        url = _sub_url(info.get("automatic_captions") or {})
        how, kind = "כתוביות אוטומטיות של יוטיוב", "auto_subs"
    if s.get("accurate"):       # the subtitles were not clear: transcribed here with the accurate model
        url = None
    if url:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
        r.encoding = "utf-8"
        text = vtt_to_text(r.text)
        if len(text) > 300:
            s["note"], s["how"] = how, kind
            return header + text + ("\n\n[תיאור הסרטון]\n" + desc if desc else "")
    return header + transcribe_download(project, s, s["url"], settings, progress, should_stop, info) + \
        ("\n\n[תיאור הסרטון]\n" + desc if desc else "")


def _prompt(project):
    d = project.data
    return tr.torah_prompt(d.get("rav_full_name") or d.get("rav", ""), d.get("request", ""))


CORRECT = """לפניך {part} תמלול אוטומטי של שיעור של {rav} בנושא "{topic}".
בתמלול יש שגיאות שמיעה: שמות של חכמים וספרים, ציטוטים מפסוקים, מגמרא וממדרש, ביטויים בארמית, ומילים שנשמעו לא נכון.
תקן רק שגיאות כאלה, לפי ההקשר ולפי הידיעה שלך במקורות. **אל תשנה את הניסוח של הרב, אל תקצר, אל תסכם ואל תוסיף.**
שמור על החלוקה לפסקאות. מילה שאינך בטוח בה — השאר כמו שהיא.
החזר רק את הטקסט המתוקן, בלי שום הערה.

<<<
{text}
>>>"""


def correct_transcript(project, s, text):
    """Claude goes over a transcript and fixes what was misheard (names, sources, Aramaic).
    The transcript as it came out is kept in sources/NNN.raw.txt."""
    d = project.data
    if not d["settings"].get("correct_transcripts", True) or len(text) < 300:
        return text
    project.write(text, "sources", f"{s['id']:03d}.raw.txt")
    parts, out = [], []
    cur = ""
    for para in text.split("\n\n"):          # parts of about 12,000 characters, at paragraph ends
        if cur and len(cur) + len(para) > 12000:
            parts.append(cur)
            cur = ""
        cur += (("\n\n" if cur else "") + para)
    if cur:
        parts.append(cur)
    log(f"Claude מתקן את התמלול ({len(text):,} תווים, {len(parts)} חלקים)…")
    try:
        for i, part in enumerate(parts):
            label = f"חלק {i + 1} מתוך {len(parts)} של" if len(parts) > 1 else ""
            fixed = ask(CORRECT.format(part=label, rav=d.get("rav_full_name") or d["rav"], topic=d["request"],
                                       text=part), model=d["settings"].get("model") or None, timeout=1200).strip()
            # a "correction" much shorter than the part is not a correction: the part stays as it was
            out.append(fixed if len(fixed) > 0.7 * len(part) else part)
    except ClaudeError as e:
        log(f"התיקון לא הושלם ({str(e).splitlines()[0]}) — נשאר התמלול כמו שיצא")
        return text
    s["note"] = (s.get("note") or "") + " · תוקן ע\"י Claude"
    return "\n\n".join(out)


def whisper_model(s, settings):
    """The transcription model for s: the accurate one when the first transcription was unclear."""
    return "ivrit-ai" if s.get("accurate") else settings.get("whisper_model", "ivrit-ai")


def transcribe_download(project, s, url, settings, progress, should_stop, info=None):
    if not tr.available():
        raise Skip("רכיב התמלול (faster-whisper) לא מותקן")
    path = download_audio(project, s, url)
    progress("מתמלל במחשב…")
    model = whisper_model(s, settings)
    text = tr.transcribe(path, model, progress, should_stop, prompt=_prompt(project))
    s["note"], s["how"] = "תומלל במחשב" + (" (במודל המדויק)" if s.get("accurate") else ""), "whisper:" + model
    return text


def download_audio(project, s, url):
    """The recording, in media/NNN.* (only the sound when there is a choice, no conversion)."""
    media = project.path("media")
    for f in os.listdir(media):
        if f.startswith(f"{s['id']:03d}.") and not f.endswith(".part"):
            return os.path.join(media, f)
    low = url.lower().split("?")[0]
    if low.endswith(MEDIA_EXT):
        import requests
        ext = os.path.splitext(low)[1]
        out = os.path.join(media, f"{s['id']:03d}{ext}")
        log(f"מוריד הקלטה: {url}")
        with requests.get(url, headers={"User-Agent": UA}, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(out + ".part", "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
        os.replace(out + ".part", out)
        return out
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "format": "bestaudio[ext=m4a]/bestaudio/best[height<=360]/best",
            "outtmpl": os.path.join(media, f"{s['id']:03d}.%(ext)s"), "postprocessors": []}
    log(f"מוריד הקלטה: {url}")
    _info, path = ytdl(opts, url, download=True)
    return path


# ---------- web pages ----------
def from_web(project, s, settings, progress, should_stop):
    import requests
    url = s["url"]
    if is_video_host(url):
        return from_media_site(project, s, settings, progress, should_stop)
    if url.lower().split("?")[0].endswith(MEDIA_EXT):
        return transcribe_download(project, s, url, settings, progress, should_stop)
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "he,en;q=0.8"}, timeout=60)
    r.raise_for_status()
    ctype = r.headers.get("content-type", "").lower()
    if "pdf" in ctype or url.lower().split("?")[0].endswith(".pdf"):
        p = project.path("media", f"{s['id']:03d}.pdf")
        with open(p, "wb") as f:
            f.write(r.content)
        return text_of_pdf(p)
    if ctype.startswith(("audio/", "video/")):
        return transcribe_download(project, s, url, settings, progress, should_stop)
    if "wordprocessingml" in ctype:
        p = project.path("media", f"{s['id']:03d}.docx")
        with open(p, "wb") as f:
            f.write(r.content)
        return text_of_docx(p)
    if r.encoding is None or r.encoding.lower() in ("iso-8859-1", "ascii"):
        r.encoding = r.apparent_encoding
    html = r.text
    text = text_of_html(html)
    if len(text) < 2500:
        # maybe the page is built by its scripts (like yeshiva.org.il): open it in a browser
        progress("פותח את הדף בדפדפן (בלי חלון)…")
        built = render(url)
        if built and len(text_of_html(built)) > len(text):
            html, text = built, text_of_html(built)
            log(f"הדף נקרא דרך הדפדפן ({len(text):,} תווים)")
    links = lesson_links(html, url)
    if is_list_page(s, url, text, links):
        n = 0
        for u, title in links[:40]:
            before = len(project.sources)
            project.add_source(u, title, "", f"מתוך הרשימה: {s['title']}", "רשימה")
            n += len(project.sources) - before
        if n:
            raise Listed(f"דף רשימה — נוספו ממנו {n} שיעורים לטבלה")
        log("דף שנראה כמו רשימה, אבל כל השיעורים שבו כבר בטבלה — הטקסט שלו נשמר")
    media = media_links(html, url)
    # a page with the lesson written out (often a transcript under the video) is read, not heard
    wants_media = len(text) < 2500
    if wants_media:
        log(f"בדף {len(text):,} תווים; הקלטות שנמצאו בדף: {len(media)}" + (f" ({media[0]})" if media else ""))
    if media and wants_media:
        m = media[0]
        progress(f"בדף יש הקלטה — {m}")
        try:
            if is_video_host(m):
                sub = dict(s, url=m)
                heard = from_media_site(project, sub, settings, progress, should_stop)
                s["note"], s["how"] = sub.get("note", ""), sub.get("how", "")
            else:
                heard = transcribe_download(project, s, m, settings, progress, should_stop)
            return text + "\n\n[השיעור המוקלט]\n" + heard
        except Skip as e:
            log(f"ההקלטה בדף לא תומללה: {e}")
    if len(text) < 300:
        raise ShortPage("אין בדף טקסט")
    return text


FAILED_MARK = "@@לא-נפתח@@"


STOP_WORDS = {"של", "על", "את", "עם", "הרב", "הרה\"ג", "שליט\"א", "זצ\"ל", "שיעור", "שיחה", "חלק", "מאת", "לפי", "גם",
              "או", "כי", "זה", "זו", "the", "and", "of"}


def _words(t):
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", t or "")        # (the category in brackets is not the title)
    return {w.strip("'\"׳״-") for w in re.findall(r"[\w'\"׳״-]+", t)
            if len(w.strip("'\"׳״-")) > 1 and w.strip("'\"׳״-") not in STOP_WORDS}


TITLES = {"הרב", "רבי", "הגאון", "ר'", "רב", "הרה\"ג", "שליט\"א", "זצ\"ל", "זצל", "הגר\"א"}


def rav_words(rav):
    """The words of the rabbi's name without titles ("הרב זלמן מלמד" → זלמן, מלמד)."""
    return [w for w in rav.replace("״", '"').split() if w not in TITLES and len(w) > 1]


def title_match(lesson, video, rav):
    """How well the video's title is the lesson's title (0..1); 0 when the rabbi's whole name
    (first name and family name) is not in the video."""
    name = rav_words(rav)
    if not name or not all(w in video for w in name):
        return 0.0
    a, b = _words(lesson) - set(name), _words(video) - set(name)

    def covered(x, y):
        return sum(1 for w in x if w in y or any(len(v) > 2 and (w in v or v in w) for v in y)) / len(x)
    score = covered(a, b) if len(a) >= 2 else 0.0
    if len(b) >= 3:                       # a shorter video title, all of it in the lesson's title
        score = max(score, covered(b, a))
    return score


def find_on_youtube(s, rav, need=0.7):
    """A YouTube video of the same lesson (same title, same rabbi), or None."""
    title = s.get("title") or ""
    if not title or title == s.get("url"):
        return None
    try:
        import yt_dlp
        q = re.sub(r"\([^)]*\)", " ", title).strip() + " " + " ".join(rav_words(rav))
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": True}) as ydl:
            res = ydl.extract_info(f"ytsearch8:{q}", download=False)
    except Exception as e:
        log(f"חיפוש השיעור ביוטיוב נכשל: {type(e).__name__}")
        return None
    best, score = None, 0.0
    for e in res.get("entries") or []:
        v = (e.get("title") or "") + " " + (e.get("channel") or "")
        sc = title_match(title, v, rav)
        if sc > score:
            best, score = e, sc
    if best is None or score < need:
        log(f"השיעור לא נמצא ביוטיוב ({title[:50]})")
        return None
    url = best.get("url") or ""
    if not url.startswith("http"):
        url = f"https://www.youtube.com/watch?v={best.get('id')}"
    log(f"השיעור נמצא ביוטיוב: {best.get('title')} ({score:.0%} מהשם)")
    return url


def via_claude(url, model=None):
    """When the program cannot read a page (blocked, built in the browser), Claude reads it and
    writes out everything in it in detail."""
    prompt = (f"פתח את הדף {url}. כתוב בפירוט מלא את כל מה שיש בתוכן העיקרי שלו (המאמר או השיעור): כל רעיון, "
              "הסבר, משל, סיפור, הלכה ומקור, לפי הסדר, ובלשון הכותב ככל האפשר, עם ציטוטים קצרים של המשפטים "
              "האופייניים. בלי תפריטים ופרסומות. אם בדף יש רק רשימה של שיעורים, כתוב את שמות השיעורים והקישורים "
              f"אליהם. אם הדף לא נפתח — ענה רק {FAILED_MARK}. החזר רק את התוכן.")
    text = ask(prompt, tools=("WebFetch",), model=model, timeout=300)
    if FAILED_MARK in text or len(text) < 300:
        raise Skip("הדף לא נפתח (גם לא דרך Claude)")
    return text


def collect_one(project, s, progress=lambda m: None, should_stop=None):
    """Get the text of source s into sources/NNN.txt. Sets s['state'] to 'text' or 'failed'."""
    settings = project.data["settings"]
    url = s["url"]
    try:
        if is_local(url):
            low = url.lower()
            if low.endswith(".pdf"):
                text = text_of_pdf(url)
            elif low.endswith(".docx"):
                text = text_of_docx(url)
            elif low.endswith(MEDIA_EXT):
                if not tr.available():
                    raise Skip("רכיב התמלול (faster-whisper) לא מותקן")
                progress("מתמלל במחשב…")
                model = whisper_model(s, settings)
                text = tr.transcribe(url, model, progress, should_stop, prompt=_prompt(project))
                s["note"], s["how"] = "תומלל במחשב", "whisper:" + model
            elif low.endswith((".html", ".htm")):
                with open(url, encoding="utf-8", errors="replace") as f:
                    text = text_of_html(f.read())
            else:
                with open(url, encoding="utf-8", errors="replace") as f:
                    text = f.read()
        elif s.get("media_url") and not is_recording_link(s["media_url"], url):
            m = s.pop("media_url")
            raise Skip(f"הועתק הקישור של הדף ({m}) ולא של הסרטון: בדף, קליק ימני על הסרטון עצמו ← "
                       "העתקת כתובת הסרטון")
        elif s.get("media_url"):
            # the link of the recording, copied by the user from the page in the browser
            m = s["media_url"]
            if is_video_host(m):
                sub = dict(s, url=m)
                text = from_media_site(project, sub, settings, progress, should_stop)
                s["note"], s["how"] = "הקלטה מהדף — " + (sub.get("note") or ""), sub.get("how", "")
            else:
                text = transcribe_download(project, s, m, settings, progress, should_stop)
        else:
            try:
                text = from_web(project, s, settings, progress, should_stop)
            except Skip:
                raise
            except InterruptedError:
                raise
            except Exception as e:
                if is_video_host(url) or url.lower().split("?")[0].endswith(MEDIA_EXT):
                    raise
                built = "" if isinstance(e, ShortPage) else render(url)   # (a short page was rendered already)
                if built and len(text_of_html(built)) >= 300:
                    log(f"הדף נקרא דרך הדפדפן ({e})")
                    text = text_of_html(built)
                    s["note"] = "נקרא דרך הדפדפן"
                elif (yt := find_on_youtube(s, project.data["rav"])):
                    # the page did not open: the same lesson on YouTube is heard instead
                    sub = dict(s, url=yt)
                    text = from_media_site(project, sub, settings, progress, should_stop)
                    s["note"] = f"הדף לא נפתח; השיעור נמצא ביוטיוב ({yt}) — {sub.get('note', '')}".strip(" —")
                    s["how"] = sub.get("how", "")
                else:
                    if _gave_up("claude"):
                        raise Skip("הדף לא נפתח במחשב הזה, והשיעור לא נמצא ביוטיוב "
                                   "(אפשר להעתיק את הטקסט מהדפדפן לקובץ ולהוסיף אותו)")
                    log(f"לא הצלחתי לקרוא את הדף בעצמי ({e}) — מבקש מ־Claude")
                    try:
                        text = via_claude(url, settings.get("model") or None)
                    except (Skip, ClaudeError):
                        _result("claude", False)
                        raise
                    _result("claude", True)
                    s["note"] = "נקרא דרך Claude"
        text = text.strip()
        if len(text) < 200:
            raise Skip("כמעט אין טקסט")
        if (s.get("how") or "").startswith("whisper") or s.get("how") == "auto_subs":
            text = correct_transcript(project, s, text)
        project.write(f"מקור: {s['title']}\n{url}\n\n" + text, "sources", f"{s['id']:03d}.txt")
        s["state"], s["chars"] = "text", len(text)
        log(f"✓ {s['title'][:60]} — {len(text):,} תווים")
    except InterruptedError:
        raise
    except Skip as e:
        _forget(project, s)
        s["state"], s["note"] = "failed", str(e)
        log(f"✗ {s['title'][:60]} — {e}")
    except ClaudeError as e:
        _forget(project, s)
        s["state"], s["note"] = "failed", str(e).split("\n")[0]
        log(f"✗ {s['title'][:60]} — {e}")
    except Exception as e:
        _forget(project, s)
        s["state"], s["note"] = "failed", f"{type(e).__name__}: {e}"[:300]
        log(f"✗ {s['title'][:60]} — {e}")
    project.save()


def _forget(project, s):
    """No text of an earlier try stays behind a source that failed now."""
    p = project.source_text_path(s)
    if os.path.isfile(p):
        os.remove(p)
