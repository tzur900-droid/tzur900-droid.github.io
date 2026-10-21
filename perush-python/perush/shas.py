"""Pesakei HaRosh and the Rif with the Ran (or the commentary that is printed around
the Rif in its place), one book per masechet: first the Rosh, then the Rif with the
commentary on both sides of it, and a daily division of the whole Shas into 354 days.

  * The Rosh is set in two columns; each day begins at the start of a siman.
  * The Rif is set in the middle of the page and the commentary in two columns on its
    sides. Where the commentary is longer than the Rif on the page it runs on under it
    (each column widens to half the page); where it is shorter, the Rif widens under it.
    The commentary of a passage of the Rif is on the page where the passage ends; only
    the passage that continues on the next page takes its commentary with it, and when
    the commentary owed fills more than a page, a page of commentary only follows.
    Each day begins at the start of a passage (after the Rif's colon).
  * In the Rosh, what he quotes from the Rif is bold; in the commentary, what it quotes
    from Rashi is bold (beside the dibbur hamatchil, which is always bold).
  * Every page says in its head where the same place is in the other half of the book.
"""
import bisect
import html
import os
import re
from dataclasses import dataclass

from .engine import Frame, Page
from .abbrev import expand
from .model import heb
from .textlayout import PT_PER_MM, Line, Style, Word, break_lines, full_width, space, width

EPS = 0.01
NIKUD = re.compile("[֑-ׇ]")
FINALS = str.maketrans("ךםןףץ", "כמנפצ")


# ---------------------------------------------------------------- reading the texts

def norm(w):
    return re.sub(r"[^א-ת]", "", NIKUD.sub("", w)).translate(FINALS)


def clean_refs(s):
    """No empty parentheses; a reference to the Gemara gives the amud as . or :"""
    s = re.sub(r"\(\s*\)", " ", s)
    s = re.sub(r"\(\(+", "(", s)
    s = re.sub(r"\)\)+", ")", s)
    s = re.sub(r"\b([א-ת]{1,3})\s+ע(?:\"|''|״|')([אב])(?=[\s)\],.;:]|$)",
               lambda m: m.group(1) + ("." if m.group(2) == "א" else ":"), s)
    return s


def tokens(line, bold_tags=True):
    """An Otzaria line -> [[word, bold]]: <b>/<strong> are bold, other tags go."""
    s = clean_refs(re.sub(r"<i [^>]*>\s*</i>", "", line))
    s = s.replace("&nbsp;", " ").replace("&thinsp;", " ")
    if bold_tags:
        s = re.sub(r"<(b|strong)>", " \x01 ", s)
        s = re.sub(r"</(b|strong)>", " \x02 ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    out, bold = [], False
    for w in s.split():
        if w == "\x01":
            bold = True
        elif w == "\x02":
            bold = False
        else:
            out.append([w, bold])
    return out


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read().replace("\r", "").split("\n")


def gem_daf(label):
    """'(דף ב ע"א)' or 'ב.' -> a sortable number (amud)."""
    m = re.search(r"([א-ת]+)\s*(?:ע\"([אב])|([.:]))", label)
    if not m:
        return None
    n = sum({"א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5, "ו": 6, "ז": 7, "ח": 8, "ט": 9, "י": 10, "כ": 20, "ל": 30,
             "מ": 40, "נ": 50, "ס": 60, "ע": 70, "פ": 80, "צ": 90, "ק": 100, "ר": 200, "ש": 300, "ת": 400}.get(c, 0)
            for c in m.group(1))
    side = 1 if (m.group(2) == "ב" or m.group(3) == ":") else 0
    return n * 2 + side


SIMAN_HEAD = re.compile(r"^(?:הלכה|סימן|סעיף)?\s*([א-ת]{1,4})['\"׳״]?$")


def parse_rosh(lines):
    """-> [{'perek': name, 'num': siman letter, 'paras': [tokens]}]. The headings differ
    from masechet to masechet (פרק / הלכה, a section of halachot and bare numbers, הלכה
    with no perek, ...): a heading that is a number (with הלכה, סימן or סעיף before it or
    not) begins a siman, any other heading is the name of the perek (or section) that
    follows; text before the first number of a section is a siman of its own."""
    simanim, perek, fresh = [], "", True
    for l in lines[1:]:
        m = re.match(r"\s*<h(\d)>(.*?)</h\1>", l)
        if m:
            head = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if not head:
                continue
            n = SIMAN_HEAD.match(head)
            if n and m.group(1) != "1":
                simanim.append({"perek": perek, "num": n.group(1), "paras": []})
                fresh = False
            elif m.group(1) != "1":
                perek, fresh = head, True
            continue
        if l.startswith("<h") or not l.strip():
            continue
        t = tokens(l)
        if not t:
            continue
        if fresh or not simanim:
            if not simanim and not perek:
                continue      # the name of the book, before any heading
            simanim.append({"perek": perek, "num": heb(sum(1 for x in simanim if x["perek"] == perek) + 1),
                            "paras": []})
            fresh = False
        if t and re.match(r"^\(\S{1,3}\)$", t[0][0]):
            t = t[1:]
        if t and not simanim[-1]["paras"] and t[0][0] == simanim[-1]["num"]:
            t = t[1:]
        # "הדרן עלך ..." at the end of a perek: a line of its own (the source has it
        # run on, sometimes after a stray 0)
        h = next((k for k, x in enumerate(t) if x[0].lstrip("0") == "הדרן"), None)
        if h is not None:
            t[h][0] = t[h][0].lstrip("0")
            hadran = [[w, "hadran"] for w, *_ in t[h:]]
            t = t[:h]
        if t:
            simanim[-1]["paras"].append(t)
        if h is not None:
            simanim[-1]["paras"].append(hadran)
    return [x for x in simanim if x["paras"]]


def parse_rif(lines):
    """-> [{'tokens', 'daf' (Rif page label at the start), 'dafs': [(word index, label)]}]"""
    paras, daf, pending = [], None, None
    for l in lines[1:]:
        m = re.match(r"\s*<h2>\s*דף\s*(.*?)\s*</h2>", l)
        if m:
            daf = m.group(1)
            pending = daf
            continue
        if l.startswith("<h") or not l.strip() or daf is None:
            continue
        t = tokens(l)
        if not t:
            continue
        prev = paras[-1] if paras else None
        if pending and prev and not re.search(r"[:.]\)?$", prev["tokens"][-1][0]):
            prev["dafs"].append((len(prev["tokens"]), daf))
            prev["tokens"].extend(t)
        else:
            paras.append({"tokens": t, "daf": daf, "dafs": [(0, daf)]})
        pending = None
    return paras


def parse_comm(lines):
    """A commentary on the Rif, by the Rif's pages -> [{'daf', 'tokens'}]"""
    out, daf = [], None
    for l in lines[1:]:
        m = re.match(r"\s*<h2>\s*דף\s*(.*?)\s*</h2>", l)
        if m:
            daf = m.group(1)
            continue
        if l.startswith("<h") or not l.strip() or daf is None:
            continue
        t = tokens(l)
        if t:
            out.append({"daf": daf, "tokens": t})
    return out


def mark_labels(paras):
    """'גמ'' after the Mishna and 'מתני'' after the Gemara, where a new part begins (at the
    start of a passage or after a full stop), are set in their own font."""
    for toks in paras:
        for i, t in enumerate(toks):
            if norm(t[0]) in ("גמ", "גמרא", "מתני", "מתניתין") and (
                    i == 0 or re.search(r"[:.]$", toks[i - 1][0])):
                t[1] = "label"


# ---------------------------------------------------------------- quotations

def grams(words, n):
    seq = [w for w in (norm(x) for x in words) if w]
    return {tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)}


def mark_quotes(toks, ref, excl, n=4, min_run=6):
    """Make bold the runs of words (min_run or more) of toks that come from ref and not
    from excl (sets of n-grams)."""
    idx = [i for i, t in enumerate(toks) if norm(t[0])]
    seq = [norm(toks[i][0]) for i in idx]
    hit = [False] * len(seq)
    for k in range(len(seq) - n + 1):
        g = tuple(seq[k:k + n])
        if g in ref and g not in excl:
            for j in range(k, k + n):
                hit[j] = True
    k = 0
    count = 0
    while k < len(seq):
        if hit[k]:
            e = k
            while e < len(seq) and hit[e]:
                e += 1
            if e - k >= min_run:
                for j in range(k, e):
                    toks[idx[j]][1] = True
                    count += 1
            k = e
        else:
            k += 1
    return count


def loose(w):
    """A word for finding quotations: without vav and yod, so that full and defective
    spellings match."""
    return re.sub("[וי]", "", norm(w)).replace("מ", "נ") if norm(w) else ""


def lwords(w):
    """A word for finding quotations, abbreviations written out: [loose words]."""
    ex = expand(w)
    if ex:
        return [x for x in (loose(e) for e in ex) if x]
    x = loose(w)
    return [x] if x else []


def lseq(toks):
    """-> (loose words, index of the token each comes from)"""
    seq, src = [], []
    for i, t in enumerate(toks):
        for x in lwords(t[0] if isinstance(t, list) else t):
            seq.append(x)
            src.append(i)
    return seq, src


def nwords(src, a, b):
    """How many words of the text the loose words a..b-1 come from (an abbreviation
    written out is one word)."""
    return len(set(src[a:b]))


def loose_counts(words, n):
    seq = lseq(words)[0]
    out = {}
    for i in range(len(seq) - n + 1):
        g = tuple(seq[i:i + n])
        out[g] = out.get(g, 0) + 1
    return out


# words that change what is said: a quotation with one of them that the source has not
# is not the source's wording (the Rif says צריך, the Rosh לא צריך)
MEANING = {norm(w) for w in """לא ולא דלא שלא אין ואין דאין שאין אינו ואינו אינה אינן ליכא וליכא לית ולית לאו ולאו
    אי ואי אסור ואסור מותר ומותר שרי ושרי חייב וחייב פטור ופטור כשר וכשר פסול ופסול טמא וטמא טהור וטהור
    אבל ואבל אלא בלא ובלא חוץ""".split()}


def stem(x):
    """A loose word without a one-letter prefix and a final ה or א, so that באיסקופה and
    אסקופה, ארבע and ארבעה match."""
    if len(x) > 3 and x[0] in "בהדלשכ":
        x = x[1:]
    if len(x) > 3 and x[-1] in "הא":
        x = x[:-1]
    return x


