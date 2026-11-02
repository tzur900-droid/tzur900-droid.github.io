"""The window: the request at the top, the steps as buttons, the list of sources (to choose and
add), the plan of the book (to edit before writing), the book, and what the program is doing."""
import os
import threading

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
                               QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)

from . import claude_cli, compose, pipeline, transcribe
from .log import listeners, log
from .project import KINDS, Project, books_dir
from .version import VERSION

STATES = {"new": "ממתין", "text": "נאסף", "read": "נקרא ✓", "irrelevant": "לא שייך", "failed": "נכשל"}
KIND_NAMES = {"text": "טקסט", "audio": "שמע", "video": "וידאו", "pdf": "PDF", "file": "קובץ"}


class Settings(QDialog):
    def __init__(self, project, parent):
        super().__init__(parent)
        self.setWindowTitle("הגדרות")
        s = project.data["settings"]
        f = QFormLayout(self)
        self.max_sources = QSpinBox()
        self.max_sources.setRange(5, 300)
        self.max_sources.setValue(s["max_sources"])
        f.addRow("כמה מקורות לחפש (לכל היותר):", self.max_sources)
        self.minutes = QSpinBox()
        self.minutes.setRange(5, 600)
        self.minutes.setValue(s["max_video_minutes"])
        f.addRow("הקלטה ארוכה מ־(דקות) — לדלג:", self.minutes)
        self.auto = QCheckBox("כשאין כתוביות של אדם — להשתמש בכתוביות האוטומטיות של יוטיוב (מהיר, פחות מדויק)")
        self.auto.setChecked(s["auto_subs"])
        f.addRow(self.auto)
        self.whisper = QComboBox()
        for k, (_, desc) in transcribe.MODELS.items():
            self.whisper.addItem(desc, k)
        self.whisper.setCurrentIndex(max(0, self.whisper.findData(s["whisper_model"])))
        f.addRow("מודל התמלול במחשב:", self.whisper)
        self.model = QComboBox()
        for label, val in (("ברירת המחדל של החשבון", ""), ("Opus — הכי טוב", "opus"),
                           ("Sonnet — מהיר וחסכוני יותר", "sonnet")):
            self.model.addItem(label, val)
        self.model.setCurrentIndex(max(0, self.model.findData(s.get("model", ""))))
        f.addRow("מודל של Claude:", self.model)
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        f.addRow(b)
        self.project = project

    def accept(self):
        s = self.project.data["settings"]
        s.update(max_sources=self.max_sources.value(), max_video_minutes=self.minutes.value(),
                 auto_subs=self.auto.isChecked(), whisper_model=self.whisper.currentData(),
                 model=self.model.currentData())
        self.project.save()
        super().accept()


