"""ספר מהרב — run the program.

    python main.py                                   open the window
    python main.py --new "הרב זלמן מלמד" "חנוכה" [book|series|article|summary]
                                                     a new book, all the steps, without a window
    python main.py --selftest FOLDER                 check that everything loads (writes a small book there)
    python main.py --step STEP FOLDER                one step on an existing book's folder
        STEP: search | collect | read | outline | write | export | all
"""
import sys
import traceback

from rav.log import log


def on_error(kind, value, tb):
    text = "".join(traceback.format_exception(kind, value, tb))
    log("ERROR שגיאה:\n" + text)
    try:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "ספר מהרב", "אירעה שגיאה (נשמרה בקובץ rav.log):\n\n" + text[-1500:])
    except Exception:
        pass


STYLE = """
QMainWindow, QDialog { background: #f3eee2; }
QToolBar { background: #fbf8f0; border: none; border-bottom: 1px solid #e2d9c6; padding: 4px; }
QToolButton { padding: 5px 9px; border-radius: 8px; } QToolButton:hover { background: #efe6d3; }
QPushButton { background: #fbf8f0; border: 1px solid #e2d9c6; border-radius: 8px; padding: 6px 12px; }
QPushButton:hover { background: #efe6d3; } QPushButton:disabled { color: #b0a690; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QTableWidget {
  background: #fbf8f0; border: 1px solid #e2d9c6; border-radius: 8px; padding: 4px; }
QTabWidget::pane { border: 1px solid #e2d9c6; border-radius: 8px; }
"""


def cli(argv):
    from rav import pipeline
    from rav.project import Project
    if argv[0] == "--new":
        p = Project.new(argv[1], argv[2], argv[3] if len(argv) > 3 else "book")
        step = "all"
    else:
        step, p = argv[1], Project(argv[2])
    print("תיקייה:", p.folder, flush=True)
    fn = {"search": pipeline.step_search, "collect": pipeline.step_collect, "read": pipeline.step_read,
          "outline": lambda pr: pipeline.step_outline(pr, again=True), "write": pipeline.step_write,
          "export": pipeline.step_export, "all": pipeline.run_all}[step]
    res = fn(p)
    if isinstance(res, dict):
        for v in res.values():
            print(v)
    return 0


def main():
    sys.excepthook = on_error
    if sys.stdout is None:
        import os
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    from rav.version import VERSION
    log(f"התחלה · גרסה {VERSION} · Python {sys.version.split()[0]} · {sys.platform}")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    log("פותח את Qt")
    try:      # the browser inside the program must be loaded before the application is made
        import PySide6.QtWebEngineCore  # noqa: F401
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    except Exception as e:
        log(f"אין דפדפן מובנה: {e}")
    app = QApplication(sys.argv[:1])
    log("Qt מוכן")
    from rav import webview
    webview.start()
    app.setApplicationName("rav")
    app.setLayoutDirection(Qt.RightToLeft)
    if len(sys.argv) > 2 and sys.argv[1] == "--selftest":
        # the build checks that the parts load and a book comes out (Word and PDF)
        import os
        log("בדיקה: טוען רכיבים")
        from rav import collect, compose, export, search, transcribe  # noqa: F401
        import yt_dlp  # noqa: F401
        log("בדיקה: Word ו־PDF")
        md = "# בדיקה\n\n## פרק\n\nשלום **עולם** {מקור 1}\n"
        export.to_docx(md, os.path.join(sys.argv[2], "selftest.docx"))
        export.to_pdf(md, os.path.join(sys.argv[2], "selftest.pdf"))
        # the window, and a step run in the background that comes back to the window
        from PySide6.QtCore import QTimer
        from rav.app import MainWindow
        log("בדיקה: החלון")
        win = MainWindow()
        win.show()
        log("בדיקה: צעד ברקע")
        got = []
        win.run(lambda: 42, lambda res: (got.append(res), app.quit()))
        QTimer.singleShot(20000, app.quit)
        app.exec()
        if got != [42]:
            raise RuntimeError("a step in the background did not come back to the window")
        log("בדיקה: הכל עבד")
        # a recording is opened the way faster-whisper opens it (new PyAV versions broke that once)
        import wave
        wav = os.path.join(sys.argv[2], "selftest.wav")
        with wave.open(wav, "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\0\0" * 16000)
        transcribe._fix_av()
        from faster_whisper.audio import decode_audio
        n = len(decode_audio(wav))
        log(f"בדיקה: הקלטה נפתחה ({n} דגימות)")
        open(os.path.join(sys.argv[2], "selftest.txt"), "w").write("ok whisper=%s audio=%d" % (transcribe.available(), n))
        return 0
    if len(sys.argv) > 3 and sys.argv[1] == "--render":
        # a check of reading a page through the browser, from inside the program itself
        import threading
        from rav import collect
        res = {}

        def work():
            res["html"] = collect.render(sys.argv[2])
            app.quit()
        threading.Thread(target=work, daemon=True).start()
        app.exec()          # the browser inside the program works in this thread
        html = res.get("html", "")
        text = collect.text_of_html(html) if html else ""
        with open(sys.argv[3], "w", encoding="utf-8") as f:
            f.write(f"builtin={webview.available()} browser={collect.find_browser()} html={len(html)} "
                    f"text={len(text)}\n{text[:400]}\n")
        return 0
    if len(sys.argv) > 1 and sys.argv[1] in ("--new", "--step"):
        from rav import log as logmod
        logmod.listeners.append(lambda m: print(m, flush=True))
        return cli(sys.argv[1:])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    from rav.app import MainWindow
    win = MainWindow()
    win.show()
    log("WINDOW-SHOWN החלון מוצג")
    return app.exec()


def finish(code):
    """Leave without Python taking Qt's objects apart one by one, which can crash on the way out."""
    import os
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    if sys.platform == "win32":
        # os._exit still unloads Qt's libraries one by one, which crashed there (access violation)
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32")
        k.GetCurrentProcess.restype = wintypes.HANDLE      # a 64-bit handle, not a C int
        k.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
        k.TerminateProcess(k.GetCurrentProcess(), code or 0)
    os._exit(code or 0)


if __name__ == "__main__":
    try:
        finish(main())
    except SystemExit:
        raise
    except BaseException:
        on_error(*sys.exc_info())
        sys.exit(1)
