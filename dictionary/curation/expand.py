"""Find good words that are not in ord.db yet.

    python3 dictionary/curation/expand.py [bm|nn] [--fetch N]

Sources, each written as its own ranked list in cache/expand_<dict>.md:

1. unused   Headwords in ordbokene that parse.mjs threw away: nouns, words of
            six letters or fewer, and everything else not in the DB. Scored with
            the definition-free subset of the signals in features.py.
2. forgotten Words common in 1920-79 books that have faded since (DHLAB).
3. norsk-ordbok  Headwords in Norsk Ordbok (dict=no, ~280k entries, the big
            dialect dictionary) that are in neither bm nor nn.

--fetch N downloads the ordbokene articles of the top N candidates per source,
so the report can show definitions (and the score can use them).
"""

import json
import math
import os
import re
import sys
import urllib.request
from collections import Counter

import features
import frequency
import lexicon
import score

INDEX = "https://ord.uib.no/{d}/fil/article.json"
ARTICLE = "https://ord.uib.no/{d}/article/{id}.json"


def get_json(url, cache_name=None):
    if cache_name:
        cached = lexicon.cache_load(cache_name)
        if cached is not None:
            return cached
    with urllib.request.urlopen(url, timeout=120) as r:
        data = json.load(r)
    if cache_name:
        lexicon.cache_save(cache_name, data)
    return data


def index(d):
    """lemma -> first article id, for one of bm / nn / no."""
    out = {}
    for article_id, lemma, *_ in get_json(INDEX.format(d=d), f"index_{d}.json"):
        if lemma and re.fullmatch(r"[a-zæøåéèêóòâôü]+", lemma):
            out.setdefault(lemma, article_id)
    return out


def article(d, article_id):
    os.makedirs(f"{lexicon.CACHE}/articles_{d}", exist_ok=True)
    return get_json(ARTICLE.format(d=d, id=article_id), f"articles_{d}/{article_id}.json")


def simplify(art):
    """Turn a raw ordbokene article into the (definitions, etymology) shape of ord.db."""
    texts, examples = [], []

    def walk(node):
        if isinstance(node, dict):
            t = node.get("type_")
            if t == "explanation" and node.get("content"):
                texts.append(fill(node["content"], node.get("items", [])))
            elif t == "example" and node.get("quote"):
                examples.append(fill(node["quote"]["content"], node["quote"].get("items", [])))
            for v in node.values():
                if isinstance(v, (list, dict)):
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    def fill(content, items):
        for item in items:
            word = item.get("text") or item.get("id") or ""
            if item.get("lemmas"):
                word = item["lemmas"][0].get("lemma", "")
            content = content.replace("$", str(word), 1)
        return content

    body = art.get("body", {})
    walk(body.get("definitions", []))
    etymology = []
    for e in body.get("etymology", []) or []:
        etymology.append(fill(e.get("content", ""), e.get("items", [])))
    return {"forklaring": texts, "eksempel": examples}, etymology


def split_compound(word, vocabulary):
    """Best guess at A+B for words the ordbank does not analyse (Norsk Ordbok)."""
    for i in range(3, len(word) - 2):
        head, tail = word[:i], word[i:]
        if tail in vocabulary and (head in vocabulary or head[:-1] in vocabulary):
            return head, tail
    return None


def odd(surprisal, mean):
    """Unusual spelling helps, but capped: otherwise loans and acronyms win."""
    return min(max(surprisal - mean, -1.0), 1.0)


def plausible(lemma):
    return len(lemma) >= 4 and re.search(r"[aeiouyæøå]", lemma) and not re.search(r"[cqwxz]", lemma)


def lexical_score(f, mean_surprisal, freq_known=True):
    """score.py's weights, using only the signals that need no definitions."""
    t = score.terms(f, mean_surprisal)
    t["surprisal"] = odd(f["surprisal"], mean_surprisal)
    if not freq_known:
        for key in ("too_common", "unattested", "forgotten"):
            t[key] = 0.0
    return sum(score.WEIGHTS[k] * v for k, v in t.items())


def unused(dictionary, db):
    pos = lexicon.pos(dictionary)
    freqs = frequency.load(dictionary)
    out = []
    for lemma, article_id in index(dictionary).items():
        if lemma in db or lemma not in pos or not plausible(lemma):
            continue
        tags = pos[lemma]
        if not tags & {"subst", "adj", "verb", "adv", "interj"}:
            continue
        f = features.compute(lemma, dictionary, freq=freqs.get(lemma))
        f["pos"] = "/".join(sorted(tags & {"subst", "adj", "verb", "adv", "interj"}))
        f["why"] = "noun" if "subst" in tags else ("short" if len(lemma) <= 6 else "other")
        f["has_freq"] = lemma in freqs
        out.append((lemma, article_id, f))
    mean = sum(f["surprisal"] for _, _, f in out) / len(out)
    for _, _, f in out:
        f["score"] = lexical_score(f, mean, f["has_freq"])
        # Unknown frequency (not fetched yet) gets the median modern frequency.
    out.sort(key=lambda x: -x[2]["score"])
    return out


