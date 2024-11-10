import { MongoClient } from "mongodb";
import fetch from "node-fetch";

const INDEX = "https://ord.uib.no/api/articles?w={}&dict=bm&scope=e";
const DESCRIPTION = "https://ord.uib.no/bm/article/{}.json";

async function id(words) {
  const operations = [];

  for (const word of words) {
    const response = await fetch(INDEX.replace("{}", word.word));
    if (response.status != 200) break;
    const data = await response.json();

    if (data.meta.bm.total === 0) {
      operations.push({
        deleteOne: { filter: { word: word.word } },
      });
      continue;
    }

    operations.push({
      updateOne: {
        filter: { word: word.word },
        update: { $set: { id: data.articles.bm[0] } },
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

    // Handle different item types
    if (item.type_ === "language") {
      replacement = item.id;
    } else if (item.type_ === "usage") {
      replacement = item.text;
    } else if (item.type_ === "article_ref") {
      replacement = item.lemmas[0].lemma;
    }

    result = result.replace("$", replacement);
    itemIndex++;
  }

  return result.trim();
}

function clean(element) {
  const article = {
    id: element.article_id,
    pronunciation: element.body.pronunciation,
  };

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
  article.definitions = element.body.definitions.flatMap((def) =>
    def.elements.map((element) => {
      const parsed = {
        type: element.type_,
        meta: { items: element.items, lemmas: element.lemmas },
      };

      parsed.text = placeholders(element.content, element.items);

      // Handle explanation if present.
      if (element.explanation) {
        parsed.explanation = placeholders(element.explanation.content, element.explanation.items);
      }

      return parsed;
    }),
  );

  return article;
}

async function describe(words) {
  const operations = [];

  for (const word of words) {
    const response = await fetch(DESCRIPTION.replace("{}", word.id));
    if (!response.ok) break;
    const element = await response.json();

    if (!element.body.definitions || element.body.definitions.length === 0) {
      operations.push({
        deleteOne: { filter: { id: word.id } },
      });
      continue;
    }

    operations.push({
      updateOne: {
        filter: { id: word.id },
        update: { $set: clean(element) },
      },
    });
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
    const collection = database.collection("ord");

    let words;
    let operations;

    // Extract the ID for the words.
    words = await collection.find({ id: { $exists: false } }, { word: 1, _id: 0 }).toArray();
    operations = await id(words);
    await collection.bulkWrite(operations);

    // Extract the details for the words.
    words = await collection.find({}, { word: 1, id: 1, _id: 0 }).toArray();
    operations = await describe(words);
    await collection.bulkWrite(operations);
  } finally {
    await client.close();
  }
}

detail();
