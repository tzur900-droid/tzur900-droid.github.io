"""Temporary: which requests the yeshiva site makes to load a lesson (real Edge on Windows)."""
import re
from playwright.sync_api import sync_playwright

URLS = ["https://www.yeshiva.org.il/midrash/1120", "https://www.yeshiva.org.il/midrash/6592"]
heb = lambda t: len(re.findall(r"[א-ת]", t))
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(locale="he-IL")
    for u in URLS:
        print("=" * 20, u, flush=True)
        pg = ctx.new_page()
        seen = []

        def on_resp(r):
            try:
                if r.request.resource_type in ("xhr", "fetch", "document"):
                    body = r.text()
                    seen.append((r.request.method, r.url, r.status, r.headers.get("content-type", ""),
                                 len(body), heb(body), body[:500], r.request.post_data or ""))
            except Exception as e:
                seen.append(("?", r.url, 0, str(e), 0, 0, "", ""))
        pg.on("response", on_resp)
        pg.goto(u, wait_until="load", timeout=90000)
        pg.wait_for_timeout(12000)
        print("page text:", len(pg.inner_text("body")))
        for m, url, st, ct, n, h, head, post in sorted(seen, key=lambda x: -x[5])[:10]:
            print(m, st, n, "heb", h, ct, url[:300])
            if post:
                print("   POST DATA:", post[:400])
            if h > 30:
                print("   ", head.replace("\n", " ")[:500])
        pg.close()
    b.close()