def forgotten(dictionary, db):
    freqs = frequency.load(dictionary)
    ids = index(dictionary)
    out = []
    for lemma, fr in freqs.items():
        if lemma not in ids or fr["mid"] < 0.1:
            continue
        decline = math.log10((fr["mid"] + 0.002) / (fr["modern"] + 0.002))
        if decline >= 0.7:
            f = features.compute(lemma, dictionary, freq=fr)
            f["in_db"] = lemma in db
            f["score"] = decline + 0.5 * f["simplex"] - 0.3 * f["suffix_productivity"]
            out.append((lemma, ids[lemma], f))
    out.sort(key=lambda x: -x[2]["score"])
    return out


def norsk_ordbok(dictionary):
    no = index("no")
    known = set(index("bm")) | set(index("nn"))
    vocabulary = known | set(no)
    out = []
    for lemma, article_id in no.items():
        if lemma in known or not plausible(lemma):
            continue
        parts = split_compound(lemma, vocabulary)
        f = {
            "simplex": parts is None,
            "parts": "+".join(parts) if parts else "",
            "surprisal": features.surprisal(lemma, "nn"),
            "length": len(lemma),
        }
        out.append((lemma, article_id, f))
    # Book frequency (lemma form only) separates real-but-rare words from
    # one-parish phonetic spellings. Run with --no-frequency to skip.
    freq = {}
    if "--no-frequency" not in sys.argv:
        lemmas = [lemma for lemma, _, _ in out]
        freq = {p: frequency.form_frequencies(lemmas, p, "no_") for p in ("mid", "modern")}
    mean = sum(f["surprisal"] for _, _, f in out) / len(out)
    for lemma, _, f in out:
        # Short, uncompounded, odd-sounding dialect words that someone has printed.
        f["score"] = 1.5 * f["simplex"] + 0.6 * odd(f["surprisal"], mean)
        f["score"] -= 0.15 * max(0, f["length"] - 8)
        if freq:
            seen = max(freq["mid"].get(lemma, 0.0), freq["modern"].get(lemma, 0.0))
            f["per_million"] = seen
            # Sweet spot: 0.003-0.3 per million. Unseen or common words lose.
            f["score"] += -1.5 if seen == 0 else -0.8 * abs(math.log10(seen) + 1.5) + 1.0
    out.sort(key=lambda x: -x[2]["score"])
    return out


def describe(d, article_id):
    try:
        definitions, etymology = simplify(article(d, article_id))
    except Exception as error:
        return f"(could not fetch: {error})", None, None
    text = "; ".join(definitions["forklaring"][:3])
    text = re.sub(r"\s+", " ", text)[:160]
    return text, definitions, etymology


def section(title, items, d, fetch, extra=lambda f: ""):
    lines = [f"\n## {title} ({len(items)} candidates)\n"]
    head = items[:fetch] if fetch else []
    for lemma, article_id, f in head:
        text, _, _ = describe(d, article_id)
        lines.append(f"- **{lemma}** {extra(f)} — {text}")
    rest = [lemma for lemma, _, _ in items[len(head) : len(head) + 300]]
    if rest:
        lines.append("\nNext 300: " + ", ".join(rest))
    return lines


if __name__ == "__main__":
    dictionary = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "bm"
    fetch = int(sys.argv[sys.argv.index("--fetch") + 1]) if "--fetch" in sys.argv else 0
    db = {w["word"] for w in lexicon.db_words(dictionary)}

    out = [f"# Expansion candidates ({dictionary})"]
    u = unused(dictionary, db)
    counts = Counter(f["why"] for _, _, f in u)
    out.append(
        f"\n{len(u)} ordbokene headwords are not in the DB "
        f"({counts['noun']} nouns, {counts['short']} short words, {counts['other']} other)."
    )
    for why in ("noun", "short", "other"):
        group = [x for x in u if x[2]["why"] == why]
        out += section(f"Unused: {why}", group, dictionary, fetch, lambda f: f"_{f['pos']}_")

    fg = forgotten(dictionary, db)
    out += section(
        "Forgotten (≥5x rarer today than in 1920-79 books)",
        fg,
        dictionary,
        fetch,
        lambda f: f"_x{10 ** f['decline']:.0f}{' (in DB)' if f['in_db'] else ''}_",
    )

    if dictionary == "nn":
        no = norsk_ordbok(dictionary)
        out += section("Norsk Ordbok only (dialect words)", no, "no", fetch)

    path = f"{lexicon.CACHE}/expand_{dictionary}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"Wrote {path}")
