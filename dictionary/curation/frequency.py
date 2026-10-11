"""Corpus frequencies from Nasjonalbiblioteket (DHLAB API).

For each base form we sum the counts of all its inflected forms in three periods
of digitised books, and store frequency per million words:

    old     1800-1919
    mid     1920-1979
    modern  2000-2024

Usage: python3 dictionary/curation/frequency.py [bm|nn] [--all]
  default: words in ord.db; --all: every lemma in the ordbank (for expansion).
"""

import json
import sys
import time
import urllib.request

import lexicon

API = "https://api.nb.no/dhlab/reference_words"
PERIODS = {"old": (1800, 1919), "mid": (1920, 1979), "modern": (2000, 2024)}
BATCH = 2000


def fetch(words, start, end):
    body = json.dumps(
        {"doctype": "digibok", "from_year": start, "to_year": end, "words": words}
    ).encode()
    for attempt in range(5):
        try:
            req = urllib.request.Request(
                API, data=body, headers={"content-type": "application/json"}
            )
            return json.load(urllib.request.urlopen(req, timeout=180))
        except Exception as error:
            print(f"  retry {attempt + 1}: {error}", file=sys.stderr)
            time.sleep(2**attempt)
    raise RuntimeError("DHLAB unavailable")


def form_frequencies(forms, period, prefix=""):
    """Relative frequency per million for every form, cached per period."""
    name = f"{prefix}forms_{period}.json"
    cache = lexicon.cache_load(name, {})
    missing = sorted(set(forms) - cache.keys())
    start, end = PERIODS[period]
    for i in range(0, len(missing), BATCH):
        batch = missing[i : i + BATCH]
        found = {w: rel * 1e6 for w, _, rel in fetch(batch, start, end)}
        for w in batch:
            cache[w] = found.get(w, 0.0)
        if (i // BATCH) % 10 == 0:
            print(f"  {period}: {i + len(batch)}/{len(missing)}", file=sys.stderr)
            lexicon.cache_save(name, cache)
    lexicon.cache_save(name, cache)
    return cache


def lemma_frequencies(dictionary, words):
    all_forms = lexicon.forms(dictionary)
    wanted = {w: (all_forms.get(w) or set()) | {w} for w in words}
    flat = set().union(*wanted.values())
    out = {w: {} for w in words}
    for period in PERIODS:
        freq = form_frequencies(flat, period)
        for w, fs in wanted.items():
            out[w][period] = sum(freq.get(f, 0.0) for f in fs)
    return out


def load(dictionary):
    return lexicon.cache_load(f"freq_{dictionary}.json", {})


if __name__ == "__main__":
    dictionary = sys.argv[1] if len(sys.argv) > 1 else "bm"
    if "--all" in sys.argv:
        words = {w.lower() for w in lexicon.lemmas(dictionary).values() if w.isalpha()}
    else:
        words = {w["word"] for w in lexicon.db_words(dictionary)}
    result = load(dictionary)
    todo = sorted(words - result.keys())
    print(f"{dictionary}: {len(todo)} lemmas to look up", file=sys.stderr)
    result.update(lemma_frequencies(dictionary, todo))
    lexicon.cache_save(f"freq_{dictionary}.json", result)
