"""Sort every word the curation looked at into words/*.json, each word in exactly one file.

    python3 dictionary/curation/catalogue.py

Then `node dictionary/curation/export.mjs` turns words/approved.json into the database
documents in dictionary/curated/.

Inputs: labels.csv (the user's verdicts), dialect.json (dialect flags), opus_review.json (Opus
keep/drop over the approved words and the 30-40 band, prompts/opus_review.md), and the caches
in cache/ (candidate universe from sweep.py, Sonnet scores from sonnet.py).

| File | What |
|---|---|
| approved.json | the user's yes-words, words Sonnet scored >= 40, and 30-40 words Opus kept |
| rejected.json | words the user said no to |
| excluded.json | approved, then dropped: dialect, accented spelling, no bokmål/nynorsk article, or Opus review |
| sonnet_30-40.json ... sonnet_0-10.json | unreviewed words by Sonnet's yes-probability |
| haiku_vetoed.json | Haiku vetoed them (reason in `flag`); Sonnet never saw them |
| haiku_rejected.json | Haiku's ranking put them below the review line; Sonnet never saw them |
| classifier_low.json | the logistic model scored them too low to screen |
| rule_filtered.json | hard filters: technical term, place, number, person noun, dialect/archaic tag ... |

A bm/nn twin counts as one word: only one side is kept, in its dictionary.
"""

import csv
import json
import os
import re
import sqlite3
from collections import Counter

import expand
import lexicon
import sonnet

HERE = os.path.dirname(os.path.abspath(__file__))
WORDS = os.path.join(HERE, "words")
SWEEP = os.path.join(lexicon.CACHE, "sweep")

APPROVE = sonnet.APPROVE
BANDS = [(30, 40), (20, 30), (10, 20), (0, 10)]
# "dialekter" / "i dialekt" are the ordbokene labels; dialektal(t) is used in prose.
DIALECT = re.compile(r"\bdialekt(?!ik)", re.I)
ACCENTED = re.compile(r"[^a-zæøå]")
# Opus reasons that break the user's stated rules. On taste (common, dull, derived) the user's own
# yes stands; for words only a model approved, any Opus drop counts.
RULES = {"dialect", "technical", "archaic", "spelling", "offensive"}
TAG_GROUP = {"NOUN": "substantiv", "ADJ": "adjektiv", "VERB": "verb", "ADV": "adverb",
             "INTJ": "interjeksjon", "PRON": "pronomen", "DET": "determinativ",
             "ADP": "preposisjon", "CCONJ": "konjunksjon", "SCONJ": "subjunksjon"}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def labels():
    with open(os.path.join(HERE, "labels.csv"), encoding="utf-8") as f:
        return {(r["dictionary"], r["word"]): (int(r["label"]), r["source"])
                for r in csv.DictReader(f) if r["label"] in ("0", "1")}


def db_rows():
    con = sqlite3.connect(os.path.join(lexicon.ROOT, "ord.db"))
    return {(d, w): (i, g, defs) for w, d, i, g, defs in
            con.execute("SELECT word, dictionary, id, wordgroup, definitions FROM words")}


def wordgroups(d):
    """Word group as parse.mjs derives it from the ordbank (last paradigm per lemma wins)."""
    def number(s):  # parseInt: "21A" -> 21
        return int(re.match(r"\d+", s).group())

    paradigm = {number(r[1]): r[2] for r in lexicon.rows(d, "paradigme.txt")}
    by_lemma = {int(r[1]): paradigm.get(number(r[2])) for r in lexicon.rows(d, "lemma_paradigme.txt")}
    out = {}
    for lemma_id, word in lexicon.lemmas(d).items():
        if by_lemma.get(lemma_id):
            out.setdefault(word.lower(), by_lemma[lemma_id])
    return out


def text_of(node):
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        return " ".join(text_of(v) for v in node.values())
    if isinstance(node, list):
        return " ".join(text_of(v) for v in node)
    return ""


class Resolver:
    """Find the ordbokene article (and word group) behind a word, as the database stores it."""

    def __init__(self, db):
        self.db = db
        self.index = {d: expand.index(d) for d in ("bm", "nn")}
        self.groups = {d: wordgroups(d) for d in ("bm", "nn")}

    def __call__(self, d, w):
        if (d, w) in self.db:
            article_id, group, defs = self.db[(d, w)]
            return article_id, group, text_of(json.loads(defs or "{}"))
        if w not in self.index[d]:
            return None
        article_id = self.index[d][w]
        art = expand.article(d, article_id)
        tags = [t for lemma in art.get("lemmas", []) for p in lemma.get("paradigm_info", [])
                for t in p.get("tags", [])]
        group = self.groups[d].get(w) or next((TAG_GROUP[t] for t in tags if t in TAG_GROUP), None)
        return article_id, group, text_of(expand.simplify(art)[0])


def entry(x, **extra):
    out = {"d": x["d"], "w": x["w"], "src": x.get("src"), "m": x.get("m") or "", "e": x.get("e") or ""}
    out.update({k: v for k, v in extra.items() if v is not None})
    return out


