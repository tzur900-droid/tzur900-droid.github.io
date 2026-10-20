"""Checking the bold of a masechet (the Rif's wording in the Rosh, Rashi's in the Ran)
before it is laid out: what is surely wrong is corrected, what may be wrong is reported.

Each finding: {'kind', 'where', 'text', 'fixed'}; kinds:
  far       a quotation of the Rif matched to a passage far from the siman's (a chance
            meeting of words); short ones lose their bold, long ones are reported
  lone      a word or two bold alone, with no quotation around them; they lose it
  missed    a stretch of six words or more that is in the siman's passages of the Rif and
            is not bold (the Rosh brings it a second time, or it is worded differently)
  link      a comment of the Ran whose dibbur hamatchil is in the Rif, but not in the
            passage it was put with
  no_rashi  a comment of the Ran on a passage that brings no Gemara of the masechet, so
            Rashi was not looked at for it
  ran_lone  one word of the Ran bold alone as Rashi's; it loses it
"""
from .shas import loose, lseq, norm, stem

LONG = 8          # a far quotation this long or longer is reported, not corrected
MISSED = 6


def text(toks, a, b):
    return " ".join(t[0] for t in toks[max(0, a):b])


def rosh_flat(rosh):
    """The Rosh's tokens as mark_aligned saw them (without the marks of the Gemara's pages
    put in since), with their siman."""
    flat, siman = [], []
    for i, s in enumerate(rosh):
        for p in s["paras"]:
            for t in p:
                if t[1] != "gem":
                    flat.append(t)
                    siman.append(i)
    return flat, siman


def check_rosh(rosh, rif, al, found):
    out = []
    if not rosh or not rif:
        return out
    flat, siman = rosh_flat(rosh)
    rflat = [j for j, p in enumerate(rif) for _ in p["tokens"]]

    def window(i):
        nxt = [al[k] for k in range(i + 1, len(rosh)) if al[k] > al[i]]
        return al[i] - 2, (nxt[0] if nxt else al[i]) + 2

    for a, b, c, d in found:
        if a >= len(flat) or c >= len(rflat):
            continue
        i, j = siman[a], rflat[c]
        lo, hi = window(i)
        if lo <= j <= hi:
            continue
        n = b - a + 1
        where = f"סימן {rosh[i]['num']} ({rosh[i]['perek']})"
        if n < LONG:
            for k in range(a, b + 1):
                if flat[k][1] is True:
                    flat[k][1] = False
            out.append({"kind": "far", "where": where, "text": text(flat, a, b + 1), "fixed": True})
        else:
            out.append({"kind": "far", "where": where, "text": text(flat, a, b + 1), "fixed": False})
    # a word or two bold alone
    k = 0
    while k < len(flat):
        if flat[k][1] is True:
            e = k
            while e < len(flat) and flat[e][1] is True:
                e += 1
            if e - k <= 2 and (k == 0 or flat[k - 1][1] is not True) and \
                    (e >= len(flat) or flat[e][1] is not True) and \
                    sum(len(lseq([flat[q][0]])[0]) for q in range(k, e)) < 3:
                where = f"סימן {rosh[siman[k]]['num']} ({rosh[siman[k]]['perek']})"
                ctx = text(flat, k - 4, e + 4)
                for q in range(k, e):
                    flat[q][1] = False
                out.append({"kind": "lone", "where": where, "text": ctx, "fixed": True})
            k = e
        else:
            k += 1
    # long stretches of the Rif's passages left plain
    for i, s in enumerate(rosh):
        lo, hi = window(i)
        bag = set()
        for p in rif[max(0, lo):hi + 1]:
            r = [stem(x) for x in lseq(p["tokens"])[0]]
            bag |= {tuple(r[q:q + 3]) for q in range(len(r) - 2)}
        for p in s["paras"]:
            seq, src = lseq(p)
            seq = [stem(x) for x in seq]
            hit = [False] * len(seq)
            for q in range(len(seq) - 2):
                if tuple(seq[q:q + 3]) in bag:
                    hit[q] = hit[q + 1] = hit[q + 2] = True
            q = 0
            while q < len(seq):
                if hit[q] and p[src[q]][1] is False:
                    e = q
                    while e < len(seq) and hit[e] and p[src[e]][1] is False:
                        e += 1
                    toks = sorted(set(src[q:e]))
                    if len(toks) >= MISSED:
                        out.append({"kind": "missed", "where": f"סימן {s['num']} ({s['perek']})",
                                    "text": text(p, toks[0], toks[-1] + 1), "fixed": False})
                    q = e
                else:
                    q += 1
    return out


def check_ran(rif, comm):
    out = []
    every = [[loose(t[0]) for t in p["tokens"]] for p in rif]
    for e in comm:
        where = f"דף {e['daf']} ברי\"ף"
        dh = [loose(t[0]) for t in e["tokens"][:e.get("dh_len", 0)] if norm(t[0]) not in ("גמ", "מתני", "וכו", "כו")]
        dh = [w for w in dh if w][:3]
        if rif and len(dh) >= 3:
            def has(j):
                s = every[j]
                return any(s[q:q + 3] == dh for q in range(len(s) - 2))
            near = [j for j in (e["para"] - 1, e["para"], e["para"] + 1) if 0 <= j < len(rif)]
            # a comment on Gemara the Rif does not bring is no mistake; one whose words are
            # in the Rif, but in another passage, is
            if not any(has(j) for j in near):
                elsewhere = [j for j in range(len(rif)) if has(j)]
                if elsewhere:
                    out.append({"kind": "link", "where": where, "text": text(e["tokens"], 0, 12), "fixed": False})
        if e.get("why") is None:
            out.append({"kind": "no_rashi", "where": where, "text": text(e["tokens"], 0, 8), "fixed": False})
        toks = e["tokens"]
        for k, t in enumerate(toks):
            if t[1] == "rashi" and k >= e.get("dh_len", 0) and \
                    (k == 0 or toks[k - 1][1] != "rashi") and (k + 1 >= len(toks) or toks[k + 1][1] != "rashi") \
                    and len(lseq([t[0]])[0]) < 2:
                t[1] = False
                out.append({"kind": "ran_lone", "where": where, "text": text(toks, k - 4, k + 5), "fixed": True})
    return out


def fix(rosh, rif, comm, al, found):
    """The check that build_masechet runs before the layout."""
    return check_rosh(rosh, rif, al, found) + check_ran(rif, comm)


KINDS = {
    "far": "ציטוט מקטע רחוק ברי\"ף",
    "lone": "מילה או שתיים מודגשות לבד",
    "missed": "לשון הרי\"ף שלא הודגשה",
    "link": "דיבור בר\"ן שנמצא בקטע אחר ברי\"ף",
    "no_rashi": "דיבור בר\"ן בלי בדיקת רש\"י",
    "ran_lone": "מילה אחת בר\"ן מודגשת לבד",
    "overflow": "טקסט יוצא מהעמוד",
    "hole": "חלל בתחתית עמוד",
    "empty": "טור ריק",
    "comm_only": "עמוד של מפרש בלבד",
}
