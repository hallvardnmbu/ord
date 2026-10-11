"""Sonnet as judge: score open candidates against the user's verdicts, then split.

Batches live in cache/sonnet/batch_<b>.tsv (and shuffled copies batch_<b>_r.tsv for a
second independent pass). Each batch hides already-labelled "gold" words (ids sg*),
used to check each pass and to pick thresholds.

    python3 dictionary/curation/sonnet.py
"""

import json
import os

import numpy as np

import learn
import lexicon

DIR = f"{lexicon.CACHE}/sonnet"
DATA = os.path.join(os.path.dirname(__file__), "data")

APPROVE = 40  # gold: 97% yes; held-out hard words from the last page: 5 of 5
ASK = 30  # held-out hard words at 30-40: about half liked


def scores():
    batches = json.load(open(f"{DIR}/batches.json"))
    items = []
    for b, batch in enumerate(batches):
        passes = [json.load(open(f"{DIR}/{name}_batch_{b}.json"))
                  for name in ("out", "out2") if os.path.exists(f"{DIR}/{name}_batch_{b}.json")]
        for item in batch:
            ps = [p[item["id"]] for p in passes if item["id"] in p]
            items.append({**item, "p_sonnet": float(np.mean(ps)) if ps else 0.0, "passes": ps})
    return items


def report(items):
    gold = [i for i in items if i["id"].startswith("sg")]
    y = np.array([i["label"] for i in gold])
    for k in range(max(len(i["passes"]) for i in gold)):
        print(f"pass {k + 1} gold AUC {learn.auc(np.array([i['passes'][k] for i in gold], float), y):.3f}")
    print(f"mean   gold AUC {learn.auc(np.array([i['p_sonnet'] for i in gold]), y):.3f}")
    cands = [i for i in items if not i["id"].startswith("sg")]
    for t in (15, 20, 25, 30, 35, 40, 45, 50):
        kept = [i["label"] for i in gold if i["p_sonnet"] >= t]
        print(f"p>={t}: gold kept {len(kept)} ({np.mean(kept) if kept else 0:.0%} yes), "
              f"candidates {sum(i['p_sonnet'] >= t for i in cands)}")


def dedupe(items):
    """One entry per word: a bm/nn twin keeps its better-scored side."""
    best = {}
    for i in sorted(items, key=lambda i: -i["p_sonnet"]):
        best.setdefault(i["w"], i)
    return list(best.values())


def split(items):
    seen = {w for _, w in learn.load_labels(os.path.join(os.path.dirname(__file__), "labels.csv"))} | {g["w"] for g in json.load(open(f"{DATA}/greenlit.json"))}
    cands = dedupe([i for i in items if not i["id"].startswith("sg") and i["w"] not in seen])
    out = {"approve": [], "ask": [], "reject": []}
    for i in sorted(cands, key=lambda i: -i["p_sonnet"]):
        key = "approve" if i["p_sonnet"] >= APPROVE else "ask" if i["p_sonnet"] >= ASK else "reject"
        out[key].append({k: i.get(k) for k in ("w", "d", "src", "m", "e", "p_sonnet")})
    for key, words in out.items():
        with open(f"{DATA}/sonnet_{key}.json", "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False, indent=1)
        print(key, len(words), sum(w["d"] == "bm" for w in words), "bm")
    return out


def page():
    """Review page: the uncertain band, best first, alternating bm/nn while both last."""
    ask = json.load(open(f"{DATA}/sonnet_ask.json"))
    queues = {d: [w for w in ask if w["d"] == d] for d in ("bm", "nn")}
    items = []
    while any(queues.values()):
        for d in ("nn", "bm"):
            if queues[d]:
                w = queues[d].pop(0)
                items.append({"w": w["w"], "d": w["d"], "m": w["m"], "e": w["e"] or "", "src": w["src"]})
    template = open(os.path.join(os.path.dirname(__file__), "labeler.html"), encoding="utf-8").read()
    html = template.replace("/*POOL*/[]", json.dumps(items, ensure_ascii=False))
    open(f"{lexicon.CACHE}/labeler.html", "w", encoding="utf-8").write(html)
    print(len(items), "words on the review page")


if __name__ == "__main__":
    items = scores()
    report(items)
    split(items)
    page()
