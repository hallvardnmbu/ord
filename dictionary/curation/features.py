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

# Specialist vocabulary: medicine, biology, chemistry and other sciences.
TECH_DOMAIN = re.compile(
    r"^(i|innan|innen|om|brukt i)\s+(medisin|biologi|botanikk|zoologi|anatomi|fysiologi|kjemi|biokjemi"
    r"|fysikk|geologi|mineralogi|astronomi|matematikk|statistikk|språkvit\w+|grammatikk|fonetikk"
    r"|psykologi|psykiatri|farmasi|patologi|genetikk|mikrobiologi|teknikk|fagspråk|bot|zool|med)\b",
    re.I,
)
# Only words that make the definition *about* a specialist topic; passing mentions
# ("død av alderdom eller sykdom") do not count.
TECH_WORDS = re.compile(
    r"\b(betennelse|infeksjon|kjertel\w*|celle\w*|vev|organisme\w*|bakterie\w*|virus|legemiddel"
    r"|enzym\w*|hormon\w*|molekyl\w*|grunnstoff|kromosom\w*|arveanlegg|svulst|protein\w*"
    r"|planteslekt|plantefamilie|dyreslekt|slekta|slekten|underklasse|fosteret|kjemisk\w*"
    r"|\w*legering|\w*forbindelse|fargestoff\w*|grunnstoff\w*|syre|salt av|metall\w*|mineral\w*"
    r"|amin|\w*kolbe|destill\w*|måleinstrument"
    r"|(apparat|instrument|innretning) (til|for) å|laboratori\w*|spesialist i)\b"
    r"|^(\w+ )?(sykdom|sjukdom|lidelse|tilstand) (som|i|med|der|kjenneteikna|kjennetegnet)",
    re.I,
)
# Genus + species: "Lysimachia vulgaris", not "Homer rungende".
# Unmistakably medical/biological word shapes, checked even when a definition
# exists but carries no subject label (ødematisk, kolloidal, supradental).
MEDICAL_SHAPE = re.compile(
    r"(oidal|ploid|dental|itis|osisk|algi|algisk|genetisk|cytt|krin|tomi|ektomi|plasma|plasmatisk"
    r"|viral|bakteriell|cellulær|vaskulær|kardial|nevral|fytt|zoisk|zoon|emisk|ematisk|meter|skop"
    r"|tron|metri)$"
    r"|^(kardio|nevro|hemo|hemat|osteo|gastro|dermat|myo|hepat|nefr|pneum|cyto|angio|histo|onko"
    r"|lymf|pato|bakter|kromo|intra)(?=[a-zæøå]{4,})"
)
# Everyday words that share those shapes.
MEDICAL_SHAPE_OK = re.compile(r"(akademisk|polemisk|blasfemisk|problematisk|systematisk|tematisk|skjematisk"
                              r"|matematisk|dilemmatisk|emblematisk|anatemisk|bohemisk|ambrosisk|nostalgisk|oksidental"
                              r"|transcendental|telegraf|fotograf|fotografi|biografi|geografi|kalligrafi|koreograf|koreografi"
                              r"|typograf|typografi|monograf|monografi|seismograf|parameter|kilometer)$|^(gastronom|histori)")
LATIN_NAME = re.compile(
    r"\b[A-Z][a-z]+ [a-z]+(us|um|is|ae|ii|ensis|oides|atus|ata|osa|osus|alis|aris|ica|icus|ella|ina|inus|eus|ia)\b"
)
TECH_SHAPE = re.compile(
    r"(itt|ose|emi|algi|algisk|patisk|patologi|terapi|terapeutisk|cytt|oid|skop|meter|metri|logisk|logi"
    r"|genese|genetisk|lytisk|ektomi|tomi|plasma|fytt|krin|trofi)$"
    r"|^(kardio|nevro|hemo|hemat|osteo|gastro|derm|myo|hepat|nefr|pneum|cyto|bio|hydro"
    r"|lymf|angio|fysio|pato|immun|kromo|histo|onko|psyko)"
)
DATED = re.compile(r"(foreldet|eldre|gammeldags|arkaiserende|dialekt|sjelden)", re.I)

