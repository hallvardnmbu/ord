# Word curation experiments

Tools for (1) filtering boring words out of `ord.db` and (2) finding new words to add.
Python 3 with only `numpy` beyond the standard library. Everything is cached in `cache/` (gitignored).

```sh
cd dictionary/curation
python3 frequency.py bm            # book frequencies for words in ord.db (~3 min)
python3 frequency.py bm --all      # ... for every ordbank lemma (expansion, ~1 h)
python3 score.py bm                # cache/scores_bm.csv + cache/report_bm.md
python3 expand.py nn --fetch 25    # cache/expand_nn.md, with definitions for the top 25
python3 pool.py --next labels.csv  # cache/labeler.html: next balanced labeling round
python3 learn.py labels.csv        # fit weights to your labels (exported from the labeling page)
```

## Signals (features.py)

| Signal | Source | Idea |
|---|---|---|
| compound / simplex | `leddanalyse.txt` | Non-compounds are words in their own right. |
| transparent compound | compound parts + definition | If the definition repeats a part (*lovfeste*: "fastsette ved lov") the word explains itself. |
| suffix productivity | `leddanalyse.txt` | Last parts shared by hundreds of compounds (-vis, -messig, -laus) mark assembly-line words. |
| definition templates | ordbokene | "som gjelder ...", "det å ...", "med X": derived words. |
| place / number | definition, compound parts | Demonyms (*gabonsk*), *treårig*, ordinals. |
| origin | etymology | Old Norse, Low German, dialect and sound words score up; Latinate -ere/-isk slightly down. |
| register tags | ordbokene | overført, ironisk, foreldet, dialekt, spøkefullt ... |
| too common | NB books 2000-24 | Everyone already knows *koordinere*. |
| unattested | NB books, all periods | Never printed: probably dead weight. |
| forgotten | NB books 1920-79 vs 2000-24 | Words that faded: *annamme*, *formedelst*, *navnkundig*. |
| odd spelling | letter-trigram model over the lexicon | Unusual letter sequences: loans and sound words. |

`score.py` combines them with hand-set `WEIGHTS` and applies `HARD` filters. `learn.py` replaces
the guesses with weights fitted to labels and reports each filter's false positives.

## Expansion sources (expand.py)

- **Unused ordbokene headwords.** `parse.mjs` drops all nouns and every word of six letters or
  fewer. That is ~60k headwords per dictionary, including *kåt*, *snål*, *nifs*, *fjåg*.
- **Forgotten words.** DHLAB frequencies over all lemmas, ranked by decline since 1920-79.
- **Norsk Ordbok** (`dict=no` on the same API, ~280k headwords). The big nynorsk dialect
  dictionary, ranked to favour short, uncompounded words that have appeared in print.

Note that the Norsk Ordbok articles use another structure (place abbreviations, `attest`), so
`detailed.mjs` would need a branch for them.
