"""Greenlight pipeline: see PLAN.md.

    python3 greenlight.py pool        # pass 0 + 1: candidates with classifier scores
    python3 greenlight.py screen      # pass 2 batches (with hidden gold) for the judge
    python3 greenlight.py gold        # per-batch agreement with the hidden gold
    python3 greenlight.py critic      # pass 3 batches for survivors
    python3 greenlight.py final       # pass 4 + 5: greenlit list and review page

Judge outputs go to cache/greenlight/out_<batch>.json.
"""

import concurrent.futures
import csv
import json
import os
import random
import re
import sys

import numpy as np

import expand
import features
import learn
import lexicon
import pool
import score

DIR = f"{lexicon.CACHE}/greenlight"
os.makedirs(DIR, exist_ok=True)

DB_PER_DICT = 1000
UNUSED_FETCH = 1500
UNUSED_PER_DICT = 500
NO_FETCH = 400
NO_KEEP = 150
BATCH = 200
GOLD_PER_BATCH = 20


def save(name, data):
    json.dump(data, open(f"{DIR}/{name}", "w"), ensure_ascii=False)


def load(name):
    return json.load(open(f"{DIR}/{name}"))


def labels():
    return {(r["dictionary"], r["word"]): int(r["label"]) for r in csv.DictReader(open("labels.csv"))}


def fetch_all(d, items):
    """Download articles in parallel (cached on disk)."""
    def one(x):
        lemma, article_id = x[0], x[1]
        try:
            return lemma, expand.describe(d, article_id)
        except Exception:
            return lemma, ("", None, None)

    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        return dict(ex.map(one, items))


def classifier():
    """Logistic model over score.terms, fitted on every labelled DB word."""
    lab = labels()
    rows = []
    for d in ("bm", "nn"):
        scored = score.score_all(features.for_db(d))
        mean = sum(r["surprisal"] for r in scored) / len(scored)
        for r in scored:
            if lab.get((d, r["word"])) in (0, 1):
                rows.append((score.terms(r, mean), lab[(d, r["word"])]))
    names = [n for n in score.WEIGHTS if n != "loan_verb"]
    X = np.array([[t[n] for n in names] for t, _ in rows])
    y = np.array([l for _, l in rows], dtype=float)
    w, b = learn.fit(X, y)

    def predict(terms):
        return float(1 / (1 + np.exp(-(np.array([terms[n] for n in names]) @ w + b))))

    return predict


def entry(d, w, src, meaning, example, f, mean, predict):
    t = score.terms(f, mean)
    return {
        "d": d, "w": w, "src": src, "m": re.sub(r"\s+", " ", meaning)[:180], "e": (example or "")[:110],
        "score": float(sum(score.WEIGHTS[k] * v for k, v in t.items())), "p_cls": predict(t),
        "root": (features.derivation(w) or ("",))[0],
    }


