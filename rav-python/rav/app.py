"""The window: the request at the top, the steps as buttons, the list of sources (to choose and
add), the plan of the book (to edit before writing), the book, and what the program is doing."""
import os
import re
import threading

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
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
        self.correct = QCheckBox("Claude מתקן כל תמלול (שמות, מקורות, ארמית) — מדויק יותר, משתמש יותר במגבלת החשבון")
        self.correct.setChecked(s.get("correct_transcripts", True))
        f.addRow(self.correct)
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
                 correct_transcripts=self.correct.isChecked(),
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
        self.job = None
        self.stop_flag = threading.Event()
        self._build()
        self.log_line.connect(self._append_log)
        self.step_done.connect(self._finished)
        listeners.append(self.log_line.emit)
        self._open_last()
        self._check_update_quietly()

    # ---------- building ----------
    def _build(self):
        tb = self.addToolBar("main")
        tb.setMovable(False)
        for text, fn in (("חדש", self.new_project), ("שיחות על חומש…", self.new_parasha_book),
                         ("פתיחה…", self.open_project),
                         ("תיקיית הספר", self.open_folder), ("מה אני רוצה בספר…", self.edit_instructions),
                         ("הגדרות", self.settings),
                         ("חיבור ל־Claude…", self.connect_claude), ("בדיקת Claude", self.check_claude),
                         ("עדכון תוכנה", self.update_program)):
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
        for text, fn in (("חיפוש ביוטיוב…", self.search_youtube_more), ("הוספת קישור…", self.add_url), ("הוספת קבצים מהמחשב…", self.add_files),
                         ("סימון הכל", lambda: self._mark(True)), ("ביטול הכל", lambda: self._mark(False)),
                         ("לנסות שוב את מה שנכשל", self.retry_failed), ("קריאה דרך הדפדפן שלי…", self.read_in_my_browser),
                         ("איסוף מחדש לנבחרים", self.recollect_selected),
                         ("ייבוא תמלול לשורה…", self.import_transcript), ("תיקיית ההקלטות", self.open_media),
                         ("הצגת הטקסט שנאסף", self.show_text)):
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
        ov.addWidget(QLabel("הערות לתכנית (למשל: לאחד את פרקים 3 ו־4, להוסיף פרק על המהדרין, להקדים את ההלכות):"))
        self.comments = QPlainTextEdit()
        self.comments.setMaximumHeight(90)
        ov.addWidget(self.comments)
        orow = QHBoxLayout()
        for text, fn in (("תיקון התכנית לפי ההערות", self.revise_outline), ("שמירת התכנית", self.save_outline),
                         ("תכנון מחדש", self.redo_outline), ("כתיבת פרק אחד מחדש…", self.rewrite_chapter)):
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
        self.setWindowTitle(f"ספר מהרב {VERSION} · {project.label()}")
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
                self.ask_instructions(first=True)
                return True
            p.data.update(rav=rav, request=req)
        p.data["kind"] = kind
        p.save()
        return True

    def new_parasha_book(self):
        """A book of talks on a chumash, in one go: the rabbi, the book, how many videos and talks."""
        d = ParashaDialog(self)
        if d.exec() != QDialog.Accepted:
            return
        rav, book, videos, talks, fast = d.values()
        p = Project.new(rav, f"שיחות על ספר {book}", "parasha")
        p.data["parasha_mode"] = {"book": book, "videos": videos, "talks": talks}
        p.data["settings"]["auto_subs"] = fast
        p.save()
        self.load(p)
        if not self.ask_instructions(first=True):
            return
        log(f"מתחיל: {videos} שיחות ביוטיוב לכל פרשה בספר {book}, ועד {talks} שיחות לכל פרשה בספר")
        self.run(lambda: pipeline.run_all(p, self.stopped), self._book_ready)

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
            c.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
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

    def search_youtube_more(self):
        """More searches on YouTube, written by the user (one per line); the rabbi's name is added."""
        if not (self.project or self.ensure_project()):
            return
        from . import search
        p = self.project
        start = "\n".join(q[len(p.data["rav"]):].strip() for q in search.youtube_queries(p))
        text, ok = QInputDialog.getMultiLineText(
            self, "חיפוש ביוטיוב",
            f"חיפוש בכל שורה (שם הרב, {p.data['rav']}, נוסף לבד). למשל: שיחת מוצאי שבת וישב", start)
        if not ok:
            return
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines:
            qs = [f"{p.data['rav']} {ln}" for ln in lines]
            self.run(lambda: search.search_youtube(p, queries=qs),
                     lambda n: log(f"נוספו {n} סרטונים. עברו על הטבלה ואז '2. איסוף ותמלול'."))

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

    def open_media(self):
        """The folder of the downloaded recordings (to transcribe them elsewhere, like אלף בוט)."""
        if self.project:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.project.path("media")))
            log("בתיקייה ההקלטות שהורדו, לפי מספר המקור (למשל 012.m4a = מקור 12)")

    def import_transcript(self):
        """A transcript made elsewhere (אלף בוט, Word or text) becomes the text of the chosen row."""
        if not self.project:
            return
        rows = self._chosen_rows()
        s = self._source_at(rows[0]) if rows else None
        if s is None:
            QMessageBox.information(self, "ספר מהרב", "בחרו קודם בטבלה את השורה של השיעור.")
            return
        f, _ = QFileDialog.getOpenFileName(self, f"התמלול של: {s['title']}", "",
                                           "תמלול (*.docx *.txt *.srt *.vtt *.pdf);;הכל (*)")
        if not f:
            return
        from . import collect
        low = f.lower()
        try:
            if low.endswith(".docx"):
                text = collect.text_of_docx(f)
            elif low.endswith(".pdf"):
                text = collect.text_of_pdf(f)
            else:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
                if low.endswith((".srt", ".vtt")):
                    text = collect.vtt_to_text(text)
        except Exception as e:
            QMessageBox.warning(self, "ספר מהרב", f"לא הצלחתי לקרוא את הקובץ: {e}")
            return
        text = text.strip()
        if len(text) < 100:
            QMessageBox.warning(self, "ספר מהרב", "בקובץ כמעט אין טקסט.")
            return
        p = self.project
        if os.path.isfile(p.note_path(s)):
            os.remove(p.note_path(s))
        p.write(f"מקור: {s['title']}\n{s['url']}\n\n" + text, "sources", "%03d.txt" % s["id"])
        s.update(state="text", chars=len(text), note="תומלל מחוץ לתוכנה (קובץ שיובא)", how="imported",
                 accurate=True, use=True)
        s.pop("media_url", None)
        p.save()
        self.fill_table()
        log(f"✓ {s['title'][:60]} — יובא תמלול ({len(text):,} תווים). לחצו '3. קריאה'.")

    def recollect_selected(self):
        """The chosen rows back to waiting: what was collected from them (text, recording link,
        what Claude took from them) is removed, and 'איסוף ותמלול' gets them again."""
        if not self.project:
            return
        chosen = [x for x in (self._source_at(r) for r in self._chosen_rows()) if x]
        if not chosen:
            QMessageBox.information(self, "ספר מהרב", "בחרו בטבלה את השורות (Ctrl+לחיצה לכמה שורות), ואז לחצו שוב.")
            return
        if QMessageBox.question(self, "ספר מהרב", f"להחזיר {len(chosen)} מקורות לממתין ולמחוק את מה שנאסף מהם?") \
                != QMessageBox.Yes:
            return
        for x in chosen:
            for path in (self.project.source_text_path(x), self.project.note_path(x)):
                if os.path.isfile(path):
                    os.remove(path)
            x.pop("media_url", None)
            x.update(state="new", chars=0, note="", use=True)
        self.project.save()
        self.fill_table()
        log(f"{len(chosen)} מקורות חזרו לממתין — לחצו '2. איסוף ותמלול'")

    def read_in_my_browser(self):
        """The web pages that failed, one after the other, in the user's own browser."""
        if not self.project:
            return
        from .collect import MEDIA_EXT, is_local, is_video_host
        chosen = [x for x in (self._source_at(r) for r in self._chosen_rows()) if x]
        web = lambda s: s and not is_local(s["url"]) and not is_video_host(s["url"]) \
            and not s["url"].lower().split("?")[0].endswith(MEDIA_EXT)
        if chosen:      # the rows chosen in the table, whatever their state
            todo = [s for s in chosen if web(s)]
        else:           # otherwise every page that failed or still waits
            todo = [s for s in self.project.sources if web(s) and s["use"] and s["state"] in ("failed", "new")]
        if not todo:
            QMessageBox.information(self, "ספר מהרב", "אין דפים שנכשלו או שממתינים. (אפשר גם לבחור בטבלה "
                                    "שורות — אחת או כמה — ואז ללחוץ: הן ייפתחו לפי הסדר.)")
            return
        self._copy = CopyDialog(self, todo)
        self._copy.show()

    def _chosen_rows(self):
        """The rows chosen in the table (also the row of the cell that has the focus)."""
        rows = {i.row() for i in self.table.selectedItems()}
        rows |= {ix.row() for ix in self.table.selectionModel().selectedRows()}
        if not rows and self.table.currentRow() >= 0:
            rows = {self.table.currentRow()}
        return sorted(rows)

    def show_text(self):
        if not self.project:
            return
        rows = self._chosen_rows()
        s = self._source_at(rows[0]) if rows else None
        if s is None:
            QMessageBox.information(self, "ספר מהרב", "לחצו קודם על שורה בטבלה (על שם המקור), ואז על 'הצגת הטקסט שנאסף'.")
            return
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
        if self.job is not None:
            return
        self.stop_flag.clear()
        for b in self.buttons:
            b.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._after = after
        self.job = threading.Thread(target=self._work, args=(fn,), daemon=True)
        self.job.start()

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
        self.job = None
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
            self.run(lambda: pipeline.step_read(p, self.stopped), lambda _: self._nothing_to_read(p))

    def _nothing_to_read(self, p):
        if not any(s["use"] and s["state"] == "text" for s in p.sources) and \
                not any(s["state"] == "new" and s["use"] for s in p.sources):
            read = sum(1 for s in p.sources if s["state"] == "read")
            self.status.setText(self.status.text() + f"   ·   כל המקורות נקראו ({read}) — אפשר '4. תכנון הספר'")

    def ask_instructions(self, first=False):
        """The window 'what I want in the book'. False when it was cancelled."""
        d = InstructionsDialog(self, self.project.data.get("instructions", ""), first)
        if d.exec() != QDialog.Accepted:
            return False
        self.project.data["instructions"] = d.text()
        self.project.save()
        return True

    def edit_instructions(self):
        if self.project or self.ensure_project():
            if self.ask_instructions():
                log("ההנחיות לספר נשמרו")

    def _chapters_written(self):
        d = self.project.path("chapters")
        return [f for f in os.listdir(d) if f.endswith(".md")] if os.path.isdir(d) else []

    def _plan_changed(self):
        """The plan changed: chapters written by the old plan are written again (asking first)."""
        old = self._chapters_written()
        if old and QMessageBox.question(
                self, "ספר מהרב", f"התכנית השתנתה, וכבר נכתבו {len(old)} פרקים לפי התכנית הקודמת.\n"
                "למחוק אותם, כדי שייכתבו מחדש לפי התכנית החדשה? (מומלץ)") == QMessageBox.Yes:
            for f in old:
                os.remove(self.project.path("chapters", f))
            log(f"{len(old)} פרקים נמחקו — ייכתבו מחדש ב'5. כתיבה'")

    def do_outline(self):
        if self.ensure_project() and self.ask_instructions():
            p = self.project
            self.run(lambda: pipeline.step_outline(p, again=True),
                     lambda _: (self.tabs.setCurrentIndex(1), self._plan_changed()))

    def redo_outline(self):
        self.do_outline()

    def revise_outline(self):
        if not self.project or not self.project.read("outline.md"):
            QMessageBox.information(self, "ספר מהרב", "עוד אין תכנית. לחצו קודם '4. תכנון הספר'.")
            return
        comments = self.comments.toPlainText().strip()
        if not comments:
            QMessageBox.information(self, "ספר מהרב", "כתבו קודם הערות בתיבה שמתחת לתכנית.")
            return
        self.save_outline(quiet=True)
        p = self.project
        self.run(lambda: compose.revise_outline(p, comments, pipeline.model_of(p)),
                 lambda _: (self.comments.clear(), self._plan_changed()))

    def save_outline(self, quiet=False):
        if self.project and self.outline.toPlainText().strip():
            changed = self.outline.toPlainText().strip() != self.project.read("outline.md").strip()
            self.project.write(self.outline.toPlainText(), "outline.md")
            plan = compose.md_to_outline(self.outline.toPlainText())
            log(f"התכנית נשמרה: {len(plan['chapters'])} פרקים")
            if changed and not quiet:
                self._plan_changed()

    def do_write(self):
        if self.ensure_project() and self.ask_instructions():
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
        if self.ensure_project() and self.ask_instructions():
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
        def done(res):
            if res[0]:
                QMessageBox.information(self, "Claude", res[1])
            elif "לא מחובר" in res[1]:
                if QMessageBox.question(self, "Claude", res[1] + "\n\nלהתחבר עכשיו?") == QMessageBox.Yes:
                    self.connect_claude()
            else:
                QMessageBox.warning(self, "Claude", res[1])
        self.run(lambda: claude_cli.status(), done)

    # ---------- updating the program ----------
    update_found = Signal(str)

    def _check_update_quietly(self):
        """At start, in the background: only a line in the log and the title when there is one."""
        from . import updater
        if not updater.frozen():
            return
        threading.Thread(target=updater.clean_old, daemon=True).start()
        self.update_found.connect(self._tell_update)

        def work():
            v = updater.latest()
            if updater.newer(v):
                self.update_found.emit(v)
        threading.Thread(target=work, daemon=True).start()

    def _tell_update(self, v):
        log(f"יש גרסה חדשה של התוכנה ({v}). לחצו 'עדכון תוכנה' בסרגל העליון.")
        self.setWindowTitle(self.windowTitle() + f"   ← יש גרסה חדשה ({v}): לחצו 'עדכון תוכנה'")

    def update_program(self):
        from . import updater
        if not updater.frozen():
            QMessageBox.information(self, "עדכון תוכנה", "העדכון האוטומטי עובד בגרסת ה־exe (Rav.exe). "
                                    "בגרסה עם Python מורידים את rav-python.zip מהאתר.")
            return
        if self.job is not None:
            QMessageBox.information(self, "עדכון תוכנה", "התוכנה באמצע עבודה. לחצו קודם 'עצירה', "
                                    "חכו שהכפתורים יחזרו, ואז עדכנו. העבודה נשמרת וממשיכה אחרי העדכון.")
            return

        def checked(v):
            if not v:
                QMessageBox.warning(self, "עדכון תוכנה", "לא הצלחתי לבדוק אם יש עדכון (אין חיבור לאינטרנט?).")
            elif not updater.newer(v):
                QMessageBox.information(self, "עדכון תוכנה", f"יש לכם את הגרסה האחרונה ({VERSION}).")
            elif QMessageBox.question(self, "עדכון תוכנה",
                                      f"יש גרסה חדשה: {v} (אצלכם {VERSION}).\n\nלהוריד ולהתקין? "
                                      "ההורדה כמה מאות MB; בסוף התוכנה תיסגר ותיפתח מחדש בגרסה החדשה. "
                                      "הספרים והחיבור ל־Claude נשמרים.") == QMessageBox.Yes:
                self.run(lambda: updater.download(), installed)

        def installed(new_dir):
            if new_dir:
                updater.install_and_restart(new_dir)
                QApplication.instance().quit()
        self.run(lambda: updater.latest(), checked)

    def connect_claude(self):
        ConnectDialog(self).exec()


