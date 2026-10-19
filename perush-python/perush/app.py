"""The program window: editing on one side, the laid-out pages on the other."""
import json
import os

import sys

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QFont, QFontDatabase, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFontComboBox, QFormLayout,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
    QMenu, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from . import model
from .engine import Cancelled, Engine
from .render import export_pdf, page_image

APP_NAME = "עימוד פירושים"

HINT_MAIN = (
    "כל פסוק בשורה נפרדת. <b>#</b> בתחילת שורה = כותרת (<b># פרק א</b>); כותרת שמתחילה ב\"פרשת\" "
    "נכתבת בראש העמודים. <b>##</b> = קטע בלי פירוש, כמו הפטרה (<b>## הפטרת בראשית</b>). "
    "<b>[יב]</b> בתחילת פסוק = סימון משלך. <b>**מילים**</b> = מודגש."
)
HINT_COMM = (
    "<b>לפי סדר:</b> שורה 1 לפסוק 1, שורה 2 לפסוק 2… (שורה ריקה = אין פירוש). "
    "<b>לפי הפניה:</b> שורה שמתחילה ב־<b>@3</b> שייכת לפסוק השלישי; אפשר כמה שורות לאותו פסוק. "
    "ד\"ה מודגש אוטומטית: <b>בראשית - פירוש…</b>"
)

COMPACT = {"margin": 8, "lineHeight": 1.3, "colGap": 3, "sectionGap": 1, "minLines": 3}
ROOMY = {"margin": 16, "lineHeight": 1.6, "colGap": 6, "sectionGap": 3, "minLines": 6}


def hebrew_edit(font_family="Frank Ruhl Libre", size=13):
    e = QPlainTextEdit()
    e.setLayoutDirection(Qt.RightToLeft)
    f = QFont(font_family)
    f.setPointSizeF(size)
    e.setFont(f)
    e.document().setDefaultTextOption(e.document().defaultTextOption())
    return e


def hint(html):
    l = QLabel(html)
    l.setWordWrap(True)
    l.setStyleSheet("color:#555; font-size:12px;")
    return l


