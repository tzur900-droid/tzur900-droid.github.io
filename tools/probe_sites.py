"""Diagnostics on a Windows runner: how the program reads lesson sites (direct, Edge)."""
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rav-python"))
import requests  # noqa: E402
from rav import collect  # noqa: E402

URLS = sys.argv[1:] or [
    "https://www.yeshiva.org.il/midrash/6592",
    "https://www.yeshiva.org.il/midrash/1120",
    "https://www.yeshiva.org.il/tags/%D7%97%D7%A0%D7%95%D7%9B%D7%94/3",
    "https://www.inn.co.il/news/532664",
    "https://meirtv.com/shiurim/shiur-13522/",
]
heb = lambda t: len(re.findall(r"[א-ת]", t))
print("browser:", collect.find_browser(), flush=True)
for u in URLS:
    print("=" * 30, u, flush=True)
    try:
        r = requests.get(u, headers={"User-Agent": collect.UA, "Accept-Language": "he,en;q=0.8"}, timeout=60)
        r.encoding = r.apparent_encoding if (r.encoding or "").lower() in ("iso-8859-1", "ascii", "") else r.encoding
        h = r.text
        t = collect.text_of_html(h)
        print("direct:", r.status_code, r.headers.get("content-type"), "html", len(h), "heb", heb(h), "text", len(t),
              "| next", "__NEXT_DATA__" in h, "nuxt", "__NUXT__" in h, "cf", "cloudflare" in h.lower() or "cf-" in str(r.headers).lower())
        print("direct text:", t[:300].replace("\n", " | "))
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", h, re.S)
        big = sorted(scripts, key=heb, reverse=True)[:2]
        for s in big:
            print("script heb", heb(s), "len", len(s), ":", s[:300].replace("\n", " "))
        print("api-like urls:", sorted(set(re.findall(r"https?://[^\"' ]*api[^\"' ]*", h)))[:10])
    except Exception as e:
        print("direct failed:", e)
    t0 = time.time()
    b = collect.render(u)
    bt = collect.text_of_html(b) if b else ""
    print(f"edge: {time.time() - t0:.1f}s html", len(b), "heb", heb(b), "text", len(bt))
    print("edge text:", bt[:600].replace("\n", " | "))
    if "/tags/" in u or "filter" in u:
        print("links:", collect.lesson_links(b or "", u)[:10])
