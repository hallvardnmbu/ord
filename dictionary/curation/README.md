# Word curation

How the curated word list in `dictionary/curated/` was chosen, and how to continue.
Python 3 with `numpy` beyond the standard library; Node or Bun for the `.mjs` scripts.
Fetched articles, frequencies and model outputs are cached in `cache/` (gitignored).

## Result

`words/approved.json`: **956 words, 498 bokmål and 458 nynorsk.** At one word per language per
day the site loops after about 16 months.

- 747 are words the user marked *Dagsord!* on the labelling page (minus 22 dialect words).
- 209 are words Sonnet scored at 40 or above. The user has not reviewed these individually.

`export.mjs` turns them into database documents in `dictionary/curated/{bm,nn}.json`.

## The catalogue: every word looked at, in exactly one file

`catalogue.py` writes `words/`. A bm/nn twin counts as one word.

| File | Words | What |
|---|---:|---|
| `approved.json` | 956 | the final list (`picked_by`: `user` or `sonnet`) |
| `rejected.json` | 882 | the user said no |
| `excluded.json` | 52 | approved, then dropped: dialect (22) or no bokmål/nynorsk article (30, Norsk Ordbok) |
| `sonnet_30-40.json` | 427 | **next to review.** The user liked 74 of the first 131 from this band |
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

## What is missing

- The 209 Sonnet-approved words are not individually reviewed. Spot-check them on the labeller.
- `sonnet_30-40.json` (427 words) is half-reviewed territory: worth finishing.
- The bands below were scored with the round-7 examples. Rebuild batches with the latest
  labels (`sonnet.py build`) before trusting them.
- The dictionaries rarely mark dialect; `dialect.json` is Sonnet's judgement of clear cases.
- Norsk Ordbok words would need their own article parser and link target.
