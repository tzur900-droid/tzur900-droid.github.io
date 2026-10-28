"""עימוד פירושים — run the program.

    python main.py                       open the window
    python main.py project.json out.pdf  lay out a project straight to PDF (no window)
    python main.py project.json out.pdf --cover   the book's cover to PDF (the spread, with bleed)
    python main.py --import OUT_DIR files…  convert Sefaria text files into project files
        (--comms onkelos,orhachaim chooses the commentaries; default onkelos,rashi,ramban)
"""
import os
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
    if sys.stdout is None:          # the exe without a console: printed messages go nowhere
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    log(f"התחלה · Python {sys.version.split()[0]} · {sys.platform} · {base_dir()}")
    app = QApplication(sys.argv)
    import PySide6
    log(f"Qt מוכן · PySide6 {PySide6.__version__}")
    app.setApplicationName("perush")
    app.setLayoutDirection(Qt.RightToLeft)
    from perush import theme
    theme.apply(app)
    from perush.textlayout import load_bundled_fonts, user_fonts_dir
    load_bundled_fonts(os.path.join(base_dir(), "fonts"))
    load_bundled_fonts(user_fonts_dir())
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

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if len(args) == 2:
        from perush.engine import layout_project
        from perush.model import load_project
        from perush.render import export_pdf
        project = load_project(args[0])
        if "--cover" in sys.argv:
            from perush.cover import export_cover, make_cover
            from perush.engine import Engine
            eng = Engine(project)
            pages = eng.run()
            c = make_cover(project, len(pages), eng.title_lines())
            export_cover(c, args[1], project["title"])
            w, h = c.size_mm()
            print(f"כריכה {w:.1f}×{h:.1f} מ\"מ (שדרה {c.spine / 72 * 25.4:.1f} מ\"מ, {len(pages)} עמודים) נשמרה ב־{args[1]}")
            return 0
        pages, warnings = layout_project(project)
        for w in warnings:
            print("⚠", w)
        export_pdf(pages, args[1], project["title"])
        print(f"{len(pages)} עמודים נשמרו ב־{args[1]}")
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
