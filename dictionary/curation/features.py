"""Per-word signals for how interesting (or boring) a word is.

Every feature is cheap and computed from data we already have: the ordbank
(compound analysis, inflections), ordbokene (definitions, etymology) and
book frequencies from Nasjonalbiblioteket (see frequency.py).
"""

import json
import math
import re
from collections import Counter
from functools import lru_cache

import frequency
import lexicon

LANGUAGES = set(
    json.load(open(f"{lexicon.DICT}/abbreviations/mappings.json"))["language"].values()
)
LATINATE = re.compile(
    r"\b(\w*latin|gresk|fransk|engelsk|italiensk|spansk|portugisisk|arabisk)\b", re.I
)
# Old Norse, Low German, dialects and sound words: homely, quirky Norwegian.
HOMELY = re.compile(
    r"\b(norrønt?|lavtysk|nedertysk|nederlandsk|dansk|svensk|dialekt\w*|lydord"
    r"|lydmalende|lydhermende|foreldet|eldre|gammalnorsk|islandsk)\b",
    re.I,
)
OTHER_LANGUAGE = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, LANGUAGES), key=len, reverse=True)) + r")\b", re.I
)
UNKNOWN_ORIGIN = re.compile(r"\b(uviss|usikker|ukjent|uklar)\w*\b", re.I)
DERIVED_ETYMOLOGY = re.compile(r"^(av|til|fra|jamfør|jf\.?|se)\s+\S+$|^jamfør -", re.I)

# Tags ordbokene uses for register/style. Words carrying them have character.
REGISTER = re.compile(
    r"\b(overført|ironisk|arkaiserende|nedsettende|nedsetjande|litterært|foreldet|eldre"
    r"|spøkefullt?|muntlig|munnleg|dialekt(?!i)\w*|slang|sjelden|gammeldags|poetisk"
    r"|billedlig|bileteleg|skjemtande|skjemtsamt|vulgært|hverdagslig|kvardagsleg)\b",
    re.I,
)

# Definition shapes that give away a derived, predictable word.
TEMPLATES = [
    ("som-gjelder", r"^som (gjelder|gjeld|angår|vedkommer|hører til|høyrer til|har med)\b"),
    ("det-å", r"^(det )?å \w+$|^det å\b"),
    ("som-er", r"^som (er|har|kan|ikkje|ikke) \w+( \w+)?$"),
    ("i-grad", r"^i (høy|stor|liten|lav) grad\b"),
    ("med-x", r"^(med|uten|utan) \w+( \w+)?$"),
]
TEMPLATES = [(name, re.compile(rx, re.I)) for name, rx in TEMPLATES]
# A capitalised word inside the main explanation: demonyms, "som gjelder Gabon".
PLACE = re.compile(r"(?<!^)(?<![.:] )\b[A-ZÆØÅ][a-zæøå]{2,}")
NUMBERS = set(
    "en ein to tre fire fem seks sju syv åtte ni ti elleve tolv tretten fjorten femten seksten"
    " sytten atten nitten tjue tyve tretti førti femti seksti sytti åtti nitti hundre tusen"
    " million halv fler mange dobbelt første andre tredje fjerde femte hel heil".split()
)
COLOUR = re.compile(r"(rød|raud|blå|grønn|gul|brun|grå|svart|kvit|hvit|fiolett|lilla|rosa|oransje)$")


def flatten(node):
    """All strings inside a nested definitions/etymology structure."""
    if node is None:
        return []
    if isinstance(node, str):
        return [re.sub(r"<[^>]+>", "", node)]
    if isinstance(node, dict):
        return [s for k, v in node.items() if k not in ("id", "word") for s in flatten(v)]
    return [s for item in node for s in flatten(item)]


def explanations(definitions):
    """Just the explanation strings (no examples)."""
    out = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "forklaring":
                    out.extend(flatten(v))
                elif k != "eksempel":
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(definitions)
    return out


def count_examples(definitions):
    n = 0

    def walk(node):
        nonlocal n
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "eksempel":
                    n += len(v) if isinstance(v, list) else 1
                else:
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(definitions)
    return n


