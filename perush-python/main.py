"""עימוד פירושים — run the program.

    python main.py                       open the window
    python main.py project.json out.pdf  lay out a project straight to PDF (no window)
        (--cover adds a front cover, a title page and a back cover, and writes beside it
        the whole cover for printing and the inside of the book for printing;
        --paper 70 sets the weight of the paper, which sets the width of the spine;
        --size B5 or --size 165x235 (mm) sets the page size and fits the fonts and margins to it;
        --cover-style 3 picks the style of the cover (1-10, see cover.STYLES);
        --cover-samples writes the front cover in every style beside the PDF;
        --no-front-verse leaves the verse off the front cover and the title page)
    python main.py --import OUT_DIR files…  convert Sefaria text files into project files
        (--comms onkelos,orhachaim chooses the commentaries; default onkelos,rashi,ramban)
"""
import os
import re
import sys
import time
import traceback

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


def base_dir():
    # inside a PyInstaller exe the bundled files live in sys._MEIPASS
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


LOG = None
T0 = time.time()


def log(msg):
    """A line in perush.log (beside the program, or in the temp folder): what the program
    did when, so that a problem on another computer can be found."""
    global LOG
    if LOG is None:
        for folder in (base_dir(), os.environ.get("TEMP", ""), os.path.expanduser("~")):
            try:
                LOG = open(os.path.join(folder, "perush.log"), "w", encoding="utf-8")
                break
            except OSError:
                continue
    if LOG:
        LOG.write(f"{time.time() - T0:7.1f}s  {msg}\n")
        LOG.flush()


def on_error(kind, value, tb):
    """An error the window would hide: write it down and show it."""
    text = "".join(traceback.format_exception(kind, value, tb))
    log("ERROR שגיאה:\n" + text)
    try:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "עימוד פירושים", "אירעה שגיאה (נשמרה בקובץ perush.log):\n\n" + text[-1500:])
    except Exception:
        pass


def main():
    sys.excepthook = on_error
    log(f"התחלה · Python {sys.version.split()[0]} · {sys.platform} · {base_dir()}")
    app = QApplication(sys.argv)
    import PySide6
    log(f"Qt מוכן · PySide6 {PySide6.__version__}")
    app.setApplicationName("perush")
    app.setLayoutDirection(Qt.RightToLeft)
    from perush.textlayout import load_bundled_fonts
    load_bundled_fonts(os.path.join(base_dir(), "fonts"))
    log("גופנים נטענו")

    if len(sys.argv) > 3 and sys.argv[1] == "--import":
        from perush.sefaria import DEFAULT_KINDS, convert
        rest = sys.argv[3:]
        kinds = DEFAULT_KINDS
        if "--comms" in rest:
            i = rest.index("--comms")
            kinds = tuple(rest[i + 1].split(","))
            del rest[i:i + 2]
        written, report = convert(rest, sys.argv[2], kinds)
        print("\n".join(report + written))
        return 0

    # the files: what isn't an option or the value of one
    args = [a for k, a in enumerate(sys.argv[1:], 1) if not a.startswith("-") and sys.argv[k - 1] not in ("--paper", "--size", "--cover-style")]
    if len(args) == 2:
        from perush.cover import book_info
        from perush.engine import layout_project
        from perush.model import load_project
        from perush.render import export_cover, export_pdf
        project = load_project(args[0])
        dedication = project.get("dedication")
        if "--cover" in sys.argv:
            # the cover's own title page comes instead, with the dedication at its foot
            project["titlePage"] = False
            project["dedication"] = ""
        if "--size" in sys.argv:
            from perush.model import PAGE_SIZES, fit_to_page
            size = sys.argv[sys.argv.index("--size") + 1]
            m = re.match(r"^(\d+(?:\.\d+)?)[x*×](\d+(?:\.\d+)?)$", size)
            if m:       # width x height in mm: 165x235
                project.update(pageSize="custom", pageW=float(m.group(1)), pageH=float(m.group(2)))
            elif size in PAGE_SIZES and size != "custom":
                project["pageSize"] = size
            else:
                print("גודל לא מוכר:", size, "— אפשר רוחב x גובה במ\"מ (165x235) או:",
                      ", ".join(k for k in PAGE_SIZES if k != "custom"))
                return 1
            fit_to_page(project)
        pages, warnings = layout_project(project)
        for w in warnings:
            print("⚠", w)
        cover = book_info(dict(project, dedication=dedication)) if "--cover" in sys.argv else None
        grams = int(sys.argv[sys.argv.index("--paper") + 1]) if "--paper" in sys.argv else 80
        from perush.cover import STYLES, style_of
        style = style_of(int(sys.argv[sys.argv.index("--cover-style") + 1])) if "--cover-style" in sys.argv else None
        if "--no-front-verse" in sys.argv:
            style = dict(style or STYLES[0], front_verse=False)
        if "--cover-samples" in sys.argv:
            from perush.render import export_cover_samples
            out = os.path.splitext(args[1])[0] + " - דוגמאות כריכה.pdf"
            export_cover_samples(out, pages[0].width, pages[0].height, book_info(project))
            print(f"{len(STYLES)} סגנונות כריכה נשמרו ב־{out}:",
                  " · ".join(f"{n} {s['name']}" for n, s in enumerate(STYLES, 1)))
        export_pdf(pages, args[1], project["title"], book=project.get("bookMode", False), cover=cover, style=style)
        print(f"{len(pages)} עמודים נשמרו ב־{args[1]}")
        if cover:
            base = os.path.splitext(args[1])[0]
            inside = export_pdf(pages, base + " - פנים הספר לדפוס.pdf", project["title"], book=True,
                                cover=cover, outer=False, style=style)
            print(f"פנים הספר בלי כריכה ({inside} עמודים) נשמר ב־{base} - פנים הספר לדפוס.pdf")
            out = base + " - כריכה לדפוס.pdf"
            spine = export_cover(out, pages[0].width, pages[0].height, inside, cover, grams, style)
            print(f"כריכה (קדמית, שדרה {spine:.1f} מ\"מ לנייר {grams} גרם, אחורית) נשמרה ב־{out}")
        return 0

    from perush.app import MainWindow
    win = MainWindow()
    log(f"החלון נבנה · פרויקט: {win.project.get('title') or ''} ({len(win.project.get('main', ''))} תווים)")
    win.show()
    log("WINDOW-SHOWN החלון מוצג")
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:
        on_error(*sys.exc_info())
        sys.exit(1)