def mark_aligned(toks, ref_toks, n=4, min_run=4, big=12, mid=7, near=40, far=200, max_occ=60, found=None,
                 loose_words=False, fill=None):
    """Make bold in toks every stretch (min_run words or more) of the text of ref_toks,
    each word of ref_toks used once. Long shared stretches are taken first; a line that
    appears in toks more than once but in ref_toks once goes with the occurrence that
    stands next to a stretch already taken (near it in both texts), not with a
    stray repetition. A stretch shorter than mid words is taken only within far words (in
    both texts) of one already taken. found (a list), if given, gets each stretch taken as (first and last
    token in toks, first and last token in ref_toks).
    With loose_words, words match without a one-letter prefix and a final ה or א (stem).
    With fill = (a, b), the words between two stretches taken are bold too where at most a
    words of toks and b of ref_toks (words of the text: an abbreviation is one) are between them (a word or two the quoting text adds or
    changes inside a quotation)."""
    S, src = lseq(toks)
    R, rsrc = lseq(ref_toks)
    if loose_words:
        S, R = [stem(x) for x in S], [stem(x) for x in R]
    index = {}
    for p in range(len(R) - n + 1):
        index.setdefault(tuple(R[p:p + n]), []).append(p)
    runs = []
    for i in range(len(S) - n + 1):
        ps = index.get(tuple(S[i:i + n]))
        if not ps or len(ps) > max_occ:
            continue
        for p in ps:
            if i and p and S[i - 1] == R[p - 1]:
                continue    # inside a stretch found from its start
            L = n
            while i + L < len(S) and p + L < len(R) and S[i + L] == R[p + L]:
                L += 1
            runs.append((L, i, p))
    used_r, bold_s, taken = bytearray(len(R)), bytearray(len(S)), []

    def take(L, i, p):
        k = 0
        while k < L:
            if used_r[p + k] or bold_s[i + k]:
                k += 1
                continue
            e = k
            while e < L and not used_r[p + e] and not bold_s[i + e]:
                e += 1
            if nwords(src, i + k, i + e) >= min_run and nwords(rsrc, p + k, p + e) >= min_run:
                for j in range(k, e):
                    used_r[p + j] = bold_s[i + j] = 1
                taken.append((i + k, p + k, e - k))
            k = e

    runs.sort(reverse=True)
    for L, i, p in runs:
        if L >= big:
            take(L, i, p)

    def beside(L, i, p):
        for ti, tp, tl in taken:
            if (abs(p - (tp + tl)) < near or abs(tp - (p + L)) < near) and \
                    (abs(i - (ti + tl)) < 2 * near or abs(ti - (i + L)) < 2 * near):
                return 1
        return 0

    def close(L, i, p):
        a = bisect.bisect_left(taken_p, (p - far,))
        for tp, ti in taken_p[a:]:
            if tp > p + L + far:
                break
            if abs(ti - i) < 2 * far:
                return True
        return False

    # a shorter stretch (a name, a few words) is taken only near a place in both texts
    # where the two already go together; otherwise it is a chance meeting of words
    rest = [x for x in runs if x[0] < big]
    rest.sort(key=lambda x: (beside(*x), x[0]), reverse=True)
    while rest:
        left, before = [], len(taken)
        taken_p = sorted((tp, ti) for ti, tp, _ in taken)
        for L, i, p in rest:
            if nwords(src, i, i + L) >= mid or close(L, i, p):
                take(L, i, p)
            else:
                left.append((L, i, p))
        if len(taken) == before:
            break
        rest = left
    if fill:
        order = sorted(taken)
        for (i1, p1, l1), (i2, p2, l2) in zip(order, order[1:]):
            gs, gr = i2 - (i1 + l1), p2 - (p1 + l1)
            if 0 < gs and 0 <= gr and nwords(src, i1 + l1, i2) <= fill[0] and nwords(rsrc, p1 + l1, p2) <= fill[1]:
                # not across a word that changes the meaning, which the source has not there
                theirs = {norm(ref_toks[k][0]) for k in set(rsrc[p1 + l1:p2])}
                if any(norm(toks[k][0]) in MEANING and norm(toks[k][0]) not in theirs for k in set(src[i1 + l1:i2])):
                    continue
                for k in range(i1 + l1, i2):
                    bold_s[k] = 1
    count = 0
    for k, b in enumerate(bold_s):
        if b and toks[src[k]][1] is False:
            toks[src[k]][1] = True
            count += 1
    if found is not None:
        found.extend((src[i], src[i + L - 1], rsrc[p], rsrc[p + L - 1]) for i, p, L in taken)
    return count


def parse_rashi(lines):
    """Rashi on the Gemara -> [{'amud', 'dh': loose words of the dibbur hamatchil,
    'words': loose words of the dibbur and the comment}]"""
    out, amud = [], None
    for l in lines[1:]:
        m = re.match(r"\s*<h2>\s*דף\s*(.*?)\s*</h2>", l)
        if m:
            amud = gem_daf(m.group(1))
            continue
        if l.startswith("<h") or amud is None or " - " not in l:
            continue
        dh, _, rest = re.sub(r"<[^>]+>", " ", l).partition(" - ")
        dh, rest = dh.replace("''", '"').split(), rest.replace("''", '"').split()
        words, src = lseq(rest)
        dw, dsrc = lseq(dh)
        out.append({"id": len(out), "amud": amud, "dh": dw, "dsrc": dsrc, "words": words, "src": src,
                    "dh_text": dh, "text": rest})
    return out


