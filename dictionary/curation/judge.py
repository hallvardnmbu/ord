"""Use a language model as a second judge, primed with your labels.

    python3 judge.py prep            # cache/judge/: few-shot prompt, test set, candidates
    python3 judge.py eval            # compare the judge's test ratings with the scorer

The judge reads cache/judge/prompt.md and a batch file, and writes ratings
(1-5 per word) to cache/judge/out_<batch>.json.
"""

import csv
import json
import os
import random
import sys

import numpy as np

import expand
import features
import learn
import lexicon
import pool
import score

DIR = f"{lexicon.CACHE}/judge"
CRITERIA = """Du hjelper med å velge «dagens ord» for dagsord.no (bokmål og nynorsk).
Målet er sjeldne eller uvanlige ord som likevel kan brukes i dag.

Godt ord:
- sjeldent eller uvanlig, men et gyldig ord man kan bruke i en moderne setning
- gamle ord er fine så lenge de er «ekte» ord (ikke bare gammel rettskriving)
- særpreget lyd eller betydning; lærde ord er ok (ostentativ, panegyrisk)

Dårlig ord:
- vanlige hverdagsord alle kjenner
- avledninger der roten er et vanlig ord (importere ← import, sviksam ← svik,
  kortne ← kort); sammensetninger som forklarer seg selv (lovfeste, nordvendt)
- medisinske, biologiske, kjemiske og andre fagord
- stedsadjektiv/folkenavn (gabonsk), tallord, personbetegnelser (organikar)
- dialektord er mindre relevante, men noen er ok
"""


def describe(d, w, db_defs):
    if w in db_defs.get(d, {}):
        meaning, example = pool.snippet(db_defs[d][w])
        return meaning, example
    ids = expand.index(d)
    if w in ids:
        text, definitions, _ = expand.describe(d, ids[w])
        examples = (definitions or {}).get("eksempel") or [""]
        return text, examples[0][:100]
    ids = expand.index("no")
    if w in ids:
        text, _, _ = expand.describe("no", ids[w])
        return text, ""
    return "", ""


def line(item):
    ex = f" «{item['e']}»" if item.get("e") else ""
    return f"{item['id']}\t{item['d']}\t{item['w']}\t{item['m']}{ex}"


def prep():
    os.makedirs(DIR, exist_ok=True)
    rng = random.Random(7)
    db_defs = {d: {w["word"]: w["definitions"] for w in lexicon.db_words(d)} for d in ("bm", "nn")}
    rows = [r for r in csv.DictReader(open("labels.csv")) if r["label"] in ("0", "1")]
    rng.shuffle(rows)
    liked = [r for r in rows if r["label"] == "1"]
    boring = [r for r in rows if r["label"] == "0"]
    shots = liked[:40] + boring[:40]
    test = liked[40:120] + boring[40:200]  # 80 liked + 160 boring
    rng.shuffle(test)

    def items(rs, prefix):
        out = []
        for i, r in enumerate(rs):
            m, e = describe(r["dictionary"], r["word"], db_defs)
            if m:
                out.append({"id": f"{prefix}{i}", "d": r["dictionary"], "w": r["word"], "m": m[:160],
                            "e": e, "label": int(r["label"])})
        return out

    shot_items, test_items = items(shots, "s"), items(test, "t")
    examples = "\n".join(
        f"- {x['w']} ({x['d']}): {x['m'][:90]} → {'BRA' if x['label'] else 'KJEDELIG'}" for x in shot_items
    )
    prompt = CRITERIA + "\nEksempler på brukerens egne vurderinger:\n" + examples + """

Oppgave: Gi hvert ord i batch-filen en karakter 1-5 (5 = utmerket dagens ord, 1 = kjedelig).
Vurder ordet selv og betydningen. Skriv KUN JSON: {"<id>": karakter, ...} for alle id-er.
"""
    open(f"{DIR}/prompt.md", "w").write(prompt)
    for k in range(0, len(test_items), 120):
        batch = test_items[k : k + 120]
        open(f"{DIR}/test_{k // 120}.tsv", "w").write("id\tordbok\tord\tbetydning\n" + "\n".join(map(line, batch)))
    json.dump(test_items, open(f"{DIR}/test.json", "w"), ensure_ascii=False)
    print(len(shot_items), "examples,", len(test_items), "test words")


