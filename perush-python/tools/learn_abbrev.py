"""Learn the abbreviations (ראשי תיבות) of the Rosh and the commentaries from the texts
themselves: where one text writes a word abbreviated and the text it quotes writes it in full
(the Rosh against the Rif, the Ran or Nimukei Yosef against the Rif), between the same
words on both sides, and the full words' first letters are the abbreviation's letters.
Each expansion seen at least twice goes into data/abbrev_learned.txt (abbrev.py reads it).

    python tools/learn_abbrev.py LIBRARY
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from perush import shas  # noqa: E402
from perush.abbrev import TABLE  # noqa: E402

PREFIX = "ודהבלמשכ"


def words(toks):
    return [t[0] if isinstance(t, list) else t for t in toks]


def clean(w):
    return w.strip(".,:;()[]<>*")


def letters_of(abbr):
    return abbr.replace('"', "").replace("'", "").replace("״", "").replace("׳", "")


def learn(S, R, found):
    """S: words of the quoting text, R: words of the text quoted (near it)."""
    Rl = [shas.loose(clean(w)) for w in R]
    pos = collections.defaultdict(list)
    for i, x in enumerate(Rl):
        pos[x].append(i)
    for k, w in enumerate(S):
        w0 = clean(w).replace("״", '"').replace("׳", "'")
        if '"' not in w0 or k == 0 or k + 1 >= len(S):
            continue
        letters = letters_of(w0)
        if not (2 <= len(letters) <= 5):
            continue
        p, n = shas.loose(clean(S[k - 1])), shas.loose(clean(S[k + 1]))
        if not p or not n:
            continue
        for i in pos.get(p, ()):
            for m in range(1, len(letters) + 1):
                j = i + 1 + m
                if j >= len(Rl) or Rl[j] != n:
                    continue
                full = [clean(x) for x in R[i + 1:i + 1 + m]]
                if not all(full):
                    continue
                # the abbreviation's letters: the full words' first letters, the last word
                # may give two (ר"ל = ריש לקיש; אע"פ = אף על פי; בהכ"נ = בית הכנסת)
                heads = "".join(x[0] for x in full)
                ok = heads == letters or (len(full) >= 1 and heads[:-1] + full[-1][:2] == letters)
                # a prefix written on the abbreviation (דר"י = דרבי יהודה)
                if not ok and letters[0] in PREFIX and full[0][0] == letters[0]:
                    h2 = full[0][1:2] + "".join(x[0] for x in full[1:])
                    ok = (letters[0] + h2) == letters
                if ok:
                    found[w0][" ".join(full)] += 1


def main(root):
    found = collections.defaultdict(collections.Counter)
    names = [n for _, ms in __import__("perush.shas_book", fromlist=["SEDARIM"]).SEDARIM for n in ms]
    for m in names:
        s = shas.sources(root, m)
        if not s["rosh"] or not s["rif"]:
            continue
        try:
            rosh = shas.parse_rosh(shas.read(s["rosh"]))
            rif = shas.parse_rif(shas.read(s["rif"]))
            al = shas.align(rosh, rif)
        except Exception as e:      # (a masechet the parser cannot read: skipped)
            print(m, "skipped", e)
            continue
        for i, x in enumerate(rosh):
            lo, hi = max(0, al[i] - 2), min(len(rif), (al[i + 1] if i + 1 < len(rosh) else al[i]) + 3)
            R = [w for p in rif[lo:hi] for w in words(p["tokens"])]
            for p in x["paras"]:
                learn(words(p), R, found)
        if s["comm"]:
            comm = shas.parse_comm(shas.read(s["comm"]))
            try:
                shas.link_comm(comm, rif)
            except Exception:
                comm = []
            for e in comm:
                j = e.get("para")
                if j is None:
                    continue
                R = [w for p in rif[max(0, j - 1):j + 2] for w in words(p["tokens"])]
                learn(words(e["tokens"]), R, found)
        print(m, sum(len(v) for v in found.values()), flush=True)
    out = []
    for abbr, c in sorted(found.items()):
        known = TABLE.get(abbr)
        good = [f for f, n in c.most_common(3) if n >= 2]
        if not good:
            continue
        if known and all(tuple(f.split()) in [tuple(k) for k in [known]] for f in good):
            continue
        out.append(f"{abbr}=" + "|".join(good))
    path = os.path.join(HERE, "data", "abbrev_learned.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# ראשי תיבות שנלמדו מהטקסטים עצמם (tools/learn_abbrev.py): קיצור=פירוש|פירוש\n")
        f.write("\n".join(out) + "\n")
    print(len(out), "abbreviations ->", path)


if __name__ == "__main__":
    main(sys.argv[1])