class MainWindow(QMainWindow):
    log_line = Signal(str)
    step_done = Signal(object, str)     # result, error — sent from the background, received in the window

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"ספר מהרב · {VERSION}")
        self.resize(1150, 780)
        self.project = None
        self.thread = None
        self.stop_flag = threading.Event()
        self._build()
        self.log_line.connect(self._append_log)
        self.step_done.connect(self._finished)
        listeners.append(self.log_line.emit)
        self._open_last()

    # ---------- building ----------
    def _build(self):
        tb = self.addToolBar("main")
        tb.setMovable(False)
        for text, fn in (("חדש", self.new_project), ("פתיחה…", self.open_project),
                         ("תיקיית הספר", self.open_folder), ("הגדרות", self.settings),
                         ("בדיקת Claude", self.check_claude)):
            a = QAction(text, self)
            a.triggered.connect(fn)
            tb.addAction(a)

        w = QWidget()
        v = QVBoxLayout(w)
        top = QFormLayout()
        self.rav = QLineEdit()
        self.rav.setPlaceholderText("למשל: הרב זלמן מלמד")
        self.request = QLineEdit()
        self.request.setPlaceholderText("למשל: ספר על חנוכה — נרות, ההלל, הנס, מלחמת החשמונאים ביוונים")
        self.kind = QComboBox()
        for k, name in KINDS.items():
            self.kind.addItem(name, k)
        row = QHBoxLayout()
        row.addWidget(self.rav, 2)
        row.addWidget(QLabel("סוג:"))
        row.addWidget(self.kind, 1)
        top.addRow("שם הרב:", row)
        top.addRow("מה רוצים:", self.request)
        v.addLayout(top)

        steps = QHBoxLayout()
        self.buttons = []
        for text, fn in (("1. חיפוש מקורות", self.do_search), ("2. איסוף ותמלול", self.do_collect),
                         ("3. קריאה", self.do_read), ("4. תכנון הספר", self.do_outline),
                         ("5. כתיבה", self.do_write), ("▶ הכל ברצף", self.do_all)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            steps.addWidget(b)
            self.buttons.append(b)
        self.stop_btn = QPushButton("■ עצירה")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        steps.addWidget(self.stop_btn)
        v.addLayout(steps)
        self.status = QLabel("")
        v.addWidget(self.status)

        split = QSplitter(Qt.Vertical)
        self.tabs = QTabWidget()
        # sources
        sw = QWidget()
        sv = QVBoxLayout(sw)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["", "#", "שם", "סוג", "מצב", "קישור / הערה"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemChanged.connect(self._toggle)
        self.table.cellDoubleClicked.connect(self._open_source)
        sv.addWidget(self.table)
        srow = QHBoxLayout()
        for text, fn in (("הוספת קישור…", self.add_url), ("הוספת קבצים מהמחשב…", self.add_files),
                         ("סימון הכל", lambda: self._mark(True)), ("ביטול הכל", lambda: self._mark(False)),
                         ("לנסות שוב את מה שנכשל", self.retry_failed), ("הצגת הטקסט שנאסף", self.show_text)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            srow.addWidget(b)
        sv.addLayout(srow)
        self.tabs.addTab(sw, "מקורות")
        # outline
        ow = QWidget()
        ov = QVBoxLayout(ow)
        ov.addWidget(QLabel("התכנית של הספר וסגנון הרב. אפשר לשנות כאן הכל (סדר הפרקים, כותרות, מספרי המקורות) "
                            "לפני הכתיבה — השינויים נשמרים כשלוחצים 'שמירת התכנית' או 'כתיבה'."))
        self.outline = QPlainTextEdit()
        ov.addWidget(self.outline)
        orow = QHBoxLayout()
        for text, fn in (("שמירת התכנית", self.save_outline), ("תכנון מחדש", self.redo_outline),
                         ("כתיבת פרק אחד מחדש…", self.rewrite_chapter)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            orow.addWidget(b)
        orow.addStretch()
        ov.addLayout(orow)
        self.tabs.addTab(ow, "תכנית הספר")
        # book
        bw = QWidget()
        bv = QVBoxLayout(bw)
        self.book = QPlainTextEdit()
        self.book.setReadOnly(True)
        bv.addWidget(self.book)
        brow = QHBoxLayout()
        for text, fn in (("פתיחת Word", lambda: self._open_out(".docx")), ("פתיחת PDF", lambda: self._open_out(".pdf")),
                         ("ייצוא מחדש (אחרי עריכת הפרקים בתיקייה)", self.do_export)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            brow.addWidget(b)
        brow.addStretch()
        bv.addLayout(brow)
        self.tabs.addTab(bw, "הספר")
        split.addWidget(self.tabs)
        self.logbox = QPlainTextEdit()
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumBlockCount(3000)
        split.addWidget(self.logbox)
        split.setSizes([560, 180])
        v.addWidget(split, 1)
        self.setCentralWidget(w)

    # ---------- the project ----------
    def _last_file(self):
        return os.path.join(books_dir(), ".last")

    def _open_last(self):
        try:
            folder = open(self._last_file(), encoding="utf-8").read().strip()
            if os.path.isfile(os.path.join(folder, "project.json")):
                self.load(Project(folder))
        except OSError:
            pass

    def load(self, project):
        self.project = project
        d = project.data
        self.rav.setText(d["rav"])
        self.request.setText(d["request"])
        self.kind.setCurrentIndex(max(0, self.kind.findData(d["kind"])))
        self.fill_table()
        self.outline.setPlainText(project.read("outline.md"))
        self.book.setPlainText(project.read("book.md"))
        self.setWindowTitle(f"ספר מהרב · {project.label()}")
        try:
            with open(self._last_file(), "w", encoding="utf-8") as f:
                f.write(project.folder)
        except OSError:
            pass

    def ensure_project(self):
        """The open project, or a new one from the fields. False when the fields are empty."""
        rav, req = self.rav.text().strip(), self.request.text().strip()
        if not rav or not req:
            QMessageBox.information(self, "ספר מהרב", "כתבו את שם הרב ומה רוצים.")
            return False
        kind = self.kind.currentData()
        p = self.project
        if p is None or (p.data["rav"], p.data["request"]) != (rav, req):
            if p is not None and p.sources:
                r = QMessageBox.question(self, "ספר מהרב", "השם או הבקשה השתנו. להתחיל ספר חדש?\n"
                                         "(לא — ממשיכים את הספר הפתוח עם הנוסח החדש)")
                if r == QMessageBox.Yes:
                    p = None
            if p is None:
                self.load(Project.new(rav, req, kind))
                return True
            p.data.update(rav=rav, request=req)
        p.data["kind"] = kind
        p.save()
        return True

    def new_project(self):
        self.project = None
        for w in (self.rav, self.request):
            w.clear()
        self.table.setRowCount(0)
        self.outline.clear()
        self.book.clear()
        self.setWindowTitle(f"ספר מהרב · {VERSION}")

    def open_project(self):
        folder = QFileDialog.getExistingDirectory(self, "תיקייה של ספר", books_dir())
        if folder and os.path.isfile(os.path.join(folder, "project.json")):
            self.load(Project(folder))
        elif folder:
            QMessageBox.warning(self, "ספר מהרב", "בתיקייה הזו אין ספר (project.json).")

    def open_folder(self):
        if self.project:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.project.folder))

    def settings(self):
        if self.project or self.ensure_project():
            Settings(self.project, self).exec()

    # ---------- the table ----------
    def fill_table(self):
        t = self.table
        t.blockSignals(True)
        t.setRowCount(0)
        for s in self.project.sources if self.project else []:
            r = t.rowCount()
            t.insertRow(r)
            c = QTableWidgetItem()
            c.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            c.setCheckState(Qt.Checked if s["use"] else Qt.Unchecked)
            c.setData(Qt.UserRole, s["id"])
            t.setItem(r, 0, c)
            t.setItem(r, 1, QTableWidgetItem(str(s["id"])))
            t.setItem(r, 2, QTableWidgetItem(s["title"]))
            t.setItem(r, 3, QTableWidgetItem(KIND_NAMES.get(s.get("kind"), s.get("kind") or "")))
            st = STATES.get(s["state"], s["state"])
            if s.get("chars"):
                st += f" · {s['chars'] // 1000}K" if s["chars"] >= 1000 else f" · {s['chars']}"
            t.setItem(r, 4, QTableWidgetItem(st))
            info = s["url"] + (f"   — {s['note']}" if s.get("note") else (f"   — {s['why']}" if s.get("why") else ""))
            it = QTableWidgetItem(info)
            it.setToolTip(info)
            t.setItem(r, 5, it)
        t.resizeColumnsToContents()
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        t.blockSignals(False)
        if self.project:
            ss = self.project.sources
            cnt = lambda st: sum(1 for s in ss if s["state"] == st)
            self.status.setText(f"{len(ss)} מקורות · {cnt('text') + cnt('read')} נאספו · {cnt('read')} נקראו ונמצאו "
                                f"שייכים · {cnt('failed')} נכשלו · {cnt('irrelevant')} לא שייכים   |   {self.project.folder}")

    def _source_at(self, row):
        it = self.table.item(row, 0)
        sid = it.data(Qt.UserRole) if it else None
        return next((s for s in self.project.sources if s["id"] == sid), None)

    def _toggle(self, item):
        if item.column() == 0 and self.project:
            s = self._source_at(item.row())
            if s:
                s["use"] = item.checkState() == Qt.Checked
                self.project.save()

    def _mark(self, on):
        if self.project:
            for s in self.project.sources:
                s["use"] = on
            self.project.save()
            self.fill_table()

    def _open_source(self, row, col):
        s = self._source_at(row)
        if s:
            u = s["url"]
            QDesktopServices.openUrl(QUrl.fromLocalFile(u) if collect_is_local(u) else QUrl(u))

    def add_url(self):
        if not (self.project or self.ensure_project()):
            return
        text, ok = QInputDialog.getMultiLineText(self, "הוספת קישורים",
                                                 "קישור בכל שורה (דף, PDF, יוטיוב, קובץ שמע, רשימת השמעה של יוטיוב):")
        if ok:
            for u in text.split():
                if u.startswith("http"):
                    self.project.add_source(u, "", "", "נוסף ידנית", "ידני")
            self.project.save()
            self.fill_table()

    def add_files(self):
        if not (self.project or self.ensure_project()):
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "קבצים של הרב", "",
            "כתבים והקלטות (*.pdf *.docx *.txt *.md *.html *.mp3 *.m4a *.wav *.ogg *.opus *.mp4 *.webm *.mkv *.mov);;הכל (*)")
        for f in files:
            self.project.add_source(f, os.path.basename(f), "file", "קובץ מהמחשב", "קובץ")
        self.project.save()
        self.fill_table()

    def retry_failed(self):
        if self.project:
            for s in self.project.sources:
                if s["state"] == "failed":
                    s["state"], s["note"] = "new", ""
            self.project.save()
            self.fill_table()

    def show_text(self):
        rows = {i.row() for i in self.table.selectedItems()}
        if not rows or not self.project:
            return
        s = self._source_at(min(rows))
        text = self.project.read("sources", "%03d.txt" % s["id"]) or "(עוד לא נאסף טקסט)"
        note = self.project.read("notes", "%03d.md" % s["id"])
        d = QDialog(self)
        d.setWindowTitle(s["title"])
        d.resize(900, 650)
        lay = QVBoxLayout(d)
        tabs = QTabWidget()
        for name, body in (("הטקסט שנאסף", text), ("מה ש־Claude לקח ממנו", note or "(עוד לא נקרא)")):
            e = QPlainTextEdit(body)
            e.setReadOnly(True)
            tabs.addTab(e, name)
        lay.addWidget(tabs)
        d.exec()

    # ---------- running ----------
    def _append_log(self, line):
        self.logbox.appendPlainText(line)

    def run(self, fn, after=None):
        """fn in the background (the window stays alive); then after(result) in the window."""
        if self.thread is not None:
            return
        self.stop_flag.clear()
        for b in self.buttons:
            b.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._after = after
        self.thread = threading.Thread(target=self._work, args=(fn,), daemon=True)
        self.thread.start()

    def _work(self, fn):
        try:
            res, err = fn(), ""
        except InterruptedError:
            res, err = None, ""
        except Exception as e:
            import traceback
            log("ERROR " + traceback.format_exc())
            res, err = None, str(e) or type(e).__name__
        self.step_done.emit(res, err)

    def _finished(self, res, err):
        after, self._after = self._after, None
        self.thread = None
        for b in self.buttons:
            b.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if self.project:
            self.fill_table()
            self.outline.setPlainText(self.project.read("outline.md"))
            self.book.setPlainText(self.project.read("book.md"))
        if err:
            QMessageBox.warning(self, "ספר מהרב", err[:2500])
        elif after:
            after(res)

    def stop(self):
        self.stop_flag.set()
        log("עוצר אחרי הצעד הנוכחי…")

    def stopped(self):
        if self.stop_flag.is_set():
            raise InterruptedError
        return False

    def do_search(self):
        if self.ensure_project():
            p = self.project
            self.run(lambda: pipeline.step_search(p, self.stopped),
                     lambda _: (self.tabs.setCurrentIndex(0), log(
                         "עברו על רשימת המקורות: הורידו סימון ממה שלא מתאים, הוסיפו קישורים או קבצים, ואז 'איסוף ותמלול'.")))

    def do_collect(self):
        if self.ensure_project():
            p = self.project
            self.run(lambda: pipeline.step_collect(p, self.stopped))

    def do_read(self):
        if self.ensure_project():
            p = self.project
            self.run(lambda: pipeline.step_read(p, self.stopped))

    def do_outline(self):
        if self.ensure_project():
            p = self.project
            self.run(lambda: pipeline.step_outline(p, again=True), lambda _: self.tabs.setCurrentIndex(1))

    def redo_outline(self):
        self.do_outline()

    def save_outline(self):
        if self.project and self.outline.toPlainText().strip():
            self.project.write(self.outline.toPlainText(), "outline.md")
            plan = compose.md_to_outline(self.outline.toPlainText())
            log(f"התכנית נשמרה: {len(plan['chapters'])} פרקים")

    def do_write(self):
        if self.ensure_project():
            self.save_outline()
            p = self.project
            self.run(lambda: pipeline.step_write(p, self.stopped), self._book_ready)

    def rewrite_chapter(self):
        if not self.project:
            return
        self.save_outline()
        plan = compose.load_plan(self.project)
        if not plan or not plan["chapters"]:
            return
        names = [f"{i + 1}. {c['title']}" for i, c in enumerate(plan["chapters"])]
        name, ok = QInputDialog.getItem(self, "כתיבה מחדש", "איזה פרק?", names, 0, False)
        if ok:
            i = names.index(name)
            p = self.project
            self.run(lambda: (compose.write_chapter(p, plan, i, pipeline.model_of(p)),
                              pipeline.step_export(p, plan))[1], self._book_ready)

    def do_export(self):
        if self.project and self.project.read("outline.md"):
            p = self.project
            self.run(lambda: pipeline.step_export(p), self._book_ready)

    def do_all(self):
        if self.ensure_project():
            p = self.project
            self.save_outline() if self.outline.toPlainText().strip() else None
            self.run(lambda: pipeline.run_all(p, self.stopped), self._book_ready)

    def _book_ready(self, out):
        if out:
            self.tabs.setCurrentIndex(2)
            QMessageBox.information(self, "ספר מהרב", "הספר מוכן!\n\n" + "\n".join(out.values()))

    def _open_out(self, ext):
        if not self.project:
            return
        for f in os.listdir(self.project.folder):
            if f.endswith(ext):
                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.join(self.project.folder, f)))
                return

    def check_claude(self):
        self.run(lambda: claude_cli.status(),
                 lambda res: QMessageBox.information(self, "Claude", res[1]) if res[0]
                 else QMessageBox.warning(self, "Claude", res[1]))


def collect_is_local(u):
    from .collect import is_local
    return is_local(u)
