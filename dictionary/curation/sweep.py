"""Full sweep over every bokmål/nynorsk source (Norsk Ordbok excluded).

    python3 sweep.py fetch     # definitions for every unused ordbokene headword
    python3 sweep.py score     # classifier over the whole universe, recall threshold
    python3 sweep.py screen    # judge batches (with hidden gold) above the threshold
    python3 sweep.py calibrate # P(yes) from classifier + judge, fitted on gold
    python3 sweep.py split     # auto-approve / auto-reject / ask the user
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
import frequency
import learn
import lexicon
import pool
import score

DIR = f"{lexicon.CACHE}/sweep"
os.makedirs(DIR, exist_ok=True)
BATCH = 400
GOLD_PER_BATCH = 20


def save(name, data):
    json.dump(data, open(f"{DIR}/{name}", "w"), ensure_ascii=False)


def load(name):
    return json.load(open(f"{DIR}/{name}"))


def labels():
    return {(r["dictionary"], r["word"]): int(r["label"]) for r in csv.DictReader(open("labels.csv"))}


TOP_SHARE = 0.30  # of unused headwords, by the definition-free model: keeps ~96% of liked


def shortlist():
    """Unused headwords worth fetching: cheap filters + top share by lexical score."""
    scores = json.load(open(f"{DIR}/lexical_scores.json"))
    cut = np.quantile([v[0] for v in scores.values()], 1 - TOP_SHARE)
    out = {"bm": [], "nn": []}
    for key, (s, aid) in scores.items():
        d, lemma = key.split("|", 1)
        if s >= cut:
            out[d].append((lemma, aid, None))
    return out


def fetch():
    short = shortlist()
    for d in ("bm", "nn"):
        items = short[d]
        done = 0

        def one(x):
            # The egress proxy drops connections under load: back off and retry.
            for attempt in range(4):
                try:
                    expand.article(d, x[1])
                    return
                except Exception:
                    __import__("time").sleep(2 ** attempt)

        with concurrent.futures.ThreadPoolExecutor(6) as ex:
            for _ in ex.map(one, items):
                done += 1
                if done % 5000 == 0:
                    print(f"{d}: {done}/{len(items)}", flush=True)
        print(f"{d}: fetched {len(items)}", flush=True)


def universe():
    """Every candidate with definitions and features: DB words + shortlisted unused headwords."""
    global SHORT
    SHORT = shortlist()
    rows = []
    for d in ("bm", "nn"):
        defs = {x["word"]: x for x in lexicon.db_words(d)}
        scored = score.score_all(features.for_db(d))
        mean = sum(r["surprisal"] for r in scored) / len(scored)
        for r in scored:
            m, e = pool.snippet(defs[r["word"]]["definitions"])
            rows.append({"d": d, "w": r["word"], "src": "db", "m": m, "e": e, "f": r, "mean": mean})
        freqs = frequency.load(d)
        for lemma, article_id, _ in SHORT[d]:
            # Only articles already downloaded: scoring runs in waves beside the fetch.
            if not os.path.exists(f"{lexicon.CACHE}/articles_{d}/{article_id}.json"):
                continue
            try:
                text, definitions, etymology = expand.describe(d, article_id)
            except Exception:
                continue
            if not definitions or not definitions["forklaring"]:
                continue
            f = features.compute(lemma, d, definitions, etymology, freqs.get(lemma))
            ex = (definitions.get("eksempel") or [""])[0]
            rows.append({"d": d, "w": lemma, "src": "unused", "m": re.sub(r"\s+", " ", text), "e": ex,
                         "f": f, "mean": mean})
    return rows


def terms_matrix(rows, names):
    return np.array([[score.terms(r["f"], r["mean"])[n] for n in names] for r in rows])


def score_all():
    lab = labels()
    rows = universe()
    for r in rows:
        r["hard"] = any(rule(r["f"]) for rule in score.HARD.values())
    names = [n for n in score.WEIGHTS if n != "loan_verb"]
    train = [r for r in rows if lab.get((r["d"], r["w"])) in (0, 1)]
    X, y = terms_matrix(train, names), np.array([lab[(r["d"], r["w"])] for r in train], dtype=float)

    # Cross-validated predictions on the labels pick a threshold that keeps
    # 95% of the words the user liked.
    folds = np.arange(len(y)) % 5
    np.random.default_rng(0).shuffle(folds)
    cv = np.zeros(len(y))
    for k in range(5):
        w, b = learn.fit(X[folds != k], y[folds != k])
        cv[folds == k] = 1 / (1 + np.exp(-(X[folds == k] @ w + b)))
    threshold = float(np.quantile(cv[y == 1], 0.05))
    print(f"{len(y)} labelled words in the universe, CV AUC {learn.auc(cv, y):.3f}")
    print(f"threshold keeping 95% of liked: p >= {threshold:.3f} "
          f"(drops {np.mean(cv[y == 0] < threshold):.0%} of disliked)")

    w, b = learn.fit(X, y)
    seen = pool.labelled_keys("labels.csv")
    out, gold = [], []
    for r in rows:
        p = float(1 / (1 + np.exp(-(terms_matrix([r], names)[0] @ w + b))))
        item = {"d": r["d"], "w": r["w"], "src": r["src"], "m": r["m"][:180], "e": (r["e"] or "")[:110],
                "p_cls": p, "root": (features.derivation(r["w"]) or ("",))[0], "hard": r["hard"]}
        key = (r["d"], r["w"])
        if lab.get(key) in (0, 1):
            gold.append({**item, "label": lab[key]})
        elif key not in seen and r["m"]:
            out.append(item)
    unique = {}
    for x in sorted(out, key=lambda x: x["src"] != "db"):
        unique.setdefault(x["w"], x)
    out = list(unique.values())
    above = [x for x in out if not x["hard"] and x["p_cls"] >= threshold]
    print(f"universe: {len(out)} unlabelled words, {sum(x['hard'] for x in out)} hard-filtered, "
          f"{len(above)} above threshold")
    for d in ("bm", "nn"):
        for src in ("db", "unused"):
            print(f"  {d} {src}: {sum(1 for x in above if x['d'] == d and x['src'] == src)}")
    save("universe.json", out)
    save("candidates.json", above)
    save("gold.json", gold)
    save("meta.json", {"threshold": threshold})


CRITERIA = """Du hjelper med å velge «dagens ord» for dagsord.no (bokmål og nynorsk).
Målet: så mange særpregede, uvanlige ord som mulig, som likevel er gyldige og brukbare i dag.

