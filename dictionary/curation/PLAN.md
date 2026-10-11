# Greenlight pipeline

Goal: a reviewed shortlist of rare-but-usable words (bokmål and nynorsk, 50/50), found by
several independent passes, so the human only says yes/no at the end.

Labels so far (four rounds, ~900 verdicts) are the ground truth for every calibration below.

## Pass 0: candidate pool (deterministic)

| Source | Selection | Size |
|---|---|---|
| ord.db | not hard-filtered, not labelled, top by scorer | 1000 per dictionary |
| Unused ordbokene headwords | lexical score → fetch article → full features + hard filters → rescore | 500 per dictionary |
| Norsk Ordbok | printed after 2000, uncompounded, fetch article, hard filters | 150 (nn) |

Hard filters: place/demonym, number, technical (subject label, definition cues, word shape),
person noun, assembly-line compound, accented variant spelling.

## Pass 1: classifier

Logistic model on all labels (features.py signals) plus the hand-tuned score. Each candidate gets
`p_classifier`. Nothing is dropped here; it is one vote.

## Pass 2: Haiku screen, with hidden gold

Haiku rates every candidate 1–5 against the criteria and ~80 example verdicts.
Each batch hides ~20 already-labelled words ("gold"). Per-batch agreement with the gold
is measured; a batch that disagrees badly (AUC < 0.6) is re-rated. Gold also calibrates
what a Haiku "3" means in liked-probability.

## Pass 3: Haiku critic and usability test

Survivors of pass 1+2 go to a stricter, differently framed pass. For each word Haiku must:
- write one natural modern Norwegian sentence using the word (can't → reject: not usable today)
- give reason codes for rejection: `common`, `derived` (see-through root), `technical`,
  `dialect-only`, `archaic-spelling`, `offensive`, `person/place`, or `ok`

`offensive` is a hard veto: a word of the day must not be a slur or dated ethnic term.

## Pass 4: aggregation and calibration

`combined = z(classifier) + z(haiku screen)`, critic veto applied. The threshold is set on the
gold so that the expected share of "yes" in the greenlit list is ≥ 70% (random draws: ~10%).

## Pass 5: diversity

- one entry per root (no *svimre* and *svimle*, no bm and nn twin of the same word)
- cap per ending (no wall of -sleg or -ast words)
- 50/50 bokmål/nynorsk

## Review

The labeling page shows only greenlit words, with meaning and Haiku's example sentence.
Yes/no answers go to the same label store, so they also train the next round.
