"""Build the word pool for the labeling page (labeler.html).

    python3 dictionary/curation/pool.py [per_dict]

Samples words evenly across the score range of each dictionary, so labels say
something about every part of the ranking, then adds any expansion candidates
with fetched definitions. Writes cache/labeler.html.
"""

import csv
import json
import random
import re
import sys

import expand
import features
import lexicon
import score

PER_DICT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 300
BUCKETS = 10


def snippet(definitions):
    texts = [re.sub(r"\s+", " ", t).strip() for t in features.explanations(definitions)]
    examples = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "eksempel":
                    examples.extend(features.flatten(v))
                else:
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(definitions)
    return "; ".join(texts[:3])[:220], (examples[0][:120] if examples else "")


def from_db(dictionary, rng):
    with open(f"{lexicon.CACHE}/scores_{dictionary}.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    words = {w["word"]: w for w in lexicon.db_words(dictionary)}
    size = len(rows) // BUCKETS
    out = []
    for b in range(BUCKETS):
        bucket = rows[b * size : (b + 1) * size]
        for r in rng.sample(bucket, PER_DICT // BUCKETS):
            meaning, example = snippet(words[r["word"]]["definitions"])
            out.append(
                {
                    "w": r["word"],
                    "d": dictionary,
                    "m": meaning,
                    "e": example,
                    "src": "db",
                    "decile": b + 1,
                }
            )
    return out


def from_expansion(dictionary, rng, n=60):
    """Candidates whose articles expand.py already downloaded."""
    out = []
    db = {w["word"] for w in lexicon.db_words(dictionary)}
    sources = [("unused", expand.unused(dictionary, db)[:400], dictionary)]
    if dictionary == "nn":
        sources.append(("norsk-ordbok", expand.norsk_ordbok(dictionary)[:400], "no"))
    for name, items, d in sources:
        picked = rng.sample(items, min(n, len(items)))
        for lemma, article_id, f in picked:
            text, definitions, _ = expand.describe(d, article_id)
            if not definitions or not definitions["forklaring"]:
                continue
            example = (definitions["eksempel"] or [""])[0][:120]
            out.append({"w": lemma, "d": dictionary, "m": text, "e": example, "src": name})
    return out


def item(word, dictionary, src, definitions):
    meaning, example = snippet(definitions)
    return {"w": word, "d": dictionary, "m": meaning, "e": example, "src": src}


def hard_filtered(f):
    return any(rule(f) for rule in score.HARD.values())


# Per dictionary: how many words each part of a labeling round gets.
QUOTAS = {
    "uncertain": 45,  # the model's probability is closest to 50/50
    "top": 20,  # its best unlabelled picks, to check precision
    "random": 35,  # uniform over the whole DB, hard-filtered words included
    "signals": 15,  # derived / see-through / dated, spread evenly
    "unused": 30,  # ordbokene headwords not in the DB (bm gets Norsk Ordbok's share)
    "norsk-ordbok": 5,  # nn only, still printed after 2000
}
SIGNALS = ("derived", "see_through", "dated")


def labelled_keys(labels_path):
    import glob
    import learn

    seen = set(learn.load_labels(labels_path))
    for p in glob.glob(f"{lexicon.CACHE}/labels*/**/*.json", recursive=True):
        d = json.load(open(p))
        d = d.get("data", d)
        seen.add((d["d"], d["w"]))
    return seen


def next_round(labels_path, rng):
    """A balanced labeling round: the same quotas for bokmål and nynorsk."""
    import learn
    import numpy as np

    labels = learn.load_labels(labels_path)
    seen = labelled_keys(labels_path)

    data, train = {}, []
    for dictionary in ("bm", "nn"):
        defs = {w["word"]: w["definitions"] for w in lexicon.db_words(dictionary)}
        scored = score.score_all(features.for_db(dictionary))
        mean = sum(r["surprisal"] for r in scored) / len(scored)
        for r in scored:
            r["d"], r["defs"] = dictionary, defs[r["word"]]
            r["terms"] = score.terms(r, mean)
            if (dictionary, r["word"]) in labels:
                train.append((r, labels[(dictionary, r["word"])]))
        data[dictionary] = [r for r in scored if (dictionary, r["word"]) not in seen]

    # The model only orders candidates; loan_verb stays out (labels reward -ere,
    # the stated goal does not).
    names = [n for n in score.WEIGHTS if n != "loan_verb"]
    X = np.array([[r["terms"][n] for n in names] for r, _ in train])
    y = np.array([label for _, label in train], dtype=float)
    w, b = learn.fit(X, y)

    pool, used = [], set()

    def take(candidates, n, tag):
        for r in candidates:
            if n == 0:
                break
            if r["word"] in used or not features.explanations(r["defs"]):
                continue
            used.add(r["word"])
            pool.append({**item(r["word"], r["d"], "db", r["defs"]), "tag": tag})
            n -= 1

    for dictionary, rows in data.items():
        kept = [r for r in rows if not r["hard"]]
        for r in kept:
            logit = np.array([r["terms"][n] for n in names]) @ w + b
            r["p"] = float(1 / (1 + np.exp(-logit)))
        take(sorted(kept, key=lambda r: abs(r["p"] - 0.5)), QUOTAS["uncertain"], "uncertain")
        take(sorted(kept, key=lambda r: -r["p"]), QUOTAS["top"], "top")
        take(rng.sample(rows, len(rows)), QUOTAS["random"], "random")
        per_signal = QUOTAS["signals"] // len(SIGNALS)
        for signal in SIGNALS:
            hits = [r for r in kept if r[signal]]
            take(rng.sample(hits, len(hits)), per_signal, signal)

        # Fresh candidates, screened with the same hard filters.
        n = QUOTAS["unused"] + (QUOTAS["norsk-ordbok"] if dictionary == "bm" else 0)
        db = {x["word"] for x in lexicon.db_words(dictionary)}
        items = [x for x in expand.unused(dictionary, db)[:800] if (dictionary, x[0]) not in seen]
        for lemma, article_id, f in rng.sample(items, len(items)):
            if n == 0:
                break
            text, definitions, _ = expand.describe(dictionary, article_id)
            if definitions and definitions["forklaring"] and not hard_filtered(
                features.compute(lemma, dictionary, definitions)
            ):
                example = (definitions["eksempel"] or [""])[0][:120]
                pool.append({"w": lemma, "d": dictionary, "m": text, "e": example,
                             "src": "unused", "tag": "unused"})
                n -= 1

    modern = lexicon.cache_load("no_forms_modern.json", {})
    no = [x for x in expand.norsk_ordbok("nn")[:3000] if modern.get(x[0], 0) > 0.005]
    n = QUOTAS["norsk-ordbok"]
    for lemma, article_id, f in rng.sample(no, len(no)):
        if n == 0:
            break
        if ("nn", lemma) in seen:
            continue
        text, definitions, _ = expand.describe("no", article_id)
        if definitions and definitions["forklaring"] and not hard_filtered(
            features.compute(lemma, "nn", definitions)
        ):
            pool.append({"w": lemma, "d": "nn", "m": text, "e": "", "src": "norsk-ordbok",
                         "tag": "norsk-ordbok"})
            n -= 1
    return pool


if __name__ == "__main__":
    rng = random.Random(42)
    pool = []
    if "--next" in sys.argv:
        path = sys.argv[sys.argv.index("--next") + 1]
        rng = random.Random(len(open(path).readlines()))  # a fresh draw per round
        pool = next_round(path, rng)
    else:
        for dictionary in ("bm", "nn"):
            pool += from_db(dictionary, rng)
            if "--expansion" in sys.argv:
                pool += from_expansion(dictionary, rng)
    rng.shuffle(pool)
    template = open(f"{lexicon.DICT}/curation/labeler.html", encoding="utf-8").read()
    html = template.replace("/*POOL*/[]", json.dumps(pool, ensure_ascii=False))
    with open(f"{lexicon.CACHE}/labeler.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{len(pool)} words -> {lexicon.CACHE}/labeler.html")