def build_pool():
    lab = labels()
    seen = pool.labelled_keys("labels.csv")
    predict = classifier()
    out = []
    for d in ("bm", "nn"):
        defs = {x["word"]: x["definitions"] for x in lexicon.db_words(d)}
        scored = score.score_all(features.for_db(d))
        mean = sum(r["surprisal"] for r in scored) / len(scored)
        kept = [r for r in scored if not r["hard"] and (d, r["word"]) not in seen]
        for r in kept[:DB_PER_DICT]:
            m, e = pool.snippet(defs[r["word"]])
            if m:
                out.append(entry(d, r["word"], "db", m, e, r, mean, predict))
        print(f"{d}: {sum(1 for x in out if x['d'] == d)} DB candidates")

        # Unused headwords: rank lexically, fetch the best, rescore with definitions.
        db = set(defs)
        lexical = [x for x in expand.unused(d, db) if (d, x[0]) not in seen][:UNUSED_FETCH]
        fetched = fetch_all(d, lexical)
        new = []
        for lemma, article_id, _ in lexical:
            text, definitions, etymology = fetched[lemma]
            if not definitions or not definitions["forklaring"]:
                continue
            f = features.compute(lemma, d, definitions, etymology,
                                 __import__("frequency").load(d).get(lemma))
            if pool.hard_filtered(f):
                continue
            new.append(entry(d, lemma, "unused", text, (definitions["eksempel"] or [""])[0], f, mean,
                             predict))
        new.sort(key=lambda x: -x["score"])
        out += new[:UNUSED_PER_DICT]
        print(f"{d}: {min(len(new), UNUSED_PER_DICT)} new headwords (of {len(new)} that passed filters)")

    # Norsk Ordbok, only words still printed after 2000.
    modern = lexicon.cache_load("no_forms_modern.json", {})
    no = [x for x in expand.norsk_ordbok("nn")[:4000]
          if modern.get(x[0], 0) > 0.005 and ("nn", x[0]) not in seen][:NO_FETCH]
    fetched = fetch_all("no", no)
    mean_nn = 3.4
    kept = []
    for lemma, article_id, _ in no:
        text, definitions, etymology = fetched[lemma]
        if not definitions or not definitions["forklaring"]:
            continue
        f = features.compute(lemma, "nn", definitions)
        if not pool.hard_filtered(f):
            kept.append(entry("nn", lemma, "norsk-ordbok", text, "", f, mean_nn, predict))
    out += kept[:NO_KEEP]
    print(f"norsk ordbok: {min(len(kept), NO_KEEP)}")

    # One entry per word: prefer the DB version.
    unique = {}
    for x in out:
        unique.setdefault(x["w"], x)
    out = list(unique.values())
    for i, x in enumerate(out):
        x["id"] = f"w{i}"
    save("pool.json", out)
    print(len(out), "candidates")


def line(x):
    ex = f" «{x['e']}»" if x.get("e") else ""
    return f"{x['id']}\t{x['d']}\t{x['w']}\t{x['m']}{ex}"


def gold_items():
    """Labelled words with meanings, to hide in judge batches."""
    db_defs = {d: {x["word"]: x["definitions"] for x in lexicon.db_words(d)} for d in ("bm", "nn")}
    # Words shown as examples in the judge's prompt must not be gold.
    shots = set(re.findall(r"^- (\S+) \((bm|nn)\)", open(f"{DIR}/screen_prompt.md").read(), re.M))
    shots = {(d, w) for w, d in shots}
    out = []
    for (d, w), l in labels().items():
        if l not in (0, 1) or w not in db_defs[d] or (d, w) in shots:
            continue
        m, e = pool.snippet(db_defs[d][w])
        if m:
            out.append({"d": d, "w": w, "m": m[:180], "e": e[:110], "label": l})
    return out


