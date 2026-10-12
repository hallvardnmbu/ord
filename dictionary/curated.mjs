// Load the curated word list (dictionary/curated/{bm,nn}.json) into the `bm` and `nn` collections.
//
//     node dictionary/curated.mjs            # dry run: show what would change
//     node dictionary/curated.mjs --replace  # back up each collection, then replace it
//
// The old collection is renamed to `<dictionary>_backup_<yyyymmdd>`, so nothing is lost.
// Afterwards run `dating.mjs` to give every word a date (or build ord.db directly with
// `bun build.mjs`). `bun build.mjs --curated` builds ord.db from the JSON without MongoDB.

import { MongoClient } from "mongodb";
import dotenv from "dotenv";
import fs from "fs";

dotenv.config();

const REPLACE = process.argv.includes("--replace");
const stamp = new Date().toISOString().slice(0, 10).replaceAll("-", "");

const client = new MongoClient(
  `mongodb+srv://${process.env.MONGO_USR.trim()}:${process.env.MONGO_PWD.trim()}` +
    "@ord.c8trc.mongodb.net/?retryWrites=true&w=majority&appName=ord",
);

try {
  await client.connect();
  const database = client.db("ord");

  for (const dictionary of ["bm", "nn"]) {
    const documents = JSON.parse(
      fs.readFileSync(new URL(`./curated/${dictionary}.json`, import.meta.url), "utf8"),
    );
    const existing = await database.collection(dictionary).countDocuments();
    console.log(`${dictionary}: ${existing} documents now, ${documents.length} curated.`);
    if (!REPLACE) continue;

    if (existing > 0) {
      const backup = `${dictionary}_backup_${stamp}`;
      await database.collection(dictionary).rename(backup);
      console.log(`${dictionary}: old collection kept as ${backup}.`);
    }
    // `past: false` marks the words as unused, which is what dating.mjs looks for.
    await database.collection(dictionary).insertMany(documents.map((d) => ({ ...d, past: false })));
    await database.collection(dictionary).createIndex({ word: 1 });
    console.log(`${dictionary}: inserted ${documents.length} documents.`);
  }

  if (!REPLACE) console.log("Dry run. Pass --replace to write.");
} catch (error) {
  console.log(`Error: ${error}`);
} finally {
  await client.close();
}
