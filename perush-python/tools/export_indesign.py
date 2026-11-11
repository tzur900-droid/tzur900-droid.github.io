"""Export a masechet for laying it out in InDesign: the text as it would be printed (every word
with its character style: the Rif's wording in the Rosh, the dibbur, Rashi's wording, the amud
marks, references, editors' notes), the commentary linked to its place in the Rif, the perakim,
and the days. One JSON file per masechet, and styles.json with the fonts and sizes.

    python tools/export_indesign.py LIBRARY OUT_DIR יבמות כתובות
"""
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from PySide6.QtGui import QGuiApplication  # noqa: E402

app = QGuiApplication.instance() or QGuiApplication([])
from perush import shas, shas_book, shas_check, textlayout  # noqa: E402

textlayout.load_bundled_fonts(os.path.join(HERE, "fonts"))


def style_name(st, base):
    """A name for a character style, by its font and its size beside the base text's."""
    k = round(st.size / base.size, 2)
    fam = {"Frank Ruhl Libre": "FrankRuhl", "Frank Ruhl Libre Medium": "FrankRuhlMedium",
           "Frank Ruhl Libre SemiBold": "FrankRuhlSemiBold", "Drugulin CLM": "Drugulin",
           "David Libre": "David"}.get(st.family, st.family)
    return f"{fam}{'-Bold' if st.bold else ''}-{k}"


def runs(words, base, styles, kinds):
    """[Word] -> [{text, style, (note)}], consecutive words of a style joined."""
    out = []
    for w in words:
        name = style_name(w.style, base)
        styles[name] = {"font": w.style.family, "bold": w.style.bold, "size": round(w.style.size, 2),
                        "of_base": round(w.style.size / base.size, 2)}
        note = w.ref[4:] if isinstance(w.ref, str) and w.ref.startswith("הגה:") else None
        if note:
            out.append({"text": w.text, "style": name, "note": note})
            continue
        if out and out[-1]["style"] == name and "note" not in out[-1] and not getattr(w, "brk", False) \
                and not getattr(w, "line", None):
            out[-1]["text"] += " " + w.text
        else:
            r = {"text": w.text, "style": name}
            if getattr(w, "line", None) == "center":
                r["own_line_centered"] = True
            if getattr(w, "framed", False):
                r["framed_opening_word"] = True
            if getattr(w, "brk", False):
                r["new_line"] = True
            out.append(r)
    return out


def export(root, m, out_dir):
    days, first = shas.day_plan(root)
    got = {}
    orig = shas.check_layout

    def spy(book, rp, fp):
        got["book"], got["rp"], got["fp"] = book, rp, fp
        return orig(book, rp, fp)
    shas.check_layout = spy
    pages, rep, info = shas.build_masechet(root, m, first[m], days[m], shas_book.B5, shas_book.SIZES,
                                           fix=shas_check.fix)
    shas.check_layout = orig
    b = got["book"]
    styles = {}
    data = {"masechet": m, "commentary": b.comm_name, "first_day": info["first_day"],
            "days": [{"day": d, "rosh_page": w.get("rosh"), "rif_page": w.get("rif")} for d, w in info["day_pages"]],
            "rosh": [], "rif": [], "comments": [], "pages_now": {"rosh": info["rosh_pages"], "rif": info["rif_pages"]}}
    for u in b.rosh_units_list:
        kind = {"p": "paragraph", "h": "heading"}.get(u.kind, u.kind)
        data["rosh"].append({"kind": kind, "siman": u.ref if u.kind == "p" else None, "first_of_siman": u.first,
                             "runs": runs(u.words, b.st_rosh, styles, None)})
    for k, u in enumerate(b.units):
        data["rif"].append({"kind": {"p": "passage", "h": "perek_end"}.get(u.kind, u.kind),
                            "passage": u.ref, "first_word": b.off[k], "runs": runs(u.words, b.st_rif, styles, None)})
    for k, e in enumerate(b.comm):
        a = e["c_start"]
        z = b.comm[k + 1]["c_start"] if k + 1 < len(b.comm) else len(b.cwords)
        data["comments"].append({"passage": e["para"], "anchor_rif_word": b.c_pmax[k] if k < len(b.c_pmax) else None,
                                 "runs": runs(b.cwords[a:z], b.st_comm, styles, None)})
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{m}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    sz = shas_book.SIZES
    meta = {"page_mm": shas_book.B5, "margins_mm": {"head_foot": sz["margin"], "inner": sz["inner"], "outer": sz["outer"]},
            "base": {"rosh": [b.st_rosh.family, b.st_rosh.size, round(b.lh_rosh, 2)],
                     "rif": [b.st_rif.family, b.st_rif.size, round(b.lh_rif, 2)],
                     "commentary": [b.st_comm.family, b.st_comm.size, round(b.lh_comm, 2)]},
            "character_styles": styles}
    path = os.path.join(out_dir, "styles.json")
    old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"character_styles": {}}
    meta["character_styles"] = {**old["character_styles"], **styles}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(m, len(data["rosh"]), "rosh units,", len(data["rif"]), "rif passages,", len(data["comments"]), "comments")


if __name__ == "__main__":
    for m in sys.argv[3:]:
        export(sys.argv[1], m, sys.argv[2])
