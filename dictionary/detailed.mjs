import { MongoClient } from "mongodb";
import fetch from "node-fetch";
import dotenv from "dotenv";
import { clean } from "./article.mjs";

dotenv.config();

const INDEX = "https://ord.uib.no/api/articles?w={}&dict={DICT}&scope=e";
const BM = "https://ord.uib.no/bm/article/{}.json";
const NN = "https://ord.uib.no/nn/article/{}.json";

async function id(words, dictionary) {
  const operations = [];

  for (const word of words) {
    const response = await fetch(
      INDEX.replace("{}", word.word).replace("{DICT}", dictionary),
    );
    if (response.status != 200) break;
    const data = await response.json();

    if (data.meta[dictionary].total === 0) {
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
            id: data.articles[dictionary] ? data.articles[dictionary][0] : null,
            ids: data.articles[dictionary] || [],
          },
        },
      },
    });
  }

  return operations;
}

async function describe(words, dictionary) {
  const operations = [];

  for (const word of words) {
    try {
      if (!word.id) {
        operations.push({ deleteOne: { filter: { word: word.word } } });
        continue;
      }

      let response;
      const url = dictionary === "bm" ? BM : NN;
      response = await fetch(url.replace("{}", word.id));
      if (!response.ok) {
        console.log(`Error ${response.status}: ${JSON.stringify(word)}`);
        continue;
      }

      const element = await response.json();

      if (!element.body.definitions || element.body.definitions.length === 0) {
        operations.push({ deleteOne: { filter: { word: word.word } } });
        continue;
      }

      operations.push({
        updateOne: {
          filter: { word: word.word },
          update: { $set: { ...clean(element) } },
        },
      });
    } catch (error) {
      console.log(`Error: ${error} for word: ${JSON.stringify(word)}`);
      return operations;
    }
  }

  return operations;
}

async function detail() {
  const uri =
    `mongodb+srv://${process.env.MONGO_USR.trim()}:${process.env.MONGO_PWD.trim()}` +
    "@ord.c8trc.mongodb.net/" +
    "?retryWrites=true&w=majority&appName=ord";

  const client = new MongoClient(uri);

  try {
    await client.connect();
    const database = client.db("ord");

    // Process each dictionary separately
    for (const dictionary of ["bm", "nn"]) {
      const collection = database.collection(dictionary);
      let words;
      let operations;
      let result;

      // Extract the ID for the words
      words = await collection
        .find({ id: { $exists: false } }, { word: 1, _id: 0 })
        .toArray();
      operations = await id(words, dictionary);
      if (operations.length > 0) {
        result = await collection.bulkWrite(operations);
        console.log(
          `Inserted ${result.insertedCount} new records, modified ${result.modifiedCount} existing ones, and deleted ${result.deletedCount}.`,
        );
      }

      // Extract the details for the words
      words = await collection
        .find({ id: { $exists: true } }, { word: 1, id: 1, _id: 0 })
        .toArray();
      operations = await describe(words, dictionary);
      if (operations.length > 0) {
        result = await collection.bulkWrite(operations);
        console.log(
          `Inserted ${result.insertedCount} new records, modified ${result.modifiedCount} existing ones, and deleted ${result.deletedCount}.`,
        );
      }
    }
  } catch (error) {
    console.log(`Error: ${error}`);
  } finally {
    await client.close();
  }
}

await detail();
