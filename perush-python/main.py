"""עימוד פירושים — run the program.

    python main.py                       open the window
    python main.py project.json out.pdf  lay out a project straight to PDF (no window)
    python main.py --import OUT_DIR files…  convert Sefaria text files into project files
        (--comms onkelos,orhachaim chooses the commentaries; default onkelos,rashi,ramban)
"""
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


def base_dir():
    # inside a PyInstaller exe the bundled files live in sys._MEIPASS
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("perush")
    app.setLayoutDirection(Qt.RightToLeft)
    from perush.textlayout import load_bundled_fonts
    load_bundled_fonts(os.path.join(base_dir(), "fonts"))

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
        pages, warnings = layout_project(project)
        for w in warnings:
            print("⚠", w)
        export_pdf(pages, args[1], project["title"])
        print(f"{len(pages)} עמודים נשמרו ב־{args[1]}")
        return 0

    from perush.app import MainWindow
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
