/**
 * Load both dictionaries.
 *  Here, saved to file to avoid excessively calling the API.
 *  Found in `dictionary/{nno,nob}/{nn,nb}.json`.
 *
 * Parse the elements.
 *
 * Extract all `items` lists, recursively.
 *  Store the contents of every `items` list in a new list.
 *  Optionally, filter by a specific key that must be present in the item.
 * Only keep unique items.
 *
 * Save the items to a file for further processing.
 *  Found in `dictionary/abbreviations/items.json`.
 *
 * Then, this is manually processed, with the results as a mapping.
 *  Found in `dictionary/abbreviations/mappings.json`.
 *
 * This is then used to replace the abbreviations in the definitions.
 *  Of `dictionary/detailed.mjs`.
 */

import fs from "fs";

const BM = "dictionary/nob/bm.json";
const NN = "dictionary/nno/nn.json";
const ITEMS = "dictionary/abbreviations/items.json";
const MAPPING = "dictionary/abbreviations/mappings.json";

const bm = JSON.parse(fs.readFileSync(BM));
const nn = JSON.parse(fs.readFileSync(NN));
let items = [];

function extractItems(element, contains = "id", dictionary = "bm", url = null) {
  const items = [];
  if (!url) {
    url = `https://ordbokene.no/nob/${dictionary}/${element.article_id}`;
  }

  if (Array.isArray(element)) {
    for (const subelement of element) {
      items.push(...extractItems(subelement, contains, dictionary, url));
    }
    return items;
  }

  if (typeof element === "object") {
    for (const key in element) {
      if (key === "items") {
        if (contains) {
          for (const item of element[key]) {
            if (item[contains]) {
              item.url = url;
              items.push(item);
            }
          }
        } else {
          items.push(...element[key]);
        }
      } else {
        items.push(...extractItems(element[key], contains, dictionary, url));
      }
    }
    return items;
  }

  return items;
}

function selectUnique(items) {
  const seen = new Set();
  const unique = [];

  for (const item of items) {
    const comparisonObject = { ...item };
    delete comparisonObject.url;
    const key = JSON.stringify(comparisonObject);
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(item);
    }
  }

  return unique;
}

for (const word of bm) {
  items.push(...extractItems(word, "id", "bm"));
}
for (const word of nn) {
  items.push(...extractItems(word, "id", "nn"));
}
items = selectUnique(items);

await fs.promises.writeFile(ITEMS, JSON.stringify(items, null, 2));

function initializeMapping(items) {
  const mapping = {};
  for (const item of items) {
    if (!mapping[item.type_]) {
      mapping[item.type_] = {};
    }
    mapping[item.type_][item.id] = item.url;
  }
  return mapping;
}

const mapping = initializeMapping(items);
await fs.promises.writeFile(MAPPING, JSON.stringify(mapping, null, 2));