# Definition shapes that give away a derived, predictable word.
TEMPLATES = [
    ("som-gjelder", r"^som (gjelder|gjeld|angår|vedkommer|hører til|høyrer til|har med)\b"),
    ("det-å", r"^(det )?å \w+$|^det å\b"),
    ("som-er", r"^som (er|har|kan|ikkje|ikke) \w+( \w+)?$"),
    ("i-grad", r"^i (høy|stor|liten|lav) grad\b"),
    ("med-x", r"^(med|uten|utan) \w+( \w+)?$"),
    # Person nouns: musikaliar, viktorianar, syfilitikar, grenlender.
    ("person", r"^(person|kvinne|mann|ein|en|innbyggjar|innbygger|tilhenger|tilhengar|spesialist|utøver"
     r"|utøvar|elev|student|medlem) (som|frå|fra|av|i|på|med)\b"
     r"|^\w+(ar|ist|ør|ant|ent|log|kar|ker) (som|i|innan|innen)\b"),
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
    # Neoclassical look, used to guess technical terms when no definition is at hand.
    f["latinate_shape"] = bool(re.search(r"(y|ks|ia|io|eo|ae|th|rh|ph)", word)) and len(word) > 5
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
    # Person nouns whose definition mentions a person anywhere in the main sense
    # (somatikar, rastafarianar, egosentrikar).
    person_noun = bool(texts) and re.search(r"(ar|er|ist|ing|ør|ikar|iker)$", word) and re.search(
        r"\b(person|personar|personer|tilhengar|tilhenger|innbyggjar|innbygger|folk|folkeslag)\b",
        texts[0], re.I)
    # Only the main sense counts: "brukt som adjektiv" sub-senses are normal.
    f["template"] = next(
        (name for name, rx in TEMPLATES if texts and rx.search(texts[0].strip())), ""
    )
    if person_noun and not f["template"]:
        f["template"] = "person"
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
    tags = f["register"].split(",")
    # Marked as old or regional: hard to use in a today-context.
    f["dated"] = any(DATED.match(t) for t in tags if t)
    # Marked for style (figurative, ironic, colloquial): colour that still works today.
    f["style"] = any(t and not DATED.match(t) for t in tags)

    freq = freq or {}
    eps = 0.002
    old, mid, modern = (freq.get(k, 0.0) for k in ("old", "mid", "modern"))
    f["log_modern"] = math.log10(modern + eps)
    f["log_any"] = math.log10(max(old, mid, modern) + eps)
    # Was used in the 1900s, has faded since. Mid-century is the cleaner baseline:
    # pre-1920 books are largely Dano-Norwegian.
    f["decline"] = math.log10((mid + eps) / (modern + eps))
    f["decline_old"] = math.log10((old + eps) / (modern + eps))
    # Medicine, biology, chemistry and the like: rare, but not usable day to day.
    tech_text = bool(texts) and (
        bool(TECH_DOMAIN.match(texts[0].strip()))
        or bool(TECH_WORDS.search(texts[0]))
        or bool(LATIN_NAME.search(" ".join(texts)))
    )
    f["technical"] = (
        tech_text
        or (not texts and bool(TECH_SHAPE.search(word)) and f["latinate_shape"])
        or (bool(MEDICAL_SHAPE.search(word)) and not MEDICAL_SHAPE_OK.search(word) and not f["compound"])
    )

    # Printed before, practically gone since 2000: archaic rather than rare.
    f["dead_today"] = modern < 0.003 and max(old, mid) > 0.05
    f["surprisal"] = surprisal(word, dictionary)
    d = derivation(word)
    f["derived"] = bool(d) and bool(re.search(r"-[a-zæøå]+$", d[1]))
    # Derived from a word everyone knows: you can see straight through it
    # (importere <- import, sviksam <- svik). Unusual roots are fine (approbere).
    root_freq = root_frequency(d[0]) if d else 0.0
    f["see_through"] = bool(d) and root_freq >= 1.0
    f["root"] = d[0] if d else ""
    f["prefixed"] = bool(d) and not d[1].startswith("-")
    f["loan_verb"] = word.endswith(LOAN_VERB)
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


# Derivation: the word is a known root plus a productive ending (or prefix).
DERIVING_SUFFIXES = [
    # verbs
    "ifisere", "isere", "iere", "ere", "ast", "es", "ne",
    # adjectives
    "messig", "aktig", "elig", "eleg", "lig", "leg", "sam", "som", "bar", "voren", "isk",
    "ete", "et", "ut", "ig", "ende", "ande",
    # nouns
    "else", "ning", "ing", "heit", "het", "skap", "dom", "nad", "leik", "eri", "isme", "ist",
]
DERIVING_PREFIXES = ["mis", "van", "be", "for", "u"]


@lru_cache(maxsize=None)
def vocabulary():
    words = set()
    for d in ("bm", "nn"):
        words |= {w.lower() for w in lexicon.lemmas(d).values()}
    return words


def root_candidates(stem):
    yield stem
    for end in ("e", "a", "at", "um", "us", "ion", "isk", "i", "o"):
        yield stem + end
    if len(stem) > 3 and stem[-1] == stem[-2]:
        yield stem[:-1]
    if stem.endswith("l") or stem.endswith("r"):
        yield stem[:-1] + "e" + stem[-1]  # sviml- / svimel


@lru_cache(maxsize=None)
def sorted_vocabulary():
    return sorted(vocabulary())


def shares_stem(stem, word):
    """A lemma other than the word (or its -ing/-else forms) that starts with stem."""
    import bisect

    vocab = sorted_vocabulary()
    i = bisect.bisect_left(vocab, stem)
    while i < len(vocab) and vocab[i].startswith(stem):
        other = vocab[i]
        if other != word and not other.startswith(word) and not other.startswith(word[:-1] + "ing"):
            return other
        i += 1
    return None


LOAN_VERB = ("ifisere", "isere", "iere", "ere")


@lru_cache(maxsize=None)
def _all_frequencies():
    out = {}
    for d in ("bm", "nn"):
        for w, fr in frequency.load(d).items():
            out[w] = max(out.get(w, 0.0), fr.get("modern", 0.0))
    return out


def root_frequency(root):
    """Per-million frequency of a root in books 2000-24 (0 if never looked up)."""
    return _all_frequencies().get(root, 0.0)


def derivation(word):
    """(root, affix) when the word is a known root plus a deriving affix, else None."""
    vocab = vocabulary()
    for suffix in DERIVING_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            stem = word[: -len(suffix)]
            minimum = 4 if suffix in LOAN_VERB else 3
            for root in root_candidates(stem):
                if root != word and len(root) >= minimum and root in vocab:
                    return root, "-" + suffix
            # segregere ~ segregasjon, plagiere ~ plagiat
            if suffix in LOAN_VERB and len(stem) >= 5:
                other = shares_stem(stem, word)
                if other:
                    return other, "-" + suffix
    for prefix in DERIVING_PREFIXES:
        rest = word[len(prefix):]
        if word.startswith(prefix) and len(rest) >= 4:
            if rest in vocab:
                return rest, prefix + "-"
            # u-bøt-eleg, u-visk-eleg: prefix and ending around a known root
            inner = derivation(rest)
            if inner and inner[1].startswith("-"):
                return inner[0], prefix + "-" + inner[1]
    return None
