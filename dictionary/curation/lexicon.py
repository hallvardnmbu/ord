"""Shared loaders for the Norsk ordbank files and the uncurated ord.db."""

import json
import os
import sqlite3
from collections import defaultdict
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DICT = os.path.join(ROOT, "dictionary")
CACHE = os.path.join(DICT, "curation", "cache")
FOLDERS = {"bm": "nob", "nn": "nno"}
SOURCE_COMMIT = "48590d6"  # last commit with the uncurated ord.db
ENCODING = "latin1"

os.makedirs(CACHE, exist_ok=True)


def rows(dictionary, file):
    path = os.path.join(DICT, FOLDERS[dictionary], file)
    with open(path, encoding=ENCODING) as f:
        next(f)
        for line in f:
            line = line.rstrip("\n")
            if line:
                yield line.split("\t")


@lru_cache(maxsize=None)
def lemmas(dictionary):
    """lemma_id -> base form."""
    return {int(r[1]): r[2] for r in rows(dictionary, "lemma.txt")}


@lru_cache(maxsize=None)
def pos(dictionary):
    """base form (lowercase) -> set of coarse POS tags (subst, adj, verb, ...)."""
    ids = lemmas(dictionary)
    out = defaultdict(set)
    for r in rows(dictionary, "fullformsliste.txt"):
        word = ids.get(int(r[1]))
        if word:
            out[word.lower()].add(r[3].split()[0])
    return out


@lru_cache(maxsize=None)
def forms(dictionary):
    """base form (lowercase) -> set of all inflected forms (lowercase)."""
    ids = lemmas(dictionary)
    out = defaultdict(set)
    for r in rows(dictionary, "fullformsliste.txt"):
        word = ids.get(int(r[1]))
        if word:
            out[word.lower()].add(r[2].lower())
    return out


@lru_cache(maxsize=None)
def compounds(dictionary):
    """base form (lowercase) -> (first part, last part) or None for simplex words."""
    out = {}
    for r in rows(dictionary, "leddanalyse.txt"):
        r += [""] * (14 - len(r))
        word = r[2].lower()
        if r[3] == "simplex" or not r[4]:
            out.setdefault(word, None)
        else:
            out[word] = (r[4].lower(), r[7].lower().lstrip("-"))
    return out


@lru_cache(maxsize=None)
def suffix_productivity(dictionary):
    """last part -> number of compounds ending in it. High = assembly-line words."""
    counts = defaultdict(int)
    for parts in compounds(dictionary).values():
        if parts:
            counts[parts[1]] += 1
    return counts


@lru_cache(maxsize=None)
def prefix_productivity(dictionary):
    counts = defaultdict(int)
    for parts in compounds(dictionary).values():
        if parts:
            counts[parts[0]] += 1
    return counts


def source_db():
    """The uncurated ord.db (all ~30k words) the curation started from, from the git history.

    ord.db itself now holds only the curated list, so lookups of candidates go here."""
    path = os.path.join(CACHE, "ord_source.db")
    if not os.path.exists(path):
        import subprocess
        data = subprocess.run(["git", "-C", ROOT, "show", f"{SOURCE_COMMIT}:ord.db"],
                              check=True, capture_output=True).stdout
        with open(path, "wb") as f:
            f.write(data)
    return path


def db_words(dictionary):
    """Words currently in ord.db, with parsed JSON fields."""
    db = sqlite3.connect(source_db())
    db.row_factory = sqlite3.Row
    out = []
    for r in db.execute("SELECT * FROM words WHERE dictionary = ?", (dictionary,)):
        w = dict(r)
        for key in ("etymology", "definitions", "inflection"):
            w[key] = json.loads(w[key]) if w[key] else None
        out.append(w)
    return out


def cache_load(name, default=None):
    path = os.path.join(CACHE, name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def cache_save(name, data):
    with open(os.path.join(CACHE, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
