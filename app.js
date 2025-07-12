import { Elysia } from "elysia";
import { staticPlugin } from "@elysiajs/static";
import { html } from "@elysiajs/html";
import { MongoClient, ServerApiVersion } from "mongodb";
import { dirname, join } from 'path';

let __dirname = dirname(new URL(import.meta.url).pathname);
__dirname = __dirname.startsWith('/') && __dirname.includes(':') 
  ? __dirname.replace(/^\/([A-Z]):/, '$1:\\').replace(/\//g, '\\')
  : __dirname;


const client = await MongoClient.connect(
  `mongodb+srv://${process.env.MONGO_USR}:${process.env.MONGO_PWD}@ord.c8trc.mongodb.net/?retryWrites=true&w=majority&appName=ord`,
  {
    serverApi: {
      version: ServerApiVersion.v1,
      strict: false,
      deprecationErrors: true,
    },
  },
);
const dbWord = client.db("ord");
let collectionWord = {
  bm: dbWord.collection("bm"),
  nn: dbWord.collection("nn"),
};

// Helper function to render the page template
function renderPage(data) {
  const { words, dictionary, date, week, day, error } = data;
  
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
            // Immediately redirect with dictionary preference before any rendering.
            (function() {
              const currentUrl = new URL(window.location.href);
              // Only add dictionary if it's not already in the URL.
              if (!currentUrl.searchParams.has('dictionary')) {
                const savedDictionary = localStorage.getItem('dictionary') || 'bm,nn';
                currentUrl.searchParams.set('dictionary', savedDictionary);
                window.location.replace(currentUrl.toString());
                }
            })();
        </script>
    </head>
    <body>
        <header>
          ${day && week && date ? 
            `<div>${day.charAt(0).toUpperCase() + day.slice(1)}</div>
            <div>•</div>
            <div>Uke ${week}</div>
            <div>•</div>
            <div>${date}</div>` : 
            day ? 
            `<div>Søkte etter <b>${day}</b>.</div>` : 
            `<div></div>`
          }
        </header>

        <main id="words">
            ${words && words.length > 0 ? 
              words.map(item => {
                const dictName = {bm: "bokmåls", nn: "nynorsk"}[item.dictionary];
                let heading = "";
                
                if (day && week && date) {
                  heading = `Dagens ${dictName}ord: <b><a href="https://ordbokene.no/nob/${item.dictionary}/${item.id}" target="_blank">${item.word}</a></b>.`;
                } else if (day) {
                  heading = `Fant ord: <b><a href="https://ordbokene.no/nob/${item.dictionary}/${item.id}" target="_blank">${item.word}</a></b> i ${dictName}ordboka.`;
                } else {
                  heading = `Tilfeldig ord: <b><a href="https://ordbokene.no/nob/${item.dictionary}/${item.id}" target="_blank">${item.word}</a></b> i ${dictName}ordboka.`;
                }
                
                return `<div class="heading">${heading}</div>
                ${renderWord(item)}`;
              }).join('') : 
              error ? 
              `<section><div class="message">Noe gikk galt: ${error}</div></section>` : 
              `<section><div class="message">Fant ikke dette ordet i databasen.</div></section>`
            }
        </main>

        <div id="wide" class="find">
          <form action="/" method="get">
            <input type="hidden" name="dictionary" value="${dictionary || 'bm'}">
            <button type="submit">dagens</button>
          </form>

          <form>
            <div class="select">
              <select name="dictionary">
                <option value="bm" ${dictionary === 'bm' ? 'selected' : ''}>bokmål</option>
                <option value="nn" ${dictionary === 'nn' ? 'selected' : ''}>nynorsk</option>
                <option value="bm,nn" ${dictionary === 'bm,nn' ? 'selected' : ''}>begge</option>
              </select>
            </div>
          </form>

          <form action="/search" method="get">
            <input type="hidden" name="dictionary" value="${dictionary || 'bm'}">
            <input type="text" name="word" placeholder="ord" />
            <button type="submit">søk</button>
          </form>

          <form action="/random" method="get">
            <input type="hidden" name="dictionary" value="${dictionary || 'bm'}">
            <button type="submit">tilfeldig</button>
          </form>
        </div>
        <div id="long" class="find">
          <div>
            <form action="/" method="get">
              <input type="hidden" name="dictionary" value="${dictionary || 'bm'}">
              <button type="submit">dagens</button>
            </form>

            <form>
              <div class="select">
                <select name="dictionary">
                  <option value="bm" ${dictionary === 'bm' ? 'selected' : ''}>bokmål</option>
                  <option value="nn" ${dictionary === 'nn' ? 'selected' : ''}>nynorsk</option>
                  <option value="bm,nn" ${dictionary === 'bm,nn' ? 'selected' : ''}>begge</option>
                </select>
              </div>
            </form>
          </div>

          <div>
            <form action="/random" method="get">
              <input type="hidden" name="dictionary" value="${dictionary || 'bm'}">
              <button type="submit">tilfeldig</button>
            </form>

            <form action="/search" method="get">
              <input type="hidden" name="dictionary" value="${dictionary || 'bm'}">
              <input type="text" name="word" placeholder="ord" />
              <button type="submit">søk</button>
            </form>
          </div>
        </div>

        <footer>
          <div>av <a href="https://dilettant.no" target="_blank">hallvard</a></div>
          <div id="theme">mørkt</div>
          <a href="https://github.com/hallvardnmbu/ord" target="_blank">kildekode</a>
        </footer>

        <script>
          // Function to update all dictionary inputs and selects
          function updateDictionaryElements(dictionary) {
            document.querySelectorAll('select[name="dictionary"]').forEach(select => {
              select.value = dictionary;
            });
            document.querySelectorAll('input[name="dictionary"]').forEach(input => {
              input.value = dictionary;
            });
          }

          // Update select forms
          document.querySelectorAll('select[name="dictionary"]').forEach(select => {
            select.addEventListener('change', function() {
              const dictionary = this.value;
              localStorage.setItem('dictionary', dictionary);
              window.location.href = window.location.pathname + '?dictionary=' + dictionary;
            });
          });
        </script>
        <script>
        // Theme toggle functionality
        const themeToggle = document.getElementById('theme');
        const prefersDarkScheme = window.matchMedia('(prefers-color-scheme: dark)');

        // Function to set theme
        function setTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme === 'mørkt' ? 'dark' : 'light');
            sessionStorage.setItem('theme', theme);
            themeToggle.innerHTML = theme === 'mørkt' ? 'lyst' : 'mørkt';
        }

        // Check for saved theme preference or system preference
        const savedTheme = sessionStorage.getItem('theme');
        if (savedTheme) {
            setTheme(savedTheme);
        } else if (prefersDarkScheme.matches) {
            setTheme('mørkt');
        }

        // Toggle theme when button is clicked
        themeToggle.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            setTheme(currentTheme === 'dark' ? 'lyst' : 'mørkt');
        });

        // Listen for system theme changes
        prefersDarkScheme.addEventListener('change', (e) => {
            if (!sessionStorage.getItem('theme')) {
                setTheme(e.matches ? 'mørkt' : 'lyst');
            }
        });
        </script>
    </body>