def main():
    verdicts = labels()
    dialect = load(os.path.join(HERE, "dialect.json"))
    review = load(os.path.join(HERE, "opus_review.json"))
    universe = load(f"{SWEEP}/universe.json")
    threshold = load(f"{SWEEP}/meta.json")["threshold"]
    vetoed = {(x["d"], x["w"]): x.get("flag") for x in load(f"{SWEEP}/final_veto.json")}
    scored = {(i["d"], i["w"]): i for i in sonnet.scores() if not i["id"].startswith("sg")}

    # Meaning and example for every word we know of, best source last.
    info = {}
    for x in universe + load(f"{SWEEP}/gold.json") + list(scored.values()):
        info[(x["d"], x["w"])] = x
    db = db_rows()
    resolve = Resolver(db)

    def describe(d, w, src):
        x = info.get((d, w))
        if x and x.get("m"):
            return x
        x = {"d": d, "w": w, "src": src}
        if (d, w) in db:
            defs = json.loads(db[(d, w)][2] or "{}")
            x["m"] = "; ".join(t for t in defs.get("forklaring", []) if isinstance(t, str)) or text_of(defs)[:180]
        elif w in resolve.index[d]:
            x["m"] = "; ".join(expand.simplify(expand.article(d, resolve.index[d][w]))[0]["forklaring"])[:180]
        return x

    out = {name: [] for name in ["approved", "rejected", "excluded", "haiku_vetoed", "haiku_rejected",
                                 "classifier_low", "rule_filtered"] + [f"sonnet_{lo}-{hi}" for lo, hi in BANDS]}
    placed = set()  # words (either dictionary) already in a file

    def approve(d, w, src, picked_by, p=None):
        x = describe(d, w, src)
        resolved = resolve(d, w)
        keep, why = review.get(f"{d}/{w}", (1, "ok"))
        if resolved is None:
            out["excluded"].append(entry(x, reason="no bokmål/nynorsk article", p_sonnet=p))
        elif DIALECT.search(resolved[2]) or f"{d}/{w}" in dialect:
            out["excluded"].append(entry(x, reason="dialect", p_sonnet=p))
        elif ACCENTED.search(w):
            out["excluded"].append(entry(x, reason="accented spelling", p_sonnet=p))
        elif not keep and (picked_by != "user" or why in RULES):
            out["excluded"].append(entry(x, reason=f"opus review: {why}", picked_by=picked_by, p_sonnet=p))
        else:
            out["approved"].append(entry(x, id=resolved[0], wordgroup=resolved[1],
                                         picked_by=picked_by, p_sonnet=p))
        placed.add(w)

    # 1. The user's own verdicts.
    for (d, w), (label, src) in sorted(verdicts.items()):
        if label == 1:
            approve(d, w, src, "user", scored.get((d, w), {}).get("p_sonnet"))
    for (d, w), (label, src) in sorted(verdicts.items()):
        if label == 0 and w not in placed:
            out["rejected"].append(entry(describe(d, w, src)))
            placed.add(w)

    # 2. Sonnet's scores, best first, so a bm/nn twin keeps its better side.
    for (d, w), x in sorted(scored.items(), key=lambda kv: -kv[1]["p_sonnet"]):
        if w in placed:
            continue
        p = round(x["p_sonnet"], 1)
        if p >= APPROVE:
            approve(d, w, x["src"], "sonnet", p)
            continue
        if review.get(f"{d}/{w}", (0,))[0] and not ACCENTED.search(w):
            approve(d, w, x["src"], "opus", p)  # 30-40 band words Opus would keep
            continue
        lo, hi = next(b for b in BANDS if p >= b[0])
        out[f"sonnet_{lo}-{hi}"].append(entry(x, p_sonnet=p))
        placed.add(w)

    # 3. Everything else that was fetched, by the stage that stopped it.
    for x in sorted(universe, key=lambda x: -x["p_cls"]):
        if x["w"] in placed:
            continue
        key = (x["d"], x["w"])
        p_cls = round(x["p_cls"], 3)
        if x["hard"]:
            out["rule_filtered"].append(entry(x, p_cls=p_cls))
        elif x["p_cls"] < threshold:
            out["classifier_low"].append(entry(x, p_cls=p_cls))
        elif key in vetoed:
            out["haiku_vetoed"].append(entry(x, p_cls=p_cls, flag=vetoed[key]))
        else:
            out["haiku_rejected"].append(entry(x, p_cls=p_cls))
        placed.add(x["w"])

    os.makedirs(WORDS, exist_ok=True)
    for name, words in out.items():
        if name == "approved":
            words.sort(key=lambda x: (x["d"], x["w"]))
        with open(os.path.join(WORDS, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(f"{name:16} {len(words):6}  bm {sum(x['d'] == 'bm' for x in words):5}  "
              f"nn {sum(x['d'] == 'nn' for x in words):5}")
    print("approved by:", dict(Counter((x["d"], x["picked_by"]) for x in out["approved"])))
    print("excluded:", dict(Counter(x["reason"] for x in out["excluded"])))


if __name__ == "__main__":
    main()
