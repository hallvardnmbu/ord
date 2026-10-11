"""Score every word in ord.db and write a report of what each signal does.

    python3 dictionary/curation/score.py [bm|nn]

Outputs (in dictionary/curation/cache/):
    scores_<dict>.csv   all features + score, sorted best first
    report_<dict>.md    samples per signal, best/worst words, survival counts

The weights are hand-set starting points. If labels.csv exists (word,label with
label 1 = interesting, 0 = boring), learn.py can fit them to your taste instead.
"""

import csv
import random
import sys

import features
import lexicon

# Score contributions. Positive = interesting.
WEIGHTS = {
    "simplex": 1.0,
    "transparent": -1.5,
    "suffix_productivity": -0.35,  # log(#compounds sharing the last part)
    "place": -2.0,
    "number": -2.0,
    "colour": -1.0,
    "template": -1.0,
    "loan_or_old": 0.6,
    "homely": 0.6,  # Old Norse, Low German, dialect, sound words
    "latinate": -0.3,  # -ere verbs and -isk adjectives are plentiful
    "unknown_origin": 1.5,
    "derived_etymology": 0.0,
    "register": 0.8,
    "examples": 0.15,  # per example, capped at 4
    "too_common": -2.5,  # per decade above ~5 per million in modern books
    "unattested": -0.8,  # per decade below ~0.03 per million in any period
    "forgotten": 1.5,  # per decade of decline since 1920-79
    "surprisal": 0.6,  # per bit/letter above average
}

# Suffixes that stamp out predictable words. Productivity alone is too blunt:
# -full, -beint, -kledd compounds are often vivid (pietetsfull, berrbeint).
MECHANICAL = set(
    "vis messig årig års aktig fri laus løs rik basert drevet driven styrt ramma rammet"
    " farga farget forma formet vendt sidig språklig dyktig kyndig ferdig sikker bevisst"
    " vennlig venleg fiendtlig fiendtleg politisk skapende skapande fremmende fremjande"
    " berettiga berettiget søkende søkande bærende berande holdig haldig fylt metta"
    " påvirka påverka produsert eid tilpassa tilpasset orientert relatert".split()
)

# Hard filters: words matching any of these are never worth showing.
HARD = {
    "place": lambda f: f["place"],
    "number": lambda f: f["number"],
    "assembly-line compound": lambda f: f["transparent"] and f["suffix"] in MECHANICAL,
    "derived template": lambda f: f["template"] in ("som-gjelder", "det-å", "med-x"),
}


def terms(f, mean_surprisal):
    return {
        "simplex": float(f["simplex"]),
        "transparent": float(f["transparent"]),
        "suffix_productivity": f["suffix_productivity"],
        "place": float(f["place"]),
        "number": float(f["number"]),
        "colour": float(f["colour"]),
        "template": float(bool(f["template"])),
        "loan_or_old": float(f["loan_or_old"]),
        "homely": float(f["homely"]),
        "latinate": float(f["latinate"]),
        "unknown_origin": float(f["unknown_origin"]),
        "derived_etymology": float(f["derived_etymology"]),
        "register": float(bool(f["register"])),
        "examples": min(f["n_examples"], 4),
        "too_common": max(0.0, f["log_modern"] - 0.7),
        "unattested": max(0.0, -1.5 - f["log_any"]),
        "forgotten": max(0.0, f["decline"]),
        "surprisal": f["surprisal"] - mean_surprisal,
    }


def score_all(rows, weights=WEIGHTS):
    mean = sum(r["surprisal"] for r in rows) / len(rows)
    for r in rows:
        t = terms(r, mean)
        r["score"] = sum(weights[k] * v for k, v in t.items())
        r["hard"] = ",".join(name for name, rule in HARD.items() if rule(r))
    rows.sort(key=lambda r: -r["score"])
    return rows


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        for r in rows:
            writer.writerow({k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()})


def sample(words, n=30, seed=0):
    words = list(words)
    random.Random(seed).shuffle(words)
    return ", ".join(words[:n])


def report(rows, dictionary):
    out = [f"# Curation report ({dictionary}, {len(rows)} words)\n"]
    kept = [r for r in rows if not r["hard"]]
    out.append(f"Hard filters remove **{len(rows) - len(kept)}** words, leaving {len(kept)}.\n")

    out.append("## What each hard filter removes (random sample)\n")
    for name in HARD:
        hit = [r["word"] for r in rows if name in r["hard"].split(",")]
        out.append(f"- **{name}** ({len(hit)}): {sample(hit)}")

    out.append("\n## Soft signals (random sample of words that trigger each)\n")
    signals = {
        "simplex (not a compound)": lambda r: r["simplex"],
        "loan / old origin": lambda r: r["loan_or_old"],
        "register tag (dialect, ironic, dated...)": lambda r: r["register"],
        "too common (>5 per million today)": lambda r: r["log_modern"] > 0.7,
        "unattested (<0.03 per million ever)": lambda r: r["log_any"] < -1.5,
        "forgotten (10x rarer than in 1920-79)": lambda r: r["decline"] > 1.0,
        "unusual spelling (top 5% surprisal)": None,
        "colour compound": lambda r: r["colour"],
        "homely origin (norrønt, lavtysk, dialect)": lambda r: r["homely"],
        "latinate origin": lambda r: r["latinate"],
    }
    cut = sorted(r["surprisal"] for r in rows)[int(len(rows) * 0.95)]
    signals["unusual spelling (top 5% surprisal)"] = lambda r: r["surprisal"] >= cut
    for name, rule in signals.items():
        hit = [r["word"] for r in rows if rule(r)]
        out.append(f"- **{name}** ({len(hit)}): {sample(hit)}")

    out.append("\n## Best 100 after hard filters\n")
    out.append(", ".join(r["word"] for r in kept[:100]))
    out.append("\n## Worst 100 that survive hard filters\n")
    out.append(", ".join(r["word"] for r in kept[-100:]))
    out.append("\n## Random draw from the top third (what daily words would feel like)\n")
    out.append(sample((r["word"] for r in kept[: len(kept) // 3]), n=60, seed=1))
    out.append("\n## Random draw from the bottom third (what gets dropped)\n")
    out.append(sample((r["word"] for r in kept[-len(kept) // 3 :]), n=60, seed=1))
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    dictionary = sys.argv[1] if len(sys.argv) > 1 else "bm"
    rows = score_all(features.for_db(dictionary))
    write_csv(rows, f"{lexicon.CACHE}/scores_{dictionary}.csv")
    with open(f"{lexicon.CACHE}/report_{dictionary}.md", "w", encoding="utf-8") as f:
        f.write(report(rows, dictionary))
    print(f"Wrote scores_{dictionary}.csv and report_{dictionary}.md to {lexicon.CACHE}")