</html>`;
}

// Helper function to render word details
function renderWord(word) {
  if (!word) {
    return `<section><div class="message">Noe gikk galt.</div></section>`;
  }

  const keyMappings = {
    'nn': {
      'eksempel': 'døme',
      'forklaring': 'tyding og bruk',
      'underartikkel': 'faste uttrykk'
    }
  };

  function translateKey(key, dictionaryType) {
    if (dictionaryType && keyMappings[dictionaryType] && keyMappings[dictionaryType][key]) {
      return keyMappings[dictionaryType][key];
    }
    return key;
  }

  function renderDefinitions(data, indent = 1, dictionaryType = "bm") {
    if (Array.isArray(data)) {
      return data.map(item => {
        if (typeof item === 'object' && item !== null) {
          return renderDefinitions(item, indent, dictionaryType);
        } else {
          return `<div class="definition" style="--indent: ${indent};">${item}</div>`;
        }
      }).join('');
    } else if (typeof data === 'object' && data !== null) {
      let result = '';
      for (const [key, value] of Object.entries(data)) {
        indent += 1;
        const translatedKey = translateKey(key, dictionaryType);
        result += `<div class="define" style="--indent: ${indent};"><b>${translatedKey}</b></div>`;
        
        if (key === "underartikkel") {
          for (const element of value) {
            result += `<div class="definition" style="--indent: ${indent};">
              <a href="https://ordbokene.no/nob/${dictionaryType}/${element.id}" target="_blank">${element.word}</a>
            </div>`;
            result += renderDefinitions(element.definitions, indent, dictionaryType);
          }
        } else if (key === "eksempel") {
          result += renderDefinitions(value, indent, dictionaryType);
        } else {
          result += renderDefinitions(value, indent, dictionaryType);
        }
      }
      return result;
    } else {
      return `<div class="definition" style="--indent: ${indent};">${data}</div>`;
    }
  }

  let wordHtml = `
    <section>
      <div class="top">
        <div class="words">
          <div class="word">${word.word}</div>
          ${word.pronunciation && word.pronunciation.length > 0 ? 
            `<div class="pronunciation">[${word.pronunciation}]</div>` : ''
          }
        </div>
        <div class="group">${word.wordgroup.includes(',') ? word.wordgroup.split(",")[0] : word.wordgroup}</div>
      </div>`;

  if (word.etymology) {
    word.etymology.forEach(etymology => {
      wordHtml += `<div class="etymology">${etymology}</div>`;
    });
  }

  wordHtml += `<hr />`;

  if (word.definitions) {
    for (const [type, values] of Object.entries(word.definitions)) {
      const translatedType = translateKey(type, word.dictionary);
      wordHtml += `<div class="define"><b>${translatedType}</b></div>`;
      
      if (type === "underartikkel") {
        for (const element of values) {
          wordHtml += `<div class="define" style="--indent: 2;">
            <a href="https://ordbokene.no/nob/${word.dictionary}/${element.id}" target="_blank">${element.word}</a>
          </div>`;
          wordHtml += renderDefinitions(element.definitions, 1, word.dictionary);
        }
      } else {
        wordHtml += renderDefinitions(values, 1, word.dictionary);
      }
    }
  }

  // Add inflection table if available
  if (word.inflection && word.inflection[0] && word.inflection[0].length > 1) {
    const inflectionMappings = {
      'bm': {
        'Inf': 'infinitiv',
        'Pres': 'presens',
        'Past': 'preteritum',
        'Imp': 'imperativ',
        '<PerfPart>': 'perfektum partisipp',
        'PerfPart': 'perfektum partisipp',
        'Perf Part': 'perfektum partisipp',
        '<PresPart>': 'presens partisipp',
        'PresPart': 'presens partisipp',
        'Pres Part': 'presens partisipp',
        'Sing': 'entall',
        'Pos': '',
        'Ind': '',
        'Adj': '',
        '<SPass>': '',
        'Cmp': 'komparativ',
        'Sup': 'superlativ',
        'Pass': 'passiv',
        'Plur': 'flertall',
        'Masc': 'hankjønn',
        'Fem': 'hunkjønn',
        'Masc/Fem': 'hankjønn/hunkjønn',
        'Neut': 'intetkjønn',
        'Neuter': 'intetkjønn',
        'Def': 'bestemt',
        'Indef': 'ubestemt'
      },
      'nn': {
        'Inf': 'infinitiv',
        'Pres': 'presens',
        'Past': 'preteritum',
        'Imp': 'imperativ',
        '<PerfPart>': 'perfektum partisipp',
        'PerfPart': 'perfektum partisipp',
        'Perf Part': 'perfektum partisipp',
        '<PresPart>': 'presens partisipp',
        'PresPart': 'presens partisipp',
        'Pres Part': 'presens partisipp',
        'Sing': 'eintal',
        'Pos': '',
        'Ind': '',
        'Adj': '',
        '<SPass>': '',
        'Cmp': 'komparativ',
        'Sup': 'superlativ',
        'Pass': 'passiv',
        'Plur': 'fleirtal',
        'Masc': 'hankjønn',
        'Fem': 'hokjønn',
        'Masc/Fem': 'hankjønn/hokjønn',
        'Neut': 'inkjekjønn',
        'Neuter': 'inkjekjønn',
        'Def': 'bunden',
        'Indef': 'ubunden'
      }
    };

    function processInflection(tag, dictionary) {
      let updatedTag = tag;
      const tags = tag.split(" ");
      for (const key of tags) {
        if (inflectionMappings[dictionary].hasOwnProperty(key)) {
          updatedTag = updatedTag.replace(key, inflectionMappings[dictionary][key]);
        }
      }
      return updatedTag.trim();
    }

    wordHtml += `
      <button class="toggleInflection" id="toggleInflection-${word.dictionary}" onclick="toggleInflection('${word.dictionary}')">
        bøying
      </button>

      <script>
      function toggleInflection(dictionaryId) {
          const button = document.getElementById(\`toggleInflection-\${dictionaryId}\`);
          const inflection = document.getElementById(\`inflection-\${dictionaryId}\`);

          // Toggle button text
          button.textContent = button.textContent.trim() === 'bøying'
              ? 'skjul'
              : 'bøying';

          // Toggle inflection table visibility
          inflection.style.display = inflection.style.display === 'table' ? 'none' : 'table';
      }
      </script>

      <table class="inflection" style="display: none;" id="inflection-${word.dictionary}">
        <tbody>
          ${word.inflection[0].map(inflect => {
            if (inflect.word_form && !(inflect.tags ? inflect.tags.join(' ') : '').includes(' Pass')) {
              return `<tr>
                <td class="word-cell">${inflect.word_form}</td>
                <td class="form-cell">${processInflection(inflect.tags ? inflect.tags.join(' ') : '', word.dictionary)}</td>
              </tr>`;
            }
            return '';
          }).join('')}
        </tbody>
      </table>`;
  }

  wordHtml += `</section>`;
  return wordHtml;
}