Godt ord:
- sjeldent, uvanlig eller særpreget, men et gyldig ord i dagens bokmål eller nynorsk
- særpreget lyd eller betydning; lærde ord er ok (ostentativ, fripostig, befippa)
- et ord som står i Bokmålsordboka eller Nynorskordboka er IKKE dialekt bare fordi det er uvanlig

Dårlig ord:
- vanlige hverdagsord alle kjenner
- avledninger der roten er et vanlig ord (importere, sviksam, kortne); selvforklarende sammensetninger
- fagord: medisin, biologi, kjemi, jus, grammatikk, teknikk
- stedsadjektiv/folkenavn, tallord, personbetegnelser
- dialektord: lokale ord eller lokale former som ikke hører til vanlig skriftspråk
- gammeldagse ord som ikke brukes lenger (formedelst, annamme), eller bare gammel stavemåte
- nedsettende eller støtende ord
"""


def screen_prompt(per_class=60):
    rng = random.Random(4)
    gold = load("gold.json")
    shots = []
    for want in (1, 0):
        for d in ("bm", "nn"):
            mine = [g for g in gold if g["label"] == want and g["d"] == d]
            shots += rng.sample(mine, min(per_class // 2, len(mine)))
    rng.shuffle(shots)
    lines = [f"- {g['w']} ({g['d']}): {g['m'][:90]} → {'BRA' if g['label'] else 'KJEDELIG'}" for g in shots]
    text = CRITERIA + "\nEksempler på brukerens egne vurderinger (noen eldre vurderinger kan ha godtatt" \
        " dialektord; følg kriteriene over):\n" + "\n".join(lines) + """