class ParashaDialog(QDialog):
    """The choices of a book of talks on a chumash."""

    def __init__(self, win):
        super().__init__(win)
        from .search import PARASHOT
        self.setWindowTitle("שיחות על חומש")
        f = QFormLayout(self)
        self.rav = QLineEdit(win.rav.text().strip() or "הרב זלמן ברוך מלמד")
        f.addRow("הרב:", self.rav)
        self.book = QComboBox()
        for b in PARASHOT:
            self.book.addItem(f"{b} ({len(PARASHOT[b])} פרשות)", b)
        f.addRow("חומש:", self.book)
        self.videos = QSpinBox()
        self.videos.setRange(1, 15)
        self.videos.setValue(6)
        f.addRow("כמה שיחות מיוטיוב לכל פרשה:", self.videos)
        self.talks = QSpinBox()
        self.talks.setRange(1, 6)
        self.talks.setValue(3)
        f.addRow("עד כמה שיחות בספר לכל פרשה:", self.talks)
        self.fast = QCheckBox("מהיר: קודם כתוביות של יוטיוב (Claude מתקן; תמלול גרוע מתומלל שוב במודל המדויק)")
        self.fast.setChecked(True)
        f.addRow(self.fast)
        note = QLabel("הכל ירוץ לבד: חיפוש לפי פרשות, תמלול, קריאה, תכנון וכתיבה. אפשר לעצור בכל רגע ולהמשיך "
                      "אחר כך ב'▶ הכל ברצף'.")
        note.setWordWrap(True)
        f.addRow(note)
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        b.button(QDialogButtonBox.Ok).setText("התחל")
        b.button(QDialogButtonBox.Cancel).setText("ביטול")
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        f.addRow(b)

    def values(self):
        return (self.rav.text().strip() or "הרב זלמן ברוך מלמד", self.book.currentData(), self.videos.value(),
                self.talks.value(), self.fast.isChecked())


