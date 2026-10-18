"""עימוד פירושים — run the program.

    python main.py                       open the window
    python main.py project.json out.pdf  lay out a project straight to PDF (no window)
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
