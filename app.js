import { Database } from "bun:sqlite";
import { join } from "path";

const db = new Database(join(import.meta.dir, "ord.db"), { readonly: true });

const dictCount = {};
for (const dict of ["bm", "nn"]) {
  dictCount[dict] = db.query("SELECT COUNT(*) as c FROM words WHERE dictionary = ?").get(dict).c;
}

function parseWord(row) {
  return {
    ...row,
    etymology: row.etymology ? JSON.parse(row.etymology) : [],
    definitions: row.definitions ? JSON.parse(row.definitions) : {},
    inflection: row.inflection ? JSON.parse(row.inflection) : [],
  };
}

function today() {
  const date = new Date();
  const d = date.getDate().toString().padStart(2, "0");
  const m = (date.getMonth() + 1).toString().padStart(2, "0");
  return `${d}-${m}-${date.getFullYear()}`;
}

function weekNumber(date) {
  const target = new Date(date.valueOf());
  const dayNum = date.getDay() || 7;
  target.setDate(target.getDate() + 4 - dayNum);
  const yearStart = new Date(target.getFullYear(), 0, 1);
  return Math.ceil(((target - yearStart) / 86400000 + 1) / 7);
}

function search(word, dicts) {
  const words = [];
  for (const dict of dicts) {
    let row = db.query("SELECT * FROM words WHERE word = ? AND dictionary = ? LIMIT 1").get(word, dict);
    if (!row) {
      row = db
        .query(
          `
        SELECT w.* FROM words w
        JOIN words_fts f ON f.rowid = w.rowid
        WHERE f.word MATCH ? AND w.dictionary = ?
        LIMIT 1
      `,
        )
        .get(`${word}*`, dict);
    }
    if (!row) {
      row = db.query("SELECT * FROM words WHERE word LIKE ? AND dictionary = ? LIMIT 1").get(`%${word}%`, dict);
    }
    if (row) words.push(parseWord(row));
  }
  return words;
}

function renderDefinitions(data, indent = 1, dict = "bm") {
  const nn = { eksempel: "døme", forklaring: "tyding og bruk", underartikkel: "faste uttrykk" };
  const t = (key) => (dict === "nn" ? (nn[key] ?? key) : key);

  if (Array.isArray(data)) {
    return data
      .map((item) =>
        typeof item === "object" && item !== null
          ? renderDefinitions(item, indent, dict)
          : `<div class="definition" style="--indent: ${indent};">${item}</div>`,
      )
      .join("");
  }
  if (typeof data === "object" && data !== null) {
    let result = "";
    for (const [key, value] of Object.entries(data)) {
      indent += 1;
      result += `<div class="define" style="--indent: ${indent};"><b>${t(key)}</b></div>`;
      if (key === "underartikkel") {
        for (const el of value) {
          result += `<div class="definition" style="--indent: ${indent};">
            <a href="https://ordbokene.no/nob/${dict}/${el.id}" target="_blank">${el.word}</a>
          </div>`;
          result += renderDefinitions(el.definitions, indent, dict);
        }
      } else {
        result += renderDefinitions(value, indent, dict);
      }
    }
    return result;
  }
  return `<div class="definition" style="--indent: ${indent};">${data}</div>`;
}

