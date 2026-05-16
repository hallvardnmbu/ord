import { MongoClient } from "mongodb";
import { Database } from "bun:sqlite";
import { join } from "path";

const MONGO_URI =
  `mongodb+srv://${process.env.MONGO_USR.trim()}:${process.env.MONGO_PWD.trim()}` +
  `@ord.c8trc.mongodb.net/?retryWrites=true&w=majority&appName=ord`;

function shuffle(array) {
  for (let i = array.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
}

function formatDate(date) {
  const d = date.getDate().toString().padStart(2, "0");
  const m = (date.getMonth() + 1).toString().padStart(2, "0");
  return `${d}-${m}-${date.getFullYear()}`;
}

function assignDates(words) {
  shuffle(words);
  return words.map((word, i) => {
    const date = new Date();
    date.setDate(date.getDate() + i);
    return { ...word, date: formatDate(date) };
  });
}

const mongo = new MongoClient(MONGO_URI);
await mongo.connect();
const mongoDb = mongo.db("ord");

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
  const docs = await mongoDb
    .collection(dictionary)
    .find({}, { projection: { _id: 0, date: 0, past: 0 } })
    .toArray();

  const words = assignDates(docs);

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
        $date: w.date,
      });
    }
  })();

  console.log(`${dictionary}: inserted ${words.length} words`);
}

db.run("INSERT INTO words_fts(rowid, word) SELECT rowid, word FROM words");

await mongo.close();
db.close();

console.log(`Built ${dbPath}`);
