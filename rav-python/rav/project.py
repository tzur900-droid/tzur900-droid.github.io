"""A book in the making: one folder with everything the program found and wrote, so that the
work can stop at any moment (closing the window, a usage limit) and go on from the same place.

    <folder>/project.json   the request and the list of sources (with the state of each)
    <folder>/sources/       the text of every source (a page, a PDF, a transcribed lesson)
    <folder>/media/         downloaded recordings (can be deleted after transcribing)
    <folder>/notes/         what Claude took from every source for the request
    <folder>/outline.md     the plan of the book (can be edited before writing)
    <folder>/chapters/      the chapters
    <folder>/<title>.docx / .pdf / .md   the book
"""
import json
import os
import re
import time

KINDS = {
    "book": "ספר",
    "series": "סדרת שיעורים",
    "article": "מאמר / קונטרס",
    "summary": "סיכום מקורות",
}


def documents_dir():
    home = os.path.expanduser("~")
    for name in ("Documents", "My Documents", "מסמכים"):
        p = os.path.join(home, name)
        if os.path.isdir(p):
            return p
    return home


def books_dir():
    p = os.path.join(documents_dir(), "ספר מהרב")
    os.makedirs(p, exist_ok=True)
    return p


def safe_name(s, n=60):
    s = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", s).strip(" .")
    return (s[:n].strip() or "ספר")


class Project:
    def __init__(self, folder):
        self.folder = folder
        self.data = {
            "rav": "", "request": "", "kind": "book", "created": time.strftime("%Y-%m-%d %H:%M"),
            "rav_full_name": "", "about": "", "keywords": [], "sources": [], "title": "",
            "settings": {"max_sources": 60, "auto_subs": False, "whisper_model": "ivrit-ai",
                         "model": "", "max_video_minutes": 120, "correct_transcripts": True},
        }
        p = os.path.join(folder, "project.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                saved = json.load(f)
            settings = dict(self.data["settings"], **saved.get("settings", {}))
            self.data.update(saved)
            self.data["settings"] = settings
        for sub in ("sources", "media", "notes", "chapters"):
            os.makedirs(os.path.join(folder, sub), exist_ok=True)

    @classmethod
    def new(cls, rav, request, kind):
        stamp = time.strftime("%Y-%m-%d %H%M")
        folder = os.path.join(books_dir(), safe_name(f"{rav} - {request}", 70) + " " + stamp)
        os.makedirs(folder, exist_ok=True)
        p = cls(folder)
        p.data.update(rav=rav, request=request, kind=kind)
        p.save()
        return p

    def save(self):
        tmp = os.path.join(self.folder, "project.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, os.path.join(self.folder, "project.json"))

    # -- the sources --
    @property
    def sources(self):
        return self.data["sources"]

    def add_source(self, url, title="", kind="", why="", origin="search"):
        """Add a source unless it is there already. Returns it (new or old)."""
        key = norm_url(url)
        for s in self.sources:
            if norm_url(s["url"]) == key:
                return s
        n = max([s["id"] for s in self.sources] + [0]) + 1
        s = {"id": n, "url": url, "title": title or url, "kind": kind or "", "why": why,
             "origin": origin, "use": True, "state": "new", "note": "", "chars": 0}
        self.sources.append(s)
        return s

    def path(self, *parts):
        return os.path.join(self.folder, *parts)

    def source_text_path(self, s):
        return self.path("sources", f"{s['id']:03d}.txt")

    def note_path(self, s):
        return self.path("notes", f"{s['id']:03d}.md")

    def read(self, *parts):
        p = self.path(*parts)
        if not os.path.isfile(p):
            return ""
        with open(p, encoding="utf-8") as f:
            return f.read()

    def write(self, text, *parts):
        p = self.path(*parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)

    @property
    def kind_name(self):
        return KINDS.get(self.data["kind"], self.data["kind"])

    def label(self):
        d = self.data
        return d.get("title") or f"{d['rav']} — {d['request']}"


def norm_url(u):
    u = u.strip()
    u = re.sub(r"^https?://(www\.|m\.)?", "", u)
    m = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]{11})", u)
    if m:
        return "yt:" + m.group(1)
    return u.rstrip("/").lower()
