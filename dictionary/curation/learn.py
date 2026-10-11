"""Fit the score weights to your own labels, and measure each signal.

    python3 dictionary/curation/learn.py LABELS

LABELS is either a CSV (word,dictionary,label) or a directory of JSON label
documents as exported from the labeling page ({"w", "d", "label"}; label 1 =
day-worthy, 0 = boring, -1 = skipped and ignored).

Prints:
  - how well the hand-set score ranks your labels (AUC)
  - for every hard filter: how many of the words it removes you liked
  - for every soft signal: the share of liked words with/without it
  - logistic-regression weights fitted to your labels, and their AUC
    under cross-validation, ready to paste into score.WEIGHTS.
"""

import csv
import glob
import json
import os
import sys

import numpy as np

import features
import score


def load_labels(path):
    out = {}
    if os.path.isdir(path):
        for file in glob.glob(f"{path}/**/*.json", recursive=True):
            doc = json.load(open(file))
            doc = doc.get("data", doc)
            if doc.get("label") in (0, 1):
                out[(doc["d"], doc["w"])] = doc["label"]
    else:
        for row in csv.DictReader(open(path)):
            if row["label"] in ("0", "1"):
                out[(row["dictionary"], row["word"])] = int(row["label"])
    return out


def auc(scores, labels):
    """Probability that a random liked word outranks a random boring one."""
    order = np.argsort(scores)
    ranks = np.empty(len(scores))
    ranks[order] = np.arange(1, len(scores) + 1)
    pos = labels == 1
    n_pos, n_neg = pos.sum(), (~pos).sum()
    if not n_pos or not n_neg:
        return float("nan")
    return (ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def fit(X, y, l2=1.0, steps=3000, lr=0.1):
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = (X - mu) / sd
    w, b = np.zeros(X.shape[1]), 0.0
    for _ in range(steps):
        p = 1 / (1 + np.exp(-(Z @ w + b)))
        w -= lr * (Z.T @ (p - y) / len(y) + l2 * w / len(y))
        b -= lr * (p - y).mean()
    return w / sd, b - (w / sd) @ mu  # back to raw feature units


if __name__ == "__main__":
    labels = load_labels(sys.argv[1])
    rows = []
    for dictionary in ("bm", "nn"):
        scored = score.score_all(features.for_db(dictionary))
        mean = sum(r["surprisal"] for r in scored) / len(scored)
        for r in scored:
            if (dictionary, r["word"]) in labels:
                r["label"] = labels[(dictionary, r["word"])]
                r["terms"] = score.terms(r, mean)
                rows.append(r)
    if len(rows) < 30:
        sys.exit(f"Only {len(rows)} labelled DB words; label more first.")

    y = np.array([r["label"] for r in rows], dtype=float)
    print(f"{len(rows)} labels: {int(y.sum())} day-worthy, {int(len(y) - y.sum())} boring\n")
    print(f"Hand-set score AUC: {auc(np.array([r['score'] for r in rows]), y):.3f}\n")

    print("Hard filters (liked words they would remove = false positives):")
    for name in score.HARD:
        hit = [r for r in rows if name in r["hard"].split(",")]
        liked = [r["word"] for r in hit if r["label"] == 1]
        print(f"  {name:24} removes {len(hit):3}, of which liked {len(liked):3}  {', '.join(liked[:8])}")

    print("\nSoft signals (share liked when present vs absent):")
    names = list(rows[0]["terms"])
    X = np.array([[r["terms"][n] for n in names] for r in rows])
    for i, n in enumerate(names):
        on = X[:, i] > 0
        if on.any() and (~on).any():
            print(f"  {n:22} {y[on].mean():5.0%} (n={on.sum():3})  vs  {y[~on].mean():5.0%}")

    k = 5
    folds = np.arange(len(y)) % k
    np.random.default_rng(0).shuffle(folds)
    predicted = np.zeros(len(y))
    for f in range(k):
        w, b = fit(X[folds != f], y[folds != f])
        predicted[folds == f] = X[folds == f] @ w + b
    print(f"\nFitted weights, cross-validated AUC: {auc(predicted, y):.3f}")
    w, b = fit(X, y)
    print("WEIGHTS = {")
    for n, v in sorted(zip(names, w), key=lambda t: -abs(t[1])):
        print(f'    "{n}": {v:.2f},  # hand-set {score.WEIGHTS[n]}')
    print("}")