class CommEditor(QWidget):
    """One translation or commentary."""

    def __init__(self, comm, on_change):
        super().__init__()
        self.comm = comm
        self.on_change = on_change
        lay = QVBoxLayout(self)
        grid = QGridLayout()
        self.name = QLineEdit(comm["name"])
        self.place = QComboBox()
        for k, v in model.PLACES.items():
            self.place.addItem(v, k)
        self.place.setCurrentIndex(list(model.PLACES).index(comm["place"]))
        self.side = QComboBox()
        self.side.addItem("משמאל לטקסט", "left")
        self.side.addItem("מימין לטקסט", "right")
        self.side.setCurrentIndex(0 if comm["side"] != "right" else 1)
        self.width = QSpinBox()
        self.width.setRange(10, 60)
        self.width.setSuffix("%")
        self.width.setValue(int(comm["width"]))
        self.autow = QCheckBox("רוחב אוטומטי")
        self.autow.setChecked(bool(comm["autoW"]))
        self.cols = QSpinBox()
        self.cols.setRange(1, 3)
        self.cols.setValue(int(comm["cols"]))
        self.font = QFontComboBox()
        self.font.setWritingSystem(QFontDatabase.Hebrew)
        self.font.setCurrentFont(QFont(comm["font"]))
        self.size = QDoubleSpinBox()
        self.size.setRange(5, 30)
        self.size.setSingleStep(0.5)
        self.size.setValue(float(comm["size"]))
        self.size.setSuffix(" נק'")
        grid.addWidget(QLabel("שם:"), 0, 0)
        grid.addWidget(self.name, 0, 1)
        grid.addWidget(QLabel("מיקום:"), 0, 2)
        grid.addWidget(self.place, 0, 3)
        grid.addWidget(QLabel("גופן:"), 1, 0)
        grid.addWidget(self.font, 1, 1)
        grid.addWidget(QLabel("גודל:"), 1, 2)
        grid.addWidget(self.size, 1, 3)
        self.side_lbl = QLabel("צד:")
        self.width_lbl = QLabel("רוחב:")
        self.cols_lbl = QLabel("טורים:")
        grid.addWidget(self.side_lbl, 2, 0)
        grid.addWidget(self.side, 2, 1)
        grid.addWidget(self.width_lbl, 2, 2)
        wbox = QHBoxLayout()
        wbox.addWidget(self.width)
        wbox.addWidget(self.autow)
        grid.addLayout(wbox, 2, 3)
        grid.addWidget(self.cols_lbl, 3, 0)
        grid.addWidget(self.cols, 3, 1)
        lay.addLayout(grid)
        self.text = hebrew_edit(comm["font"] if comm["font"] in QFontDatabase.families() else "Frank Ruhl Libre", 12)
        self.text.setPlainText(comm["text"])
        self.text.setPlaceholderText("שורה לכל פסוק, או @מספר-פסוק בתחילת שורה")
        lay.addWidget(self.text, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        for w in (self.name, ):
            w.textChanged.connect(self.changed)
        self.text.textChanged.connect(self.changed)
        self.place.currentIndexChanged.connect(self.changed)
        self.side.currentIndexChanged.connect(self.changed)
        self.width.valueChanged.connect(self.changed)
        self.autow.toggled.connect(self.changed)
        self.cols.valueChanged.connect(self.changed)
        self.font.currentFontChanged.connect(self.changed)
        self.size.valueChanged.connect(self.changed)
        self.update_visibility()

    def update_visibility(self):
        place = self.place.currentData()
        for w in (self.side, self.side_lbl, self.width, self.width_lbl, self.autow):
            w.setVisible(place == "side")
        for w in (self.cols, self.cols_lbl):
            w.setVisible(place == "bottom")
        self.width.setEnabled(not self.autow.isChecked())

    def changed(self, *_):
        c = self.comm
        c["name"] = self.name.text()
        c["place"] = self.place.currentData()
        c["side"] = self.side.currentData()
        c["width"] = self.width.value()
        c["autoW"] = self.autow.isChecked()
        c["cols"] = self.cols.value()
        c["font"] = self.font.currentFont().family()
        c["size"] = self.size.value()
        c["text"] = self.text.toPlainText()
        self.update_visibility()
        self.on_change()

    def set_status(self, problem, info):
        if problem:
            self.status.setText("⚠ " + problem)
            self.status.setStyleSheet("color:#b45309; font-weight:bold;")
        else:
            self.status.setText(info)
            self.status.setStyleSheet("color:#15803d;")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("perush", "perush")
        self.path = None
        self.dirty = False
        self.pages = []
        self.generation = 0
        self.running = False
        self.zoom = 1.0
        self.loading = False

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.relayout)

        self.build_toolbar()
        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.build_editor())
        split.addWidget(self.build_preview())
        split.setSizes([520, 900])
        self.setCentralWidget(split)
        self.resize(1450, 920)

        self.project = self.load_recovery() or model.example_project()
        self.fill_editor()
        self.relayout()

    # ---------------------------------------------------------------- building

    def build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)

        def act(text, slot, key=None):
            a = QAction(text, self)
            a.triggered.connect(slot)
            if key:
                a.setShortcut(key)
            tb.addAction(a)
            return a

        act("חדש", self.new_project, QKeySequence.New)
        act("פתיחה…", self.open_project, QKeySequence.Open)
        act("שמירה", self.save, QKeySequence.Save)
        act("שמירה בשם…", self.save_as, QKeySequence.SaveAs)
        tb.addSeparator()
        books = QToolButton()
        books.setText("ספרים מוכנים ▾")
        books.setPopupMode(QToolButton.InstantPopup)
        books.setMenu(self.books_menu())
        books.setStyleSheet("font-weight:bold;")
        tb.addWidget(books)
        act("דוגמה", self.load_example)
        act("ייבוא מספריא…", self.import_sefaria)
        act("בדיקת התאמה", self.show_check)
        tb.addSeparator()
        pdf = act("ייצוא PDF…", self.export, "Ctrl+P")
        tb.widgetForAction(pdf).setStyleSheet("font-weight:bold;")
        tb.addSeparator()
        tb.addWidget(QLabel(" תצוגה: "))
        self.zoom_box = QComboBox()
        for z in (50, 75, 100, 125, 150, 200):
            self.zoom_box.addItem(f"{z}%", z / 100)
        self.zoom_box.setCurrentIndex(2)
        self.zoom_box.currentIndexChanged.connect(self.set_zoom)
        tb.addWidget(self.zoom_box)

    def projects_dir(self):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base, "projects")

    def books_menu(self):
        """The ready projects that ship in the 'projects' folder: a submenu per book."""
        menu = QMenu(self)
        root = self.projects_dir()
        found = False
        if os.path.isdir(root):
            for book in sorted(os.listdir(root)):
                folder = os.path.join(root, book)
                files = sorted(f for f in os.listdir(folder) if f.endswith(".json")) if os.path.isdir(folder) else []
                if not files:
                    continue
                sub = menu.addMenu(book)
                for f in files:
                    a = sub.addAction(os.path.splitext(f)[0])
                    a.triggered.connect(lambda _=False, p=os.path.join(folder, f): self.open_path(p))
                found = True
        if not found:
            menu.addAction("לא נמצאה התיקייה projects").setEnabled(False)
        return menu

    def build_editor(self):
        area = QScrollArea()
        area.setWidgetResizable(True)
        w = QWidget()
        lay = QVBoxLayout(w)

        box = QGroupBox("טקסט עיקרי")
        bl = QVBoxLayout(box)
        self.title = QLineEdit()
        self.title.setPlaceholderText("כותרת (למשל שם הספר) — בראש כל עמוד")
        bl.addWidget(self.title)
        self.main = hebrew_edit()
        self.main.setMinimumHeight(220)
        bl.addWidget(self.main)
        bl.addWidget(hint(HINT_MAIN))
        lay.addWidget(box)

        box = QGroupBox("תרגומים ופירושים")
        bl = QVBoxLayout(box)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setMinimumHeight(360)
        self.tabs.tabCloseRequested.connect(self.remove_comm)
        self.tabs.tabBar().tabMoved.connect(self.tab_moved)
        bl.addWidget(self.tabs)
        row = QHBoxLayout()
        for place, text in (("side", "+ תרגום בטור צמוד"), ("bottom", "+ פירוש מתחת לטקסט"), ("under", "+ ביאור אחרי כל פסוק")):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, p=place: self.add_comm(p))
            row.addWidget(b)
        bl.addLayout(row)
        bl.addWidget(hint(HINT_COMM))
        lay.addWidget(box)

        box = QGroupBox("עימוד")
        form = QFormLayout(box)
        self.page_size = QComboBox()
        for k, (name, _, _) in model.PAGE_SIZES.items():
            self.page_size.addItem(name, k)
        self.main_font = QFontComboBox()
        self.main_font.setWritingSystem(QFontDatabase.Hebrew)

        def dspin(lo, hi, step, suffix=""):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setDecimals(2 if step < 0.5 else 1)
            s.setSuffix(suffix)
            return s

        def ispin(lo, hi):
            s = QSpinBox()
            s.setRange(lo, hi)
            return s

        self.sp = {
            "margin": dspin(3, 40, 1, " מ\"מ"),
            "mainSize": dspin(6, 40, 0.5, " נק'"),
            "lineHeight": dspin(1, 2.5, 0.05),
            "colGap": dspin(0, 15, 0.5, " מ\"מ"),
            "sectionGap": dspin(0, 10, 0.5, " מ\"מ"),
            "minLines": ispin(1, 40),
            "firstPage": ispin(1, 5000),
        }
        form.addRow("גודל עמוד:", self.page_size)
        form.addRow("שוליים:", self.sp["margin"])
        form.addRow("גופן הטקסט:", self.main_font)
        form.addRow("גודל הטקסט:", self.sp["mainSize"])
        form.addRow("מרווח שורות:", self.sp["lineHeight"])
        form.addRow("רווח בין טורים:", self.sp["colGap"])
        form.addRow("רווח בין חלקי העמוד:", self.sp["sectionGap"])
        form.addRow("מינימום שורות טקסט בעמוד:", self.sp["minLines"])
        form.addRow("מספר העמוד הראשון:", self.sp["firstPage"])
        self.cb = {
            "verseNewLine": QCheckBox("כל פסוק בשורה חדשה"),
            "numbers": QCheckBox("אותיות פסוקים"),
            "header": QCheckBox("כותרת עליונה ומספר עמוד"),
            "names": QCheckBox("שם המתרגם / המפרש מעל כל טור"),
            "inlineChapters": QCheckBox("פרק בתוך הטקסט (אות הפרק מודגשת, בלי שורת כותרת)"),
        }
        for c in self.cb.values():
            form.addRow(c)
        row = QHBoxLayout()
        b1 = QPushButton("חיסכון מקסימלי במקום")
        b1.clicked.connect(lambda: self.preset(COMPACT))
        b2 = QPushButton("מרווח ונוח לקריאה")
        b2.clicked.connect(lambda: self.preset(ROOMY))
        row.addWidget(b1)
        row.addWidget(b2)
        form.addRow(row)
        lay.addWidget(box)
        lay.addStretch(1)
        area.setWidget(w)

        self.title.textChanged.connect(self.changed)
        self.main.textChanged.connect(self.changed)
        self.page_size.currentIndexChanged.connect(self.changed)
        self.main_font.currentFontChanged.connect(self.changed)
        for s in self.sp.values():
            s.valueChanged.connect(self.changed)
        for c in self.cb.values():
            c.toggled.connect(self.changed)
        return area

    def build_preview(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.info = QLabel("מעמד…")
        self.info.setStyleSheet("padding:6px; color:#444;")
        lay.addWidget(self.info)
        self.warn = QLabel()
        self.warn.setWordWrap(True)
        self.warn.setStyleSheet("background:#fff4e5; border:1px solid #f5c98b; color:#7c3a06; padding:6px; border-radius:6px;")
        self.warn.hide()
        lay.addWidget(self.warn)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { background:#e9e6df; }")
        self.pages_box = QWidget()
        self.pages_box.setStyleSheet("background:#e9e6df;")
        self.pages_lay = QVBoxLayout(self.pages_box)
        self.pages_lay.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.pages_lay.setSpacing(18)
        self.scroll.setWidget(self.pages_box)
        lay.addWidget(self.scroll, 1)
        return w

    # ---------------------------------------------------------------- project <-> editor

    def fill_editor(self):
        self.loading = True
        p = self.project
        self.title.setText(p["title"])
        self.main.setPlainText(p["main"])
        self.page_size.setCurrentIndex(list(model.PAGE_SIZES).index(p["pageSize"]))
        self.main_font.setCurrentFont(QFont(p["mainFont"]))
        for k, s in self.sp.items():
            s.setValue(p[k])
        for k, c in self.cb.items():
            c.setChecked(bool(p[k]))
        self.tabs.clear()
        for c in p["comms"]:
            self.tabs.addTab(CommEditor(c, self.changed), c["name"] or "—")
        self.loading = False
        self.update_statuses()

    def read_editor(self):
        p = self.project
        p["title"] = self.title.text()
        p["main"] = self.main.toPlainText()
        p["pageSize"] = self.page_size.currentData()
        p["mainFont"] = self.main_font.currentFont().family()
        for k, s in self.sp.items():
            p[k] = s.value()
        for k, c in self.cb.items():
            p[k] = c.isChecked()
        p["comms"] = [self.tabs.widget(i).comm for i in range(self.tabs.count())]
        for i in range(self.tabs.count()):
            self.tabs.setTabText(i, self.tabs.widget(i).comm["name"] or "—")

    def changed(self, *_):
        if self.loading:
            return
        self.read_editor()
        self.dirty = True
        self.update_title()
        self.update_statuses()
        self.save_recovery()
        self.generation += 1
        self.timer.start()

    def update_statuses(self):
        _, count = model.parse_main(self.project["main"])
        for i in range(self.tabs.count()):
            ed = self.tabs.widget(i)
            _, problem, info = model.parse_comm(ed.comm, count)
            ed.set_status(problem, info)

    def update_title(self):
        name = os.path.basename(self.path) if self.path else "ללא שם"
        self.setWindowTitle(f"{'• ' if self.dirty else ''}{name} — {APP_NAME}")

    def add_comm(self, place):
        names = {"side": "תרגום", "bottom": "פירוש", "under": "ביאור"}
        c = dict(model.COMM_DEFAULTS, name=names[place], place=place)
        if place != "bottom":
            c.update(font="Noto Serif Hebrew", size=11)
        self.project["comms"].append(c)
        self.tabs.addTab(CommEditor(c, self.changed), c["name"])
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        self.changed()

    def remove_comm(self, i):
        name = self.tabs.widget(i).comm["name"]
        if QMessageBox.question(self, APP_NAME, f"למחוק את \"{name}\"?") == QMessageBox.Yes:
            self.tabs.removeTab(i)
            self.changed()

    def tab_moved(self, *_):
        self.changed()

    def preset(self, values):
        self.project.update(values)
        self.fill_editor()
        self.changed()

    # ---------------------------------------------------------------- layout and preview

    def relayout(self):
        if self.running:
            self.timer.start()
            return
        self.running = True
        gen = self.generation
        self.info.setText("מעמד…")

        def progress(n):
            self.info.setText(f"מעמד… עמוד {n + 1}")
            QApplication.processEvents()
            if self.generation != gen:
                raise Cancelled()

        try:
            eng = Engine(json.loads(json.dumps(self.project)), progress)
            pages = eng.run()
        except Cancelled:
            self.running = False
            self.timer.start()
            return
        except Exception as e:  # show the problem instead of closing the program
            self.running = False
            self.info.setText("שגיאה בעימוד")
            self.warn.setText(f"⚠ {e}")
            self.warn.show()
            return
        self.running = False
        self.pages = pages
        self.show_pages()
        sides = [f" · {self.project['comms'][c]['name']}: רוחב {round(eng.col_w[c])}%" for c in eng.sides]
        self.info.setText(f"{len(pages)} עמודים · {eng.count} פסוקים · {len(self.project['comms'])} פירושים{''.join(sides)}")
        if eng.warnings:
            self.warn.setText("\n".join("⚠ " + w for w in eng.warnings))
            self.warn.show()
        else:
            self.warn.hide()

    def show_pages(self):
        while self.pages_lay.count():
            item = self.pages_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        ratio = self.devicePixelRatioF()
        px_per_pt = self.zoom * 96 / 72 * ratio
        for page in self.pages:
            img = page_image(page, px_per_pt)
            pm = QPixmap.fromImage(img)
            pm.setDevicePixelRatio(ratio)
            lbl = QLabel()
            lbl.setPixmap(pm)
            lbl.setFrameShape(QFrame.Box)
            lbl.setStyleSheet("background:white; border:1px solid #c9c4b8;")
            self.pages_lay.addWidget(lbl, 0, Qt.AlignHCenter)

    def set_zoom(self):
        self.zoom = self.zoom_box.currentData()
        self.show_pages()

    # ---------------------------------------------------------------- files

    def recovery_path(self):
        folder = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, "recovery.json")

    def save_recovery(self):
        try:
            model.save_project(dict(self.project, _path=self.path or ""), self.recovery_path())
        except OSError:
            pass

    def load_recovery(self):
        try:
            with open(self.recovery_path(), encoding="utf-8") as f:
                data = json.load(f)
            self.path = data.get("_path") or None
            return model.normalize(data)
        except (OSError, ValueError):
            return None

    def confirm_discard(self):
        if not self.dirty:
            return True
        r = QMessageBox.question(self, APP_NAME, "יש שינויים שלא נשמרו. לשמור אותם?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.save()
        return r == QMessageBox.Discard

    def new_project(self):
        if not self.confirm_discard():
            return
        self.project = model.normalize({})
        self.path = None
        self.fill_editor()
        self.dirty = False
        self.changed()
        self.dirty = False
        self.update_title()

    def load_example(self):
        if not self.confirm_discard():
            return
        self.project = model.example_project()
        self.path = None
        self.fill_editor()
        self.changed()
        self.dirty = False
        self.update_title()

    def open_project(self):
        if not self.confirm_discard():
            return
        start = self.settings.value("lastDir", "") or self.projects_dir()
        path, _ = QFileDialog.getOpenFileName(self, "פתיחת פרויקט", start, "פרויקט (*.json)")
        if not path:
            return
        self.settings.setValue("lastDir", os.path.dirname(path))
        self.open_path(path, ask=False)

    def open_path(self, path, ask=True):
        if ask and not self.confirm_discard():
            return
        try:
            self.project = model.load_project(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, APP_NAME, f"לא ניתן לפתוח את הקובץ:\n{e}")
            return
        # a ready project is opened as a copy: saving asks where to keep it
        self.path = None if os.path.abspath(path).startswith(os.path.abspath(self.projects_dir())) else path
        self.fill_editor()
        self.changed()
        self.dirty = False
        self.update_title()

    def save(self):
        if not self.path:
            return self.save_as()
        try:
            model.save_project(self.project, self.path)
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, f"השמירה נכשלה:\n{e}")
            return False
        self.dirty = False
        self.update_title()
        self.save_recovery()
        return True

    def save_as(self):
        start = os.path.join(self.settings.value("lastDir", ""), (self.project["title"] or "פרויקט") + ".json")
        path, _ = QFileDialog.getSaveFileName(self, "שמירת פרויקט", start, "פרויקט (*.json)")
        if not path:
            return False
        if not path.lower().endswith(".json"):
            path += ".json"
        self.settings.setValue("lastDir", os.path.dirname(path))
        self.path = path
        return self.save()

    def export(self):
        if self.running or not self.pages:
            QMessageBox.information(self, APP_NAME, "העימוד עדיין רץ, נסו שוב בעוד רגע.")
            return
        base = os.path.splitext(self.path)[0] if self.path else os.path.join(self.settings.value("lastDir", ""), self.project["title"] or "עימוד")
        path, _ = QFileDialog.getSaveFileName(self, "ייצוא PDF", base + ".pdf", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            export_pdf(self.pages, path, self.project["title"])
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"הייצוא נכשל:\n{e}")
            return
        self.settings.setValue("lastDir", os.path.dirname(path))
        if QMessageBox.question(self, APP_NAME, f"נשמר: {path}\n\nלפתוח את הקובץ?") == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def import_sefaria(self):
        from .sefaria import convert
        QMessageBox.information(self, APP_NAME,
            "בחרו את קובצי הטקסט שהורדתם מספריא (ספר אחד): הפסוקים, ואם יש גם אונקלוס, רש\"י ורמב\"ן.\n"
            "אחר כך בחרו תיקייה שבה יישמרו הפרויקטים (קובץ לכל פרשה וקובץ לכל הספר).")
        paths, _ = QFileDialog.getOpenFileNames(self, "קובצי ספריא", self.settings.value("lastDir", ""), "טקסט (*.txt)")
        if not paths:
            return
        out = QFileDialog.getExistingDirectory(self, "תיקייה לשמירת הפרויקטים", os.path.dirname(paths[0]))
        if not out:
            return
        try:
            written, report = convert(paths, out)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"הייבוא נכשל:\n{e}")
            return
        self.settings.setValue("lastDir", out)
        QMessageBox.information(self, APP_NAME, "\n".join(report) + f"\n\nנשמרו {len(written)} קבצים בתיקייה:\n{out}\n\nהפרשה הראשונה תיפתח עכשיו.")
        if not self.confirm_discard():
            return
        self.project = model.load_project(written[0])
        self.path = written[0]
        self.fill_editor()
        self.changed()
        self.dirty = False
        self.update_title()

    def show_check(self):
        items, count = model.parse_main(self.project["main"])
        verses = [it for it in items if it["type"] == "v" and not it["noComm"]]
        comms = self.project["comms"]
        parsed = [model.parse_comm(c, count)[0] for c in comms]
        dlg = QDialog(self)
        dlg.setWindowTitle("בדיקת התאמה: פסוקים ↔ פירושים")
        dlg.resize(1000, 640)
        lay = QVBoxLayout(dlg)
        t = QTableWidget(len(verses), 2 + len(comms))
        t.setHorizontalHeaderLabels(["#", "פסוק"] + [c["name"] for c in comms])
        for r, v in enumerate(verses):
            t.setItem(r, 0, QTableWidgetItem(f"{v['idx'] + 1} ({v['label']})"))
            t.setItem(r, 1, QTableWidgetItem(v["plain"]))
            for k, ent in enumerate(parsed):
                txt = " · ".join(ent[v["idx"]])
                item = QTableWidgetItem(txt or "—")
                if not txt:
                    item.setBackground(Qt.yellow)
                item.setToolTip(txt)
                t.setItem(r, 2 + k, item)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        lay.addWidget(t)
        dlg.exec()

    def closeEvent(self, ev):
        if self.confirm_discard():
            ev.accept()
        else:
            ev.ignore()
