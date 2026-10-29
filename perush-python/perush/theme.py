"""The look of the program: a calm, warm (cream) modern theme (Qt's Fusion style and one style sheet)."""
import os
import tempfile

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPalette, QPen

BG = "#f3eee2"         # the window
SURFACE = "#fbf8f0"    # cards, fields, the toolbar (cream)
BORDER = "#e2d9c6"
TEXT = "#2b2620"
MUTED = "#776c5a"
ACCENT = "#5c5142"     # the colour of the text, a little lighter (no bright colour)
ACCENT_DARK = "#2b2620"
ACCENT_SOFT = "#efe6d3"
PAGES_BG = "#e8e0cf"   # behind the pages of the preview

STYLE = f"""
QWidget {{ color: {TEXT}; }}
QMainWindow, QDialog {{ background: {BG}; }}

QToolBar {{
    background: {SURFACE}; border: none; border-bottom: 1px solid {BORDER};
    padding: 4px 6px; spacing: 2px;
}}
QToolBar::separator {{ background: {BORDER}; width: 1px; margin: 4px 6px; }}
QToolButton {{
    background: transparent; border: none; border-radius: 8px; padding: 5px 8px; color: {TEXT};
}}
QToolButton:hover {{ background: {ACCENT_SOFT}; color: {ACCENT_DARK}; }}
QToolButton:pressed {{ background: #e6dcc6; }}
QToolButton#primary {{ font-weight: 600; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}

QGroupBox {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;
    margin-top: 14px; padding: 14px 12px 10px 12px; font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top right; right: 14px; padding: 0 6px;
    color: {MUTED};
}}
QGroupBox QWidget {{ font-weight: normal; }}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QFontComboBox {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 5px 8px;
    selection-background-color: {ACCENT}; selection-color: white;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QFontComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QSpinBox, QDoubleSpinBox {{ padding: 3px 4px; min-height: 24px; }}
QComboBox {{ combobox-popup: 0; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: url(ARROW); width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
    selection-background-color: {ACCENT_SOFT}; selection-color: {ACCENT_DARK}; padding: 4px;
}}

QPushButton {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 7px 14px;
}}
QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT_DARK}; }}
QPushButton:pressed {{ background: {ACCENT_SOFT}; }}
QPushButton#primary {{ font-weight: 600; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border: 1px solid #bfb39c; border-radius: 4px; background: {SURFACE};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent; border: none; border-bottom: 2px solid transparent;
    padding: 8px 16px; color: {MUTED};
}}
QTabBar::tab:selected {{ color: {ACCENT_DARK}; border-bottom: 2px solid {ACCENT}; font-weight: 600; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #cfc4ae; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #b3a78f; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #cfc4ae; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}

QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}

QMenu {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT_SOFT}; color: {ACCENT_DARK}; }}

QToolTip {{ background: {TEXT}; color: white; border: none; padding: 6px 8px; border-radius: 6px; }}
QStatusBar {{ background: {SURFACE}; border-top: 1px solid {BORDER}; }}
QLabel#info {{ color: {MUTED}; padding: 6px 8px; }}
QLabel#warn {{
    background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412; padding: 8px 10px; border-radius: 10px;
}}
QLabel#page {{ background: white; border: 1px solid #d6ccb8; border-bottom: 2px solid #c9bea8; }}
QWidget#pages {{ background: {PAGES_BG}; }}
"""


def apply(app):
    """Set the theme on the whole program."""
    app.setStyle("Fusion")
    pal = QPalette()
    for role, color in ((QPalette.Window, BG), (QPalette.Base, SURFACE), (QPalette.AlternateBase, BG),
                        (QPalette.Text, TEXT), (QPalette.WindowText, TEXT), (QPalette.Button, SURFACE),
                        (QPalette.ButtonText, TEXT), (QPalette.Highlight, ACCENT), (QPalette.HighlightedText, "#ffffff"),
                        (QPalette.ToolTipBase, TEXT), (QPalette.ToolTipText, "#ffffff"), (QPalette.PlaceholderText, "#a39883")):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    f = QFont(app.font())
    f.setPointSizeF(max(f.pointSizeF(), 10))
    app.setFont(f)
    app.setStyleSheet(STYLE.replace("ARROW", arrow_file()))


def arrow_file():
    """The little arrow of a list (a style sheet takes a picture only from a file)."""
    path = os.path.join(tempfile.gettempdir(), "perush-arrow.png")
    img = QImage(20, 20, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(MUTED), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPolyline([QPointF(3, 7), QPointF(10, 14), QPointF(17, 7)])
    p.end()
    img.save(path)
    return path.replace(os.sep, "/")
