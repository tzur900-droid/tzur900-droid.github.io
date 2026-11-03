"""The steps one after the other. Every step skips what was already done, so after a stop
(or a usage limit of the Claude account) running again goes on from the same place."""
import os

from . import collect, compose, export, search
from .log import log


def model_of(project):
    return project.data["settings"].get("model") or None


def step_search(project, stop=lambda: False, youtube=True):
    search.search_web(project, model_of(project))
    if youtube and not stop():
        search.search_youtube(project)


def step_collect(project, stop=lambda: False, progress=log):
    done = 0
    while True:      # pages that list lessons add new sources: those are collected too
        todo = [s for s in project.sources if s["use"] and s["state"] in ("new",)]
        if not todo:
            return
        for s in todo:
            if stop():
                return
            done += 1
            left = sum(1 for x in project.sources if x["use"] and x["state"] == "new")
            progress(f"[{done}/{done + left - 1}] אוסף: {s['title'][:70]}")
            collect.collect_one(project, s, progress, stop)


def step_read(project, stop=lambda: False, progress=log):
    for _round in range(2):     # a poor transcript is transcribed again (accurately) and read again, once
        todo = [s for s in project.sources if s["use"] and s["state"] == "text"]
        for n, s in enumerate(todo, 1):
            if stop():
                return
            progress(f"[{n}/{len(todo)}] Claude קורא: {s['title'][:70]}")
            compose.extract_one(project, s, model_of(project))
        again = [s for s in project.sources if s["use"] and s.get("accurate") and s["state"] == "new"]
        if not again or stop():
            return
        progress(f"מתמלל שוב במודל המדויק {len(again)} הקלטות שהתמלול שלהן לא היה ברור…")
        for s in again:
            if stop():
                return
            collect.collect_one(project, s, progress, stop)


def step_outline(project, again=False):
    if again or not project.read("outline.md"):
        compose.make_outline(project, model_of(project))
    return compose.load_plan(project)


def step_write(project, stop=lambda: False, again=False):
    plan = compose.load_plan(project) or step_outline(project)
    for i in range(len(plan["chapters"])):
        if stop():
            return None
        if again or not project.read("chapters", f"{i + 1:02d}.md"):
            compose.write_chapter(project, plan, i, model_of(project))
    return step_export(project, plan)


def step_export(project, plan=None):
    from .project import safe_name
    plan = plan or compose.load_plan(project)
    md = compose.assemble(project, plan)
    name = safe_name(plan.get("title") or project.label(), 80)
    out = {"md": project.path("book.md")}
    try:
        export.to_docx(md, project.path(name + ".docx"))
        out["docx"] = project.path(name + ".docx")
    except Exception as e:
        log(f"Word לא נשמר: {e}")
    try:
        export.to_pdf(md, project.path(name + ".pdf"))
        out["pdf"] = project.path(name + ".pdf")
    except Exception as e:
        log(f"PDF לא נשמר: {e}")
    log("הספר מוכן: " + " · ".join(os.path.basename(p) for p in out.values()))
    return out


def run_all(project, stop=lambda: False):
    if not project.sources:
        step_search(project, stop)
    for step in (step_collect, step_read):
        if stop():
            return None
        step(project, stop)
    if stop():
        return None
    step_outline(project)
    return step_write(project, stop)
