# dagsord.no

Kodebasen bak [dagsord.no](https://dagsord.no).

## Data

Selve ordene er hentet fra [Nasjonalbibliotekets språkbank](https://www.nb.no/sprakbanken/ressurskatalog/).

Tilhørende data er hentet fra [ordbokene.no](https://ordbokene.no) sitt [API](https://v1.ordbokene.no/api).

## Ordliste

Ordene er håndplukket: 1083 sjeldne, men brukbare ord (se [dictionary/curation](dictionary/curation/README.md)).
Hver ordbok er stokket og har ett ord per dag fra datoen under. Når siste dato er passert, begynner
siden på nytt fra første ord. Kjør `bun dates.mjs` for å stokke på nytt og gi nye datoer fra i dag
(tabellen under oppdateres automatisk).

<!-- dates:start -->
| Ordbok | Ord | Første dato | Siste dato |
|---|---:|---|---|
| Bokmål | 603 | 11-10-2026 | 04-06-2028 |
| Nynorsk | 480 | 11-10-2026 | 02-02-2028 |
<!-- dates:end -->

## Kjør lokalt

### Hent data

1. Sett opp MongoDB.
2. For plug-and-play, lag en database kalt `ord` og to collections derunder kalt `bm` og `nn`.
3. Følg stegene i [dictionary/README](dictionary/README.txt).

### Åpne nettsiden

1. Installer ønsket runtime (à la [Node.js](https://nodejs.org/)).
2. Installer nødvendige pakker (à la `npm install`).
3. Kjør `server.js` (à la `node server.js`).