def evaluate():
    test = json.load(open(f"{DIR}/test.json"))
    ratings = {}
    for name in os.listdir(DIR):
        if name.startswith("out_test"):
            ratings.update(json.load(open(f"{DIR}/{name}")))
    scored = {}
    for d in ("bm", "nn"):
        rows = score.score_all(features.for_db(d))
        scored.update({(d, r["word"]): r["score"] for r in rows})
    have = [t for t in test if t["id"] in ratings]
    y = np.array([t["label"] for t in have], dtype=float)
    judge = np.array([float(ratings[t["id"]]) for t in have])
    print(f"{len(have)} rated words ({int(y.sum())} liked)")
    print(f"judge AUC:  {learn.auc(judge + np.random.default_rng(0).random(len(judge)) * 1e-3, y):.3f}")
    db = [i for i, t in enumerate(have) if (t["d"], t["w"]) in scored]
    s = np.array([scored[(have[i]["d"], have[i]["w"])] for i in db])
    print(f"on {len(db)} DB words: scorer AUC {learn.auc(s, y[db]):.3f}, judge AUC {learn.auc(judge[db], y[db]):.3f}")
    z = lambda v: (v - v.mean()) / v.std()
    print(f"           combined (z-sum) AUC {learn.auc(z(s) + z(judge[db]), y[db]):.3f}")
    for k in (5, 4, 3, 2, 1):
        sel = judge == k
        if sel.any():
            print(f"  judge {k}: {sel.sum():3} words, {y[sel].mean():4.0%} liked")


if __name__ == "__main__" and sys.argv[1] in ("prep", "eval"):
    {"prep": prep, "eval": evaluate}[sys.argv[1]]()


def candidates(per_dict_db=300, per_dict_new=100, batch=125):
    """The scorer's best unlabelled words, written as batches for the judge."""
    rng = random.Random(11)
    seen = pool.labelled_keys("labels.csv")
    out = []
    for d in ("bm", "nn"):
        defs = {w["word"]: w["definitions"] for w in lexicon.db_words(d)}
        rows = [r for r in score.score_all(features.for_db(d)) if not r["hard"] and (d, r["word"]) not in seen]
        for r in rows[:per_dict_db]:
            m, e = pool.snippet(defs[r["word"]])
            if m:
                out.append({"d": d, "w": r["word"], "m": m[:160], "e": e, "src": "db", "score": r["score"]})
        db = set(defs)
        n = per_dict_new
        for lemma, article_id, f in expand.unused(d, db):
            if n == 0:
                break
            if (d, lemma) in seen:
                continue
            text, definitions, _ = expand.describe(d, article_id)
            if not definitions or not definitions["forklaring"]:
                continue
            feats = features.compute(lemma, d, definitions)
            if pool.hard_filtered(feats):
                continue
            examples = definitions.get("eksempel") or [""]
            out.append({"d": d, "w": lemma, "m": text[:160], "e": examples[0][:100], "src": "unused",
                        "score": f["score"]})
            n -= 1
    rng.shuffle(out)
    for i, item in enumerate(out):
        item["id"] = f"c{i}"
    json.dump(out, open(f"{DIR}/candidates.json", "w"), ensure_ascii=False)
    for k in range(0, len(out), batch):
        open(f"{DIR}/cand_{k // batch}.tsv", "w").write(
            "id\tordbok\tord\tbetydning\n" + "\n".join(map(line, out[k : k + batch])))
    print(len(out), "candidates in", (len(out) + batch - 1) // batch, "batches")


def rank():
    """Combine scorer and judge (z-scores, per source) into one ranking."""
    cands = json.load(open(f"{DIR}/candidates.json"))
    ratings = {}
    for name in os.listdir(DIR):
        if name.startswith("out_cand"):
            ratings.update(json.load(open(f"{DIR}/{name}")))
    for src in ("db", "unused"):
        group = [c for c in cands if c["src"] == src and c["id"] in ratings]
        s = np.array([c["score"] for c in group])
        j = np.array([float(ratings[c["id"]]) for c in group])
        zs, zj = (s - s.mean()) / s.std(), (j - j.mean()) / j.std()
        for c, a, b in zip(group, zs, zj):
            c["judge"], c["combined"] = float(ratings[c["id"]]), float(a + b)
    ranked = sorted((c for c in cands if "combined" in c), key=lambda c: -c["combined"])
    json.dump(ranked, open(f"{DIR}/ranked.json", "w"), ensure_ascii=False, indent=0)
    for d in ("bm", "nn"):
        for src in ("db", "unused"):
            top = [c for c in ranked if c["d"] == d and c["src"] == src][:40]
            print(f"\n{d} {src}: " + ", ".join(f"{c['w']}({c['judge']:.0f})" for c in top))


if __name__ == "__main__" and sys.argv[1] in ("candidates", "rank"):
    {"candidates": candidates, "rank": rank}[sys.argv[1]]()