function renderWord(word) {
  if (!word) return `<section><div class="message">Noe gikk galt.</div></section>`;

  const nn = { eksempel: "døme", forklaring: "tyding og bruk", underartikkel: "faste uttrykk" };
  const t = (key) => (word.dictionary === "nn" ? (nn[key] ?? key) : key);

  let html = `
    <section>
      <div class="top">
        <div class="words">
          <div class="word">${word.word}</div>
          ${word.pronunciation?.length > 0 ? `<div class="pronunciation">[${word.pronunciation}]</div>` : ""}
        </div>
        <div class="group">${word.wordgroup?.includes(",") ? word.wordgroup.split(",")[0] : word.wordgroup}</div>
      </div>`;

  for (const etym of word.etymology ?? []) {
    html += `<div class="etymology">${etym}</div>`;
  }
  html += `<hr />`;

  for (const [type, values] of Object.entries(word.definitions ?? {})) {
    html += `<div class="define"><b>${t(type)}</b></div>`;
    if (type === "underartikkel") {
      for (const el of values) {
        html += `<div class="define" style="--indent: 2;">
          <a href="https://ordbokene.no/nob/${word.dictionary}/${el.id}" target="_blank">${el.word}</a>
        </div>`;
        html += renderDefinitions(el.definitions, 1, word.dictionary);
      }
    } else {
      html += renderDefinitions(values, 1, word.dictionary);
    }
  }

  if (word.inflection?.[0]?.length > 1) {
    const maps = {
      bm: {
        Inf: "infinitiv",
        Pres: "presens",
        Past: "preteritum",
        Imp: "imperativ",
        "<PerfPart>": "perfektum partisipp",
        PerfPart: "perfektum partisipp",
        "Perf Part": "perfektum partisipp",
        "<PresPart>": "presens partisipp",
        PresPart: "presens partisipp",
        "Pres Part": "presens partisipp",
        Sing: "entall",
        Pos: "",
        Ind: "",
        Adj: "",
        "<SPass>": "",
        Cmp: "komparativ",
        Sup: "superlativ",
        Pass: "passiv",
        Plur: "flertall",
        Masc: "hankjønn",
        Fem: "hunkjønn",
        "Masc/Fem": "hankjønn/hunkjønn",
        Neut: "intetkjønn",
        Neuter: "intetkjønn",
        Def: "bestemt",
        Indef: "ubestemt",
      },
      nn: {
        Inf: "infinitiv",
        Pres: "presens",
        Past: "preteritum",
        Imp: "imperativ",
        "<PerfPart>": "perfektum partisipp",
        PerfPart: "perfektum partisipp",
        "Perf Part": "perfektum partisipp",
        "<PresPart>": "presens partisipp",
        PresPart: "presens partisipp",
        "Pres Part": "presens partisipp",
        Sing: "eintal",
        Pos: "",
        Ind: "",
        Adj: "",
        "<SPass>": "",
        Cmp: "komparativ",
        Sup: "superlativ",
        Pass: "passiv",
        Plur: "fleirtal",
        Masc: "hankjønn",
        Fem: "hokjønn",
        "Masc/Fem": "hankjønn/hokjønn",
        Neut: "inkjekjønn",
        Neuter: "inkjekjønn",
        Def: "bunden",
        Indef: "ubunden",
      },
    };
    const processTag = (tag) =>
      tag
        .split(" ")
        .reduce((acc, key) => acc.replace(key, maps[word.dictionary][key] ?? key), tag)
        .trim();

    html += `
      <button class="toggleInflection" id="toggleInflection-${word.dictionary}" onclick="toggleInflection('${word.dictionary}')">bøying</button>
      <script>
      function toggleInflection(id) {
        const btn = document.getElementById('toggleInflection-' + id);
        const tbl = document.getElementById('inflection-' + id);
        btn.textContent = btn.textContent.trim() === 'bøying' ? 'skjul' : 'bøying';
        tbl.style.display = tbl.style.display === 'table' ? 'none' : 'table';
      }
      </script>
      <table class="inflection" style="display: none;" id="inflection-${word.dictionary}">
        <tbody>
          ${word.inflection[0]
            .map((inflect) => {
              const tagStr = inflect.tags?.join(" ") ?? "";
              if (inflect.word_form && !tagStr.includes(" Pass")) {
                return `<tr>
                <td class="word-cell">${inflect.word_form}</td>
                <td class="form-cell">${processTag(tagStr)}</td>
              </tr>`;
              }
              return "";
            })
            .join("")}
        </tbody>
      </table>`;
  }

  return html + `</section>`;
}