Oppgave: For hvert ord i batch-filen, gi
- "r": karakter 1-5 (5 = utmerket dagens ord, 1 = kjedelig/uegnet). Bruk hele skalaen.
- "f": én merkelapp: ok, dialect, archaic, technical, derived, common, person-place, offensive
Skriv KUN JSON: {"<id>": {"r": karakter, "f": "<merkelapp>"}, ...} for alle id-er.
"""
    open(f"{DIR}/screen_prompt.md", "w").write(text)
    return {(g["d"], g["w"]) for g in shots}


def line(x):
    ex = f" «{x['e']}»" if x.get("e") else ""
    return f"{x['id']}\t{x['d']}\t{x['w']}\t{x['m']}{ex}"


def screen():
    """Append batches for candidates not yet sent to the judge (one wave)."""
    if not os.path.exists(f"{DIR}/screen_prompt.md"):
        open(f"{DIR}/shots.json", "w").write(json.dumps(sorted(screen_prompt())))
    shots = {tuple(x) for x in json.load(open(f"{DIR}/shots.json"))}
    batches = load("batches.json") if os.path.exists(f"{DIR}/batches.json") else []
    done = {x["w"] for items in batches for x in items if "label" not in x}
    rng = random.Random(6 + len(batches))
    cands = [x for x in load("candidates.json") if x["w"] not in done]
    gold = [g for g in load("gold.json") if (g["d"], g["w"]) not in shots and g["m"]]
    rng.shuffle(cands)
    first = len(batches)
    n = sum(1 for items in batches for x in items if "label" not in x)
    for k in range(0, len(cands), BATCH):
        b = len(batches)
        items = [dict(x, id=f"c{n + k + i}") for i, x in enumerate(cands[k : k + BATCH])]
        for j, g in enumerate(rng.sample(gold, GOLD_PER_BATCH)):
            items.append({**g, "id": f"g{b}_{j}"})
        rng.shuffle(items)
        batches.append(items)
        open(f"{DIR}/screen_{b}.tsv", "w").write(
            "id\tordbok\tord\tbetydning\n" + "\n".join(map(line, items)))
    save("batches.json", batches)
    print(f"new batches {first}..{len(batches) - 1} ({len(cands)} new candidates)")


def outputs():
    r = {}
    for name in os.listdir(DIR):
        if name.startswith("out_screen_"):
            try:
                r.update(json.load(open(f"{DIR}/{name}")))
            except json.JSONDecodeError:
                print("broken:", name)
    return r


def gold_check():
    batches, r = load("batches.json"), outputs()
    redo = []
    for i, items in enumerate(batches):
        g = [x for x in items if "label" in x and x["id"] in r]
        missing = sum(1 for x in items if x["id"] not in r)
        if not g:
            print(f"batch {i}: no output")
            redo.append(i)
            continue
        y = np.array([x["label"] for x in g], dtype=float)
        s = np.array([float(r[x["id"]].get("r", 0)) for x in g]) + np.linspace(0, 1e-3, len(g))
        a = learn.auc(s, y) if 0 < y.sum() < len(y) else float("nan")
        flag = " <- redo" if (a < 0.6 or missing > 10) else ""
        print(f"batch {i}: gold AUC {a:.2f}, {missing} unrated{flag}")
        if flag:
            redo.append(i)
    print("redo:", redo)


VETO = {"dialect", "archaic", "technical", "derived", "common", "person-place", "offensive"}


def calibrate():
    """P(yes) from classifier probability and judge rating, fitted on the hidden gold."""
    batches, r = load("batches.json"), outputs()
    g = [x for items in batches for x in items if "label" in x and x["id"] in r]
    X = np.array([[np.log(x["p_cls"] / (1 - x["p_cls"])), float(r[x["id"]].get("r", 0))] for x in g])
    y = np.array([x["label"] for x in g], dtype=float)
    w, b = learn.fit(X, y)
    p = 1 / (1 + np.exp(-(X @ w + b)))
    flags = np.array([r[x["id"]].get("f", "ok") for x in g])
    print(f"gold: {len(y)} words, base {y.mean():.0%}, calibrated AUC {learn.auc(p, y):.3f}")
    for f in sorted(set(flags)):
        sel = flags == f
        print(f"  flag {f:12} {sel.sum():3} gold words, {y[sel].mean():.0%} liked")
    save("calibration.json", {"w": w.tolist(), "b": float(b)})
    return w, b


def split(approve=0.80, reject=0.30):
    w, b = calibrate()
    cands = {x["id"]: x for items in load("batches.json") for x in items if "label" not in x}
    r = outputs()
    groups = {"approve": [], "ask": [], "reject": [], "veto": []}
    for i, x in cands.items():
        if i not in r:
            continue
        x["judge"], x["flag"] = float(r[i].get("r", 0)), r[i].get("f", "ok")
        x["p_yes"] = float(1 / (1 + np.exp(-(np.array([np.log(x["p_cls"] / (1 - x["p_cls"])), x["judge"]]) @ w + b))))
        if x["flag"] in VETO:
            groups["veto"].append(x)
        elif x["p_yes"] >= approve:
            groups["approve"].append(x)
        elif x["p_yes"] < reject:
            groups["reject"].append(x)
        else:
            groups["ask"].append(x)
    for k, v in groups.items():
        v.sort(key=lambda x: -x["p_yes"])
        save(f"{k}.json", v)
        print(f"{k}: {len(v)} ({sum(1 for x in v if x['d'] == 'bm')} bm / {sum(1 for x in v if x['d'] == 'nn')} nn)")


RANK_PROMPT = CRITERIA + """
Oppgave (relativ rangering): Sammenlign ordene i batch-filen med HVERANDRE.
Fordel dem på 10 like store nivåer, omtrent like mange ord i hvert nivå:
10 = de beste dagens-ord i denne lista, 1 = de svakeste.
Tenk på hvilke ord en språkinteressert leser helst ville møtt som dagens ord.
Skriv KUN JSON: {"<id>": nivå, ...} for alle id-er.
"""
RANK_BATCH = 200


def rank_batches():
    """Relative pass over every word the screen did not veto (appends new ones)."""
    open(f"{DIR}/rank_prompt.md", "w").write(RANK_PROMPT)
    shots = {tuple(x) for x in json.load(open(f"{DIR}/shots.json"))}
    r = outputs()
    pool_ = [x for items in load("batches.json") for x in items
             if "label" not in x and x["id"] in r and r[x["id"]].get("f", "ok") not in VETO]
    batches = load("rank_batches.json") if os.path.exists(f"{DIR}/rank_batches.json") else []
    done = {x["id"] for items in batches for x in items}
    todo = [x for x in pool_ if x["id"] not in done]
    gold = [g for g in load("gold.json") if (g["d"], g["w"]) not in shots and g["m"]]
    rng = random.Random(11 + len(batches))
    rng.shuffle(todo)
    first = len(batches)
    for k in range(0, len(todo), RANK_BATCH):
        b = len(batches)
        items = [dict(x) for x in todo[k : k + RANK_BATCH]]
        for j, g in enumerate(rng.sample(gold, GOLD_PER_BATCH)):
            items.append({**g, "id": f"rg{b}_{j}"})
        rng.shuffle(items)
        batches.append(items)
        open(f"{DIR}/rank_{b}.tsv", "w").write(
            "id\tordbok\tord\tbetydning\n" + "\n".join(map(line, items)))
    save("rank_batches.json", batches)
    print(f"rank batches {first}..{len(batches) - 1} ({len(todo)} words)")


def rank_outputs():
    r = {}
    for name in os.listdir(DIR):
        if name.startswith("out_rank_"):
            try:
                r.update(json.load(open(f"{DIR}/{name}")))
            except json.JSONDecodeError:
                print("broken:", name)
    return r


def final_split(approve=0.65, reject=0.40):
    """P(yes) from classifier + relative tier (fitted on rank-batch gold); screen veto first."""
    batches, rr = load("rank_batches.json"), rank_outputs()
    g = [x for items in batches for x in items if "label" in x and x["id"] in rr]
    feats = lambda x, t: [np.log(x["p_cls"] / (1 - x["p_cls"])), float(t)]
    X = np.array([feats(x, rr[x["id"]]) for x in g])
    y = np.array([x["label"] for x in g], dtype=float)
    w, b = learn.fit(X, y)
    p = 1 / (1 + np.exp(-(X @ w + b)))
    print(f"rank gold: {len(y)} words, base {y.mean():.0%}, tier AUC "
          f"{learn.auc(X[:, 1] + np.linspace(0, 1e-3, len(y)), y):.3f}, combined AUC {learn.auc(p, y):.3f}")
    for lo, hi in ((0, .35), (.35, .5), (.5, .65), (.65, .75), (.75, 1.01)):
        sel = (p >= lo) & (p < hi)
        if sel.any():
            print(f"  gold P {lo:.2f}-{hi:.2f}: {sel.sum():3} words, {y[sel].mean():.0%} liked")
    screen = outputs()
    groups = {"approve": [], "ask": [], "reject": [], "veto": [], "unranked": []}
    for items in load("batches.json"):
        for x in items:
            if "label" in x or x["id"] not in screen:
                continue
            x = dict(x, judge=float(screen[x["id"]].get("r", 0)), flag=screen[x["id"]].get("f", "ok"))
            if x["flag"] in VETO:
                groups["veto"].append(x)
                continue
            if x["id"] not in rr:
                groups["unranked"].append(x)
                continue
            x["tier"] = rr[x["id"]]
            x["p_yes"] = float(1 / (1 + np.exp(-(np.array(feats(x, x["tier"])) @ w + b))))
            key = "approve" if x["p_yes"] >= approve else ("reject" if x["p_yes"] < reject else "ask")
            groups[key].append(x)
    for k, v in groups.items():
        v.sort(key=lambda x: -x.get("p_yes", 0))
        save(f"final_{k}.json", v)
        print(f"{k}: {len(v)} ({sum(1 for x in v if x['d'] == 'bm')} bm / {sum(1 for x in v if x['d'] == 'nn')} nn)")


REFINE_PROMPT = """Du hjelper med å velge «dagens ord» for dagsord.no (bokmål og nynorsk).

