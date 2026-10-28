"""The program window: editing on one side, the laid-out pages on the other."""
import html
import json
import re
import os

import sys

from PySide6.QtCore import QEvent, QObject, QSettings, QSize, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import (QAction, QColor, QIcon, QDesktopServices, QFont, QFontDatabase, QKeySequence, QPixmap, QShortcut,
                           QTextCursor, QTextDocument)
from PySide6.QtWidgets import (
    QAbstractSpinBox, QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFontComboBox, QFormLayout,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
    QMenu, QSizePolicy, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from . import cover, model
from .checks import check, describe, summary
from .engine import Cancelled, Engine
from .render import export_pdf, page_image

APP_NAME = "עימוד פירושים"


def _log(msg):
    main = sys.modules.get("__main__")
    if hasattr(main, "log"):
        main.log(msg)

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


class PageLabel(QLabel):
    """A page in the preview: a click on a line opens its source in the editor."""

    def __init__(self, window, index, px_per_pt):
        super().__init__()
        self.window, self.index, self.k = window, index, px_per_pt
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("לחיצה על שורה פותחת אותה בעורך")

    def mousePressEvent(self, ev):
        pos = ev.position() if hasattr(ev, "position") else ev.pos()
        self.window.page_clicked(self.index, (pos.x() - 1) / self.k, (pos.y() - 1) / self.k)


class WheelGuard(QObject):
    """A spin box or list passed over by the mouse wheel ignores it (the page scrolls)
    unless it has been clicked."""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Wheel and not obj.hasFocus():
            ev.ignore()
            return True
        return False


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
        self.autosave = QTimer(self)
        self.autosave.setSingleShot(True)
        self.autosave.setInterval(1500)
        self.autosave.timeout.connect(self.save_quietly)
        self.cover_timer = QTimer(self)
        self.cover_timer.setSingleShot(True)
        self.cover_timer.setInterval(250)
        self.cover_timer.timeout.connect(self.show_cover)
        self.engine = None

        self.build_toolbar()
        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.build_editor())
        split.addWidget(self.build_preview())
        split.setSizes([520, 900])
        self.setCentralWidget(split)
        self.resize(1450, 920)

        self.project = self.load_recovery() or model.example_project()
        self.fill_editor()
        # lay out once the window is on the screen (a whole book takes a while, and the
        # window should open at once and show how far it has got)
        QTimer.singleShot(0, self.relayout)

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
        prep = act("הכנת טקסט…", self.open_prepare)
        tb.widgetForAction(prep).setStyleSheet("font-weight:bold;")
        act("ייבוא מספריא…", self.import_sefaria)
        act("בדיקת התאמה", self.show_check)
        tb.addSeparator()
        pdf = act("ייצוא PDF…", self.export, "Ctrl+P")
        tb.widgetForAction(pdf).setStyleSheet("font-weight:bold;")
        act("ייצוא כריכה…", self.export_cover)
        tb.addSeparator()
        tb.addWidget(QLabel(" תצוגה: "))
        self.zoom_box = QComboBox()
        for z in (50, 75, 100, 125, 150, 200):
            self.zoom_box.addItem(f"{z}%", z / 100)
        self.zoom_box.setCurrentIndex(2)
        self.zoom_box.currentIndexChanged.connect(self.set_zoom)
        tb.addWidget(self.zoom_box)
        tb.addWidget(QLabel("  עמוד: "))
        self.page_no = QSpinBox()
        self.page_no.setRange(1, 9999)
        self.page_no.setToolTip("מעבר לעמוד בתצוגה (לפי הסדר, מהעמוד הראשון)")
        self.page_no.editingFinished.connect(self.go_to_page)
        tb.addWidget(self.page_no)
        tb.addSeparator()
        self.search = QLineEdit()
        self.search.setPlaceholderText("חיפוש בטקסט… (Enter)")
        self.search.setMaximumWidth(190)
        self.search.returnPressed.connect(self.find_text)
        tb.addWidget(self.search)
        QShortcut(QKeySequence.Find, self, lambda: (self.search.setFocus(), self.search.selectAll()))
        tb.addSeparator()
        act("עדכון תוכנה", self.update_program)

    def update_program(self):
        """Download the latest version from the site and install it over this one."""
        from . import updater
        if updater.frozen():
            url = "https://github.com/tzur900-droid/tzur900-droid.github.io/releases/download/exe/Perush-windows.zip"
            if QMessageBox.question(self, APP_NAME, "בגרסת ה־exe מעדכנים כך: מורידים את הקובץ Perush-windows.zip "
                                    "ומחלצים אותו במקום התיקייה הקיימת (הפרויקטים שלך במסמכים לא נוגעים).\n\n"
                                    "לפתוח את ההורדה עכשיו?") == QMessageBox.Yes:
                QDesktopServices.openUrl(QUrl(url))
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            remote = updater.remote_version()
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, APP_NAME, f"לא הצלחתי לבדוק אם יש עדכון (צריך חיבור לאינטרנט).\n{e}")
            return
        QApplication.restoreOverrideCursor()
        if not updater.newer(remote):
            QMessageBox.information(self, APP_NAME, f"יש לך כבר את הגרסה האחרונה ({updater.VERSION}).")
            return
        if QMessageBox.question(self, APP_NAME, f"יש גרסה חדשה ({remote}; אצלך {updater.VERSION}).\n"
                                "לעדכן עכשיו? התוכנה תיסגר ותיפתח מחדש (העבודה שלך נשמרת).") != QMessageBox.Yes:
            return
        self.info.setText("מוריד את העדכון…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        try:
            data = updater.fetch(updater.ZIP_NAME, 120)

            def progress(k, n):
                self.info.setText(f"מעדכן… {k} מתוך {n} קבצים")
                QApplication.processEvents()

            written, failed, req_changed = updater.install(data, progress)
            if req_changed:
                self.info.setText("מתקין רכיבים חדשים…")
                QApplication.processEvents()
                updater.update_packages()
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, APP_NAME, f"העדכון נכשל:\n{e}")
            return
        QApplication.restoreOverrideCursor()
        note = f"\n(לא עודכנו {len(failed)} קבצים שהיו פתוחים, למשל גופנים — הם יתעדכנו בפעם הבאה.)" if failed else ""
        QMessageBox.information(self, APP_NAME, f"העדכון הותקן ({written} קבצים).{note}\nהתוכנה תיפתח עכשיו מחדש.")
        self.save_recovery()
        updater.restart()
        self.dirty = False
        QApplication.quit()

    def projects_dir(self):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base, "projects")

    def books_menu(self):
        """The ready projects that ship in the 'projects' folder: a submenu per book."""
        menu = QMenu(self)
        root = self.projects_dir()
        found = False
        if os.path.isdir(root):
            order = ["בראשית", "שמות", "ויקרא", "במדבר", "דברים"]
            for book in sorted(os.listdir(root), key=lambda b: (order.index(b.split(" - ")[0]) if b.split(" - ")[0] in order else 99, b)):
                if "╫" in book:
                    continue    # a folder whose Hebrew name an old zip garbled
                folder = os.path.join(root, book)
                files = sorted(f for f in os.listdir(folder) if f.endswith(".json")) if os.path.isdir(folder) else []
                if not files:
                    continue
                if len(files) == 1:
                    # a book in one file: open it straight from the menu
                    a = menu.addAction(book)
                    a.triggered.connect(lambda _=False, p=os.path.join(folder, files[0]): self.open_path(p))
                    found = True
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
        """The editing side, in three tabs: each editor gets the full height and scrolls on
        its own, instead of boxes inside one long scrolling page."""
        side = QTabWidget()
        self.side = side
        side.setDocumentMode(True)
        side.setStyleSheet("QTabBar::tab { padding:6px 14px; font-size:13px; }")

        box = QWidget()
        bl = QVBoxLayout(box)
        self.title = QLineEdit()
        self.title.setPlaceholderText("כותרת (למשל שם הספר) — בראש כל עמוד")
        bl.addWidget(self.title)
        self.main = hebrew_edit()
        bl.addWidget(self.main, 1)
        bl.addWidget(hint(HINT_MAIN))
        side.addTab(box, "טקסט עיקרי")

        box = QWidget()
        bl = QVBoxLayout(box)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.remove_comm)
        self.tabs.tabBar().tabMoved.connect(self.tab_moved)
        bl.addWidget(self.tabs, 1)
        row = QHBoxLayout()
        for place, text in (("side", "+ תרגום בטור צמוד"), ("bottom", "+ פירוש מתחת לטקסט"), ("under", "+ ביאור אחרי כל פסוק")):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, p=place: self.add_comm(p))
            row.addWidget(b)
        bl.addLayout(row)
        bl.addWidget(hint(HINT_COMM))
        side.addTab(box, "תרגומים ופירושים")

        area = QScrollArea()
        area.setWidgetResizable(True)
        w = QWidget()
        lay = QVBoxLayout(w)
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
            "pageW": dspin(50, 500, 1, " מ\"מ"),
            "pageH": dspin(50, 700, 1, " מ\"מ"),
            "gutter": dspin(0, 30, 1, " מ\"מ"),
            "gmBand": ispin(0, 10),
            "gmMain": dspin(20, 70, 1, "%"),
        }
        # the shape of the page: Mikraot Gedolot, or a Talmud page
        self.layout_box = QComboBox()
        self.layout_box.addItem("מקראות גדולות (תרגום בטור צמוד, פירושים מתחת)", "mg")
        self.layout_box.addItem("דף גמרא (הפסוקים באמצע, פירוש מכל צד ומעליהם)", "gemara")
        form.addRow("צורת העמוד:", self.layout_box)
        self.gm_hint = hint("בדף גמרא: בלשונית של כל פירוש בחרו מיקום \"צד פנימי\" (ליד הכריכה, כמו רש\"י) "
                            "או \"צד חיצוני\" (כמו תוספות). פירוש נוסף יכול להיות \"מתחת לטקסט\" או \"אחרי כל פסוק\".")
        self.gm_hint.setWordWrap(True)
        form.addRow(self.gm_hint)
        self.gm_band_lbl = QLabel("שורות פירוש מעל הפסוקים:")
        form.addRow(self.gm_band_lbl, self.sp["gmBand"])
        self.gm_main_lbl = QLabel("רוחב טור הפסוקים:")
        form.addRow(self.gm_main_lbl, self.sp["gmMain"])
        form.addRow("גודל עמוד:", self.page_size)
        dims = QHBoxLayout()
        dims.addWidget(QLabel("רוחב:"))
        dims.addWidget(self.sp["pageW"])
        dims.addWidget(QLabel("גובה:"))
        dims.addWidget(self.sp["pageH"])
        form.addRow(dims)
        fit = QPushButton("התאמת גופנים ושוליים לגודל העמוד")
        fit.setToolTip("מקטין או מגדיל את האותיות, השוליים והרווחים ביחס לגודל העמוד (לעומת A4)")
        fit.clicked.connect(self.fit_to_page)
        form.addRow(fit)
        form.addRow("שוליים:", self.sp["margin"])
        self.sp["gutter"].setToolTip("בצורת ספר: תוספת לשוליים בצד הפנימי, שנבלע בכריכה")
        form.addRow("תוספת לשוליים הפנימיים (כריכה):", self.sp["gutter"])
        form.addRow("גופן הטקסט:", self.main_font)
        form.addRow("גודל הטקסט:", self.sp["mainSize"])
        form.addRow("מרווח שורות:", self.sp["lineHeight"])
        form.addRow("רווח בין טורים:", self.sp["colGap"])
        form.addRow("רווח בין חלקי העמוד:", self.sp["sectionGap"])
        form.addRow("מינימום שורות טקסט בעמוד:", self.sp["minLines"])
        form.addRow("מספר העמוד הראשון:", self.sp["firstPage"])
        self.ded = QPlainTextEdit()
        self.ded.setMaximumHeight(56)
        self.ded.setToolTip("נכתב באותיות קטנות בתחתית העמוד הראשון. שורה חדשה = שורה נפרדת. ריק = בלי הקדשה.")
        form.addRow("הקדשה בעמוד הראשון:", self.ded)
        self.title_sub = QLineEdit()
        self.title_sub.setPlaceholderText("ריק = לפי הפירושים, למשל: עם תרגום אונקלוס, רש\"י ורמב\"ן")
        form.addRow("כיתוב בשער מתחת לשם:", self.title_sub)
        self.cb = {
            "verseNewLine": QCheckBox("כל פסוק בשורה חדשה"),
            "numbers": QCheckBox("אותיות פסוקים"),
            "header": QCheckBox("כותרת עליונה ומספר עמוד"),
            "names": QCheckBox("שם המתרגם / המפרש מעל כל טור"),
            "inlineChapters": QCheckBox("פרק בתוך הטקסט (אות הפרק גדולה ומודגשת, בלי שורת כותרת)"),
            "bookMode": QCheckBox("צורת ספר: התרגום תמיד בצד הפנימי (העמוד הראשון שמאלי)"),
            "titlePage": QCheckBox("עמוד שער (שם הספר, הפירושים וההקדשה)"),
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
        side.addTab(area, "עימוד")
        side.addTab(self.build_cover(), "כריכה")
        side.currentChanged.connect(lambda _: self.cover_timer.start())    # drawn to the width it is shown at
        # the mouse wheel scrolls the settings, it doesn't change a number or a choice it
        # happens to pass over (only one that was clicked first)
        self.wheel_guard = WheelGuard(self)
        for child in w.findChildren(QWidget) + self.cover_box.findChildren(QWidget):
            if isinstance(child, (QAbstractSpinBox, QComboBox)):
                child.setFocusPolicy(Qt.StrongFocus)
                child.installEventFilter(self.wheel_guard)

        self.title.textChanged.connect(self.changed)
        self.main.textChanged.connect(self.changed)
        self.page_size.currentIndexChanged.connect(self.page_size_changed)
        self.layout_box.currentIndexChanged.connect(self.changed)
        self.main_font.currentFontChanged.connect(self.changed)
        for s in self.sp.values():
            s.valueChanged.connect(self.changed)
        for c in self.cb.values():
            c.toggled.connect(self.changed)
        self.ded.textChanged.connect(self.changed)
        self.title_sub.textChanged.connect(self.changed)
        return side

    def build_cover(self):
        """The cover: the front, the spine and the back in one spread, for the printer. Its
        settings are kept in the project; a change shows at once in the picture above them."""
        area = QScrollArea()
        area.setWidgetResizable(True)
        self.cover_area = area
        w = QWidget()
        self.cover_box = w
        lay = QVBoxLayout(w)
        self.cover_view = QLabel()
        self.cover_view.setAlignment(Qt.AlignCenter)
        self.cover_view.setMinimumHeight(200)
        self.cover_view.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)   # the picture follows the tab's width
        lay.addWidget(self.cover_view)
        self.cover_info = QLabel()
        self.cover_info.setWordWrap(True)
        self.cover_info.setStyleSheet("color:#444;")
        lay.addWidget(self.cover_info)
        lay.addWidget(hint("משמאל החזית, באמצע השדרה ומימין הגב (ספר עברי נפתח מימין). הקו המקווקו הוא קו החיתוך "
                           "וקפלי השדרה — הוא לא מודפס. הרקע ממשיך מעבר לקו החיתוך (שוליים לחיתוך, bleed)."))

        box = QGroupBox("עיצוב")
        form = QFormLayout(box)
        self.cv_palette = QComboBox()
        for k, (name, _, _) in cover.PALETTES.items():
            self.cv_palette.addItem(name, k)
        form.addRow("צבעים:", self.cv_palette)
        row = QHBoxLayout()
        self.cv_bg = QPushButton("רקע")
        self.cv_ink = QPushButton("עיטור וכיתוב")
        self.cv_bg.clicked.connect(lambda: self.pick_cover_color("coverBg"))
        self.cv_ink.clicked.connect(lambda: self.pick_cover_color("coverInk"))
        row.addWidget(self.cv_bg)
        row.addWidget(self.cv_ink)
        form.addRow("צבע חופשי:", row)
        self.cv_font = QFontComboBox()
        self.cv_font.setWritingSystem(QFontDatabase.Hebrew)
        form.addRow("גופן:", self.cv_font)
        # the ornaments: each list shows a small picture of each choice, in the cover's colours
        self.cv_orn = {}
        for key, kind, names, label in (("coverFrame", "frame", cover.FRAMES, "מסגרת:"),
                                        ("coverCorner", "corner", cover.CORNERS, "עיטור בפינות:"),
                                        ("coverDivider", "divider", cover.DIVIDERS, "עיטור מתחת לשם:")):
            box_ = QComboBox()
            box_.setIconSize(QSize(72, 30))
            for k, name in names.items():
                box_.addItem(name, k)
            box_.currentIndexChanged.connect(self.cover_changed)
            form.addRow(label, box_)
            self.cv_orn[key] = (box_, kind)
        lay.addWidget(box)

        box = QGroupBox("חזית")
        form = QFormLayout(box)
        self.cv_title = QLineEdit()
        self.cv_title.setPlaceholderText("ריק = שם הספר")
        form.addRow("שם:", self.cv_title)
        self.cv_sub = QPlainTextEdit()
        self.cv_sub.setMaximumHeight(60)
        self.cv_sub.setPlaceholderText("ריק = כמו בשער (למשל: עם תרגום אונקלוס ורש\"י). שורה לכל שורה.")
        form.addRow("שורות מתחת לשם:", self.cv_sub)
        self.cv_foot = QLineEdit()
        self.cv_foot.setPlaceholderText("למשל: ירושלים תשפ\"ז, או שם ההוצאה")
        form.addRow("שורה בתחתית:", self.cv_foot)
        lay.addWidget(box)

        box = QGroupBox("שדרה")
        form = QFormLayout(box)
        self.cv_spine = QLineEdit()
        self.cv_spine.setPlaceholderText("ריק = השם שבחזית")
        form.addRow("שם:", self.cv_spine)
        self.cv_spine_sub = QLineEdit()
        self.cv_spine_sub.setPlaceholderText("למשל: רש\"י ואור החיים, או כרך א")
        form.addRow("אחריו (קטן יותר):", self.cv_spine_sub)
        self.cv_dir = QComboBox()
        for k, name in cover.SPINE_DIRS.items():
            self.cv_dir.addItem(name, k)
        form.addRow("כיוון הכיתוב:", self.cv_dir)
        self.cv_logo = self.image_row(form, "סמל (בתחתית השדרה):", "coverLogo")
        lay.addWidget(box)

        box = QGroupBox("גב")
        form = QFormLayout(box)
        self.cv_back = QPlainTextEdit()
        self.cv_back.setMinimumHeight(110)
        self.cv_back.setPlaceholderText("תיאור הספר, הקדשה… שורה ריקה = רווח בין פסקאות")
        form.addRow("טקסט:", self.cv_back)
        self.cv_barcode = self.image_row(form, "ברקוד (תמונה):", "coverBarcode")
        lay.addWidget(box)

        box = QGroupBox("מידות לדפוס (כריכה רכה)")
        form = QFormLayout(box)
        self.cv_paper = QDoubleSpinBox()
        self.cv_paper.setRange(0.03, 0.5)
        self.cv_paper.setSingleStep(0.01)
        self.cv_paper.setDecimals(3)
        self.cv_paper.setSuffix(" מ\"מ")
        self.cv_paper.setToolTip("העובי של דף אחד (שני עמודים). בערך: נייר 70 גרם 0.09, 80 גרם 0.1, 90 גרם 0.11, "
                                 "נייר דק (תנ\"כי) 0.05. בית הדפוס יודע לומר את המספר המדויק.")
        form.addRow("עובי דף (2 עמודים):", self.cv_paper)
        self.cv_spine_w = QDoubleSpinBox()
        self.cv_spine_w.setRange(0, 120)
        self.cv_spine_w.setSingleStep(0.5)
        self.cv_spine_w.setDecimals(1)
        self.cv_spine_w.setSuffix(" מ\"מ")
        self.cv_spine_w.setSpecialValueText("לפי מספר העמודים")
        form.addRow("רוחב השדרה:", self.cv_spine_w)
        self.cv_bleed = QDoubleSpinBox()
        self.cv_bleed.setRange(0, 10)
        self.cv_bleed.setSingleStep(0.5)
        self.cv_bleed.setDecimals(1)
        self.cv_bleed.setSuffix(" מ\"מ")
        form.addRow("שוליים לחיתוך (bleed):", self.cv_bleed)
        self.cv_marks = QCheckBox("סימני חיתוך מחוץ לשוליים")
        form.addRow(self.cv_marks)
        lay.addWidget(box)

        exp = QPushButton("ייצוא כריכה ל־PDF…")
        exp.setStyleSheet("font-weight:bold; padding:6px;")
        exp.clicked.connect(self.export_cover)
        lay.addWidget(exp)
        lay.addStretch(1)
        area.setWidget(w)

        for e in (self.cv_title, self.cv_foot, self.cv_spine, self.cv_spine_sub):
            e.textChanged.connect(self.cover_changed)
        for e in (self.cv_sub, self.cv_back):
            e.textChanged.connect(self.cover_changed)
        for e in (self.cv_palette, self.cv_dir):
            e.currentIndexChanged.connect(self.cover_changed)
        for e in (self.cv_paper, self.cv_spine_w, self.cv_bleed):
            e.valueChanged.connect(self.cover_changed)
        self.cv_marks.toggled.connect(self.cover_changed)
        self.cv_font.currentFontChanged.connect(self.cover_changed)
        return area

    def image_row(self, form, label, key):
        """A picture chosen from a file: its name, a button to choose it, and one to take it off."""
        row = QHBoxLayout()
        name = QLineEdit()
        name.setReadOnly(True)
        name.setPlaceholderText("אין")
        pick = QPushButton("בחירה…")
        clear = QPushButton("הסרה")

        def choose():
            start = os.path.dirname(self.project.get(key) or "") or self.settings.value("lastDir", "")
            path, _ = QFileDialog.getOpenFileName(self, label.rstrip(":"), start, "תמונה (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
            if path:
                self.project[key] = path
                self.cover_changed()

        def take_off():
            self.project[key] = ""
            self.cover_changed()

        pick.clicked.connect(choose)
        clear.clicked.connect(take_off)
        row.addWidget(name, 1)
        row.addWidget(pick)
        row.addWidget(clear)
        form.addRow(label, row)
        return name

    def pick_cover_color(self, key):
        bg, ink = cover.colors(self.project)
        c = QColorDialog.getColor(QColor(bg if key == "coverBg" else ink), self, "בחירת צבע")
        if not c.isValid():
            return
        self.project["coverBg"], self.project["coverInk"] = bg, ink
        self.project[key] = c.name()
        self.loading = True
        self.cv_palette.setCurrentIndex(list(cover.PALETTES).index("custom"))
        self.loading = False
        self.cover_changed()

    def fill_cover(self):
        p = self.project
        self.cv_palette.setCurrentIndex(list(cover.PALETTES).index(p["coverPalette"]) if p["coverPalette"] in cover.PALETTES else 0)
        self.cv_font.setCurrentFont(QFont(p.get("coverFont") or p["mainFont"]))
        for key, (box_, _) in self.cv_orn.items():
            i = box_.findData(p.get(key))
            box_.setCurrentIndex(max(0, i))
        self.cv_title.setText(p["coverTitle"])
        self.cv_sub.setPlainText(p["coverSub"])
        self.cv_foot.setText(p["coverFoot"])
        self.cv_spine.setText(p["coverSpine"])
        self.cv_spine_sub.setText(p["coverSpineSub"])
        self.cv_dir.setCurrentIndex(list(cover.SPINE_DIRS).index(p["coverSpineDir"]) if p["coverSpineDir"] in cover.SPINE_DIRS else 0)
        self.cv_back.setPlainText(p["coverBack"])
        self.cv_paper.setValue(float(p["coverPaper"] or 0.1))
        self.cv_spine_w.setValue(float(p["coverSpineW"] or 0))
        self.cv_bleed.setValue(float(p["coverBleed"]))
        self.cv_marks.setChecked(bool(p["coverMarks"]))
        self.show_cover_fields()

    def read_cover(self):
        p = self.project
        p["coverPalette"] = self.cv_palette.currentData()
        font = self.cv_font.currentFont().family()
        p["coverFont"] = "" if font == p["mainFont"] else font
        for key, (box_, _) in self.cv_orn.items():
            p[key] = box_.currentData()
        p["coverTitle"] = self.cv_title.text()
        p["coverSub"] = self.cv_sub.toPlainText()
        p["coverFoot"] = self.cv_foot.text()
        p["coverSpine"] = self.cv_spine.text()
        p["coverSpineSub"] = self.cv_spine_sub.text()
        p["coverSpineDir"] = self.cv_dir.currentData()
        p["coverBack"] = self.cv_back.toPlainText()
        p["coverPaper"] = self.cv_paper.value()
        p["coverSpineW"] = self.cv_spine_w.value()
        p["coverBleed"] = self.cv_bleed.value()
        p["coverMarks"] = self.cv_marks.isChecked()
        self.show_cover_fields()

    def show_cover_fields(self):
        """The chosen colours on their buttons, and the names of the chosen pictures."""
        bg, ink = cover.colors(self.project)
        for b, c in ((self.cv_bg, bg), (self.cv_ink, ink)):
            text = "white" if QColor(c).lightness() < 128 else "black"
            b.setStyleSheet(f"QPushButton {{ background:{c}; color:{text}; padding:4px 12px; border:1px solid #888; border-radius:4px; }}")
        if (bg, ink) != getattr(self, "orn_colors", None):
            self.orn_colors = (bg, ink)
            for box_, kind in self.cv_orn.values():
                for i in range(box_.count()):
                    box_.setItemIcon(i, QIcon(QPixmap.fromImage(cover.sample(kind, box_.itemData(i), bg, ink, 144, 60))))
        for e, key in ((self.cv_logo, "coverLogo"), (self.cv_barcode, "coverBarcode")):
            path = self.project.get(key) or ""
            e.setText(os.path.basename(path) + ("" if not path or os.path.isfile(path) else "  (הקובץ לא נמצא)"))
            e.setToolTip(path)

    def cover_changed(self, *_):
        """A change on the cover: kept like any change, but the pages need no new layout."""
        if self.loading:
            return
        self.read_cover()
        self.dirty = True
        self.save_recovery()
        self.autosave.start()
        self.cover_timer.start()

    def current_cover(self):
        subs = self.engine.title_lines() if self.engine else []
        return cover.make_cover(self.project, len(self.pages), subs)

    def show_cover(self):
        """The cover drawn small in its tab, and its measures."""
        if not hasattr(self, "cover_view"):
            return
        c = self.current_cover()
        ratio = self.devicePixelRatioF()
        room = max(240, self.cover_area.viewport().width() - 30)
        k = room / c.width
        img = cover.cover_image(c, k * ratio)
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(ratio)
        self.cover_view.setPixmap(pm)
        w, h = c.size_mm()
        spine = c.spine / cover.MM
        note = ""
        if spine < 5 and self.project.get("coverSpineDir") != "across":
            note = " · השדרה צרה — אין בה מקום לכיתוב ברור" if spine < 3 else " · השדרה צרה: הכיתוב בה קטן"
        if not self.pages:
            note += " · עוד אין עמודים (מעמד…)"
        self.cover_info.setText(f"<b>כריכה {w:.1f}×{h:.1f} מ\"מ</b> (כולל שוליים לחיתוך) · עמוד {c.w / cover.MM:.0f}×{c.h / cover.MM:.0f} · "
                                f"שדרה {spine:.1f} מ\"מ לפי {len(self.pages)} עמודים{note}")

    def export_cover(self):
        if self.stale and not self.running:
            self.request_relayout()     # the spine is as wide as the book is now
        if self.running or not self.pages:
            QMessageBox.information(self, APP_NAME, "העימוד עדיין רץ (רוחב השדרה תלוי במספר העמודים), נסו שוב בעוד רגע.")
            return
        for key, what in (("coverBarcode", "הברקוד"), ("coverLogo", "הסמל")):
            path = self.project.get(key)
            if path and not os.path.isfile(path):
                if QMessageBox.question(self, APP_NAME, f"התמונה של {what} לא נמצאה:\n{path}\n\nלייצא בלעדיה?") != QMessageBox.Yes:
                    return
        base = os.path.splitext(self.path)[0] if self.path else os.path.join(self.settings.value("lastDir", ""), self.project["title"] or "עימוד")
        path, _ = QFileDialog.getSaveFileName(self, "ייצוא כריכה", base + " - כריכה.pdf", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        c = self.current_cover()
        try:
            cover.export_cover(c, path, self.project["title"])
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"הייצוא נכשל:\n{e}")
            return
        self.settings.setValue("lastDir", os.path.dirname(path))
        w, h = c.size_mm()
        if QMessageBox.question(self, APP_NAME, f"נשמר: {path}\n\nגודל {w:.1f}×{h:.1f} מ\"מ, שדרה {c.spine / cover.MM:.1f} מ\"מ "
                                f"({len(self.pages)} עמודים). כדאי לבדוק את רוחב השדרה מול בית הדפוס.\n\nלפתוח את הקובץ?") == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def open_prepare(self):
        """The window for preparing text (it keeps what was pasted while it is closed)."""
        if getattr(self, "prep_dlg", None) is None:
            self.prep_dlg = QDialog(self)
            self.prep_dlg.setWindowTitle("הכנת טקסט")
            self.prep_dlg.resize(900, 760)
            QVBoxLayout(self.prep_dlg).addWidget(self.build_prepare())
        self.prep_targets()
        self.prep_dlg.show()
        self.prep_dlg.raise_()
        self.prep_dlg.activateWindow()

    def build_prepare(self):
        """Text as it comes (running text, copied from a site or a PDF) made ready for the
        program and put into the main text or a commentary."""
        box = QWidget()
        self.prep_box = box
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(hint(
            "הדביקו כאן טקסט בכל צורה (מלל רץ, העתקה מאתר או מ־PDF) ולחצו <b>הכן</b>. "
            "<b>טקסט עיקרי:</b> כל פסוק לשורה (לפי הנקודתיים שבסוף פסוק, או לפי מספרי פסוקים כמו (א) {א} [א]), "
            "\"פרשת…\" ← <b># פרשת…</b>, \"פרק…\" ← <b># פרק…</b>, \"הפטרת…\" ← <b>## הפטרת…</b>. "
            "<b>פירוש:</b> קטע שמתחיל במספר פסוק ((א), פסוק א, אחרי שורת \"פרק ב\") מקבל <b>@</b> של הפסוק בטקסט העיקרי."))
        row = QHBoxLayout()
        row.addWidget(QLabel("זה:"))
        self.prep_target = QComboBox()
        row.addWidget(self.prep_target, 1)
        go = QPushButton("הכן ▼")
        go.setStyleSheet("font-weight:bold; padding:4px 18px;")
        go.clicked.connect(self.prepare_text)
        row.addWidget(go)
        lay.addLayout(row)
        split = QSplitter(Qt.Vertical)
        self.prep_in = hebrew_edit(size=12)
        self.prep_in.setPlaceholderText("הדביקו כאן את הטקסט…")
        self.prep_out = hebrew_edit(size=12)
        self.prep_out.setPlaceholderText("כאן יופיע הטקסט המוכן (אפשר לתקן בו לפני שמכניסים)")
        split.addWidget(self.prep_in)
        split.addWidget(self.prep_out)
        lay.addWidget(split, 1)
        self.prep_report = QLabel()
        self.prep_report.setWordWrap(True)
        self.prep_report.setStyleSheet("color:#15803d;")
        lay.addWidget(self.prep_report)
        row = QHBoxLayout()
        b1 = QPushButton("הכנס במקום מה שיש")
        b1.clicked.connect(lambda: self.insert_prepared(False))
        b2 = QPushButton("הוסף בסוף")
        b2.clicked.connect(lambda: self.insert_prepared(True))
        row.addWidget(b1)
        row.addWidget(b2)
        lay.addLayout(row)
        return box

    def prep_targets(self):
        cur = self.prep_target.currentIndex() if self.prep_target.count() else 0
        self.prep_target.blockSignals(True)
        self.prep_target.clear()
        self.prep_target.addItem("הטקסט העיקרי (פסוקים)", -1)
        for i in range(self.tabs.count() if hasattr(self, "tabs") else 0):
            self.prep_target.addItem(f"פירוש: {self.tabs.widget(i).comm['name'] or '—'}", i)
        self.prep_target.setCurrentIndex(min(cur, self.prep_target.count() - 1))
        self.prep_target.blockSignals(False)

    def prepare_text(self):
        from .prepare import prepare_comm, prepare_main
        raw = self.prep_in.toPlainText()
        if not raw.strip():
            return
        if self.prep_target.currentData() == -1:
            text, report, title = prepare_main(raw)
            self.prep_title = title
            if title:
                report += f" · שם הספר: {title}"
        else:
            text, report = prepare_comm(raw, self.project["main"])
            self.prep_title = None
        self.prep_out.setPlainText(text)
        self.prep_report.setText(report)

    def insert_prepared(self, append):
        text = self.prep_out.toPlainText().strip()
        if not text:
            return
        target = self.prep_target.currentData()
        edit = self.main if target == -1 else self.tabs.widget(target).text
        old = edit.toPlainText().rstrip()
        edit.setPlainText((old + "\n" + text) if append and old else text)
        if target == -1 and getattr(self, "prep_title", None) and not self.title.text().strip():
            self.title.setText(self.prep_title)
        self.prep_report.setText("הוכנס. לחצו על עימוד מחדש כדי לראות את התוצאה.")
        self.prep_dlg.hide()

    def build_preview(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.info = QLabel("מעמד…")
        self.info.setStyleSheet("padding:6px; color:#444;")
        lay.addWidget(self.info)
        self.warn = QLabel()
        self.warn.setWordWrap(True)
        self.warn.setTextFormat(Qt.RichText)
        self.warn.linkActivated.connect(self.open_problem)
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
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 8)
        self.stale_lbl = QLabel("")
        self.stale_lbl.setStyleSheet("color:#7c3a06;")
        self.relayout_btn = QPushButton("עימוד מחדש  (F5)")
        self.relayout_btn.setShortcut("F5")
        self.relayout_btn.setMinimumHeight(34)
        self.relayout_btn.clicked.connect(self.request_relayout)
        bar.addWidget(self.relayout_btn)
        bar.addWidget(self.stale_lbl, 1)
        lay.addLayout(bar)
        self.set_stale(False)
        return w

    def set_stale(self, stale):
        """Changes not yet laid out: the button stands out until it is pressed."""
        self.stale = stale
        self.stale_lbl.setText("יש שינויים שעוד לא עומדו — לחצו על עימוד מחדש" if stale else "")
        self.relayout_btn.setStyleSheet(
            "QPushButton { background:#b45309; color:white; font-weight:bold; padding:4px 18px; border-radius:6px; }"
            if stale else "QPushButton { padding:4px 18px; }")

    def request_relayout(self):
        self.generation += 1
        self.relayout()

    # ---------------------------------------------------------------- project <-> editor

    def fill_editor(self):
        self.loading = True
        p = self.project
        self.title.setText(p["title"])
        self.main.setPlainText(p["main"])
        self.page_size.setCurrentIndex(list(model.PAGE_SIZES).index(p["pageSize"]))
        w, h = model.page_mm(p)
        self.sp["pageW"].setEnabled(p["pageSize"] == "custom")
        self.sp["pageH"].setEnabled(p["pageSize"] == "custom")
        self.main_font.setCurrentFont(QFont(p["mainFont"]))
        for k, s in self.sp.items():
            s.setValue(p[k])
        self.sp["pageW"].setValue(w)
        self.sp["pageH"].setValue(h)
        for k, c in self.cb.items():
            c.setChecked(bool(p[k]))
        self.layout_box.setCurrentIndex(1 if p.get("layout") == "gemara" else 0)
        self.update_layout_fields()
        self.ded.setPlainText(p.get("dedication", ""))
        self.title_sub.setText(p.get("titleSub", ""))
        self.fill_cover()
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
        p["layout"] = self.layout_box.currentData()
        self.update_layout_fields()
        p["dedication"] = self.ded.toPlainText()
        p["titleSub"] = self.title_sub.text()
        self.read_cover()
        p["comms"] = [self.tabs.widget(i).comm for i in range(self.tabs.count())]
        for i in range(self.tabs.count()):
            self.tabs.setTabText(i, self.tabs.widget(i).comm["name"] or "—")

    def update_layout_fields(self):
        """The settings of a Talmud page only when it is chosen."""
        gm = self.layout_box.currentData() == "gemara"
        for w in (self.gm_hint, self.gm_band_lbl, self.sp["gmBand"], self.gm_main_lbl, self.sp["gmMain"]):
            w.setVisible(gm)

    def changed(self, *_):
        if self.loading:
            return
        self.read_editor()
        self.dirty = True
        self.edits = getattr(self, "edits", 0) + 1
        self.update_statuses()
        self.save_recovery()
        self.autosave.start()
        self.set_stale(True)

    def loaded(self):
        """A project was opened (or started): show it laid out; nothing to save yet."""
        self.autosave.stop()
        self.dirty = False
        self.update_statuses()
        self.save_recovery()
        self.update_title()
        self.request_relayout()

    def my_projects_dir(self):
        """Where projects without a file of their own are kept (a new one, or a ready one
        that was changed): a folder in Documents."""
        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or os.path.expanduser("~")
        folder = os.path.join(docs, APP_NAME)
        os.makedirs(folder, exist_ok=True)
        return folder

    def save_quietly(self):
        """Every change is kept: in the project's file, or (for a project that has none yet)
        in a new file in the projects folder."""
        if not self.dirty:
            return
        if not self.path:
            name = getattr(self, "copy_name", None) or self.project.get("title") or ""
            name = re.sub(r'[\\/:*?"<>|]', "", name) or "פרויקט חדש"
            folder = self.my_projects_dir()
            path, k = os.path.join(folder, name + ".json"), 2
            while os.path.exists(path):
                path, k = os.path.join(folder, f"{name} ({k}).json"), k + 1
            self.path = path
        try:
            model.save_project(self.project, self.path)
        except OSError:
            return
        self.dirty = False
        self.update_title()
        self.save_recovery()

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

    def page_size_changed(self, *_):
        """Show the chosen size in the width / height boxes; they are editable for 'custom'."""
        key = self.page_size.currentData()
        custom = key == "custom"
        if not custom and not self.loading:
            _, w, h = model.PAGE_SIZES[key]
            self.loading = True
            self.sp["pageW"].setValue(w)
            self.sp["pageH"].setValue(h)
            self.loading = False
        self.sp["pageW"].setEnabled(custom)
        self.sp["pageH"].setEnabled(custom)
        self.changed()

    def fit_to_page(self):
        """Scale the fonts, margins and gaps by the page width compared with A4, for a book
        printed smaller (or larger) than the A4 the projects were set up for."""
        w, _ = model.page_mm(self.project)
        k = w / 210.0
        p = self.project
        p["mainSize"] = round(max(7.0, p["mainSize"] * k) * 2) / 2
        p["margin"] = round(max(5.0, p["margin"] * k))
        p["colGap"] = round(max(2.0, p["colGap"] * k) * 2) / 2
        p["sectionGap"] = round(max(1.0, p["sectionGap"] * k) * 2) / 2
        for c in p["comms"]:
            c["size"] = round(max(6.0, c["size"] * k) * 2) / 2
        self.fill_editor()
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
        edits = getattr(self, "edits", 0)
        self.info.setText("מעמד…")
        _log("מתחיל לעמד")

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
        self.engine = eng
        self.cover_timer.start()
        self.set_stale(getattr(self, "edits", 0) != edits)
        _log(f"עימוד: {len(pages)} עמודים")
        self.show_pages()
        _log("התצוגה מוכנה")
        sides = [f" · {self.project['comms'][c]['name']}: רוחב {round(eng.col_w[c])}%" for c in eng.sides]
        self.info.setText(f"{len(pages)} עמודים · {eng.count} פסוקים · {len(self.project['comms'])} פירושים{''.join(sides)}")
        self.show_problems(eng, pages)

    def show_problems(self, eng, pages):
        """The layout checked against the rules (RULES.md): faults and known exceptions, each
        with a link to its page."""
        try:
            problems = check(eng, pages)
        except Exception as e:  # a fault in the check must not stop the program
            _log(f"check failed: {e}")
            problems = []
        errors, known, warns = summary(problems)
        rows = []
        for p_ in errors + known:
            text = html.escape(describe(p_))
            if p_.page >= 0:
                text = f'<a href="page:{p_.page}">{text}</a>'
            rows.append(("⚠ " if p_.severity == "error" else "• ") + text)
        if not rows:
            self.warn.hide()
            return
        head = []
        if errors:
            head.append(f"<b>בדיקת עימוד: {len(errors)} תקלות</b>")
        if known:
            head.append(f"{len(known)} חריגים מותרים (ראו RULES.md)")
        more = len(rows) - 12
        self.warn.setText(" · ".join(head) + "<br>" + "<br>".join(rows[:12]) + (f"<br>ועוד {more}…" if more > 0 else ""))
        self.warn.show()

    def open_problem(self, link):
        if link.startswith("page:"):
            self.page_no.setValue(int(link[5:]) + 1)
            self.go_to_page()

    def show_pages(self):
        while self.pages_lay.count():
            item = self.pages_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        ratio = self.devicePixelRatioF()
        px_per_pt = self.zoom * 96 / 72 * ratio
        gen = self.generation
        self.draw_id = draw = getattr(self, "draw_id", 0) + 1
        for n, page in enumerate(self.pages):
            if n and n % 4 == 0:
                # a long book: let the window answer while its pages are drawn
                QApplication.processEvents()
                if self.generation != gen or self.draw_id != draw:
                    return
            img = page_image(page, px_per_pt)
            pm = QPixmap.fromImage(img)
            pm.setDevicePixelRatio(ratio)
            lbl = PageLabel(self, n, self.zoom * 96 / 72)
            lbl.setPixmap(pm)
            lbl.setFrameShape(QFrame.Box)
            lbl.setStyleSheet("background:white; border:1px solid #c9c4b8;")
            self.pages_lay.addWidget(lbl, 0, Qt.AlignHCenter)

    def page_clicked(self, n, x, y):
        """A click on the preview: open the line under it in the editor."""
        if not (0 <= n < len(self.pages)):
            return
        hit = None
        for x1, y1, x2, y2, to in getattr(self.pages[n], "links", []):
            if x1 - 2 <= x <= x2 + 2 and y1 <= y <= y2:
                hit = to
                break
        if hit is None:
            return
        if hit[0] == "main":
            self.side.setCurrentIndex(0)
            self.select_line(self.main, hit[1])
        else:
            _, c, v, k = hit
            if c >= self.tabs.count():
                return
            self.side.setCurrentIndex(1)
            self.tabs.setCurrentIndex(c)
            edit = self.tabs.widget(c).text
            self.select_line(edit, self.comm_line(edit.toPlainText(), v, k))

    @staticmethod
    def comm_line(text, v, k):
        """The line of a commentary's text that holds passage k of verse v (from 0): by
        reference ('@N'), or by order (line N)."""
        lines = text.replace("\r", "").split("\n")
        if not any(re.match(r"^\s*@\s*\d+", l) for l in lines):
            rows = [i for i, l in enumerate(lines) if not l.strip().startswith("#")]
            return rows[v] if v < len(rows) else 0
        cur, found = -1, []
        for i, l in enumerate(lines):
            m = re.match(r"^\s*@\s*(\d+)", l)
            if m:
                cur = int(m.group(1)) - 1
            if cur == v and l.strip() and not re.match(r"^\s*@\s*\d+\s*$", l):
                found.append(i)
        if not found:
            return 0
        return found[min(k, len(found) - 1)]

    def select_line(self, edit, line):
        block = edit.document().findBlockByNumber(max(0, line))
        cur = edit.textCursor()
        cur.setPosition(block.position())
        cur.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        edit.setTextCursor(cur)
        edit.centerCursor()
        edit.setFocus()

    def find_text(self, backward=False):
        """Find the next place (in the editor that is open) with what is in the search box."""
        word = self.search.text()
        if not word:
            return
        if self.side.currentIndex() == 1 and self.tabs.count():
            edit = self.tabs.currentWidget().text
        else:
            self.side.setCurrentIndex(0)
            edit = self.main
        # vowels and cantillation marks don't count: "קרבן" finds "קׇרְבָּנוֹ"
        text = edit.toPlainText()
        marks = re.compile("[\u0591-\u05C7]")
        plain, where = [], []
        for i, ch in enumerate(text):
            if not marks.match(ch):
                plain.append(ch)
                where.append(i)
        plain = "".join(plain)
        needle = marks.sub("", word)
        if not needle:
            return
        cur = edit.textCursor()
        here = cur.selectionStart() if backward else cur.selectionEnd()
        pos = next((k for k, i in enumerate(where) if i >= here), len(where))
        k = plain.rfind(needle, 0, max(0, pos - 1) + len(needle) - 1) if backward else plain.find(needle, pos)
        if k < 0:
            k = plain.rfind(needle) if backward else plain.find(needle)      # from the other end
        if k < 0:
            self.info.setText(f"\"{word}\" לא נמצא")
            return
        start = where[k]
        end = where[k + len(needle) - 1] + 1
        while end < len(text) and marks.match(text[end]):
            end += 1                     # the marks on the last letter go with it
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.KeepAnchor)
        edit.setTextCursor(cur)
        edit.centerCursor()
        edit.setFocus()

    def go_to_page(self):
        n = self.page_no.value() - 1
        if 0 <= n < self.pages_lay.count():
            w = self.pages_lay.itemAt(n).widget()
            if w:
                self.scroll.ensureWidgetVisible(w, 0, 0)
                self.scroll.verticalScrollBar().setValue(w.y())

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
        """Nothing to ask: what was changed is saved before another project is opened."""
        self.autosave.stop()
        self.save_quietly()
        return True

    def new_project(self):
        if not self.confirm_discard():
            return
        self.copy_name = None
        self.project = model.normalize({})
        self.path = None
        self.fill_editor()
        self.loaded()

    def load_example(self):
        if not self.confirm_discard():
            return
        self.copy_name = None
        self.project = model.example_project()
        self.path = None
        self.fill_editor()
        self.loaded()

    def open_project(self):
        if not self.confirm_discard():
            return
        start = self.settings.value("lastDir", "") or self.my_projects_dir()
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
        # a ready project is opened as a copy: once it is changed, it is kept under the same
        # name in the projects folder
        ready = os.path.abspath(path).startswith(os.path.abspath(self.projects_dir()))
        self.path = None if ready else path
        self.copy_name = os.path.splitext(os.path.basename(path))[0] if ready else None
        self.fill_editor()
        self.loaded()

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
        if self.stale and not self.running:
            self.request_relayout()     # the PDF shows what is in the editor now
        if self.running or not self.pages:
            QMessageBox.information(self, APP_NAME, "העימוד עדיין רץ, נסו שוב בעוד רגע.")
            return
        from PySide6.QtWidgets import QInputDialog
        rng, ok = QInputDialog.getText(
            self, "ייצוא PDF", f"אילו עמודים? (ריק = כל {len(self.pages)} העמודים; למשל 1-20 או 5,8,10-12 — לפי הסדר בתצוגה)")
        if not ok:
            return
        chosen = self.page_range(rng, len(self.pages))
        if chosen is None:
            QMessageBox.warning(self, APP_NAME, "לא הבנתי את טווח העמודים. כתבו למשל 1-20 או 5,8,10-12.")
            return
        base = os.path.splitext(self.path)[0] if self.path else os.path.join(self.settings.value("lastDir", ""), self.project["title"] or "עימוד")
        if len(chosen) < len(self.pages):
            base += f" (עמודים {rng.strip()})"
        path, _ = QFileDialog.getSaveFileName(self, "ייצוא PDF", base + ".pdf", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            export_pdf([self.pages[i] for i in chosen], path, self.project["title"])
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"הייצוא נכשל:\n{e}")
            return
        self.settings.setValue("lastDir", os.path.dirname(path))
        if QMessageBox.question(self, APP_NAME, f"נשמר: {path}\n\nלפתוח את הקובץ?") == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @staticmethod
    def page_range(text, n):
        """'1-20' / '5,8,10-12' / '' -> page indices (from 0), or None if it can't be read."""
        text = text.strip().replace(" ", "")
        if not text:
            return list(range(n))
        out = []
        for part in text.split(","):
            m = re.match(r"^(\d+)(?:-(\d+))?$", part)
            if not m:
                return None
            a = int(m.group(1))
            b = int(m.group(2) or a)
            if a > b:
                a, b = b, a
            out.extend(i - 1 for i in range(a, b + 1) if 1 <= i <= n)
        return sorted(set(out)) or None

    def import_sefaria(self):
        from .sefaria import convert
        QMessageBox.information(self, APP_NAME,
            "בחרו את קובצי הטקסט שהורדתם מספריא (ספר אחד): הפסוקים, ואם יש גם אונקלוס, רש\"י ורמב\"ן.\n"
            "להפטרות בחרו יחד איתם גם את ספרי הנביאים מאוצריא (ישעיהו, ירמיהו וכו').\n"
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
        self.loaded()

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
        # no question on closing: the work is saved, and opens again next time as it was
        self.autosave.stop()
        self.save_quietly()
        self.save_recovery()
        ev.accept()
