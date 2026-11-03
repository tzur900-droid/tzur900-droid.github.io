"""A browser inside the program (Qt WebEngine, Chromium): pages built by their own scripts, like
the yeshiva site, are opened here, without a window, and read after they finished loading.

Some sites (the yeshiva site among them) put a "verify you are human" check (Cloudflare) in
front of programs. The program does not try to get around it: it opens the page in a window,
the user passes the check, and the site's permission is kept (cookies in a profile of the
program's own), so the next pages open without a window.

The browser has to live in the window's thread (Qt's rule), while the collecting runs in the
background: render() sends the address to the window's thread and waits for the page there."""
import os
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


def _plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html or "", flags=re.S | re.I)))


def is_check(html):
    """Whether the page is a "verify you are human" check and not the page itself."""
    if not html:
        return False
    text = _plain(html)
    if re.search(r"Performing security verification|Verify you are human|Just a moment\.\.\.|Checking your browser",
                 text, re.I) and len(text) < 3000:
        return True
    return bool(re.search(r"cf-turnstile|cf_chl_opt|challenge-platform", html, re.I)) and len(text) < 1500


def render(url, timeout=75):
    """The page's HTML after its scripts ran, or "" (no browser, or the page did not open).
    When the site asks to verify a human, a window opens for the user to pass the check."""
    if _renderer is None:
        return ""
    html = _ask(url, False, timeout)
    if is_check(html):
        log("האתר מבקש לוודא שמדובר באדם — פותח חלון: סמנו 'אני אדם' (או המתינו), והחלון ייסגר מעצמו")
        html = _ask(url, True, 300)
        if html and not is_check(html):
            _renderer.checked_once = True
            log("האימות עבר — הדפים הבאים ייפתחו בלי חלון")
    return "" if is_check(html) else html


def _ask(url, visible, timeout):
    box = {"event": threading.Event(), "html": ""}
    _renderer.asked.emit(url, visible, timeout, box)
    box["event"].wait(timeout + 20)
    return box["html"]


def _profile_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    p = os.path.join(base, "rav", "browser")
    os.makedirs(p, exist_ok=True)
    return p


def _make():
    from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

    from .collect import UA

    class Renderer(QObject):
        asked = Signal(str, bool, int, object)

        def __init__(self):
            super().__init__()
            # a profile of its own, kept on disk: the permission a site gave after its check stays
            self.profile = QWebEngineProfile("rav", self)
            d = _profile_dir()
            self.profile.setPersistentStoragePath(d)
            self.profile.setCachePath(os.path.join(d, "cache"))
            try:
                self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
            except Exception:
                pass
            self.profile.setHttpUserAgent(UA)
            self.profile.setHttpAcceptLanguage("he,en;q=0.8")
            self.checked_once = None
            self.asked.connect(self.load)

        def load(self, url, visible, timeout, box):
            page = QWebEnginePage(self.profile, self)
            try:
                page.setAudioMuted(True)
            except Exception:
                pass
            view = None
            if visible:
                from PySide6.QtWebEngineWidgets import QWebEngineView
                view = QWebEngineView()
                view.setPage(page)
                view.setWindowTitle("ספר מהרב — האתר מבקש לוודא שאתם אדם: סמנו את התיבה, והחלון ייסגר מעצמו")
                view.resize(900, 700)
                view.setAttribute(Qt.WA_DeleteOnClose, False)
                view.show()
                view.raise_()
                view.activateWindow()
            state = {"done": False, "tries": 0, "last": -1}
            limit = max(10, timeout // 2)

            def finish(html):
                if state["done"]:
                    return
                state["done"] = True
                box["html"] = html or ""
                box["event"].set()
                if view is not None:
                    view.close()
                    view.deleteLater()
                page.deleteLater()

            def look():
                # ready when the page has text, it is not the check page, and it stopped growing
                def got(html):
                    if state["done"]:
                        return
                    n = len(_plain(html))
                    state["tries"] += 1
                    if is_check(html):
                        if not visible and state["tries"] > 6:      # a check: the window will be needed
                            finish(html)
                            return
                    elif n > 600 and n == state["last"]:
                        finish(html)
                        return
                    if state["tries"] > limit:
                        finish(html)
                        return
                    state["last"] = n
                    QTimer.singleShot(2000, look)
                page.toHtml(got)

            page.loadFinished.connect(lambda ok: QTimer.singleShot(1500, look))
            QTimer.singleShot(timeout * 1000, lambda: None if state["done"] else page.toHtml(finish))
            page.load(QUrl(url))

    return Renderer()
