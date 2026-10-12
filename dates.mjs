// Shuffle each dictionary in ord.db and give every word a date, one per day from today.
//
//     bun dates.mjs
//
// Rerun once the last date has passed (the site keeps looping through the old order until then).
// It rewrites the "Ordliste" dates in README.md. build.mjs uses the same function.

import { Database } from "bun:sqlite";
import { join } from "path";

function shuffle(array) {
  for (let i = array.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
}

export function formatDate(date) {
  const d = date.getDate().toString().padStart(2, "0");
  const m = (date.getMonth() + 1).toString().padStart(2, "0");
  return `${d}-${m}-${date.getFullYear()}`;
}

// Returns { bm: { count, first, last }, nn: ... }.
export function redate(db, start = new Date()) {
  const update = db.prepare("UPDATE words SET date = ? WHERE rowid = ?");
  const summary = {};
  for (const dictionary of ["bm", "nn"]) {
    const rowids = shuffle(
      db.query("SELECT rowid FROM words WHERE dictionary = ?").all(dictionary).map((r) => r.rowid),
    );
    const dates = rowids.map((_, i) => {
      const date = new Date(start);
      date.setDate(date.getDate() + i);
      return formatDate(date);
    });
    db.transaction(() => rowids.forEach((rowid, i) => update.run(dates[i], rowid)))();
    summary[dictionary] = { count: rowids.length, first: dates[0], last: dates.at(-1) };
  }
  return summary;
}

export async function writeReadme(summary) {
  const path = join(import.meta.dir, "README.md");
  const names = { bm: "Bokmål", nn: "Nynorsk" };
  const block = [
    "<!-- dates:start -->",
    "| Ordbok | Ord | Første dato | Siste dato |",
    "|---|---:|---|---|",
    ...Object.entries(summary).map(
      ([d, s]) => `| ${names[d]} | ${s.count} | ${s.first} | ${s.last} |`,
    ),
    "<!-- dates:end -->",
  ].join("\n");
  const readme = await Bun.file(path).text();
  await Bun.write(path, readme.replace(/<!-- dates:start -->[\s\S]*<!-- dates:end -->/, block));
}

if (import.meta.main) {
  const db = new Database(join(import.meta.dir, "ord.db"));
  const summary = redate(db);
  db.close();
  await writeReadme(summary);
  for (const [d, s] of Object.entries(summary)) console.log(`${d}: ${s.count} words, ${s.first} – ${s.last}`);
}