def screen_prompt(per_class=60):
    """Criteria plus a balanced sample of the user's verdicts."""
    import judge

    rng = random.Random(3)
    db_defs = {d: {x["word"]: x["definitions"] for x in lexicon.db_words(d)} for d in ("bm", "nn")}
    lab = [(d, w, l) for (d, w), l in labels().items() if l in (0, 1) and w in db_defs[d]]
    rng.shuffle(lab)
    shots = []
    for want in (1, 0):
        for d in ("bm", "nn"):
            shots += [x for x in lab if x[2] == want and x[0] == d][: per_class // 2]
    rng.shuffle(shots)
    lines = []
    for d, w, l in shots:
        m, _ = pool.snippet(db_defs[d][w])
        lines.append(f"- {w} ({d}): {m[:90]} → {'BRA' if l else 'KJEDELIG'}")
    text = (judge.CRITERIA + "- nedsettende eller støtende ord (også utdaterte betegnelser på folkegrupper) er alltid dårlige\n"
            + "\nEksempler på brukerens egne vurderinger:\n" + "\n".join(lines) + """

Oppgave: Gi hvert ord i batch-filen en karakter 1-5 (5 = utmerket dagens ord, 1 = kjedelig).
Bruk hele skalaen; brukeren liker omtrent ett av tre ord i slike lister. Vurder ordet og betydningen.
Skriv KUN JSON: {"<id>": karakter, ...} for alle id-er.
""")
    open(f"{DIR}/screen_prompt.md", "w").write(text)


def screen_batches():
    screen_prompt()
    rng = random.Random(5)
    cands = load("pool.json")
    gold = gold_items()
    rng.shuffle(cands)
    batches = []
    for k in range(0, len(cands), BATCH):
        items = [dict(x) for x in cands[k : k + BATCH]]
        g = rng.sample(gold, GOLD_PER_BATCH)
        for j, x in enumerate(g):
            items.append({**x, "id": f"g{k // BATCH}_{j}"})
        rng.shuffle(items)
        batches.append(items)
        open(f"{DIR}/screen_{k // BATCH}.tsv", "w").write(
            "id\tordbok\tord\tbetydning\n" + "\n".join(map(line, items)))
    save("screen_batches.json", batches)
    print(len(batches), "screen batches of", BATCH, "+", GOLD_PER_BATCH, "gold")


def gold_report(prefix="screen"):
    batches = load(f"{prefix}_batches.json")
    bad = []
    for i, items in enumerate(batches):
        path = f"{DIR}/out_{prefix}_{i}.json"
        if not os.path.exists(path):
            print(f"batch {i}: missing")
            continue
        r = json.load(open(path))
        g = [x for x in items if "label" in x and x["id"] in r]
        y = np.array([x["label"] for x in g], dtype=float)
        s = np.array([float(r[x["id"]]) for x in g]) + np.linspace(0, 1e-3, len(g))
        a = learn.auc(s, y) if 0 < y.sum() < len(y) else float("nan")
        missing = sum(1 for x in items if x["id"] not in r)
        print(f"batch {i}: gold AUC {a:.2f} ({int(y.sum())}/{len(y)} liked), {missing} unrated")
        if a < 0.6 or missing > 10:
            bad.append(i)
    print("re-rate:", bad)
    return bad


CRITIC = """Du er en streng redaktør for «dagens ord» på dagsord.no.
Målet: sjeldne eller uvanlige ord som likevel kan brukes naturlig i dag.

For HVERT ord i batch-filen:
1. Prøv å skrive én naturlig, moderne setning med ordet (på samme målform som ordboka: bm = bokmål,
   nn = nynorsk). Hvis det bare går med en kunstig eller historisk setning, er ordet ikke brukbart i dag.
2. Gi én kode:
   ok              – sjeldent/uvanlig, brukbart i dag, et godt dagens ord
   common          – vanlig ord de fleste kjenner
   derived         – åpenbar avledning av et vanlig ord (importere, sviksam, kortne, uvelkommen)
   technical       – fagord (medisin, biologi, kjemi, jus, grammatikk, teknikk …)
   dialect         – dialektord som få forstår, eller bare en lokal variant
   archaic         – bare gammel stavemåte/form av et vanlig ord, eller umulig å bruke i dag
   offensive       – nedsettende, støtende eller utdatert betegnelse på folkegrupper
   person-place    – person- eller stedsbetegnelse, folkenavn
Vær streng: bare de beste ordene skal få «ok».

Skriv KUN JSON: {"<id>": {"c": "<kode>", "s": "<setning, eller tom>"}, ...} for alle id-er.
"""


def survivors():
    """Pass 1 + 2 combined: candidates worth a closer look."""
    cands = {x["id"]: x for x in load("pool.json")}
    ratings = {}
    for name in os.listdir(DIR):
        if name.startswith("out_screen_"):
            ratings.update(json.load(open(f"{DIR}/{name}")))
    rated = [x for x in cands.values() if x["id"] in ratings]
    for x in rated:
        x["judge"] = float(ratings[x["id"]])
    p = np.array([x["p_cls"] for x in rated])
    j = np.array([x["judge"] for x in rated])
    for x, zp, zj in zip(rated, (p - p.mean()) / p.std(), (j - j.mean()) / j.std()):
        x["combined"] = float(zp + zj)
    save("rated.json", rated)
    return rated


def critic_batches():
    rated = survivors()
    # Keep a word if the judge likes it, or if both votes are above average.
    keep = [x for x in rated if x["judge"] >= 3 or x["combined"] > 0.5]
    keep.sort(key=lambda x: -x["combined"])
    rng = random.Random(9)
    gold = gold_items()
    batches = []
    for k in range(0, len(keep), BATCH):
        items = [dict(x) for x in keep[k : k + BATCH]]
        for j, g in enumerate(rng.sample(gold, GOLD_PER_BATCH)):
            items.append({**g, "id": f"cg{k // BATCH}_{j}"})
        rng.shuffle(items)
        batches.append(items)
        open(f"{DIR}/critic_{k // BATCH}.tsv", "w").write(
            "id\tordbok\tord\tbetydning\n" + "\n".join(map(line, items)))
    open(f"{DIR}/critic_prompt.md", "w").write(CRITIC)
    save("critic_batches.json", batches)
    print(len(keep), "survivors in", len(batches), "critic batches")


def critic_gold():
    batches = load("critic_batches.json")
    hits = {"ok": [0, 0]}
    for i, items in enumerate(batches):
        path = f"{DIR}/out_critic_{i}.json"
        if not os.path.exists(path):
            print(f"critic batch {i}: missing")
            continue
        r = json.load(open(path))
        for x in items:
            if "label" in x and x["id"] in r:
                code = r[x["id"]].get("c", "?")
                hits.setdefault(code, [0, 0])[x["label"]] += 1
    print("gold by critic code [boring, liked]:", hits)


READER = """Du leser ord for «dagens ord» på dagsord.no, en nettside for nysgjerrige voksne som liker språk.

For HVERT ord i batch-filen:
1. Skriv én naturlig, moderne setning med ordet, på samme målform som ordboka (bm = bokmål,
   nn = nynorsk). Setningen skal vise hva ordet betyr. Hold den kort.
2. Gi en karakter 1-5: «Ville en nysgjerrig leser bli glad for å lære dette ordet i dag,
   og kunne bruke det?» 5 = ja, absolutt; 3 = greit nok; 1 = nei (kjedelig, uforståelig,
   bare fagspråk, nedsettende eller umulig å bruke i dag).

Skriv KUN JSON: {"<id>": {"r": karakter, "s": "<setning>"}, ...} for alle id-er.
"""


def reader_batches(size=170):
    picked = load("greenlit.json")
    open(f"{DIR}/reader_prompt.md", "w").write(READER)
    for k in range(0, len(picked), size):
        open(f"{DIR}/reader_{k // size}.tsv", "w").write(
            "id\tordbok\tord\tbetydning\n" + "\n".join(map(line, picked[k : k + size])))
    print((len(picked) + size - 1) // size, "reader batches")


def apply_reader(drop_below=2.5):
    """Average the reader's rating with the screen rating; drop words both found weak."""
    picked = load("greenlit.json")
    r = {}
    for name in os.listdir(DIR):
        if name.startswith("out_reader_"):
            r.update(json.load(open(f"{DIR}/{name}")))
    kept, dropped = [], []
    for x in picked:
        v = r.get(x["id"])
        if v:
            x["reader"] = float(v.get("r", 3))
            x["sentence"] = v.get("s") or x.get("sentence", "")
        both = (x["judge"] + x.get("reader", x["judge"])) / 2
        (kept if both >= drop_below else dropped).append(x)
    save("greenlit.json", kept)
    print(len(kept), "kept,", len(dropped), "dropped:", ", ".join(x["w"] for x in dropped))


VETO = {"technical", "derived", "common", "person-place", "offensive"}


def precision_estimate():
    """Liked-share among screen gold, by combined-score quantile (expected review yield)."""
    predict = classifier()
    batches = load("screen_batches.json")
    r = {}
    for i in range(len(batches)):
        r.update(json.load(open(f"{DIR}/out_screen_{i}.json")))
    rows = []
    feats = {}
    for d in ("bm", "nn"):
        scored = score.score_all(features.for_db(d))
        mean = sum(x["surprisal"] for x in scored) / len(scored)
        feats.update({(d, x["word"]): (x, mean) for x in scored})
    for items in batches:
        for x in items:
            if "label" in x and x["id"] in r and (x["d"], x["w"]) in feats:
                f, mean = feats[(x["d"], x["w"])]
                rows.append((predict(score.terms(f, mean)), float(r[x["id"]]), x["label"]))
    p = np.array([a for a, _, _ in rows]); j = np.array([b for _, b, _ in rows]); y = np.array([c for _, _, c in rows])
    comb = (p - p.mean()) / p.std() + (j - j.mean()) / j.std()
    order = np.argsort(-comb)
    print(f"gold: {len(y)} words, base rate {y.mean():.0%}, combined AUC {learn.auc(comb, y):.2f}")
    for q in (0.1, 0.2, 0.3, 0.5):
        top = order[: max(1, int(len(y) * q))]
        print(f"  top {q:.0%} by combined: {y[top].mean():.0%} liked")


def final(target_per_dict=250):
    rated = {x["id"]: x for x in load("rated.json")}
    verdicts = {}
    for name in os.listdir(DIR):
        if name.startswith("out_critic_"):
            verdicts.update(json.load(open(f"{DIR}/{name}")))
    out = []
    for i, x in rated.items():
        v = verdicts.get(i)
        if not v:
            continue
        x["code"], x["sentence"] = v.get("c", "?"), v.get("s", "")
        # On the gold, the critic's "ok" was no better than chance and its
        # "dialect" was the best (61% liked); only its reject codes are reliable.
        if x["code"] not in VETO:
            out.append(x)
    out.sort(key=lambda x: -x["combined"])

    # Diversity: one word per root and per word form, capped endings, 50/50 split.
    picked, roots, endings = [], set(), {}
    for d in ("bm", "nn"):
        n = 0
        for x in (y for y in out if y["d"] == d):
            if n >= target_per_dict:
                break
            root = x.get("root") or x["w"]
            ending = x["w"][-4:]
            if root in roots or x["w"] in roots or endings.get((d, ending), 0) >= 8:
                continue
            roots.update({root, x["w"]})
            endings[(d, ending)] = endings.get((d, ending), 0) + 1
            picked.append(x)
            n += 1
    save("greenlit.json", picked)
    print(len(picked), "greenlit:", {d: sum(1 for x in picked if x["d"] == d) for d in ("bm", "nn")})
    return picked


def page():
    picked = load("greenlit.json")
    rng = random.Random(1)
    items = [{"w": x["w"], "d": x["d"], "m": x["m"], "e": x["e"], "s": x.get("sentence", ""),
              "src": x["src"], "tag": "greenlit"} for x in picked]
    rng.shuffle(items)
    template = open(f"{lexicon.DICT}/curation/labeler.html", encoding="utf-8").read()
    html = template.replace("/*POOL*/[]", json.dumps(items, ensure_ascii=False))
    open(f"{lexicon.CACHE}/labeler.html", "w", encoding="utf-8").write(html)
    print(len(items), "words on the review page")


if __name__ == "__main__":
    {"pool": build_pool, "screen": screen_batches, "gold": gold_report, "critic": critic_batches,
     "critic-gold": critic_gold, "final": final, "page": page, "precision": precision_estimate,
     "reader": reader_batches, "apply-reader": apply_reader}[sys.argv[1]]()