Gi hvert ord to UAVHENGIGE karakterer:

"c" – VANLIGHET (1-5): Hvor mye brukes SELVE ORDET i dagens norsk?
  5 = ord nesten alle bruker jevnlig (fekte, snekre, irritere, skumle, gjette)
  4 = godt kjent, brukes ofte nok (forvalte, hvesse, blunde)
  3 = kjent for de fleste, men brukes sjelden
  2 = mange kjenner det ikke
  1 = sjeldent, få kjenner ordet
  VIKTIG: vurder hvor vanlig ORDET er, ikke om tingen det beskriver er vanlig.
  «kukelure» beskriver noe hverdagslig, men selve ordet er sjeldent → 1-2.
  «fekte» brukes ofte («fekte med armene») → 5.

"r" – EGNETHET som dagens ord (1-5), med sunn fornuft:
  5 = særpreget, uvanlig ord som likevel kan brukes i en eller annen hverdagslig sammenheng
  3 = greit, men ikke spesielt
  1 = kjedelig/vanlig, fagord (medisin, biologi, kjemi, jus, teknikk), dialekt, gammeldags
      og ute av bruk, eller umulig å bruke i dag
  Ikke vær for streng med «hverdagslig»: et lærd eller litterært ord er fint om det kan brukes.

Skriv KUN JSON: {"<id>": {"c": n, "r": n}, ...} for alle id-er.
"""


def refine_batches(size=200):
    """Refinement over everything not already decided against (approve + ask)."""
    open(f"{DIR}/refine_prompt.md", "w").write(REFINE_PROMPT)
    lab = labels()
    words = [x for k in ("approve", "ask") for x in load(f"final_{k}.json")
             if lab.get((x["d"], x["w"])) not in (0, 1)]
    gold = [g for g in load("gold.json") if g["m"]]
    rng = random.Random(21)
    rng.shuffle(words)
    batches = []
    for k in range(0, len(words), size):
        b = len(batches)
        items = [dict(x, id=f"f{k + i}") for i, x in enumerate(words[k : k + size])]
        for j, g in enumerate(rng.sample(gold, GOLD_PER_BATCH)):
            items.append({**g, "id": f"fg{b}_{j}"})
        rng.shuffle(items)
        batches.append(items)
        open(f"{DIR}/refine_{b}.tsv", "w").write(
            "id\tordbok\tord\tbetydning\n" + "\n".join(map(line, items)))
    save("refine_batches.json", batches)
    print(len(batches), "refine batches;", len(words), "words")


def refine_outputs():
    r = {}
    for name in os.listdir(DIR):
        if name.startswith("out_refine_"):
            try:
                r.update(json.load(open(f"{DIR}/{name}")))
            except json.JSONDecodeError:
                print("broken:", name)
    return r


def refine_report():
    batches, r = load("refine_batches.json"), refine_outputs()
    g = [x for items in batches for x in items if "label" in x and x["id"] in r]
    print(f"gold: {len(g)} words")
    for key in ("c", "r"):
        for v in range(1, 6):
            sel = [x for x in g if r[x["id"]].get(key) == v]
            if sel:
                print(f"  {key}={v}: {len(sel):3} gold, {np.mean([x['label'] for x in sel]):.0%} liked")
    y = np.array([x["label"] for x in g], dtype=float)
    for key in ("c", "r"):
        s_ = np.array([float(r[x["id"]].get(key, 3)) for x in g]) + np.linspace(0, 1e-3, len(g))
        print(f"  AUC of {key}: {learn.auc(s_ if key == 'r' else -s_, y):.3f}")
    cands = [x for items in batches for x in items if "label" not in x and x["id"] in r]
    grid = {}
    for x in cands:
        k = (r[x["id"]].get("c"), r[x["id"]].get("r"))
        grid[k] = grid.get(k, 0) + 1
    print("candidates by (c, r):")
    for c in range(1, 6):
        print("  c=%d: " % c + "  ".join(f"r{rr}:{grid.get((c, rr), 0):4}" for rr in range(1, 6)))


def refine_split(approve=0.5, ask_floor=0.35):
    """Final verdicts. Very common words (c>=4) go; rare words (c<=2) with P(yes)
    >= approve are approved; borderline commonness (c=3) that looks suitable, and
    rare words just under the bar, are asked; the rest are rejected."""
    m = json.load(open(f"{DIR}/refine_model.json"))
    w, b = np.array(m["w"]), m["b"]
    batches, r = load("refine_batches.json"), refine_outputs()
    groups = {"approve": [], "ask": [], "reject": [], "common": []}
    for items in batches:
        for x in items:
            if "label" in x or x["id"] not in r:
                continue
            c, rr = r[x["id"]].get("c", 3), r[x["id"]].get("r", 3)
            p = float(1 / (1 + np.exp(-(np.array([np.log(x["p_cls"] / (1 - x["p_cls"])), c, rr]) @ w + b))))
            x = dict(x, common=c, suit=rr, p_final=p)
            if c >= 4:
                groups["common"].append(x)
            elif c <= 2 and p >= approve:
                groups["approve"].append(x)
            elif (c == 3 and rr >= 3) or (c <= 2 and p >= ask_floor):
                groups["ask"].append(x)
            else:
                groups["reject"].append(x)
    for k, v in groups.items():
        v.sort(key=lambda x: -x["p_final"])
        save(f"refined_{k}.json", v)
        print(f"{k}: {len(v)} ({sum(1 for x in v if x['d'] == 'bm')} bm / {sum(1 for x in v if x['d'] == 'nn')} nn)")



if __name__ == "__main__":
    {"refine-report": refine_report, "refine-split": refine_split, "refine": refine_batches, "final": final_split, "rank": rank_batches, "fetch": fetch, "score": score_all, "screen": screen, "gold": gold_check,
     "calibrate": calibrate, "split": split}[sys.argv[1]]()
