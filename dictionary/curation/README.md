# Word curation

How the curated word list in `dictionary/curated/` was chosen, and how to continue.
Python 3 with `numpy` beyond the standard library; Node or Bun for the `.mjs` scripts.
Fetched articles, frequencies and model outputs are cached in `cache/` (gitignored).

## Result

`words/approved.json`: **984 words, 583 bokmål and 401 nynorsk.** At one word per language per
day the site loops after about 13 months (nynorsk) and 19 months (bokmål).

- 578 are words the user marked *Dagsord!* on the labelling page.
- 172 are words Sonnet scored at 40 or above.
- 234 are words from Sonnet's 30-40 band that Opus kept.
- Then an Opus review (`opus_review.md`, brief in `prompts/opus_review.md`): the user's own
  yes-words were dropped only for the user's rules (dialect, technical, archaic, spelling,
  offensive), model-approved words for any reason. Accented spellings (diatomé) are dropped.

`export.mjs` turns them into database documents in `dictionary/curated/{bm,nn}.json`.

## The catalogue: every word looked at, in exactly one file

`catalogue.py` writes `words/`. A bm/nn twin counts as one word.

| File | Words | What |
|---|---:|---|
| `approved.json` | 984 | the final list (`picked_by`: `user`, `sonnet` or `opus`) |
| `rejected.json` | 882 | the user said no |
| `excluded.json` | 289 | approved, then dropped, with `reason`: Opus review (203), no bokmål/nynorsk article (61), dialect (22), accented spelling (3) |
| `sonnet_30-40.json` | 162 | the part of the 30-40 band Opus dropped |
| `sonnet_20-30.json` | 741 | Sonnet less sure |
| `sonnet_10-20.json` | 683 | probably not |
| `sonnet_0-10.json` | 227 | almost certainly not |
| `haiku_rejected.json` | 1,288 | Haiku ranked them below the review line; never seen by Sonnet |
| `haiku_vetoed.json` | 8,188 | Haiku vetoed them (`flag`: common, derived, technical, ...); never seen by Sonnet |
| `classifier_low.json` | 10,731 | the logistic model scored them too low to screen |
| `rule_filtered.json` | 4,714 | hard filters: technical term, place, number, person noun, dialect/archaic tag |

Each entry has `d` (bm/nn), `w`, `src` (`db`: in ord.db; `unused`: an ordbokene headword the
old pipeline skipped; `norsk-ordbok`), `m` (meaning), `e` (example) and the score that placed
it (`p_sonnet` 0-100 or `p_cls` 0-1).

## Pipeline

```sh
cd dictionary/curation
python3 frequency.py bm             # NB book frequencies (DHLAB) for ord.db words
python3 sweep.py fetch              # fetch unused ordbokene articles (cache/articles_*)
python3 sweep.py score              # features + classifier over all candidates -> cache/sweep/
python3 sonnet.py build r2 20-30    # Sonnet batches for a band (see sonnet.py)
python3 sonnet.py                   # gold report + labeler page for the 30-40 band
python3 catalogue.py                # labels + scores -> words/*.json
node export.mjs                     # words/approved.json -> dictionary/curated/{bm,nn}.json
```

- `lexicon.py`: Norsk ordbank loaders. `frequency.py`: DHLAB book frequencies.
- `features.py`, `score.py`, `learn.py`: hand-made signals, hard filters and a logistic model.
- `expand.py`: candidates beyond ord.db (unused headwords, forgotten words, Norsk Ordbok).
- `pool.py`, `labeler.html`: labelling rounds. The page saves verdicts in the artifact's
  database; export them, merge into `labels.csv`.
- `sweep.py`: candidate universe and the Haiku stages (kept for reference, see below).
- `sonnet.py`: Sonnet as judge. `prompts/`: the prompts used.
- `dialect.json`: dialect flags (Sonnet, clear cases only) for the user's yes-words.
- `opus_review.json`: Opus keep/drop per word; `opus_review.md` lists what it changed.
- `catalogue.py`, `export.mjs`: the steps that produce the deliverable.

## What was tried

Ground truth is `labels.csv`: 1,779 verdicts from eight labelling rounds.

| Approach | Outcome |
|---|---|
| Hand-made signals + hard filters (`score.py`) | AUC 0.75 on labels; top of the ranking is 5-8x richer in liked words than a random draw (~10%). Kept as the first filter. |
| Logistic model on the signals (`learn.py`) | Cross-validated AUC 0.68, below the hand weights, since each round samples harder words. |
| Expansion: unused ordbokene headwords | The biggest win. `parse.mjs` dropped all nouns and words of six letters or fewer; 309 approved words come from there (*hikkas*, *kukelure*, *jeremiade*). |
| Expansion: forgotten words (DHLAB decline since 1920-79) | Mostly archaic; the user excludes those. Used as a feature only. |
| Expansion: Norsk Ordbok | Dialect-heavy, and its words have no bokmål/nynorsk article to link to. Skipped. |
| Haiku screen + critic, 473 words | User said yes to 368 (78%), but these were the easiest, top-ranked words. |
| Haiku screen/rank/refine over 12,078 candidates | Failed: of the "uncertain" words shown to the user only 18% were liked; Haiku's scores did not separate liked from disliked (AUC ~0.52 on hard words). It also misjudges well-known words as rare. |
| Sonnet as judge (two passes, 300 verdicts as examples, hidden gold) | Works: gold AUC 0.86; pilot on hard words 0.73; the user liked 56% of the 30-40 band, against 18% for Haiku's. Within that band the score no longer separates. |
| Opus review (low reasoning, brief from the whole conversation) | A stricter final pass: kept 62% of the 30-40 band; disagreed with 38% of the user's own yes-words, mostly calling nynorsk words dialect. Used as a filter on rules, not on taste. |

## What is missing

- 406 model-approved words (Sonnet and Opus) are not individually reviewed by the user.
- Opus ran on low reasoning: some drops look wrong (e.g. *minuend*, *hoppsa* as "technical").
  Check `opus_review.md`.
- The bands below were scored with the round-7 examples. Rebuild batches with the latest
  labels (`sonnet.py build`) before trusting them.
- The dictionaries rarely mark dialect; `dialect.json` is Sonnet's judgement of clear cases.
- Norsk Ordbok words would need their own article parser and link target.