@lru_cache(maxsize=None)
def char_model(dictionary):
    """Letter trigram model over every lemma: how 'normal' does a spelling look?"""
    tri, bi = Counter(), Counter()
    for w in lexicon.lemmas(dictionary).values():
        w = f"^^{w.lower()}$"
        for i in range(len(w) - 2):
            tri[w[i : i + 3]] += 1
            bi[w[i : i + 2]] += 1
    return tri, bi


def surprisal(word, dictionary):
    """Mean bits per letter. High = unusual letter sequences (loans, sound words)."""
    tri, bi = char_model(dictionary)
    w = f"^^{word}$"
    bits = 0.0
    for i in range(len(w) - 2):
        p = (tri[w[i : i + 3]] + 0.1) / (bi[w[i : i + 2]] + 3.0)
        bits -= math.log2(p)
    return bits / (len(w) - 2)


def stem(part):
    """Crude stem for checking if a compound part reappears in its definition."""
    part = part.lower().strip("-")
    return part[: max(3, len(part) - 2)] if len(part) > 4 else part


def compute(word, dictionary, definitions=None, etymology=None, freq=None):
    f = {}
    compounds = lexicon.compounds(dictionary)
    parts = compounds.get(word, "unknown")
    f["length"] = len(word)
    f["simplex"] = parts is None
    f["compound"] = isinstance(parts, tuple)

    suffixes = lexicon.suffix_productivity(dictionary)
    prefixes = lexicon.prefix_productivity(dictionary)
    f["suffix_productivity"] = math.log1p(suffixes.get(parts[1], 0)) if f["compound"] else 0.0
    f["prefix_productivity"] = math.log1p(prefixes.get(parts[0], 0)) if f["compound"] else 0.0
    f["suffix"] = parts[1] if f["compound"] else ""

    texts = explanations(definitions)
    text = " ".join(texts).lower()
    f["n_explanations"] = len(texts)
    f["n_examples"] = count_examples(definitions)
    f["definition_length"] = len(text.split())

    # A compound whose definition just repeats its parts is fully predictable.
    f["transparent"] = bool(
        f["compound"]
        and texts
        and (stem(parts[0]) in text or stem(parts[1]) in text)
    )
    # Only the main sense counts: "brukt som adjektiv" sub-senses are normal.
    f["template"] = next(
        (name for name, rx in TEMPLATES if texts and rx.search(texts[0].strip())), ""
    )
    f["place"] = bool(texts and PLACE.search(texts[0].strip()))
    f["number"] = bool(f["compound"] and parts[0] in NUMBERS) or bool(
        re.search(r"\b(ordenstall|ordenstal|grunntall|grunntal)\w*", text)
    )
    f["colour"] = bool(f["compound"] and COLOUR.search(word))

    etym = " ".join(flatten(etymology))
    f["has_etymology"] = bool(etym.strip())
    f["latinate"] = bool(LATINATE.search(etym))
    f["homely"] = bool(HOMELY.search(etym))
    f["loan_or_old"] = bool(OTHER_LANGUAGE.search(etym)) or f["homely"]
    f["unknown_origin"] = bool(UNKNOWN_ORIGIN.search(etym))
    f["derived_etymology"] = bool(etym and DERIVED_ETYMOLOGY.search(etym.strip()))
    all_text = " ".join(flatten(definitions)) + " " + etym
    f["register"] = ",".join(sorted({m.lower() for m in REGISTER.findall(all_text)}))

    freq = freq or {}
    eps = 0.002
    old, mid, modern = (freq.get(k, 0.0) for k in ("old", "mid", "modern"))
    f["log_modern"] = math.log10(modern + eps)
    f["log_any"] = math.log10(max(old, mid, modern) + eps)
    # Was used in the 1900s, has faded since. Mid-century is the cleaner baseline:
    # pre-1920 books are largely Dano-Norwegian.
    f["decline"] = math.log10((mid + eps) / (modern + eps))
    f["decline_old"] = math.log10((old + eps) / (modern + eps))
    f["surprisal"] = surprisal(word, dictionary)
    return f


def for_db(dictionary):
    freqs = frequency.load(dictionary)
    out = []
    for w in lexicon.db_words(dictionary):
        feats = compute(
            w["word"], dictionary, w["definitions"], w["etymology"], freqs.get(w["word"])
        )
        out.append({"word": w["word"], "wordgroup": w["wordgroup"], **feats})
    return out
