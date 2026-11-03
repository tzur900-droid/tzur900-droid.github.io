"""A browser inside the program (Qt WebEngine, Chromium): pages built by their own scripts, like
the yeshiva site, are opened here, without a window, and read after they finished loading.

It has to live in the window's thread (Qt's rule), while the collecting runs in the background:
render() sends the address to the window's thread and waits for the page there."""
import re
import threading

from .log import log

_renderer = None


def start(app=None):
    """Make the browser (in the window's thread, after QApplication). False if it is missing."""
    global _renderer
    if _renderer is not None:
        return True
    try:
        _renderer = _make()
        return True
    except Exception as e:
        log(f"הדפדפן המובנה לא זמין: {type(e).__name__}: {e}")
        return False


def available():
    return _renderer is not None


def render(url, timeout=75):
    """The page's HTML after its scripts ran, or "" (no browser, or the page did not open)."""
    if _renderer is None:
        return ""
    box = {"event": threading.Event(), "html": ""}
    _renderer.asked.emit(url, box)
    box["event"].wait(timeout + 15)
    return box["html"]


def _make():
    from PySide6.QtCore import QObject, QTimer, QUrl, Signal
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

    from .collect import UA

    class Renderer(QObject):
        asked = Signal(str, object)

        def __init__(self):
            super().__init__()
            self.profile = QWebEngineProfile(self)          # off the record: nothing kept on disk
            self.profile.setHttpUserAgent(UA)
            self.profile.setHttpAcceptLanguage("he,en;q=0.8")
            self.asked.connect(self.load)

        def load(self, url, box):
            page = QWebEnginePage(self.profile, self)
            try:
                page.setAudioMuted(True)
            except Exception:
                pass
            state = {"done": False, "tries": 0, "last": -1}

            def finish(html):
                if state["done"]:
                    return
                state["done"] = True
                box["html"] = html or ""
                box["event"].set()
                page.deleteLater()

            def look():
                # the page is ready when it has text and it stopped growing (a security check
                # page, like Cloudflare's, first shows a few words and then moves on by itself)
                def got(text):
                    if state["done"]:
                        return
                    n = len(text or "")
                    checking = bool(re.search(r"security verification|Just a moment|Checking your browser",
                                              text or "", re.I))
                    state["tries"] += 1
                    if (n > 600 and not checking and n == state["last"]) or state["tries"] > 30:
                        page.toHtml(finish)
                    else:
                        state["last"] = n
                        QTimer.singleShot(2000, look)
                page.toPlainText(got)

            page.loadFinished.connect(lambda ok: QTimer.singleShot(1500, look))
            QTimer.singleShot(75000, lambda: None if state["done"] else page.toHtml(finish))  # never for ever
            page.load(QUrl(url))

    return Renderer()