const ordApp = new Elysia()
  .use(staticPlugin({
    assets: join(__dirname, "public"),
    prefix: "/"
  }))
  .use(html())
  .get("/", async ({ query }) => {
    const dictionary = query.dictionary || "bm,nn";
    const date = new Date();
    
    const getWeek = (date) => {
      const target = new Date(date.valueOf());
      const dayNum = date.getDay() || 7;
      target.setDate(target.getDate() + 4 - dayNum);
      const yearStart = new Date(target.getFullYear(), 0, 1);
      const weekNo = Math.ceil(((target - yearStart) / 86400000 + 1) / 7);
      return weekNo;
    };
    
    const week = getWeek(date);
    const day = date.toLocaleDateString("no-NB", { weekday: "long" }).toLowerCase();
    const today = date
      .toLocaleDateString("no-NB", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      })
      .split(".")
      .join("-");

    try {
      const words = [];
      for (const dict of dictionary.split(",")) {
        words.push(...(await collectionWord[dict].find({ date: today }).toArray()));
      }

      return renderPage({
        words: words,
        dictionary: dictionary,
        date: today,
        week: week,
        day: day,
        error: null,
      });
    } catch (error) {
      return renderPage({
        words: [],
        dictionary: dictionary,
        date: today,
        week: week,
        day: day,
        error: error.message,
      });
    }
  })
  .get("/search", async ({ query }) => {
    if (!query.word || typeof query.word !== "string" || !query.word.trim()) {
      return new Response(null, { status: 301, headers: { Location: "/" } });
    }
    
    const word = query.word.trim().toLowerCase();
    const dictionary = query.dictionary || "bm,nn";

    try {
      const words = [];
      for (const dict of dictionary.split(",")) {
        words.push(
          ...(await collectionWord[dict]
            .aggregate([
              {
                $search: {
                  index: "word",
                  compound: {
                    should: [
                      {
                        text: {
                          query: word,
                          path: "word",
                          score: { boost: { value: 10 } },
                        },
                      },
                      {
                        text: {
                          query: word,
                          path: "word",
                          fuzzy: {
                            maxEdits: 2,
                            prefixLength: 1,
                            maxExpansions: 1,
                          },
                        },
                      },
                    ],
                  },
                },
              },
              { $limit: 1 },
            ])
            .toArray()),
        );
      }

      return renderPage({
        words: words,
        dictionary: dictionary,
        date: null,
        week: null,
        day: word,
        error: null,
      });
    } catch (error) {
      return renderPage({
        words: [],
        dictionary: dictionary,
        date: null,
        week: null,
        day: word,
        error: error.message,
      });
    }
  })
  .get("/random", async ({ query }) => {
    const dictionary = query.dictionary || "bm,nn";

    try {
      const words = [];
      for (const dict of dictionary.split(",")) {
        words.push(...(await collectionWord[dict].aggregate([{ $sample: { size: 1 } }]).toArray()));
      }

      return renderPage({
        words: words,
        dictionary: dictionary,
        date: null,
        week: null,
        day: null,
        error: null,
      });
    } catch (error) {
      return renderPage({
        words: [],
        dictionary: dictionary,
        date: null,
        week: null,
        day: null,
        error: error.message,
      });
    }
  });

export default ordApp;

if (import.meta.main) {
    ordApp.listen(3000);
    console.log(`http://${ordApp.server?.hostname}:${ordApp.server?.port}`);
}