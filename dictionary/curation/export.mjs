// Turn words/approved.json (from catalogue.py) into database documents: dictionary/curated/{bm,nn}.json.
//
//     node dictionary/curation/export.mjs
//
// Each document has exactly the fields the `bm` / `nn` collections hold after parse.mjs and
// detailed.mjs (word, dictionary, wordgroup, id, pronunciation, etymology, definitions,
// inflection), built with the same `clean` as detailed.mjs. Articles are read from the curation
// cache when present and fetched from ord.uib.no otherwise.

import fs from "fs";
import { clean } from "../article.mjs";

const HERE = new URL(".", import.meta.url);
const CACHE = new URL("cache/", HERE);
const OUT = new URL("../curated/", HERE);
const ARTICLE = "https://ord.uib.no/{d}/article/{id}.json";

async function article(dictionary, id) {
  const cached = new URL(`articles_${dictionary}/${id}.json`, CACHE);
  if (fs.existsSync(cached)) return JSON.parse(fs.readFileSync(cached, "utf8"));
  for (let attempt = 0; ; attempt++) {
    try {
      const response = await fetch(ARTICLE.replace("{d}", dictionary).replace("{id}", id));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      fs.mkdirSync(new URL(`articles_${dictionary}/`, CACHE), { recursive: true });
      fs.writeFileSync(cached, JSON.stringify(data));
      return data;
    } catch (error) {
      if (attempt === 3) throw new Error(`${dictionary}/${id}: ${error.message}`);
      await new Promise((resolve) => setTimeout(resolve, 2000 * 2 ** attempt));
    }
  }
}

const approved = JSON.parse(fs.readFileSync(new URL("words/approved.json", HERE), "utf8"));
fs.mkdirSync(OUT, { recursive: true });

for (const dictionary of ["bm", "nn"]) {
  const words = approved.filter((w) => w.d === dictionary);
  const documents = [];
  for (let i = 0; i < words.length; i += 6) {
    const batch = words.slice(i, i + 6);
    const articles = await Promise.all(batch.map((w) => article(dictionary, w.id)));
    batch.forEach((w, j) => {
      const { id, pronunciation, etymology, definitions, inflection } = clean(articles[j]);
      documents.push({
        word: w.w,
        dictionary,
        wordgroup: w.wordgroup,
        id,
        pronunciation,
        etymology,
        definitions,
        inflection,
      });
    });
  }
  documents.sort((a, b) => a.word.localeCompare(b.word, "nb"));
  fs.writeFileSync(new URL(`${dictionary}.json`, OUT), JSON.stringify(documents, null, 1) + "\n");
  console.log(`${dictionary}: ${documents.length} documents`);
}
