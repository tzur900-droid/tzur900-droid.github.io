"""report.html: what the check of the whole Shas found, masechet by masechet (from the
report that shas_book writes)."""
import html
import json

STYLE = """
:root{--bg:#f3f4f6;--sheet:#fff;--ink:#1d2228;--muted:#646c76;--rule:#d5d9de;--fix:#1f7a4d;--fix-bg:#dff3e8;
--open:#9a3b00;--open-bg:#fbe7d2}
@media (prefers-color-scheme:dark){:root{--bg:#15181c;--sheet:#1d2126;--ink:#e3e6ea;--muted:#9aa2ad;--rule:#343a42;
--fix:#7ad7a6;--fix-bg:#173a29;--open:#ffb36b;--open-bg:#4a2e12}}
body{background:var(--bg);color:var(--ink);font-family:"Frank Ruhl Libre","David",serif;direction:rtl;margin:0;
padding:20px max(16px,4vw)}
h1{margin:0 0 4px} .sub{color:var(--muted);margin-bottom:18px}
table{border-collapse:collapse;background:var(--sheet);width:100%;margin-bottom:22px}
th,td{border:1px solid var(--rule);padding:4px 8px;text-align:right;font-variant-numeric:tabular-nums}
th{background:var(--bg)}
details{background:var(--sheet);border:1px solid var(--rule);border-radius:6px;margin:8px 0;padding:6px 12px}
summary{cursor:pointer;font-weight:700}
.pill{display:inline-block;border-radius:9px;padding:0 7px;margin-inline-start:6px;font-size:.85em}
.fix{background:var(--fix-bg);color:var(--fix)} .open{background:var(--open-bg);color:var(--open)}
li{margin:3px 0} .w{color:var(--muted);font-size:.9em}
"""


def write(rep, path):
    e = html.escape
    out = [f"<!doctype html><meta charset='utf-8'><title>בדיקת הש\"ס</title><style>{STYLE}</style>",
           "<h1>בדיקת הרא\"ש והרי\"ף</h1>"]
    total = sum(f["pages"] for f in rep["files"])
    out.append(f"<div class='sub'>{len(rep['masechtot'])} מסכתות · {len(rep['files'])} קבצים · {total} עמודים</div>")
    out.append("<table><tr><th>קובץ</th><th>מסכתות</th><th>עמודים</th></tr>")
    for f in rep["files"]:
        out.append(f"<tr><td>{e(f['name'])}</td><td>{e(', '.join(f['masechtot']))}</td><td>{f['pages']}</td></tr>")
    out.append("</table>")
    out.append("<table><tr><th>מסכת</th><th>עמודים</th><th>רא\"ש</th><th>רי\"ף</th><th>ימים</th>"
               "<th>תוקן</th><th>לבדיקה</th></tr>")
    for m in rep["masechtot"]:
        fixed = sum(c["n"] for c in m["counts"] if c["fixed"])
        open_ = sum(c["n"] for c in m["counts"] if not c["fixed"])
        out.append(f"<tr><td>{e(m['name'])}</td><td>{m['pages']}</td><td>{m['rosh_pages']}</td><td>{m['rif_pages']}</td>"
                   f"<td>{m['days'][0]}–{m['days'][1]}</td><td>{fixed}</td><td>{open_}</td></tr>")
    out.append("</table>")
    for m in rep["masechtot"]:
        pills = "".join(f"<span class='pill {'fix' if c['fixed'] else 'open'}'>{e(c['label'])}: {c['n']}</span>"
                        for c in m["counts"])
        out.append(f"<details><summary>מסכת {e(m['name'])}{pills}</summary>")
        for c in m["counts"]:
            items = [x for x in m["issues"] if x["kind"] == c["kind"] and x["fixed"] == c["fixed"]]
            state = "תוקן" if c["fixed"] else "לבדיקה"
            out.append(f"<h4>{e(c['label'])} ({state})</h4><ul>")
            for x in items[:300]:
                detail = x.get("detail", "")
                out.append(f"<li><span class='w'>{e(x['where'])}</span> {e(x['text'] or detail)}</li>")
            if len(items) > 300:
                out.append(f"<li class='w'>ועוד {len(items) - 300}…</li>")
            out.append("</ul>")
        out.append("</details>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


if __name__ == "__main__":
    import sys
    write(json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2])
