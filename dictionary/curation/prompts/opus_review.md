# Review: Norwegian word of the day (dagsord.no)

You are reviewing candidate words for dagsord.no, a site that shows one Norwegian word of the
day in bokmål (bm) and one in nynorsk (nn). The words loop after a year or two, so the list
should hold only words the site owner would be glad to show. Their taste, from many rounds of
feedback:

WANT
- Rare or unusual words with character, that could still be used in a today-context
  (don't be too restrictive: learned, playful, old-fashioned-but-valid words are fine).
- Sound-painting, expressive, humorous or learned words: plapre, hikkas, omkalfatre, raljere,
  befippa, kukelure, skuddermudder, jeremiade, luguber, pamfilius.

DO NOT WANT
- Words that are themselves very commonly used, or well known to most adult Norwegians even if
  not used daily. "fekte" is WAY too regular. Others rejected: snabel, myldre, skarlagen,
  burlesk, stringent, varg, merino, intrikat, forvalte. (Judge how widely the word is USED,
  not whether it describes something common.)
- Medical, biological, chemical, legal, grammatical or other technical/subject terms.
- Derived words with a see-through common root (importere <- import, sviksam <- svik;
  -ere, -sam, -leg/-lig, -het, -else on an everyday root). An unusual root is fine (approbere).
- Dialect words and local forms; archaic words that are no longer used.
- Variant spellings with accents (diatomé, koryfé), place/person/nationality words,
  numbers, offensive or ethnic terms.

The owner accepts roughly half of the words that already look promising, so be honest but
not harsh: keep a word if a curious reader would enjoy learning it and could use it.

The owner's own verdicts (YES = wanted, NO = not wanted):
{examples}

TASK
Read the batch file named in your instructions (tab-separated: id, dict, word, meaning,
example). For EVERY id decide keep (1) or drop (0) and give a short reason code:
ok, common, technical, derived, dialect, archaic, spelling, offensive, dull.
Write the output file with the Write tool as valid JSON only:
{"<id>": [1, "ok"], "<id>": [0, "common"], ...}
