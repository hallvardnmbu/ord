// Turn a raw ordbokene article into the document shape stored in the `bm` / `nn` collections.
// Shared by detailed.mjs (fetching) and curation/export.mjs (the curated word list).

import fs from "fs";

const MAPPING = JSON.parse(
  fs.readFileSync(new URL("./abbreviations/mappings.json", import.meta.url)),
);
const TYPES = {
  definition: "definisjon",
  example: "eksempel",
  explanation: "forklaring",
  sub_article: "underartikkel",
};

function placeholders(content, items) {
  if (!content || !items || !items.length) return content;

  let result = content;
  let itemIndex = 0;

  while (result.includes("$")) {
    const item = items[itemIndex];
    let replacement = "";

    // Handle different item types.
    switch (item.type_) {
      case "language":
        replacement = MAPPING["language"][item.id] || item.id;
        break;
      case "relation":
        replacement = MAPPING["relation"][item.id] || item.id;
        break;
      case "grammar":
        replacement = MAPPING["grammar"][item.id] || item.id;
        break;
      case "domain":
        replacement = MAPPING["domain"][item.id] || item.id;
        break;
      case "temporal":
        replacement = MAPPING["temporal"][item.id] || item.id;
        break;
      case "rhetoric":
        replacement = MAPPING["rhetoric"][item.id] || item.id;
        break;
      case "entity":
        replacement = MAPPING["entity"][item.id] || item.id;
        break;
      case "article_ref":
        replacement = item.lemmas[0].lemma;
        break;
      case "usage":
        replacement = item.text.includes("$")
          ? placeholders(item.text, item.items)
          : item.text;
        break;
      case "explanation":
        replacement = placeholders(item.content, item.items);
        break;
      case "superscript":
        replacement = `<sup>${item.text}</sup>`;
        break;
      case "subscript":
        replacement = `<sub>${item.text}</sub>`;
        break;
      case "quote_inset":
        replacement = ` «${placeholders(item.content, item.items).trim()}» `;
        break;
      case "fraction":
        replacement = `${item.numerator}/${item.denominator}`;
        break;
      default:
        throw new Error(`Unknown type: ${item.type_}`);
    }

    result = result.replace("$", replacement);
    itemIndex++;
  }

  return result.trim();
}

function formatDefinition(definition, word) {
  if (Array.isArray(definition.content)) {
    return definition.content
      .flatMap((subDef) => formatDefinition(subDef, word))
      .filter(Boolean);
  } else if (
    typeof definition.content === "object" &&
    definition.content !== null
  ) {
    return [
      {
        id: definition.content.id || null,
        word: word,
        definitions: definition.content.definitions || definition.content,
      },
    ];
  }
  return [definition.content];
}

function processDefinitions(definitions) {
  const formattedDefinitions = {};

  for (const definition of definitions) {
    let formattedDefinition;
    if (Array.isArray(definition.content)) {
      formattedDefinition = [processDefinitions(definition.content)];
    } else {
      formattedDefinition = formatDefinition(definition, definition.word);
    }
    formattedDefinitions[definition.type] = formattedDefinitions[
      definition.type
    ]
      ? formattedDefinitions[definition.type].concat(formattedDefinition)
      : formattedDefinition;
  }

  return formattedDefinitions;
}

function definititons(element) {
  const parsed = {
    type: TYPES[element.type_] || element.type_,
  };

  if (element.content) {
    parsed.content = placeholders(element.content, element.items);
  } else if (element.quote) {
    parsed.content = `<i>${placeholders(element.quote.content, element.quote.items)}</i>`;
  } else if (element.elements) {
    parsed.content = element.elements.map((subelement) =>
      definititons(subelement),
    );
  } else if (element.article) {
    parsed.content = clean(element.article);
    parsed.word =
      element.article.lemmas && element.article.lemmas.length > 0
        ? element.article.lemmas[0].lemma
        : null;
  }

  return parsed;
}

export function clean(element) {
  const article = {
    id: element.article_id,
  };

  try {
    // Parse pronunciation.
    article.pronunciation =
      element.body.pronunciation && element.body.pronunciation.length > 0
        ? placeholders(
            element.body.pronunciation[0].content,
            element.body.pronunciation[0].items,
          )
        : null;

    // Parse lemmas and inflections.
    article.inflection = element.lemmas
      .map((data) => {
        const inflection = data.paradigm_info
          ? data.paradigm_info[data.paradigm_info.length - 1]
          : null;
        return inflection ? inflection.inflection : null;
      })
      .filter(Boolean);

    // Parse etymology.
    article.etymology = element.body.etymology
      ? element.body.etymology.map((etym) =>
          placeholders(etym.content, etym.items),
        )
      : [];

    // Parse definitions.
    article.definitions = element.body.definitions
      ? element.body.definitions.flatMap((def) =>
          def.elements.map((element) => definititons(element)),
        )
      : [];

    article.definitions = processDefinitions(article.definitions);

    return article;
  } catch (error) {
    console.log(`Error: ${error} for element: ${JSON.stringify(element)}`);
  }
}