def passage_amudim(rif, gem_lines):
    """The amud of the Gemara each passage of the Rif is on (by the Gemara it brings; a
    passage that brings none takes the one before it)."""
    gtoks, amud = parse_gemara(gem_lines)
    flat = [j for j, p in enumerate(rif) for _ in p["tokens"]]
    found = []
    mark_aligned([[t[0], False] for p in rif for t in p["tokens"]], gtoks, found=found)
    got = {}
    for a, b, c, d in found:
        got.setdefault(flat[a], []).extend([amud[c][0]] * (b - a + 1))
    out, last = [], None
    for j in range(len(rif)):
        # a passage that brings the Gemara of another masechet meets ours only by chance
        if len(got.get(j, ())) >= 10:
            last = sorted(got[j])[len(got[j]) // 2]
        out.append(last)
    # the middle of the passage and the two on each side of it, so that a passage that
    # brings the Gemara of another place does not move it
    smooth = []
    for j in range(len(out)):
        near = sorted(x for x in out[max(0, j - 2):j + 3] if x is not None)
        smooth.append(near[len(near) // 2] if near else None)
    return smooth


def mark_rashi(toks, entries, gem, value="rashi", gap=3, trace=None):
    """Make bold in a commentary entry what it takes from Rashi (entries: Rashi's comments
    on the place; gem: loose 3-grams of the Gemara), as the Oz Vehadar Rif does:
      * its dibbur hamatchil (marked "dh" in toks), where Rashi has a dibbur with the
        same words;
      * in what it says, Rashi's own words (not the Gemara's): three or more in the order
        Rashi has them, a few words between them at most; or two, opening what it says
        on a dibbur that is Rashi's, where Rashi's comment opens with them;
      * where it says that Rashi explained ("ופירש"י ז"ל ..."), the sentence it brings.
    trace (a list), if given, gets why each stretch is bold: (kind, first and last token,
    the Rashi comment's id, the indices of its words that are the same; for "dh" of its
    dibbur, for "words" of the comment)."""
    seq, src = lseq(toks)
    dh_end = 0
    while dh_end < len(seq) and toks[src[dh_end]][1] == "dh":
        dh_end += 1
    bold = bytearray(len(seq))
    dh = seq[:dh_end]
    mine = []      # Rashi's comments on this dibbur
    for e in entries:
        # the longest run of words the two dibburim share
        r, best = e["dh"], (0, 0, 0)
        for a in range(dh_end):
            for b in range(len(r)):
                L = 0
                while a + L < dh_end and b + L < len(r) and dh[a + L] == r[b + L]:
                    L += 1
                if L > best[2]:
                    best = (a, b, L)
        a, b, L = best
        rt = len(set(e["dsrc"][b:b + L])) if L else 0
        if (L >= 2 and len(set(src[a:a + L])) >= 2 and rt >= 2) or (L == 1 and len(r) == 1 and len(r[0]) >= 4):
            mine.append(e)
            for k in range(a, a + L):
                bold[k] = 1
            if trace is not None:
                trace.append(("dh", src[a], src[a + L - 1], e["id"], sorted(set(e["dsrc"][b:b + L]))))
    # a short dibbur Rashi has half of: all of it
    if dh_end and len(set(src[:dh_end])) <= 5 and sum(bold[:dh_end]) * 2 >= dh_end:
        for k in range(dh_end):
            bold[k] = 1

    def gemara_word(k):
        return any(tuple(seq[j:j + 3]) in gem for j in range(max(0, k - 2), k + 1))

    sseq = [stem(x) for x in seq]
    for e in entries:
        r, rsrc = e["words"], e["src"]
        # as in the Rosh: words match without a one-letter prefix and a final ה or א, and
        # not across a word that changes the meaning which Rashi has not there
        at = {}
        for p, w in enumerate(r):
            at.setdefault(stem(w), []).append(p)
        rtext = e["text"]

        def same_sense(ci, i2, cp, p2):
            mine = {norm(toks[k][0]) for k in set(src[ci + 1:i2])} & MEANING
            if not mine:
                return True
            theirs = {norm(rtext[k]) for k in set(rsrc[cp + 1:p2])}
            return mine <= theirs

        i = dh_end
        while i < len(seq):
            best = []
            for p0 in at.get(sseq[i], ()):
                chain, ci, cp = [(i, p0)], i, p0
                while True:
                    nxt = None
                    for i2 in range(ci + 1, min(len(seq), ci + gap + 1)):
                        ps = [p for p in at.get(sseq[i2], ()) if cp < p <= cp + gap + 1 and same_sense(ci, i2, cp, p)]
                        if ps:
                            nxt = (i2, ps[0])
                            break
                    if not nxt:
                        break
                    chain.append(nxt)
                    ci, cp = nxt
                if len(chain) > len(best):
                    best = chain
            if not best:
                i += 1
                continue
            i0, i1 = best[0][0], best[-1][0]
            dense = len(best) / (i1 - i0 + 1) >= 0.6
            # words of the two texts (an abbreviation is one), leaving out the Gemara's
            own = [(i, p) for i, p in best if not gemara_word(i)]
            n = min(len({src[i] for i, _ in own}), len({rsrc[p] for _, p in own}))
            head = len(best) == 2 and e in mine and i0 == dh_end and best[0][1] == 0
            if dense and (n >= 3 or head):
                for k in range(i0, i1 + 1):
                    bold[k] = 1
                if trace is not None:
                    trace.append(("words", src[i0], src[i1], e["id"], sorted({rsrc[p] for _, p in best})))
            i = i1 + 1 if dense and len(best) >= 2 else i + 1
    # "ופירש"י ז"ל ...": to the end of the sentence
    for k in range(len(seq)):
        if not rashi_marker(toks[src[k]][0]) or (k and src[k - 1] == src[k]):
            continue
        q = src[k] + 1
        while q < len(toks) and norm(toks[q][0]) in ("זל", "זצל"):
            q += 1
        e = q
        while e < len(toks) and e - q < 30 and not re.search(r"[.:]$", toks[e][0]):
            e += 1
        if e < len(toks) and e - q < 30:
            for k2, sk in enumerate(src):
                if q <= sk <= e:
                    bold[k2] = 1
            if trace is not None:
                trace.append(("said", q, e, None, []))
    count = 0
    for k, b in enumerate(bold):
        t = toks[src[k]]
        if b and t[1] != value:
            t[1] = value
            count += 1
    return count


SKIP_DH = ("גמ", "גמרא", "מתני", "מתניתין", "וכו", "כו", "פי", "וגו")


def dh_words(e):
    """The loose words of a commentary entry's dibbur hamatchil, without גמ', וכו' and the
    like."""
    return [w for w in lseq(e["tokens"][:e.get("dh_len", 0)])[0] if w not in {loose(x) for x in SKIP_DH}]


def comm_gemara_marks(comm, amudim, gtoks, gamud):
    """Where the commentary comes to a new amud of the Gemara, the amud before the entry
    (e['gem'], set as [דף ב:]): the amud where its dibbur hamatchil is found in the Gemara,
    near the amud of the Rif's passage."""
    seq, src = lseq(gtoks)
    index = {}
    for k in range(len(seq) - 1):
        index.setdefault(tuple(seq[k:k + 2]), []).append(k)
    last, count = None, 0
    for e in comm:
        a = amudim[e["para"]]
        dh = dh_words(e)
        if a is None or len(dh) < 2:
            continue
        found = []
        for k in index.get(tuple(dh[:2]), ()):
            if seq[k:k + min(len(dh), 4)] == dh[:4]:
                n, label = gamud[src[k]]
                if a - 1 <= n <= a + 3:
                    found.append((n, label))
        # forward from the last mark, or far back where the Rif goes on to a perek that
        # comes earlier in the Gemara
        back = last is not None and a < last - 6
        ahead = [x for x in found if last is None or x[0] >= last or (back and x[0] < last - 6)]
        if not ahead:
            continue
        n, label = min(ahead, key=lambda x: abs(x[0] - a))
        if last is None or n > last or (back and n < last - 6):
            e["gem"] = label
            last = n
            count += 1
    return count


def mishna_openers(comm, rif):
    """The first word of a commentary entry that opens a Mishna (its dibbur hamatchil is
    the Mishna's first words) large, in square letters (e['open'])."""
    starts = {}
    for j, p in enumerate(rif):
        # the passage's words without the references in parentheses ("(דף ב.)")
        toks, inside = [], False
        for t in p["tokens"]:
            if t[0].startswith("("):
                inside = True
            if not inside:
                toks.append(t)
            if t[0].endswith(")"):
                inside = False
        seq, src = lseq(toks)
        for k in range(len(seq)):
            t = toks[src[k]]
            if (k == 0 and j == 0) or (t[1] == "label" and norm(t[0]) in ("מתני", "מתניתין")
                                       and (k == 0 or src[k - 1] != src[k])):
                at = k + (0 if j == 0 and k == 0 else 1)
                starts.setdefault(j, []).append(tuple(seq[at:at + 2]))
    count = 0
    for e in comm:
        dh = dh_words(e)
        if len(dh) < 2:
            continue
        if any(tuple(dh[:2]) in starts.get(j, ()) for j in (e["para"] - 1, e["para"], e["para"] + 1)):
            e["open"] = True
            count += 1
    return count


def rif_marker(w):
    n = norm(w)
    return n.endswith("ריפ") or "אלפס" in n


def rashi_marker(w):
    n = norm(w)
    return n in ("רשי", "ורשי", "לרשי", "שרשי", "פרשי", "ופרשי", "פירשי", "ופירשי", "שפרשי", "כפרשי", "וכפרשי", "דרשי")


# ---------------------------------------------------------------- linking

def link_comm(comm, rif):
    """Attach each commentary entry to the passage of the Rif it explains: the passages on
    the entry's page of the Rif where its dibbur hamatchil is found are its candidates, and
    of all the ways to choose one for each entry that keep the order of the Rif, the one
    that agrees with the most (and the longest) dibburim is taken; an entry with none in
    that choice goes with the passage of the entry before it."""
    by_daf = {}
    for j, p in enumerate(rif):
        for _, d in p["dafs"]:
            by_daf.setdefault(d, []).append(j)
    texts = [lseq(p["tokens"])[0] for p in rif]
    skip = {loose(w) for w in ("וכו", "כו", "גמ", "מתני", "וגו", "רן", "פי")}
    cands = []
    for e in comm:
        dh = [w for w in lseq([t for t in e["tokens"][:12] if t[1] is True])[0] if w not in skip][:4]
        got = {}
        for j in by_daf.get(e["daf"], []):
            t = texts[j]
            for k in range(len(dh), 0, -1):
                if any(t[i:i + k] == dh[:k] for i in range(len(t) - k + 1)):
                    got[j] = k * k        # a longer agreement counts for more
                    break
        cands.append(got)
    # the heaviest chain (passages never going back), a tree of the best chain ending at a
    # passage or before it
    P = len(rif) + 1
    tree = [(0, -1, -1)] * (P + 1)

    def query(j):
        best, q = (0, -1, -1), j + 1
        while q > 0:
            if tree[q][0] > best[0]:
                best = tree[q]
            q -= q & -q
        return best

    def update(j, v):
        q = j + 1
        while q <= P:
            if v[0] > tree[q][0]:
                tree[q] = v
            q += q & -q

    back = {}
    end = (0, -1, -1)
    for k, got in enumerate(cands):
        vals = [(j, w, query(j)) for j, w in got.items()]
        for j, w, prev in vals:
            v = prev[0] + w
            back[(k, j)] = (prev[1], prev[2])
            update(j, (v, k, j))
            if v > end[0]:
                end = (v, k, j)
    chosen = {}
    k, j = end[1], end[2]
    while k >= 0:
        chosen[k] = j
        k, j = back[(k, j)]
    last = 0
    for k, e in enumerate(comm):
        if k in chosen:
            last = chosen[k]
        elif not cands[k]:
            # its dibbur is not in the Rif (a comment on the Gemara): when its page of the
            # Rif is further on, with the first passage of that page (not past the next
            # entry that was placed)
            later = [chosen[q] for q in chosen if q > k]
            nxt = min(later) if later else len(rif) - 1
            pages = [j for j in by_daf.get(e["daf"], []) if last < j <= nxt]
            if pages and last not in by_daf.get(e["daf"], []):
                last = pages[0]
        e["para"] = last


def align(rosh, rif, n=3):
    """For every siman of the Rosh, the passage of the Rif with the same material
    (monotonic, by the words they share). Where the Rif has the perakim in another
    order than the Rosh (Megilla: the Rif follows the order of the Mishna), each perek
    of the Rosh is aligned with its own stretch of the Rif."""
    rg = [grams([w for p in s["paras"] for w, *_ in p], n) for s in rosh]
    fg = [grams([w for w, *_ in p["tokens"]], n) for p in rif]
    S, P = len(rg), len(fg)
    if not P:
        return [0] * S
    score = [[len(a & b) for b in fg] for a in rg]
    blocks = []
    for i, s in enumerate(rosh):
        if blocks and rosh[blocks[-1][0]]["perek"] == s["perek"]:
            blocks[-1].append(i)
        else:
            blocks.append([i])

    def centre(b):
        # the middle of the perek in the Rif, by where each siman shares the most
        pts = sorted((max(range(P), key=score[i].__getitem__), max(score[i])) for i in b)
        half, acc = sum(w for _, w in pts) / 2, 0
        for j, w in pts:
            acc += w
            if acc >= half:
                return j
        return 0

    order = sorted(range(len(blocks)), key=lambda k: centre(blocks[k]))
    if order == sorted(order):
        return align_part(score, list(range(S)), 0, P)
    # the Rif cut into a stretch for each perek, in the Rif's order: the cuts that keep the
    # most of what each perek shares with its own stretch (best over all the cuts together)
    K = len(order)
    NEG = float("-inf")
    best = [[NEG] * (P + 1) for _ in range(K + 1)]
    back = [[0] * (P + 1) for _ in range(K + 1)]
    best[0][0] = 0.0
    for k in range(1, K + 1):
        sims = blocks[order[k - 1]]
        for c0 in range(P + 1):
            if best[k - 1][c0] == NEG:
                continue
            run = [0] * len(sims)
            got = best[k - 1][c0]
            # an empty stretch (a perek the Rif has not), then longer and longer ones
            if got > best[k][c0]:
                best[k][c0], back[k][c0] = got, c0
            for c in range(c0 + 1, P + 1):
                for q, i in enumerate(sims):
                    if score[i][c - 1] > run[q]:
                        run[q] = score[i][c - 1]
                v = got + sum(run)
                if v > best[k][c]:
                    best[k][c], back[k][c] = v, c0
    cuts, c = [], P
    for k in range(K, 0, -1):
        c = back[k][c]
        cuts.append(c)
    cuts = cuts[::-1][1:]
    out = [0] * S
    edges = [0] + cuts + [P]
    for k, b in enumerate(order):
        if edges[k + 1] <= edges[k]:
            # a perek the Rif has not: with the passage where its place would be
            for i in blocks[b]:
                out[i] = min(edges[k], P - 1)
            continue
        part = align_part(score, blocks[b], edges[k], edges[k + 1])
        for i, j in zip(blocks[b], part):
            out[i] = j
    return out


def align_part(score, simanim, lo, hi):
    """align() for the simanim given against the passages lo..hi-1."""
    S, P = len(simanim), max(1, hi - lo)
    sc = [[score[i][lo + j] if lo + j < len(score[i]) else 0 for j in range(P)] for i in simanim]
    dp = [[0.0] * P for _ in range(S)]
    back = [[0] * P for _ in range(S)]
    for i in range(S):
        best, arg = -1.0, 0
        for j in range(P):
            prev = 0.0
            if i:
                if dp[i - 1][j] > best:
                    best, arg = dp[i - 1][j], j
                prev = best
            dp[i][j] = sc[i][j] + prev
            back[i][j] = arg
    j = max(range(P), key=lambda x: dp[S - 1][x])
    out = [0] * S
    for i in range(S - 1, -1, -1):
        out[i] = j
        j = back[i][j]
    # where the siman's material begins in the Rif: the first passage after the previous
    # siman's that shares a good part of what the best one does
    for i in range(S):
        first = out[i - 1] + 1 if i else 0
        best = sc[i][out[i]]
        for j in range(min(first, out[i]), out[i]):
            if best and sc[i][j] >= 0.3 * best and sc[i][j] >= 3:
                out[i] = j
                break
    return [lo + j for j in out]


OWN = {"פי", "פירוש", "ופי", "ופירוש", "פירש", "כלומר", "ונראה", "נראה", "ולי", "ומיהו", "וקשה", "קשה", "והקשה"}


def complete_sentences(rosh, rif, al, most=6):
    """A quotation of the Rif that ends (or begins) a few words short of the end (or
    the start) of its sentence: the rest of the sentence bold too, where it is at most
    `most` words and half of them or more are in the Rif's passages of the siman (the
    Rosh says it a little differently, as the Oz Vehadar Rosh has it)."""
    count = 0
    for i, s in enumerate(rosh):
        lo = max(0, al[i] - 1)
        hi = (al[i + 1] if i + 1 < len(rosh) and al[i + 1] > al[i] else al[i]) + 1
        bag = {stem(x) for p in rif[lo:hi + 1] for x in lseq(p["tokens"])[0]}
        for p in s["paras"]:
            # sentences: up to a word that ends with . or :
            start = 0
            for k in range(len(p) + 1):
                if k < len(p) and not re.search(r"[.:]$", p[k][0]):
                    continue
                sent = list(range(start, min(k + 1, len(p))))
                start = k + 1
                bold = [j for j in sent if p[j][1] is True]
                if not bold:
                    continue
                for part in (sent[sent.index(bold[-1]) + 1:], sent[:sent.index(bold[0])]):
                    words = [j for j in part if p[j][1] is False]
                    if not part or len(words) != len(part) or len(part) > most:
                        continue
                    # the Rosh explaining in his own words, or saying something else
                    if any(norm(p[j][0]) in OWN or norm(p[j][0]) in MEANING for j in part) or \
                            any(len(norm(p[j][0])) == 1 for j in part):
                        continue
                    stems = [stem(x) for j in part for x in lwords(p[j][0])]
                    if stems and sum(x in bag for x in stems) * 2 >= len(stems):
                        for j in part:
                            p[j][1] = True
                            count += 1
    return count


def rif_page_marks(rosh, rif, al):
    """Mark in the Rosh where each page of the Rif begins: the place in the Rosh where the
    words that open the page are found (near the siman that matches its passage), or else
    the start of that siman. The label goes on the token (its third element)."""
    flat = [(i, pi, ti) for i, s in enumerate(rosh) for pi, p in enumerate(s["paras"]) for ti, t in enumerate(p)
            if loose(t[0])]
    if not flat:
        return
    seq = [loose(rosh[i]["paras"][pi][ti][0]) for i, pi, ti in flat]
    first_of = {}
    for k, (i, _, _) in enumerate(flat):
        first_of.setdefault(i, k)
    index = {}
    for k in range(len(seq) - 3):
        index.setdefault(tuple(seq[k:k + 4]), []).append(k)
    rflat = [(j, w) for j, p in enumerate(rif) for w in range(len(p["tokens"]))]
    rpos = {jw: k for k, jw in enumerate(rflat)}
    rwords = [loose(rif[j]["tokens"][w][0]) for j, w in rflat]
    last, seen = 0, set()
    for j, p in enumerate(rif):
        lo_s = max([i for i in range(len(rosh)) if al[i] <= j] or [0])
        hi_s = min([i for i in range(len(rosh)) if al[i] > j] or [len(rosh) - 1])
        lo_s, hi_s = max(0, lo_s - 1), min(len(rosh) - 1, hi_s + 1)
        for w, daf in p["dafs"]:
            if daf in seen:
                continue
            seen.add(daf)
            k0 = rpos.get((j, w), 0)
            rseq = [x for x in rwords[k0:k0 + 80] if x]
            found = None
            for q in range(len(rseq) - 3):
                for pos in index.get(tuple(rseq[q:q + 4]), []):
                    if pos >= last and lo_s <= flat[pos][0] <= hi_s:
                        found = pos
                        break
                if found is not None:
                    break
            if found is None:
                found = max(last, first_of.get(lo_s + (1 if lo_s < hi_s else 0), last))
            last = found
            i, pi, ti = flat[found]
            t = rosh[i]["paras"][pi][ti]
            label = f"רי\"ף {daf}"
            if len(t) > 2:
                if daf not in t[2].split():
                    t[2] = t[2] + " " + daf
            else:
                t.append(label)


GEM_MARK = re.compile(r"^\[דף [א-ת]+[.:]\]$")


def parse_gemara(lines):
    """The Gemara of the masechet -> (tokens, the amud of each: a sortable number, label)."""
    toks, amud = [], []
    cur = None
    for l in lines[1:]:
        m = re.match(r"\s*<h2>\s*דף\s*(.*?)\s*</h2>", l)
        if m:
            cur = (gem_daf(m.group(1)), m.group(1))
            continue
        if l.startswith("<h") or cur is None or cur[0] is None:
            continue
        for t in tokens(l, bold_tags=False):
            toks.append(t)
            amud.append(cur)
    return toks, amud


def gemara_marks(rosh, gem_lines):
    """Where the Rosh comes to a new amud of the Gemara, a mark in the line: [דף ב:]. The
    place is where the Gemara he brings first comes from that amud, following the main
    line of the Gemara through the siman (the order of the amudim, by the longest chain
    of quotations that goes forward), not a passing quotation from elsewhere."""
    gtoks, amud = parse_gemara(gem_lines)
    if not gtoks:
        return 0
    flat = [(i, pi, ti) for i, s in enumerate(rosh) for pi, p in enumerate(s["paras"]) for ti in range(len(p))]
    found = []
    mark_aligned([[rosh[i]["paras"][pi][ti][0], False] for i, pi, ti in flat], gtoks, found=found)
    found = sorted(x for x in found if rosh[flat[x[0]][0]]["paras"][flat[x[0]][1]][flat[x[0]][2]][1] != "hadran")
    # the heaviest chain of quotations whose amudim never go back (a tree of the best
    # chain ending at each amud or before it)
    top = max(x[0] for x in amud) + 2
    tree = [(0, -1)] * (top + 1)
    best, back = [], []
    for k, (a, b, c, d) in enumerate(found):
        n = amud[c][0] + 1
        w, arg, q = 0, -1, n
        while q > 0:
            if tree[q][0] > w:
                w, arg = tree[q]
            q -= q & -q
        best.append(w + (b - a + 1))
        back.append(arg)
        q = n
        while q <= top:
            if best[k] > tree[q][0]:
                tree[q] = (best[k], k)
            q += q & -q
    if not best:
        return 0
    k = max(range(len(best)), key=best.__getitem__)
    chain = []
    while k >= 0:
        chain.append(found[k])
        k = back[k]
    chain.reverse()
    marks, cur = [], None
    for a, b, c, d in chain:
        n, label = amud[c]
        if cur is None or n > cur:
            marks.append((a, label))
            cur = n
    # into the text, from the end so that the places stay right
    for a, label in reversed(marks):
        i, pi, ti = flat[a]
        rosh[i]["paras"][pi].insert(ti, [f"[דף {label}]", "gem"])
    return len(marks)


# ---------------------------------------------------------------- units of text

@dataclass
class Unit:
    kind: str          # p: paragraph, h: heading, d: day marker
    words: list        # [Word]
    ref: object = None  # siman / passage index
    first: bool = True  # first paragraph of its siman / passage


class Book:
    def __init__(self, name, rosh, rif, comm, comm_name, page=(210, 297), margin=14, rosh_size=12, rif_size=11.5,
                 comm_size=10, head_size=9):
        self.name = name
        self.rosh, self.rif, self.comm, self.comm_name = rosh, rif, comm, comm_name
        self.pw, self.ph = page[0] * PT_PER_MM, page[1] * PT_PER_MM
        self.m = margin * PT_PER_MM
        self.W = self.pw - 2 * self.m
        self.hs = head_size
        self.head_h = head_size * 1.3 + 5 * PT_PER_MM
        self.H = self.ph - 2 * self.m - self.head_h
        self.gap = 5 * PT_PER_MM
        self.vgap = 2.5 * PT_PER_MM
        self.st_rosh = Style("Frank Ruhl Libre", rosh_size)
        self.st_rif = Style("Frank Ruhl Libre", rif_size)
        self.st_comm = Style("Noto Rashi Hebrew", comm_size)
        self.lh_rosh = rosh_size * 1.45
        self.lh_rif = rif_size * 1.34
        self.lh_comm = comm_size * 1.26
        self.head_style = Style("Frank Ruhl Libre", head_size)
        self.cw = self.W * 0.25            # a commentary column beside the Rif
        self.ktop = 4                      # lines of the commentary above the Rif
        self.wide = (self.W - self.gap) / 2  # a commentary column under it

    # -------------------------------------------------- words
    def words(self, toks, st):
        if st.family == self.st_comm.family:
            b = Style("Frank Ruhl Libre", st.size, True)
        else:
            b = st.with_bold(True)
        lab = Style("David Libre", st.size * 1.08, True)
        big = Style(st.family, st.size * 1.3, True)
        gem = Style(st.family, st.size * 0.75)
        copen = Style("Frank Ruhl Libre", st.size * 1.4, True)
        dh = Style("Frank Ruhl Libre", st.size, True)
        out = []
        for t in toks:
            w, bold = t[0], t[1]
            s_ = {"label": lab, "open": big, "gem": gem, "rashi": st.with_bold(True), "hadran": b, "dh": dh, "copen": copen}.get(bold) or (b if bold else st)
            out.append(Word(w, s_, width(s_, w), t[2] if len(t) > 2 else None))
        return out

    def marker(self, day, st):
        s = Style(st.family, st.size * 1.25, True)
        t = f"יום {heb(day)}"
        return Unit("d", [Word(t, s, width(s, t))])

    def heading(self, text, st, k=1.3):
        s = Style(st.family, st.size * k, True)
        return Unit("h", [Word(w, s, width(s, w)) for w in text.split()])

    def rosh_units(self, day_at):
        """day_at: siman index -> day number starting there."""
        units, perek = [], None
        for i, s in enumerate(self.rosh):
            if i in day_at:
                units.append(self.marker(day_at[i], self.st_rosh))
            if s["perek"] != perek:
                perek = s["perek"]
                if perek:
                    units.append(self.heading(perek, self.st_rosh))
            for k, p in enumerate(s["paras"]):
                if p and p[0][1] == "hadran":
                    units.append(self.heading(" ".join(w for w, *_ in p), self.st_rosh, 1.1))
                    continue
                toks = p
                if k == 0:
                    # the siman's letter and its first word large, as in the printed Rosh
                    # (a mark of the Gemara's page before it stays between them)
                    toks = [list(t) for t in p]
                    w = next((t for t in toks if t[1] != "gem"), None)
                    if w is not None and w[1] != "label":
                        w[1] = "open"
                    toks = [[s["num"], "open"]] + toks
                units.append(Unit("p", self.words(toks, self.st_rosh), i, k == 0))
        return units

    def rif_units(self, day_at):
        """The Rif's passages; they run on with no break between them. Where a day begins,
        its number goes in the margin beside the line (the passage's first word carries it)."""
        units, self.rif_day_at = [], dict(day_at)
        for j, p in enumerate(self.rif):
            toks = p["tokens"]
            if j in day_at and toks:
                toks = [[toks[0][0], toks[0][1], f"יום {heb(day_at[j])}"]] + toks[1:]
            units.append(Unit("p", self.words(toks, self.st_rif), j))
        return units

    # -------------------------------------------------- the Rosh: two columns
    def lines_of(self, units, w, st, lh):
        out = []
        for u in units:
            if u.kind == "p":
                ls = break_lines(u.words, st, lh, full_width(w))
            else:
                hl = lh * 1.35
                ls = break_lines(u.words, u.words[0].style, hl, full_width(w), 0.0, "center")
                for l in ls:
                    l.last = True
            for l in ls:
                l.unit = u
            out.extend(ls)
        return out

    def layout_rosh(self, units):
        self.rosh_units_list = units
        colw = (self.W - self.gap) / 2
        lines = self.lines_of(units, colw, self.st_rosh, self.lh_rosh)
        pages, i, n = [], 0, len(lines)
        while i < n:
            cols = []
            for _ in range(2):
                col, h = [], 0.0
                while i < n and h + lines[i].h <= self.H + EPS:
                    col.append(lines[i])
                    h += lines[i].h
                    i += 1
                # no heading or day marker alone at the bottom of a column
                while col and col[-1].unit.kind != "p" and i < n:
                    i -= 1
                    col.pop()
                cols.append(col)
            last = i >= n
            for col in cols:
                tot = sum(l.h for l in col)
                spare = self.H - tot
                if col and not last and 0 < spare < self.lh_rosh * 2.5:
                    for l in col:
                        l.h += spare / len(col)
                y = 0.0
                for l in col:
                    l.y = y
                    y += l.h
            pages.append({"kind": "rosh", "cols": cols, "colw": colw})
        return pages

    # -------------------------------------------------- the Rif with the commentary around it
    def rif_flow(self, units):
        """The Rif as a list of words with positions, for cutting pages anywhere."""
        self.units = units
        self.off, t = [], 0
        for u in units:
            self.off.append(t)
            t += len(u.words)
        self.total = t
        # the commentary as one run of words, entry after entry
        self.cwords, self.c_end_of_para = [], {}
        # where a day begins in the commentary: its first entry on the day's passage of the
        # Rif (or after it)
        day_entry, pending = {}, sorted(getattr(self, "rif_day_at", {}).items())
        for k, e in enumerate(self.comm):
            while pending and e["para"] >= pending[0][0]:
                day_entry.setdefault(k, pending[0][1])
                pending.pop(0)
        for k, e in enumerate(self.comm):
            toks = e["tokens"]
            # the dibbur hamatchil in its own letters (square, bold), also where it is Rashi's
            toks = [[t[0], "dh"] if q < e.get("dh_len", 0) and t[1] in (True, "rashi", "dh") else t
                    for q, t in enumerate(toks)]
            if k in day_entry and toks:
                toks = [[toks[0][0], toks[0][1], f"יום {heb(day_entry[k])}"]] + toks[1:]
            if e.get("open"):
                # the word that opens a Mishna, large in square letters
                k = next((i for i, t in enumerate(toks) if norm(t[0]) not in SKIP_DH), 0)
                toks = toks[:k] + [[toks[k][0], "copen"] + list(toks[k][2:])] + toks[k + 1:]
            if e.get("gem"):
                toks = [[f"[דף {e['gem']}]", "gem"]] + toks
            ws = self.words(toks, self.st_comm)
            self.cwords.extend(ws)
            self.c_end_of_para[e["para"]] = len(self.cwords)

    def c_upto(self, para):
        """How many commentary words belong to passages up to para (inclusive)."""
        best = 0
        for p, end in self.c_end_of_para.items():
            if p <= para and end > best:
                best = end
        return best

    def unit_at(self, g):
        lo, hi = 0, len(self.off) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.off[mid] <= g:
                lo = mid
            else:
                hi = mid - 1
        return lo

    def text_lines(self, a, b, width_at, y0=0.0):
        """Lines of the Rif words a..b laid out with width_at(y), from y0 down: one run of
        text, a passage going on in the line where the one before it ended. Each line
        knows its first passage (unit) and all the passages in it (refs)."""
        words, owner = [], []
        for k in range(self.unit_at(a), self.unit_at(max(a, b - 1)) + 1):
            u = self.units[k]
            s = max(a, self.off[k]) - self.off[k]
            e = min(b, self.off[k] + len(u.words)) - self.off[k]
            words += u.words[s:e]
            owner += [k] * max(0, e - s)
        if not words:
            return [], y0
        out = break_lines(words, self.st_rif, self.lh_rif, width_at, y0)
        i = 0
        for l in out:
            n = len(l.words)
            l.unit = self.units[owner[i]]
            l.refs = [self.units[k].ref for k in sorted(set(owner[i:i + n]))]
            i += n
        if b < self.total:
            out[-1].last = False
            out[-1].cut = True
        return out, out[-1].y + out[-1].h

    def take_cols(self, words, width_at, H, y0=0.0, band=None):
        """Fill the right column and then the left one, from y0 down; width_at(y) ->
        (right, width). band (y1, y2): no lines there (the Rif across the page); a column
        goes on under it."""
        cols, i, n = [], 0, len(words)
        sp = space(self.st_comm)
        for _ in range(2):
            col, y = [], y0
            while i < n:
                if band and band[0] - EPS <= y < band[1] - EPS:
                    y = band[1]
                if y + self.lh_comm > H + EPS:
                    break
                right, w = width_at(y)
                cur, nat, j = [words[i]], words[i].w, i + 1
                while j < n and nat + sp + words[j].w <= w + 0.01:
                    nat += sp + words[j].w
                    cur.append(words[j])
                    j += 1
                col.append(Line(cur, right, w, nat, self.lh_comm, self.st_comm, "justify", j >= n, y))
                y += self.lh_comm
                i = j
            cols.append(col)
        return cols, i

    def around(self, T, end):
        """The commentary's width at y: across its half of the page in the top block (above
        T) and under the Rif (from end), beside the Rif between them."""
        return lambda y: (0.0, self.wide) if y < T - EPS or y >= end - EPS else (0.0, self.cw)

    def beside(self, cws, limit):
        """The commentary cws as short as it goes: in the top block, then beside the Rif,
        no lower than limit. -> (cols, height, top block height) or None."""
        top = self.ktop * self.lh_comm
        for rows in range(0, int(self.H // self.lh_comm) + 1):
            h = rows * self.lh_comm
            if h > min(limit, self.H) + EPS:
                return None
            T = min(h, top)
            cs, k = self.take_cols(cws, self.around(T, self.H + 1), h)
            if k >= len(cws):
                return cs, h, T
        return None

    def compose(self, a, b, cptr, comm_only=False):
        """A page of the Rif from word a to b with the commentary from cptr. As on a page of
        the Gemara: the commentary's first lines (ktop) across its two columns at the top,
        the Rif under them in the middle with the commentary on its two sides, and the
        commentary under the Rif when it is longer; when it is shorter, the Rif widens
        under it."""
        Wt = self.W - 2 * (self.cw + self.gap)
        narrow = lambda y: (self.cw + self.gap, Wt)
        r = {"a": a, "b": b, "cptr": cptr, "at_end": b >= self.total}
        if b > a and not comm_only:
            last_unit = self.unit_at(b - 1)
            u = self.units[last_unit]
            done_unit = last_unit if self.off[last_unit] + len(u.words) <= b else last_unit - 1
            started = [x.ref for x in self.units[:last_unit + 1] if x.kind == "p"]
            completed = [x.ref for x in self.units[:done_unit + 1] if x.kind == "p"]
            avail = self.c_upto(started[-1]) if started else cptr
            req = self.c_upto(completed[-1]) if completed else cptr
        else:
            avail = req = cptr
            back = [x.ref for x in self.units[:self.unit_at(a) if a < self.total else len(self.units)] if x.kind == "p"]
            if a < self.total and self.off[self.unit_at(a)] < a:
                back = back[:-1]
            avail = req = max(cptr, self.c_upto(back[-1]) if back else cptr)
        if r["at_end"]:
            avail = req = len(self.cwords)
        avail, req = max(avail, cptr), max(req, cptr)
        cws = self.cwords[cptr:avail]
        T = self.ktop * self.lh_comm if cws else 0.0
        t0 = T + self.vgap / 2 if T else 0.0
        if comm_only or b <= a:
            text, th = [], 0.0
        else:
            text, th = self.text_lines(a, b, narrow, t0)
        r["t0"] = t0
        lim = th + self.vgap if text else T
        cols, n = self.take_cols(cws, self.around(T, lim), self.H)
        mode = "long"
        total = self.H
        if n >= len(cws):
            hcol = max((len(c) for c in cols), default=0) * self.lh_comm
            # the commentary is shorter: can it stay above and beside the Rif?
            fit = self.beside(cws, th if text else 0.0) if text else None
            if fit is not None:
                cols, hc, T2 = fit
                mode = "short"
                r["T"] = T2
                t02 = T2 + self.vgap / 2 if T2 else 0.0
                lim2 = hc + self.vgap if hc > T2 else 0.0
                wa = lambda y: (self.cw + self.gap, Wt) if y < lim2 else (0.0, self.W)
                text, th = self.text_lines(a, b, wa, t02)
                total = th
                r["hc"], r["t0"] = hc, t02
            else:
                # under the Rif, as far down as it goes: balance the two columns
                best = (cols, hcol)
                for rows in range(1, int(self.H // self.lh_comm) + 1):
                    h = rows * self.lh_comm
                    cs, k = self.take_cols(cws, self.around(T, lim), h)
                    if k >= len(cws):
                        best = (cs, h)
                        break
                cols, total = best
                total = max(total, th)
                mode = "under"
        if mode == "long" and text and (th > self.H + EPS or cptr + n < req):
            # the Rif doesn't fit narrow (or the commentary owed doesn't fit around it): keep
            # the commentary owed above and beside the Rif and let the Rif widen under it;
            # the commentary of the passage that goes on follows it to the next page
            alt = self.short_layout(a, b, self.cwords[cptr:req], th)
            if alt is not None:
                cols, hc, text, th2, t02 = alt
                r.update(text=text, th=th2, cols=cols, n=req - cptr, mode="short", total=th2, req=req, avail=avail,
                         hc=hc, t0=t02, T=max(0.0, t02 - self.vgap / 2))
                r["cnext"] = req
                r["fits"] = th2 <= self.H + EPS
                return r
        r.update(text=text, th=th, cols=cols, n=n if mode == "long" else len(cws), mode=mode, total=total,
                 req=req, avail=avail)
        r["cnext"] = cptr + r["n"]
        r["fits"] = total <= self.H + EPS and th <= self.H + EPS and cptr + r["n"] >= req
        return r

    def short_layout(self, a, b, cws, th):
        """The commentary cws above and beside the Rif, as short as it goes, and the Rif
        widening under it. -> (cols, hc, text lines, text bottom, text top) or None."""
        Wt = self.W - 2 * (self.cw + self.gap)
        fit = self.beside(cws, th)
        if fit is None:
            return None
        cs, h, T = fit
        t0 = T + self.vgap / 2 if T else 0.0
        lim = h + self.vgap if h > T else 0.0
        wa = lambda y: (self.cw + self.gap, Wt) if y < lim else (0.0, self.W)
        text, t = self.text_lines(a, b, wa, t0)
        return cs, h, text, t, t0

    def backlog(self, a, cptr):
        if a <= 0:
            return False
        k = self.unit_at(a - 1)
        u = self.units[k]
        if self.off[k] + len(u.words) > a:
            k -= 1
        refs = [x.ref for x in self.units[:k + 1] if x.kind == "p"]
        return bool(refs) and self.c_upto(refs[-1]) > cptr

    def layout_rif(self, units):
        self.rif_flow(units)
        pages, a, cptr, guard = [], 0, 0, 0
        min_text = 3 * self.lh_rif
        while (a < self.total or cptr < len(self.cwords)) and guard < 3000:
            guard += 1
            if a >= self.total:
                r = self.compose(a, a, cptr, comm_only=True)
                if r["n"] == 0:
                    break
                pages.append(self.finish(r))
                cptr = r["cnext"]
                continue
            lo, hi, g = a + 1, min(self.total, a + 800), 0
            while lo <= hi:
                mid = (lo + hi) // 2
                if self.compose(a, mid, cptr)["fits"]:
                    g, lo = mid, mid + 1
                else:
                    hi = mid - 1
            if g:
                x, miss = g + 1, 0
                while x <= min(self.total, g + 40) and miss < 8:
                    if self.compose(a, x, cptr)["fits"]:
                        g, miss = x, 0
                    else:
                        miss += 1
                    x += 1
            r = self.compose(a, g, cptr) if g else None
            if r is None or r["th"] - r.get("t0", 0.0) < min_text and not r["at_end"]:
                if self.backlog(a, cptr):
                    r2 = self.compose(a, a, cptr, comm_only=True)
                    if r2["n"]:
                        pages.append(self.finish(r2))
                        cptr = r2["cnext"]
                        continue
                # a commentary longer than a page: a few lines of the Rif, the rest runs on
                x = a + 1
                while x < self.total and self.text_lines(a, x, lambda y: (0, self.W - 2 * (self.cw + self.gap)))[1] < min_text:
                    x += 1
                r = self.compose(a, x, cptr)
                r["cnext"] = cptr + r["n"]
            if not r["at_end"] and r["b"] > a:
                # end the page at the end of a passage (the Rif's colon) when it stays full
                for k in range(self.unit_at(r["b"] - 1), -1, -1):
                    e = self.off[k] + len(self.units[k].words)
                    if e > r["b"]:
                        continue
                    if e <= a or r["b"] - e > 70:
                        break
                    if self.units[k].kind != "p":
                        continue
                    q = self.compose(a, e, cptr)
                    if q["fits"] and self.full(q):
                        r = q
                        break
            if r["mode"] == "short" and not r["at_end"] and self.H - r["total"] > 1.5 * self.lh_rif:
                # the Rif widened under a short commentary and still leaves a hole: rather a
                # little less of the Rif, with the commentary filling the page around it
                x = r["b"] - 1
                while x > a + 1:
                    q = self.compose(a, x, cptr)
                    if q["fits"] and q["mode"] == "long" and q["th"] - q.get("t0", 0.0) >= min_text:
                        r = q
                        break
                    x -= 3
            r = self.end_on_line(r)
            r = self.fill_below(r)
            pages.append(self.finish(r))
            a, cptr = r["b"], r["cnext"]
        return pages

    def fill_below(self, r):
        """A page where the Rif widened under a short commentary and ended (at the end of a
        passage) with room left at the bottom: the commentary goes on under the Rif in its
        two columns, as on a page of the Gemara (each column: the top block, beside the
        Rif, and on under it)."""
        if r["mode"] != "short" or r["at_end"] or not r["text"]:
            return r
        y0 = r["th"] + self.vgap
        rows = int((self.H - y0 + EPS) // self.lh_comm)
        if rows < 2 or r["avail"] <= r["cnext"]:
            return r
        hc, T = r.get("hc", 0.0), r.get("T", 0.0)
        top = self.around(T, self.H + 1)
        width_at = lambda y: top(y) if y < hc - EPS else (0.0, self.wide)
        words = self.cwords[r["cptr"]:r["avail"]]
        cs, k = self.take_cols(words, width_at, y0 + rows * self.lh_comm, 0.0, (hc, y0))
        if k <= r["cnext"] - r["cptr"]:
            return r
        for c in cs:
            for l in c:
                l.keep = l.y < hc - EPS
        r["cols"] = cs
        r["cnext"] = r["cptr"] + k
        r["below"] = y0
        return r

    def full(self, q):
        if q["mode"] == "long":
            return True
        if q["mode"] == "short":
            return self.H - q["total"] < 1.5 * self.lh_rif
        return self.H - q["total"] < 2 * self.lh_comm

    def end_on_line(self, r):
        """End the Rif on a full line when the page stays full without the last line."""
        t = r["text"]
        if r["at_end"] or not t or not getattr(t[-1], "cut", False):
            return r
        last = t[-1]
        if last.natural >= last.width * 0.9 or len(t) < 2:
            return r
        b2 = r["b"] - len(last.words)
        if b2 <= r["a"]:
            return r
        r2 = self.compose(r["a"], b2, r["cptr"])
        if r2["fits"] and (r2["mode"] == "long" or self.H - r2["total"] < self.lh_rif * 1.5):
            return r2
        return r

    def finish(self, r):
        """Stretch the lines so that every column and the text reach the bottom."""
        def stretch(lines, target, cap):
            if not lines:
                return
            h = sum(l.h for l in lines)
            spare = target - (lines[0].y + h)      # the lines may begin lower (the Rif under the top block)
            if 0 < spare <= cap:
                for l in lines:
                    l.h += spare / len(lines)
            y = lines[0].y if lines else 0.0
            for l in lines:
                l.y = y
                y += l.h

        last = r["at_end"] and r["cnext"] >= len(self.cwords)
        if r["mode"] == "long":
            for c in r["cols"]:
                stretch(c, self.H, self.lh_comm * 1.5)
        elif r["mode"] == "short" and "below" in r:
            T = r.get("T", 0.0)
            for c in r["cols"]:
                # the top block stays as it is: only the lines beside the Rif open
                side = [l for l in c if getattr(l, "keep", False) and l.y >= T - EPS]
                under = [l for l in c if not getattr(l, "keep", False)]
                stretch(side, r.get("hc", 0.0), self.lh_comm * 1.5)
                stretch(under, self.H, self.lh_comm * 1.5)
            stretch(r["text"], r["below"] - self.vgap, self.lh_rif * 0.25 * max(1, len(r["text"])))
        elif r["mode"] == "short":
            hc, T = r.get("hc", 0.0), r.get("T", 0.0)
            for c in r["cols"]:
                stretch([l for l in c if l.y >= T - EPS], hc, self.lh_comm * 1.5)
            if not last:
                stretch(r["text"], self.H, self.lh_rif * 0.25 * max(1, len(r["text"])))
        else:
            for c in r["cols"]:
                stretch(c, r["total"] if last else self.H, self.lh_comm * 0.3 * max(1, len(c)))
        r["kind"] = "rif"
        return r

    # -------------------------------------------------- pages
    def render(self, rosh_pages, rif_pages, xref, title_rosh, title_rif, first=1):
        out = []
        allp = rosh_pages + rif_pages
        for n, pg in enumerate(allp):
            page = Page(self.pw, self.ph)
            L, R, T = self.m, self.pw - self.m, self.m
            right = f"{self.name} · {title_rosh if pg and pg['kind'] == 'rosh' else title_rif}"
            center = xref[n]
            num = heb(first + n)
            if n % 2 == 1:
                right, num = num, right
            if pg is None:
                # a blank page, so that the Rif begins on a left-hand page
                out.append(page)
                continue
            page.head = (right, center, num, self.head_style, T + self.hs * 1.3 * 0.8)
            page.rules.append((L, T + self.hs * 1.3 + 1 * PT_PER_MM, R))
            top = T + self.head_h
            if pg["kind"] == "rosh":
                page.marks = []
                mst = Style("Frank Ruhl Libre", 7.5, True)
                for k, col in enumerate(pg["cols"]):
                    if col:
                        page.frames.append(Frame(col, R - k * (pg["colw"] + self.gap), top))
                    for l in col:
                        labels = [w.ref for w in l.words if isinstance(w.ref, str)]
                        if labels:
                            # in the outer margin beside the line: the right column's on the right
                            x = R + self.m / 2 if k == 0 else L - self.m / 2
                            page.marks.append((x, top + l.y + l.h * 0.72, " ".join(labels), mst))
            else:
                # where a day begins: in the margin beside the line, of the Rif on the right,
                # of the commentary on its column's side
                page.marks = []
                mst = Style("Frank Ruhl Libre", 7.5, True)
                sides = [(pg["text"], R + self.m / 2)]
                if pg["cols"]:
                    sides.append((pg["cols"][0], R + self.m / 2))
                if len(pg["cols"]) > 1:
                    sides.append((pg["cols"][1], L - self.m / 2))
                for lines, x in sides:
                    for l in lines:
                        labels = [w.ref for w in l.words if isinstance(w.ref, str)]
                        if labels:
                            page.marks.append((x, top + l.y + l.h * 0.72, " ".join(labels), mst))
                if pg["text"]:
                    page.frames.append(Frame(pg["text"], R, top))
                cols = pg["cols"]
                if cols and cols[0]:
                    page.frames.append(Frame(cols[0], R, top))
                if len(cols) > 1 and cols[1]:
                    # the left column: lines beside the Rif sit at its left edge
                    for l in cols[1]:
                        l.right = (self.wide - l.width) if l.width < self.wide - 0.5 else 0.0
                    page.frames.append(Frame(cols[1], L + self.wide, top))
            out.append(page)
        return out


# ---------------------------------------------------------------- the whole Shas

MASECHTOT = ["ברכות", "שבת", "עירובין", "פסחים", "יומא", "סוכה", "ביצה", "ראש השנה", "תענית", "מגילה", "מועד קטן",
             "יבמות", "כתובות", "נדרים", "גיטין", "קידושין", "בבא קמא", "בבא מציעא", "בבא בתרא", "סנהדרין", "מכות",
             "שבועות", "עבודה זרה", "מנחות", "חולין", "בכורות", "נידה"]
DAYS = 354


def find_file(root, *names):
    for name in names:
        for base, _, files in os.walk(root):
            if name in files:
                return os.path.join(base, name)
    return None


def sources(root, m):
    """The files of masechet m under the Otzaria library folder root."""
    rish = os.path.join(root, "אוצריא", "תלמוד בבלי", "ראשונים")
    comm, comm_name = None, ""
    for fname, nm in ((f"רן על {m}.txt", 'ר"ן'), (f"נימוקי יוסף על {m}.txt", "נימוקי יוסף"),
                      (f"רבינו יונה על {m}.txt", "רבינו יונה"),
                      (f"רבינו יהונתן מלוניל על {m}.txt", "רבינו יהונתן")):
        p = find_file(os.path.join(rish, "ריף", "מפרשים"), fname)
        if p:
            comm, comm_name = p, nm
            break
    gem = [find_file(os.path.join(root, "אוצריא", "תלמוד בבלי"), f"{m}.txt"),
           find_file(os.path.join(root, "OraytaToOtzaria"), f"{m}.txt")]
    rashi = [find_file(os.path.join(rish, "רשי"), f"רשי על {m}.txt"),
             find_file(os.path.join(root, "OraytaToOtzaria"), f"תלמוד בבלי - {m} - רשי.txt")]
    return {
        "rosh": find_file(os.path.join(rish, "ראש"), f"פסקי הראש על {m}.txt"),
        "rif": find_file(os.path.join(rish, "ריף"), f"ריף {m}.txt", f"הלכות קטנות לריף ({m}).txt"),
        "comm": comm, "comm_name": comm_name,
        "gemara": [p for p in gem if p], "rashi": [p for p in rashi if p],
    }


def count_words(path):
    if not path:
        return 0
    with open(path, encoding="utf-8") as f:
        return len(re.sub(r"<[^>]+>", " ", f.read()).split())


def day_plan(root):
    """How many days each masechet gets (of DAYS, by the length of its texts), and the
    number of its first day."""
    w = {}
    for m in MASECHTOT:
        s = sources(root, m)
        w[m] = count_words(s["rosh"]) + count_words(s["rif"]) + count_words(s["comm"])
    tot = sum(w.values())
    raw = {m: DAYS * w[m] / tot for m in MASECHTOT}
    days = {m: max(1, int(raw[m])) for m in MASECHTOT}
    left = DAYS - sum(days.values())
    for m in sorted(MASECHTOT, key=lambda x: raw[x] - int(raw[x]), reverse=True)[:max(0, left)]:
        days[m] += 1
    first, n = {}, 1
    for m in MASECHTOT:
        first[m] = n
        n += days[m]
    return days, first


def plain_refs(toks):
    """A reference in round brackets ("(סנהדרין פו.)", "(דף ב.)") is not part of a
    quotation: never bold."""
    for k, t in enumerate(toks):
        if not t[0].startswith("("):
            continue
        # to the closing bracket, if it comes within a few words (a reference is short)
        e = next((q for q in range(k, min(len(toks), k + 6)) if toks[q][0].endswith(")")), None)
        if e is None:
            continue
        for q in range(k, e + 1):
            if toks[q][1] in (True, "rashi"):
                toks[q][1] = False


def load_masechet(root, m, found=None):
    s = sources(root, m)
    rosh = parse_rosh(read(s["rosh"])) if s["rosh"] else []
    rif = parse_rif(read(s["rif"])) if s["rif"] else []
    comm = parse_comm(read(s["comm"])) if s["comm"] else []
    report = []
    if comm and comm[0]["tokens"] and norm(comm[0]["tokens"][0][0]) == "רנ":
        # the title at the head of the commentary ("ר"ן מגילה")
        k = 1 + len(m.split())
        if [norm(w) for w, *_ in comm[0]["tokens"][1:k]] == [norm(w) for w in m.split()]:
            comm[0]["tokens"] = comm[0]["tokens"][k:]
        else:
            comm[0]["tokens"] = comm[0]["tokens"][1:]
    if comm:
        link_comm(comm, rif)
    mark_labels([t for x in rosh for t in x["paras"]])
    mark_labels([p["tokens"] for p in rif])
    if rif:
        n = mark_aligned([t for x in rosh for p in x["paras"] for t in p], [t for p in rif for t in p["tokens"]],
                         loose_words=True, fill=(3, 5), found=found)
        report.append(f"ברא\"ש הודגשו {n} מילים מהרי\"ף")
    if comm:
        # the commentary's own dibbur hamatchil in plain type (as in the Oz Vehadar Rif);
        # bold is what it takes from Rashi on the Gemara of the place
        for e in comm:
            e["dh_len"] = 0
            for t in e["tokens"]:
                if t[1] is True:
                    t[1] = "dh"
                    e["dh_len"] += 1
        if s["rashi"] and s["gemara"]:
            rashi = parse_rashi(read(s["rashi"][0]))
            gl = read(s["gemara"][0])
            amudim = passage_amudim(rif, gl)
            gtoks, gamud = parse_gemara(gl)
            g = lseq(gtoks)[0]
            gem = {tuple(g[k:k + 3]) for k in range(len(g) - 2)}
            n = 0
            for e in comm:
                a = amudim[e["para"]]
                near = [x for x in rashi if a is not None and a - 2 <= x["amud"] <= a + 2]
                e["why"] = [] if a is not None else None     # None: no Gemara of ours, Rashi not looked at
                n += mark_rashi(e["tokens"], near, gem, trace=e["why"])
            report.append(f"ב{s['comm_name']} הודגשו {n} מילים מרש\"י")
            report.append(f"ב{s['comm_name']} {comm_gemara_marks(comm, amudim, gtoks, gamud)} סימני דפי הגמרא")
        report.append(f"ב{s['comm_name']} {mishna_openers(comm, rif)} פתיחות של משנה")
    for x in rosh:
        for p in x["paras"]:
            plain_refs(p)
    for e in comm:
        plain_refs(e["tokens"])
    return rosh, rif, comm, s["comm_name"], report


def day_starts(rosh, rif, comm, ndays, al):
    """Where each day begins: (siman index, passage index) pairs, the Rosh at the start of a
    siman and the Rif at the start of a passage, both about the same place; the days as
    even as they can be (first_starts, then balance_days)."""
    starts = first_starts(rosh, rif, comm, ndays, al)
    return balance_days(starts, rosh, rif, comm, al)


def day_amounts(starts, rw_cum, rif_cum, nrif):
    """The words of each day: the Rosh from its siman to the next day's, the Rif (with the
    commentary) from its passage to the next day's marker in the Rif's own order."""
    ks = [k for k, _ in starts] + [len(rw_cum) - 1]
    js = sorted(j for _, j in starts)
    nxt = {a: b for a, b in zip(js, js[1:] + [nrif])}
    return [rw_cum[ks[d + 1]] - rw_cum[ks[d]] + (rif_cum[nxt[j]] - rif_cum[j] if nrif else 0)
            for d, (_, j) in enumerate(starts)]


def balance_days(starts, rosh, rif, comm, al, reach=10, rif_reach=(-1, 4)):
    """Make the days as even as they can be: each day's start moved a few simanim (and its
    passage in the Rif a passage or two from the siman's own, or anywhere in Rif that has
    nothing in the Rosh before the siman's) while that makes the largest
    day's distance from the mean smaller, or (the largest the same) all of them together."""
    if len(starts) < 2:
        return starts
    rw = [sum(len(p) for p in s["paras"]) for s in rosh]
    fw = [len(p["tokens"]) for p in rif]
    for e in comm:
        fw[e["para"]] += len(e["tokens"])
    rw_cum, rif_cum = [0], [0]
    for x in rw:
        rw_cum.append(rw_cum[-1] + x)
    for x in fw:
        rif_cum.append(rif_cum[-1] + x)
    nrif = len(rif)
    mean = (rw_cum[-1] + rif_cum[-1]) / len(starts)

    def cost(st):
        a = day_amounts(st, rw_cum, rif_cum, nrif)
        dev = [abs(x - mean) / mean for x in a]
        return (round(max(dev), 4), sum(d * d for d in dev))

    def options(d, st):
        lo = st[d - 1][0] + 1
        hi = (st[d + 1][0] - 1) if d + 1 < len(st) else len(rosh) - 1
        k0 = st[d][0]
        taken = {j for i, (_, j) in enumerate(st) if i != d}
        for k in range(max(lo, k0 - reach), min(hi, k0 + reach) + 1):
            if not nrif:
                yield (k, 0)
                continue
            # about the siman's place in the Rif: between the places of the simanim a few
            # before and after it (where the Rosh is short against the Rif, its simanim are
            # far apart there); or, where the passages before it are Rif the Rosh has
            # nothing against (Shevuot: the Rif's first perakim), any of them
            near = [al[i] for i in range(max(0, k - 3), min(len(al), k + 4)) if abs(al[i] - al[k]) <= 40]
            below = [a for a in al if a < al[k]]
            lo_j = min(min(near) + rif_reach[0], (max(below) + 1) if below else 1)
            hi_j = max(near) + rif_reach[1]
            # in the order of the days, unless the Rif goes back here (perakim in another order)
            pj, pk = st[d - 1][1], st[d - 1][0]
            if al[k] >= al[pk] - 6:
                lo_j = max(lo_j, pj + 1)
            if pj < min(al):
                # the day before begins in the Rif before anything of the Rosh: this one may
                # too (that stretch shared among the first days)
                lo_j = min(lo_j, pj + 1)
            if d + 1 < len(st) and al[st[d + 1][0]] >= al[k] - 6:
                hi_j = min(hi_j, st[d + 1][1] - 1)
            for j in range(max(1, lo_j, al[k] - 80), hi_j + 1):
                if 0 < j < nrif and j not in taken:
                    yield (k, j)

    st, best = list(starts), cost(starts)
    for _ in range(60):
        better = False
        for d in range(1, len(st)):
            for o in options(d, st):
                if o == st[d]:
                    continue
                trial = st[:d] + [o] + st[d + 1:]
                c = cost(trial)
                if c < best:
                    st, best, better = trial, c, True
        if better:
            continue
        # stuck: two neighbouring starts moved together, around the day furthest from the
        # mean (making one day smaller makes the next one larger)
        a = day_amounts(st, rw_cum, rif_cum, nrif)
        worst = max(range(len(a)), key=lambda i: abs(a[i] - mean))
        for d in {x for x in (worst - 1, worst, worst + 1, worst + 2) if 1 <= x < len(st) - 1}:
            for o in list(options(d, st)):
                t1 = st[:d] + [o] + st[d + 1:]
                for o2 in options(d + 1, t1):
                    trial = t1[:d + 1] + [o2] + t1[d + 2:]
                    c = cost(trial)
                    if c < best:
                        st, best, better = trial, c, True
        if not better:
            break
    return st


def first_starts(rosh, rif, comm, ndays, al):
    """A first division into days: each day's start the siman nearest to where its share of
    the masechet begins."""
    rw = [sum(len(p) for p in s["paras"]) for s in rosh]
    fw = [len(p["tokens"]) for p in rif]
    cw = [0] * len(rif)
    for e in comm:
        cw[e["para"]] += len(e["tokens"])
    total = sum(rw) + sum(fw) + sum(cw)
    cum_r = [0]
    for x in rw:
        cum_r.append(cum_r[-1] + x)
    # the Rif's share of each siman: its passages up to where the next siman's (in the
    # Rif's order) begin; so the days follow the Rosh even where the Rif has the perakim
    # in another order
    share = [0] * len(rosh)
    if rif:
        firsts = sorted(set(al))
        nxt = {a: b for a, b in zip(firsts, firsts[1:] + [len(rif)])}
        owner = {}
        for k, j in enumerate(al):
            owner.setdefault(j, k)
        for j, k in owner.items():
            share[k] = sum(fw[x] + cw[x] for x in range(j, nxt[j]))
    cum_f = [0]
    for x in share:
        cum_f.append(cum_f[-1] + x)
    starts, used = [(0, 0)], {al[0] if rif else 0}
    for d in range(1, ndays):
        target = total * d / ndays
        best = None
        # leave a siman for each day that comes after this one
        for k in range(starts[-1][0] + 1, len(rosh) - (ndays - 1 - d)):
            j = al[k] if rif else 0
            if rif and (j in used or j == al[k - 1]):
                # the Rif's passage of the siman is taken: the next one that is not (the
                # day then begins in the Rif a passage later)
                j = next((x for x in range(al[k] + 1, len(rif)) if x not in used), None)
                if j is None:
                    continue
            w = cum_r[k] + cum_f[k]
            if best is None or abs(w - target) < abs(best[0] - target):
                best = (w, k, j)
        if best is None:
            break
        starts.append((best[1], best[2]))
        used.add(best[2])
    return starts


def check_layout(book, rosh_pages, rif_pages):
    """What is wrong in the layout of a masechet: text beyond the bottom of the page, a
    page left with a hole at the bottom (not the last), a page of the Rif without the Rif
    (commentary only), a column of the Rosh left empty. -> [{'kind', 'page', 'detail'}]
    (page: 1-based, in the masechet's numbering)."""
    out, H = [], book.H
    for n, pg in enumerate(rosh_pages):
        for k, col in enumerate(pg["cols"]):
            bottom = max((l.y + l.h for l in col), default=0.0)
            if bottom > H + 0.5:
                out.append({"kind": "overflow", "page": n + 1, "detail": f"טור {k + 1} של הרא\"ש יוצא מהעמוד"})
            if not col and n < len(rosh_pages) - 1:
                out.append({"kind": "empty", "page": n + 1, "detail": f"טור {k + 1} של הרא\"ש ריק"})
            elif n < len(rosh_pages) - 1 and H - bottom > 3 * book.lh_rosh:
                out.append({"kind": "hole", "page": n + 1, "detail": f"חלל בתחתית טור {k + 1} של הרא\"ש"})
    off = len(rosh_pages) + (1 if rif_pages and len(rosh_pages) % 2 == 1 else 0)
    for n, pg in enumerate(rif_pages):
        last = n == len(rif_pages) - 1
        lines = list(pg["text"]) + [l for c in pg["cols"] for l in c]
        bottom = max((l.y + l.h for l in lines), default=0.0)
        if bottom > H + 0.5:
            out.append({"kind": "overflow", "page": off + n + 1, "detail": "טקסט יוצא מתחתית העמוד"})
        if not last and H - bottom > 3 * book.lh_comm:
            out.append({"kind": "hole", "page": off + n + 1, "detail": "חלל בתחתית העמוד"})
        if not pg["text"]:
            out.append({"kind": "comm_only", "page": off + n + 1, "detail": "עמוד של מפרש בלבד"})
        # no line of the Rif on a line of the commentary
        R, cw = book.W, book.wide
        boxes = [(R - l.right - l.width, R - l.right, l.y, l.y + l.h) for l in pg["text"]]
        for k, col in enumerate(pg["cols"]):
            for l in col:
                if k == 0:
                    x1, x2 = R - l.width, R
                else:
                    right = (cw - l.width) if l.width < cw - 0.5 else 0.0
                    x2 = cw - right
                    x1 = x2 - l.width
                for a1, a2, b1, b2 in boxes:
                    if a1 < x2 - 1 and x1 + 1 < a2 and b1 < l.y + l.h - 1 and l.y + 1 < b2:
                        out.append({"kind": "overlap", "page": off + n + 1, "detail": "שורת רי\"ף על שורת מפרש"})
                        break
                else:
                    continue
                break
    # every word on the pages once, in its order: the Rosh, the Rif, the commentary
    def same(name, laid, src):
        if [id(w) for w in laid] != [id(w) for w in src]:
            lost = len({id(w) for w in src} - {id(w) for w in laid})
            twice = len(laid) - len({id(w) for w in laid})
            out.append({"kind": "words", "page": 0,
                        "detail": f"{name}: {lost} מילים חסרות, {twice} כפולות, או סדר שונה"})
    # every day marked once in the Rosh, and (where there is a Rif) once in the Rif and once
    # in the commentary
    def days_in(words):
        return [w.ref for w in words if isinstance(w.ref, str) and w.ref.startswith("יום ")]
    rosh_days = [" ".join(w.text for w in l.words) for pg in rosh_pages for c in pg["cols"] for l in c
                 if l.unit.kind == "d"]
    parts = [("הרא\"ש", rosh_days)]
    if rif_pages:
        parts.append(("הרי\"ף", days_in(w for pg in rif_pages for l in pg["text"] for w in l.words)))
        if book.cwords:
            parts.append(("המפרש", days_in(w for pg in rif_pages for c in pg["cols"] for l in c for w in l.words)))
    for name, got in parts:
        if len(got) != len(set(got)) or (len(parts) > 1 and len(got) != len(parts[0][1])):
            out.append({"kind": "days", "page": 0,
                        "detail": f"{name}: {len(got)} סימוני ימים ({len(set(got))} שונים) מול {len(parts[0][1])} ברא\"ש"})
    if rosh_pages:
        same("הרא\"ש", [w for pg in rosh_pages for c in pg["cols"] for l in c if l.unit.kind == "p" for w in l.words],
             [w for u in book.rosh_units_list if u.kind == "p" for w in u.words])
    if rif_pages:
        same("הרי\"ף", [w for pg in rif_pages for l in pg["text"] for w in l.words],
             [w for u in book.units for w in u.words])
        same("המפרש", [w for pg in rif_pages for c in pg["cols"] for l in c for w in l.words], book.cwords)
    return out


def build_masechet(root, m, first_day, ndays, page=(210, 297), sizes=None, fix=None):
    """The book of masechet m: (pages, report, info). sizes: the Book's sizes (margin,
    rosh_size, ...). fix(rosh, rif, comm, al, found), if given, checks the bold before the
    layout and corrects it, and returns what it found. Pages: the Rosh, then (from a
    left-hand page, after a blank one when needed) the Rif."""
    found = []
    rosh, rif, comm, comm_name, report = load_masechet(root, m, found)
    al = align(rosh, rif) if rif and rosh else [0] * len(rosh)
    if rif and rosh:
        report.append(f"ברא\"ש {complete_sentences(rosh, rif, al)} מילים בהשלמת משפטים")
        rif_page_marks(rosh, rif, al)
    gem = sources(root, m)["gemara"]
    if rosh and gem:
        report.append(f"ברא\"ש {gemara_marks(rosh, read(gem[0]))} סימני דפי הגמרא")
    issues = fix(rosh, rif, comm, al, found) if fix else []
    starts = day_starts(rosh, rif, comm, ndays, al)
    rosh_days = {k: first_day + d for d, (k, _) in enumerate(starts)}
    rif_days = {j: first_day + d for d, (_, j) in enumerate(starts)} if rif else {}
    book = Book(m, rosh, rif, comm, comm_name, page, **(sizes or {}))
    rosh_pages = book.layout_rosh(book.rosh_units(rosh_days)) if rosh else []
    rif_pages = book.layout_rif(book.rif_units(rif_days)) if rif else []
    # the Rif from a left-hand page (an odd one): a blank page after the Rosh when it ends on one
    pad = [None] if rif_pages and len(rosh_pages) % 2 == 1 else []
    # where each siman and each passage begins (book page index)
    siman_page, para_page = {}, {}
    for n, pg in enumerate(rosh_pages):
        for col in pg["cols"]:
            for l in col:
                u = l.unit
                if u.kind == "p" and u.first and u.ref not in siman_page:
                    siman_page[u.ref] = n
    off = len(rosh_pages) + len(pad)
    for n, pg in enumerate(rif_pages):
        for l in pg["text"]:
            for ref in getattr(l, "refs", [l.unit.ref]):
                para_page.setdefault(ref, off + n)
    xref, amud = [], None
    for n, pg in enumerate(rosh_pages):
        refs = [l.unit.ref for col in pg["cols"] for l in col if l.unit.kind == "p"]
        perek = rosh[refs[0]]["perek"] if refs else ""
        s = refs[0] if refs else None
        target = para_page.get(al[s]) if (s is not None and rif) else None
        # the amudim of the Gemara the page is on: the one it opens in, to the last marked
        ws = [w.text for col in pg["cols"] for l in col for w in l.words]
        seen = [w[4:-1] for w in ws if GEM_MARK.match(w)]
        opens = seen and any(GEM_MARK.match(w) for w in ws[:2])    # a mark at the head of the page
        first = seen[0] if (opens or not amud) and seen else amud
        if seen:
            amud = seen[-1]
        daf = (f"דף {first}" + (f"–{amud}" if amud != first else "")) if first else ""
        xref.append(" · ".join(x for x in (perek, daf) if x) +
                    (f" · ברי\"ף עמ' {heb(target + 1)}" if target is not None else ""))
    xref += [""] * len(pad)
    for n, pg in enumerate(rif_pages):
        refs = [l.unit.ref for l in pg["text"] if l.unit.kind == "p"]
        if refs:
            j = refs[0]
            daf = rif[j]["daf"]
            xref.append(f"דף {daf}")
        else:
            xref.append(comm_name)
    title_rif = f"רי\"ף ו{comm_name}" if comm_name else "רי\"ף"
    pages = book.render(rosh_pages, pad + rif_pages, xref, "פסקי הרא\"ש", title_rif)
    report.append(f"{m}: {len(rosh_pages)} עמודי רא\"ש, {len(rif_pages)} עמודי רי\"ף, ימים {heb(first_day)}–{heb(first_day + len(starts) - 1)}")
    info = {"name": m, "comm_name": comm_name, "rosh_pages": len(rosh_pages), "rif_pages": len(rif_pages),
            "first_day": first_day, "last_day": first_day + len(starts) - 1, "issues": issues,
            "layout": check_layout(book, rosh_pages, rif_pages)}
    return pages, report, info