function renderPage({ words, dictionary, date, week, day, error }) {
  const sel = (v) => (dictionary === v ? "selected" : "");
  const dictVal = dictionary || "bm";

  return `<!doctype html>
<html lang="nb">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>dagsord</title>
    <link rel="stylesheet" href="/style.css" />
    <link rel="icon" type="image/png" href="/dagsord.png">
    <link rel="apple-touch-icon" href="/dagsord.png">
    <meta property="og:image" content="/dagsord.png">
    <meta property="og:title" content="dagsord.no" />
    <meta property="og:description" content="Dagens ord." />
    <script>
      (function() {
        const url = new URL(window.location.href);
        if (!url.searchParams.has('dictionary')) {
          url.searchParams.set('dictionary', localStorage.getItem('dictionary') || 'bm,nn');
          window.location.replace(url.toString());
        }
      })();
    </script>
  </head>
  <body>
    <header>
      ${
        day && week && date
          ? `<div>${day.charAt(0).toUpperCase() + day.slice(1)}</div><div>•</div><div>Uke ${week}</div><div>•</div><div>${date}</div>`
          : day
            ? `<div>Søkte etter <b>${day}</b>.</div>`
            : `<div></div>`
      }
    </header>

    <main id="words">
      ${
        words?.length > 0
          ? words
              .map((item) => {
                const dictName = { bm: "bokmåls", nn: "nynorsk" }[item.dictionary];
                const heading =
                  day && week && date
                    ? `Dagens ${dictName}ord: <b><a href="https://ordbokene.no/nob/${item.dictionary}/${item.id}" target="_blank">${item.word}</a></b>.`
                    : day
                      ? `Fant ord: <b><a href="https://ordbokene.no/nob/${item.dictionary}/${item.id}" target="_blank">${item.word}</a></b> i ${dictName}ordboka.`
                      : `Tilfeldig ord: <b><a href="https://ordbokene.no/nob/${item.dictionary}/${item.id}" target="_blank">${item.word}</a></b> i ${dictName}ordboka.`;
                return `<div class="heading">${heading}</div>${renderWord(item)}`;
              })
              .join("")
          : error
            ? `<section><div class="message">Noe gikk galt: ${error}</div></section>`
            : `<section><div class="message">Fant ikke dette ordet i databasen.</div></section>`
      }
    </main>

    <div id="wide" class="find">
      <form action="/" method="get"><input type="hidden" name="dictionary" value="${dictVal}"><button type="submit">dagens</button></form>
      <form><div class="select"><select name="dictionary">
        <option value="bm" ${sel("bm")}>bokmål</option>
        <option value="nn" ${sel("nn")}>nynorsk</option>
        <option value="bm,nn" ${sel("bm,nn")}>begge</option>
      </select></div></form>
      <form action="/search" method="get"><input type="hidden" name="dictionary" value="${dictVal}"><input type="text" name="word" placeholder="ord" /><button type="submit">søk</button></form>
      <form action="/random" method="get"><input type="hidden" name="dictionary" value="${dictVal}"><button type="submit">tilfeldig</button></form>
    </div>
    <div id="long" class="find">
      <div>
        <form action="/" method="get"><input type="hidden" name="dictionary" value="${dictVal}"><button type="submit">dagens</button></form>
        <form><div class="select"><select name="dictionary">
          <option value="bm" ${sel("bm")}>bokmål</option>
          <option value="nn" ${sel("nn")}>nynorsk</option>
          <option value="bm,nn" ${sel("bm,nn")}>begge</option>
        </select></div></form>
      </div>
      <div>
        <form action="/random" method="get"><input type="hidden" name="dictionary" value="${dictVal}"><button type="submit">tilfeldig</button></form>
        <form action="/search" method="get"><input type="hidden" name="dictionary" value="${dictVal}"><input type="text" name="word" placeholder="ord" /><button type="submit">søk</button></form>
      </div>
    </div>

    <footer>
      <div>av <a href="https://dilettant.no" target="_blank">hallvard</a></div>
      <div id="theme">mørkt</div>
      <a href="https://github.com/hallvardnmbu/ord" target="_blank">kildekode</a>
    </footer>

    <script>
      document.querySelectorAll('select[name="dictionary"]').forEach(s => {
        s.addEventListener('change', function() {
          localStorage.setItem('dictionary', this.value);
          window.location.href = window.location.pathname + '?dictionary=' + this.value;
        });
      });
      const themeToggle = document.getElementById('theme');
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
      function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme === 'mørkt' ? 'dark' : 'light');
        sessionStorage.setItem('theme', theme);
        themeToggle.innerHTML = theme === 'mørkt' ? 'lyst' : 'mørkt';
      }
      const savedTheme = sessionStorage.getItem('theme');
      if (savedTheme) setTheme(savedTheme);
      else if (prefersDark.matches) setTheme('mørkt');
      themeToggle.addEventListener('click', () => {
        setTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'lyst' : 'mørkt');
      });
      prefersDark.addEventListener('change', (e) => {
        if (!sessionStorage.getItem('theme')) setTheme(e.matches ? 'mørkt' : 'lyst');
      });
    </script>
  </body>
</html>`;
}

const html = { headers: { "Content-Type": "text/html" } };

export default function ord(request) {
  const url = new URL(request.url);
  const { pathname, searchParams } = url;
  const dictionary = searchParams.get("dictionary") || "bm,nn";
  const dicts = dictionary.split(",");

  if (pathname === "/") {
    const date = new Date();
    const t = today();
    const week = weekNumber(date);
    const day = date.toLocaleDateString("no-NB", { weekday: "long" }).toLowerCase();
    try {
      const words = dicts.flatMap((dict) => {
        const row = db.query("SELECT * FROM words WHERE date = ? AND dictionary = ?").get(t, dict);
        return row ? [parseWord(row)] : [];
      });
      return new Response(renderPage({ words, dictionary, date: t, week, day, error: null }), html);
    } catch (e) {
      return new Response(renderPage({ words: [], dictionary, date: t, week, day, error: e.message }), html);
    }
  }

  if (pathname === "/search") {
    const word = searchParams.get("word")?.trim().toLowerCase();
    if (!word) return new Response(null, { status: 301, headers: { Location: "/" } });
    try {
      const words = search(word, dicts);
      return new Response(renderPage({ words, dictionary, date: null, week: null, day: word, error: null }), html);
    } catch (e) {
      return new Response(
        renderPage({ words: [], dictionary, date: null, week: null, day: word, error: e.message }),
        html,
      );
    }
  }

  if (pathname === "/random") {
    try {
      const words = dicts.flatMap((dict) => {
        const total = dictCount[dict] ?? 0;
        if (!total) return [];
        const offset = Math.floor(Math.random() * total);
        const row = db.query("SELECT * FROM words WHERE dictionary = ? LIMIT 1 OFFSET ?").get(dict, offset);
        return row ? [parseWord(row)] : [];
      });
      return new Response(renderPage({ words, dictionary, date: null, week: null, day: null, error: null }), html);
    } catch (e) {
      return new Response(
        renderPage({ words: [], dictionary, date: null, week: null, day: null, error: e.message }),
        html,
      );
    }
  }

  const file = Bun.file(join(import.meta.dir, "public", pathname));
  return file.exists().then((exists) => (exists ? new Response(file) : new Response("Not found", { status: 404 })));
}

if (import.meta.main) {
  const port = parseInt(process.env.PORT ?? "3000");
  Bun.serve({ fetch: ord, port });
  console.log(`Listening on http://localhost:${port}`);
}
