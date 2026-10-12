Norwegian lexicography task. Use ONLY the Read and Write tools; never call any other tool.
Read {batch} (tab-separated: id, dictionary bm=bokmål/nn=nynorsk, word, meaning, etymology).
For each word decide whether it is a DIALECT word: a regional/local word or local form that is not part of general written standard Norwegian (it would be unfamiliar or marked as dialectal to most speakers outside one region). Words that are merely rare, old-fashioned, expressive, colloquial or literary are NOT dialect. Nynorsk standard words are NOT dialect just because they are nynorsk. When in doubt, answer not dialect — only flag clear cases.
Write {out} with the Write tool: a JSON object listing ONLY the flagged ids, {"<id>": "<short reason>"}. Valid JSON only.
