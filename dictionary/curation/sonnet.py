"""Sonnet as judge: score open candidates against the user's verdicts.

Batches live in cache/sonnet/batch_<b>.tsv (and shuffled copies batch_<b>_r.tsv for a
second independent pass). Each batch hides already-labelled "gold" words (ids sg*),
used to check each pass and to pick thresholds.

    python3 dictionary/curation/sonnet.py                  # gold report + review page (30-40 band)
    python3 dictionary/curation/sonnet.py build <run> <band> ...   # new batches, e.g. build r2 20-30

`build` writes cache/sonnet/<run>/prompt.md and batch_<b>.tsv from prompts/sonnet_judge.md, the
latest labels and the chosen words/sonnet_<band>.json files. Have one Sonnet agent per batch read
the prompt and batch and write out_batch_<b>.json ({"<id>": p}); a second pass over the shuffled
batch_<b>_r.tsv into out2_batch_<b>.json halves the noise. Point DIR at the run to score it.

catalogue.py turns the scores into words/ (approve at >= APPROVE, the rest in bands).
"""

import csv
import json
import os
import random
import sys

import numpy as np

import learn
import lexicon

DIR = f"{lexicon.CACHE}/sonnet"
WORDS = os.path.join(os.path.dirname(__file__), "words")

APPROVE = 40  # gold: 97% yes. Round 8 (30-40 band): 74 of 131 liked.


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


def build(run, bands, size=200, gold=20, examples=300, seed=0):
    rng = random.Random(seed)
    here = os.path.dirname(__file__)
    with open(os.path.join(here, "labels.csv"), encoding="utf-8") as f:
        labelled = [r for r in csv.DictReader(f) if r["label"] in ("0", "1")]
    meaning = {}
    for name in os.listdir(WORDS):
        for x in json.load(open(os.path.join(WORDS, name), encoding="utf-8")):
            meaning[(x["d"], x["w"])] = x["m"]
    labelled = [r for r in labelled if meaning.get((r["dictionary"], r["word"]))]
    # A random sample of verdicts become examples; the rest are hidden gold for calibration.
    rng.shuffle(labelled)
    shots, held = labelled[:examples], labelled[examples:]
    lines = [f"- {r['word']} ({r['dictionary']}): {meaning[(r['dictionary'], r['word'])]} → "
             f"{'JA' if r['label'] == '1' else 'NEI'}" for r in shots]
    template = open(os.path.join(here, "prompts", "sonnet_judge.md"), encoding="utf-8").read()
    out = os.path.join(DIR, run)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "prompt.md"), "w", encoding="utf-8") as f:
        f.write(template.replace("{examples}", "Brukerens egne vurderinger:\n" + "\n".join(lines)))

    cands = [x for band in bands for x in json.load(open(os.path.join(WORDS, f"sonnet_{band}.json")))]
    batches = []
    for b in range(0, len(cands), size):
        items = [{**x, "id": f"s{b + i}"} for i, x in enumerate(cands[b:b + size])]
        for j, r in enumerate(rng.sample(held, gold)):
            items.append({"d": r["dictionary"], "w": r["word"], "m": meaning[(r["dictionary"], r["word"])],
                          "label": int(r["label"]), "id": f"sg{len(batches)}_{j}"})
        rng.shuffle(items)
        batches.append(items)
        for suffix, order in (("", items), ("_r", rng.sample(items, len(items)))):
            with open(os.path.join(out, f"batch_{len(batches) - 1}{suffix}.tsv"), "w", encoding="utf-8") as f:
                f.write("id\tordbok\tord\tbetydning\n")
                f.writelines(f"{x['id']}\t{x['d']}\t{x['w']}\t{x['m']}\n" for x in order)
    with open(os.path.join(out, "batches.json"), "w", encoding="utf-8") as f:
        json.dump(batches, f, ensure_ascii=False)
    print(f"{len(cands)} words in {len(batches)} batches, {len(shots)} examples -> {out}")


def page(band="30-40"):
    """Review page for one Sonnet band of words/ (from catalogue.py), alternating bm/nn."""
    ask = json.load(open(os.path.join(WORDS, f"sonnet_{band}.json"), encoding="utf-8"))
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
    if len(sys.argv) > 2 and sys.argv[1] == "build":
        build(sys.argv[2], sys.argv[3:])
        sys.exit()
    items = scores()
    report(items)
    page()