class InstructionsDialog(QDialog):
    """What the user wants in the book, in their own words: Claude follows it when it searches,
    plans and writes."""

    def __init__(self, win, text, first=False):
        super().__init__(win)
        self.setWindowTitle("מה אני רוצה בספר")
        self.resize(640, 420)
        v = QVBoxLayout(self)
        lab = QLabel("כתבו בחופשיות מה אתם רוצים בספר: סדר הפרקים, למי הוא מיועד, על מה להרחיב ועל מה לא, "
                     "מה להשמיט, אורך, כל דבר. Claude יקפיד על זה בחיפוש, בתכנון ובכתיבה."
                     + ("" if first else "\nאפשר לשנות כאן כל פעם; מה שכתוב נשמר עם הספר."))
        lab.setWordWrap(True)
        v.addWidget(lab)
        self.edit = QPlainTextEdit(text or "")
        self.edit.setPlaceholderText("לדוגמה:\n• קודם הפרקים ההלכתיים והעיוניים, ובסוף הפרקים האמוניים.\n"
                                     "• הספר לציבור הרחב — להסביר מושגים.\n• לא להכניס את השיחות על פרשת השבוע.")
        v.addWidget(self.edit)
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        b.button(QDialogButtonBox.Ok).setText("שמירה והמשך")
        b.button(QDialogButtonBox.Cancel).setText("ביטול")
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        v.addWidget(b)

    def text(self):
        return self.edit.toPlainText().strip()


