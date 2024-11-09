// TODO: Incomplete.

import { MongoClient, updateOne, deleteOne } from "mongodb";
import fetch from "node-fetch";

const INDEX = "https://ord.uib.no/api/articles?w={}&dict=bm&scope=e";
const DESCRIPTION = "https://ord.uib.no/bm/article/{}.json";

async function ids(words) {
  const operations = [];

  for (const word of words) {
    const response = await fetch(INDEX.replace("{}", word.word));
    if (response.status != 200) break;
    const data = await response.json();

    if (data.meta.bm.total === 0) {
      operations.push({
        deleteOne: { filter: { norsk: word.norsk } },
      });
      continue;
    }

    operations.push({
      updateOne: {
        filter: { word: word.word },
        update: { $set: { ids: data.articles } },
      },
    });
  }

  return operations;
}

async function describe(words) {
  const operations = [];

  for (const word of words) {
    for (const id of word.ids) {
      const response = await fetch(DESCRIPTION.replace("{}", id));
      if (!response.ok) break;
      const { body } = await response.json();

      if (body.definitions.length === 0) {
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
              uttalelse: body.pronunciation,
              etymologi: body.etymology,
              beskrivelse: body.definitions
                .flatMap((def) => def.elements)
                .filter((el) => el._type === "explanation" && !el.content.includes("$"))
                .map((el) => el.content),
              eksempel: body.definitions
                .flatMap((def) => def.elements)
                .filter((el) => el._type === "example" && !el.quote.content.includes("$"))
                .map((el) => el.quote.content),
            },
          },
        },
      });
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
    const collection = database.collection("ord");

    let words;
    let operations;

    // Extract the IDs for the words.
    words = await database.find({ ids: { $exists: false } }, { word: 1, _id: 0 }).toArray();
    operations = await ids(words);
    await collection.bulkWrite(operations);

    // Extract the details for the words.
    words = await database.find({}, { word: 1, ids: 1, _id: 0 }).toArray();
    operations = await describe(words);
    await collection.bulkWrite(operations);
  } finally {
    await client.close();
  }
}

detail();
