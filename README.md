# dagsord.no

Kodebasen bak [dagsord.no](https://dagsord.no).

## Data

Selve ordene er hentet fra [Nasjonalbibliotekets språkbank](https://www.nb.no/sprakbanken/ressurskatalog/).

Tilhørende data er hentet fra [ordbokene.no](https://ordbokene.no) sitt [API](https://v1.ordbokene.no/api).

## Kjør lokalt

### Hent data

1. Sett opp MongoDB.
2. For plug-and-play, lag en database kalt `ord` og to collections derunder kalt `bm` og `nn`.
3. Følg stegene i [dictionary/README](dictionary/README.txt).

### Åpne nettsiden

1. Installer ønsket runtime (à la [Node.js](https://nodejs.org/)).
2. Installer nødvendige pakker (à la `npm install`).
3. Kjør `server.js` (à la `node server.js`).
