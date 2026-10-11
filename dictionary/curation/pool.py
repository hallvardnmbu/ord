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

PER_DICT = int(sys.argv[1]) if len(sys.argv) > 1 else 300
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


if __name__ == "__main__":
    rng = random.Random(42)
    pool = []
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