class CopyDialog(QDialog):
    """Pages the program cannot open by itself, read in the user's own browser: the page opens
    there, the user copies it (Ctrl+A, Ctrl+C), and the copied text becomes the source; then the
    next page opens."""

    def __init__(self, win, todo):
        super().__init__(win)
        self.win, self.todo, self.i, self.saved, self.links = win, todo, 0, 0, 0
        self.setWindowTitle("קריאה דרך הדפדפן שלי")
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setModal(False)
        self.resize(560, 230)
        v = QVBoxLayout(self)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)
        v.addWidget(self.label)
        self.status = QLabel("")
        v.addWidget(self.status)
        row = QHBoxLayout()
        for text, fn in (("הקודם", self.previous), ("פתיחה שוב", self.open_page), ("דילוג", self.next),
                         ("סיום", self.close)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        v.addLayout(row)
        self.clip = QApplication.clipboard()
        self.clip.dataChanged.connect(self.copied)
        self.show_current()

    def current(self):
        return self.todo[self.i] if self.i < len(self.todo) else None

    def show_current(self):
        s = self.current()
        if s is None:
            self.label.setText(f"<b>סיימתם.</b> נשמרו {self.saved} דפים ו־{self.links} קישורים להקלטות. "
                               "עכשיו לוחצים '2. איסוף ותמלול' (להקלטות) ואחר כך '3. קריאה'.")
            self.status.setText("")
            return
        self.label.setText(
            f"<b>דף {self.i + 1} מתוך {len(self.todo)}:</b> {html_escape(s['title'])}<br><br>"
            "הדף נפתח בדפדפן שלכם.<br>"
            "• <b>יש בדף טקסט של השיעור:</b> לוחצים שם <b>Ctrl+A</b> ואחר כך <b>Ctrl+C</b>.<br>"
            "• <b>יש רק סרטון או הקלטה:</b> גם כאן <b>Ctrl+A</b> ואחר כך <b>Ctrl+C</b> — התוכנה מחפשת את "
            "ההקלטה במה שהועתק. אם היא לא נמצאה: קליק ימני על כפתור ההורדה ⬇ של הנגן ← "
            "<b>העתקת כתובת קישור</b> (או על סרטון יוטיוב ← Copy video URL).<br>"
            "• <b>זה דף של רשימת שיעורים:</b> גם כאן <b>Ctrl+A</b> ואחר כך <b>Ctrl+C</b> — השיעורים שבו "
            "יתווספו ויפתחו כאן אחד אחרי השני.<br>"
            "התוכנה שומרת ופותחת את הדף הבא לבד.")
        self.status.setText("")
        self.open_page()

    def open_page(self):
        s = self.current()
        if s:
            QDesktopServices.openUrl(QUrl(s["url"]))

    def copied(self):
        s = self.current()
        if s is None:
            return
        text = (self.clip.text() or "").strip()
        p = self.win.project
        if re.fullmatch(r"https?://\S+", text):
            from .collect import is_recording_link
            if not is_recording_link(text, s["url"]):
                self.status.setText("זה הקישור של הדף, לא של הסרטון. קליק ימני על הסרטון עצמו ← "
                                    "'העתקת כתובת הסרטון'. אם אין אפשרות כזו — 'דילוג'.")
                return
            # the link of the video or recording on the page: it is downloaded and transcribed
            s["media_url"], s["state"], s["chars"] = text, "new", 0
            s["note"] = "קישור להקלטה הועתק מהדפדפן — יתומלל ב'איסוף ותמלול'"
            p.save()
            self.links += 1
            log(f"✓ {s['title'][:60]} — קישור להקלטה: {text}")
            self.win.fill_table()
            self.next()
            return
        if self.list_page(s, text):
            return
        if len(text) < 2500 and self.recording_on_page(s):
            return
        if len(text) < 300:
            self.status.setText("הועתק מעט מדי טקסט — חכו שהשיעור ייטען, ואז Ctrl+A ו־Ctrl+C שוב "
                                "(או, אם יש רק סרטון: קליק ימני עליו ← העתקת כתובת הסרטון).")
            return
        p.write(f"מקור: {s['title']}\n{s['url']}\n\n" + text, "sources", "%03d.txt" % s["id"])
        s["state"], s["chars"], s["note"] = "text", len(text), "הועתק מהדפדפן"
        p.save()
        self.saved += 1
        log(f"✓ {s['title'][:60]} — {len(text):,} תווים (הועתק מהדפדפן)")
        self.win.fill_table()
        self.next()

    def recording_on_page(self, s):
        """A copied lesson page without (much) text but with a recording: the recording's link
        (a download button, the player, a YouTube frame) is taken from the copied HTML."""
        from .collect import is_recording_link, media_links
        md = self.clip.mimeData()
        html = md.html() if md is not None and md.hasHtml() else ""
        links = [u for u in media_links(html, s["url"]) if is_recording_link(u, s["url"])] if html else []
        log(f"בדף שהועתק: {len(html):,} תווי HTML, הקלטות: {len(links)}")
        if not links:
            return False
        p = self.win.project
        s["media_url"], s["state"], s["chars"] = links[0], "new", 0
        s["note"] = "הקלטה נמצאה בדף שהועתק — תתומלל ב'איסוף ותמלול'"
        p.save()
        self.links += 1
        log(f"✓ {s['title'][:60]} — נמצאה הקלטה בדף: {links[0]}")
        self.win.fill_table()
        self.next()
        return True

    def list_page(self, s, text):
        """A copied page that lists lessons: the lessons on it are added to the table and to the
        pages still to open here. True when it was such a page."""
        from .collect import lesson_links
        md = self.clip.mimeData()
        html = md.html() if md is not None and md.hasHtml() else ""
        if not html:
            return False
        links = lesson_links(html, s["url"])
        from .collect import is_list_page
        if not is_list_page(s, s["url"], text, links):
            return False
        p = self.win.project
        added = []
        for u, title in links[:80]:
            before = len(p.sources)
            src = p.add_source(u, title, "", f"מתוך הרשימה: {s['title']}", "רשימה")
            if len(p.sources) > before:
                added.append(src)
        s["state"], s["note"] = "irrelevant", f"דף רשימה — נוספו ממנו {len(added)} שיעורים לטבלה"
        p.save()
        self.todo[self.i + 1:self.i + 1] = added      # they open here right after this page
        log(f"✓ {s['title'][:60]} — דף רשימה: נוספו {len(added)} שיעורים")
        self.win.fill_table()
        self.status.setText(f"דף רשימה: נוספו {len(added)} שיעורים, והם ייפתחו כאן אחד אחרי השני.")
        self.next()
        return True

    def next(self):
        self.i += 1
        self.show_current()

    def previous(self):
        """Back to the page before (to copy the video's link after its text was taken)."""
        if self.i > 0:
            self.i -= 1
            self.show_current()

    def closeEvent(self, e):
        try:
            self.clip.dataChanged.disconnect(self.copied)
        except Exception:
            pass
        self.win.fill_table()
        super().closeEvent(e)


def html_escape(t):
    import html
    return html.escape(t or "")


class ConnectDialog(QDialog):
    """Connecting with a key from `claude setup-token`: the login is kept with the program."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("חיבור ל־Claude")
        self.resize(620, 330)
        v = QVBoxLayout(self)
        steps = QLabel(
            "<b>1.</b> לוחצים <b>קבלת מפתח</b>. נפתח חלון שחור ואחריו דפדפן: מתחברים לחשבון Claude שלכם "
            "ולוחצים Authorize (אם הדפדפן מראה קוד — מעתיקים אותו לחלון השחור ולוחצים Enter).<br>"
            "<b>2.</b> בסוף מופיע בחלון השחור מפתח ארוך שמתחיל ב־<code>sk-ant-oat01-</code>. מסמנים אותו בעכבר "
            "(את כולו) ולוחצים Ctrl+C.<br>"
            "<b>3.</b> מדביקים כאן (Ctrl+V) ולוחצים <b>שמירה ובדיקה</b>.<br><br>"
            "המפתח הוא כמו סיסמה: הוא נשמר רק במחשב הזה. לא שולחים אותו לאף אחד.")
        steps.setWordWrap(True)
        steps.setTextFormat(Qt.RichText)
        v.addWidget(steps)
        get = QPushButton("קבלת מפתח (פותח חלון)")
        get.clicked.connect(self.get_key)
        v.addWidget(get)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("sk-ant-oat01-…")
        self.key.setLayoutDirection(Qt.LeftToRight)
        if claude_cli.saved_key():
            self.key.setPlaceholderText("כבר שמור מפתח. אפשר להדביק חדש במקומו")
        v.addWidget(self.key)
        row = QHBoxLayout()
        save = QPushButton("שמירה ובדיקה")
        save.clicked.connect(self.save)
        forget = QPushButton("מחיקת המפתח השמור")
        forget.clicked.connect(self.forget)
        close = QPushButton("סגירה")
        close.clicked.connect(self.reject)
        for b in (save, forget, close):
            row.addWidget(b)
        v.addLayout(row)

    def get_key(self):
        try:
            claude_cli.open_setup_token_window()
        except Exception as e:
            QMessageBox.warning(self, "Claude", str(e))

    def save(self):
        key = self.key.text().strip()
        if not key.startswith("sk-ant-"):
            QMessageBox.warning(self, "Claude", "זה לא נראה כמו מפתח: המפתח מתחיל ב־sk-ant-oat01- "
                                "ויש להעתיק אותו בשלמותו.")
            return
        claude_cli.save_key(key)
        self.accept()
        self.win.check_claude()

    def forget(self):
        claude_cli.save_key("")
        QMessageBox.information(self, "Claude", "המפתח נמחק.")


def collect_is_local(u):
    from .collect import is_local
    return is_local(u)
