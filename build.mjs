import { Database } from "bun:sqlite";
import { join } from "path";
import { redate, writeReadme } from "./dates.mjs";

// Build ord.db from the MongoDB collections, or with --curated from the reviewed word list in
// dictionary/curated/{bm,nn}.json (same documents, no database needed).
const CURATED = process.argv.includes("--curated");

let mongo = null;
if (!CURATED) {
  const { MongoClient } = await import("mongodb");
  mongo = new MongoClient(
    `mongodb+srv://${process.env.MONGO_USR.trim()}:${process.env.MONGO_PWD.trim()}` +
      `@ord.c8trc.mongodb.net/?retryWrites=true&w=majority&appName=ord`,
  );
  await mongo.connect();
}

async function documents(dictionary) {
  if (CURATED) return Bun.file(join(import.meta.dir, "dictionary", "curated", `${dictionary}.json`)).json();
  return mongo
    .db("ord")
    .collection(dictionary)
    .find({}, { projection: { _id: 0, date: 0, past: 0 } })
    .toArray();
}

const dbPath = join(import.meta.dir, "ord.db");
const db = new Database(dbPath);

db.run("DROP TABLE IF EXISTS words_fts");
db.run("DROP TABLE IF EXISTS words");

db.run(`
  CREATE TABLE words (
    word        TEXT NOT NULL,
    dictionary  TEXT NOT NULL,
    wordgroup   TEXT,
    id          INTEGER,
    pronunciation TEXT,
    etymology   TEXT,
    definitions TEXT,
    inflection  TEXT,
    date        TEXT
  )
`);
db.run("CREATE INDEX idx_date ON words(date)");
db.run("CREATE INDEX idx_word ON words(word)");
db.run("CREATE INDEX idx_dictionary ON words(dictionary)");
db.run("CREATE INDEX idx_dict_date ON words(dictionary, date)");
db.run(`
  CREATE VIRTUAL TABLE words_fts USING fts5(
    word,
    content='words',
    content_rowid='rowid'
  )
`);

const insert = db.prepare(`
  INSERT INTO words (word, dictionary, wordgroup, id, pronunciation, etymology, definitions, inflection, date)
  VALUES ($word, $dictionary, $wordgroup, $id, $pronunciation, $etymology, $definitions, $inflection, $date)
`);

for (const dictionary of ["bm", "nn"]) {
  const words = await documents(dictionary);

  db.transaction(() => {
    for (const w of words) {
      insert.run({
        $word: w.word,
        $dictionary: dictionary,
        $wordgroup: w.wordgroup ?? null,
        $id: w.id ?? null,
        $pronunciation: w.pronunciation ?? null,
        $etymology: w.etymology ? JSON.stringify(w.etymology) : null,
        $definitions: w.definitions ? JSON.stringify(w.definitions) : null,
        $inflection: w.inflection ? JSON.stringify(w.inflection) : null,
        $date: null,
      });
    }
  })();

  console.log(`${dictionary}: inserted ${words.length} words`);
}

db.run("INSERT INTO words_fts(rowid, word) SELECT rowid, word FROM words");
const summary = redate(db); // shuffle each dictionary, one date per day from today
await writeReadme(summary);
db.run("VACUUM"); // reclaim the space of the dropped tables

await mongo?.close();
db.close();

console.log(`Built ${dbPath}`);
