import { MongoClient } from "mongodb";
import fetch from "node-fetch";

const INDEX = "https://ord.uib.no/api/articles?w={}&dict=bm,nn&scope=e";
const BM = "https://ord.uib.no/bm/article/{}.json";
const NN = "https://ord.uib.no/nn/article/{}.json";

async function id(words) {
  const operations = [];

  for (const word of words) {
    const response = await fetch(INDEX.replace("{}", word.word));
    if (response.status != 200) break;
    const data = await response.json();

    if (data.meta.bm.total === 0 && data.meta.nn.total === 0) {
      operations.push({
        deleteOne: { filter: { word: word.word } },
      });
      continue;
    }

    operations.push({
      updateOne: {
        filter: { word: word.word },
        update: {
          $set: {
            "bm.id": data.articles.bm ? data.articles.bm[0] : null,
            "nn.id": data.articles.nn ? data.articles.nn[0] : null,
          },
        },
      },
    });
  }

  return operations;
}

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
        replacement = item.id;
        break;
      case "relation":
        replacement = item.id;
        break;
      case "usage":
        replacement = item.text.includes("$") ? placeholders(item.text, item.items) : item.text;
        break;
      case "rhetoric":
        replacement = item.id;
        break;
      case "article_ref":
        replacement = item.lemmas[0].lemma;
        break;
      case "entity":
        replacement = item.id;
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
      case "grammar":
        replacement = item.id;
        break;
      case "domain":
        replacement = item.id;
        break;
      case "temporal":
        replacement = item.id;
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

function formatDefinition(definition) {
  if (Array.isArray(definition.text)) {
    return definition.text.flatMap((subDef) => formatDefinition(subDef)).filter(Boolean);
  }
  return [definition.text];
}

function processDefinitions(definitions) {
  const formattedDefinitions = {};
  for (const definition of definitions) {
    if (Array.isArray(definition.text)) {
      for (const element of definition.text) {
        const formattedDefinition = formatDefinition(element);
        formattedDefinitions[element.type] = formattedDefinitions[element.type]
          ? formattedDefinitions[element.type].concat(formattedDefinition)
          : formattedDefinition;
      }
    } else {
      const formattedDefinition = formatDefinition(definition);
      if (definition.word) {
        formattedDefinition[0].word = definition.word;
      }
      formattedDefinitions[definition.type] = formattedDefinitions[definition.type]
        ? formattedDefinitions[definition.type].concat(formattedDefinition)
        : formattedDefinition;
    }
  }
  return formattedDefinitions;
}

function parse(element) {
  const parsed = {
    type:
      {
        definition: "definisjon",
        example: "eksempel",
        explanation: "forklaring",
        sub_article: "underartikkel",
      }[element.type_] || element.type_,
    meta: element,
  };

  if (element.content) {
    parsed.text = placeholders(element.content, element.items);
  } else if (element.quote) {
    parsed.text = placeholders(element.quote.content, element.quote.items);
  } else if (element.elements) {
    parsed.text = element.elements.map((sub) => parse(sub));
  } else if (element.article) {
    parsed.text = clean(element.article);
    parsed.text.word =
      element.article.lemmas && element.article.lemmas.length > 0
        ? element.article.lemmas[0].lemma
        : null;
  }

  return parsed;
}

function clean(element) {
  const article = {
    id: element.article_id,
  };

  try {
    // Parse pronunciation.
    article.pronunciation =
      element.body.pronunciation && element.body.pronunciation.length > 0
        ? placeholders(element.body.pronunciation[0].content, element.body.pronunciation[0].items)
        : null;

    // Parse lemmas and inflections.
    const lemmas = element.lemmas.map((data) => {
      const lemma = {
        meta: {
          lemma: data.lemma,
          id: data.id,
          hgno: data.hgno,
          class: data.inflection_class,
        },
      };

      const inflection = data.paradigm_info ? data.paradigm_info[0] : null;
      lemma.inflection = inflection
        ? {
            tags: inflection.tags,
            inflections: inflection.inflection,
          }
        : {};

      return lemma;
    });
    article.lemmas = lemmas;

    // Parse etymology.
    article.etymology = element.body.etymology
      ? element.body.etymology.map((etym) => ({
          meta: {
            type: etym.type_,
            content: etym.content,
            items: etym.items,
          },
          text: placeholders(etym.content, etym.items),
        }))
      : [];

    // Parse definitions.
    article.definitions = element.body.definitions
      ? element.body.definitions.flatMap((def) => def.elements.map((element) => parse(element)))
      : [];

    article.definitions = processDefinitions(article.definitions);

    return article;
  } catch (error) {
    console.log(`Error: ${error} for element: ${JSON.stringify(element)}`);
  }
}

async function describe(words) {
  const operations = [];

  for (const word of words) {
    try {
      for (const dictionary of ["bm", "nn"]) {
        if (!word[dictionary] || !word[dictionary].id) {
          word[dictionary] = null;
          continue;
        }

        let response;
        switch (dictionary) {
          case "bm":
            response = await fetch(BM.replace("{}", word[dictionary].id));
            break;
          case "nn":
            response = await fetch(NN.replace("{}", word[dictionary].id));
            break;
        }
        if (!response.ok) {
          console.log(`Error ${response.status}: ${JSON.stringify(word)}`);
          break;
        }
        const element = await response.json();

        if (!element.body.definitions || element.body.definitions.length === 0) {
          word[dictionary] = null;
          continue;
        }

        word[dictionary] = {
          id: word[dictionary].id,
          wordgroup: word[dictionary].wordgroup,
          ...clean(element),
        };
      }

      if (!word.bm && !word.nn) {
        operations.push({ deleteOne: { filter: { word: word.word } } });
      } else {
        operations.push({
          updateOne: {
            filter: { word: word.word },
            update: { $set: word },
          },
        });
      }
    } catch (error) {
      console.log(`Error: ${error} for word: ${JSON.stringify(word)}`);
      return operations;
    }
  }

  return operations;
}

async function detail() {
  const uri =
    `mongodb+srv://${process.env.MONGO_USR}:${process.env.MONGO_PWD}` +
    "@ord.c8trc.mongodb.net/" +
    "?retryWrites=true&w=majority&appName=ord";

  const client = new MongoClient(uri);

  try {
    await client.connect();
    const database = client.db("ord");
    const collection = database.collection("ordbok");

    let words;
    let operations;

    // Extract the ID for the words.
    words = await collection
      .find(
        {
          $or: [{ "bm.id": { $exists: false } }, { "nn.id": { $exists: false } }],
        },
        { word: 1, _id: 0 },
      )
      .toArray();
    operations = await id(words);
    if (operations.length > 0) {
      await collection.bulkWrite(operations);
    }

    // Extract the details for the words.
    words = await collection
      .find(
        { $or: [{ "bm.id": { $exists: true } }, { "nn.id": { $exists: true } }] },
        { word: 1, _id: 0 },
      )
      .toArray();
    operations = await describe(words);
    if (operations.length > 0) {
      await collection.bulkWrite(operations);
    }
  } finally {
    await client.close();
  }
}

await detail();
