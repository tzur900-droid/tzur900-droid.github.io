"""Temporary: which requests the yeshiva site makes to load a lesson (to read it without a browser)."""
import re
from playwright.sync_api import sync_playwright

URLS = ["https://www.yeshiva.org.il/midrash/1120", "https://www.yeshiva.org.il/midrash/6592",
        "https://www.yeshiva.org.il/tags/%D7%97%D7%A0%D7%95%D7%9B%D7%94/3"]
heb = lambda t: len(re.findall(r"[א-ת]", t))
with sync_playwright() as p:
    b = p.chromium.launch()
    for u in URLS:
        print("=" * 20, u, flush=True)
        pg = b.new_page()
        seen = []

        def on_resp(r):
            try:
                ct = r.headers.get("content-type", "")
                if r.request.resource_type in ("xhr", "fetch") or "json" in ct:
                    body = r.text()
                    seen.append((r.request.method, r.url, r.status, ct, len(body), heb(body), body[:400]))
            except Exception as e:
                seen.append(("?", r.url, 0, str(e), 0, 0, ""))
        pg.on("response", on_resp)
        pg.goto(u, wait_until="networkidle", timeout=60000)
        for m, url, st, ct, n, h, head in sorted(seen, key=lambda x: -x[5])[:8]:
            print(m, st, n, "heb", h, ct, url)
            if h > 50:
                print("   ", head.replace("\n", " "))
        for m, url, st, ct, n, h, head in seen:
            if m == "POST":
                print("POST", url)
        pg.close()
    b.close()
