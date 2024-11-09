import { MongoClient } from "mongodb";
import fetch from "node-fetch";
import { Translator } from "@vitalets/google-translate-api";

const WORDS = "https://phrontistery.info/{}.html";
const PATTERNS = {
  ord: /\r\n<tr><td>(.*?)<td>/g,
  uttale: /UTTALE<\/span>.*?<span>\[(.*?)\]<\/span>/g,
  etymologi: /ETYMOLOGY<\/span>.*?<div>(.*?)<\/div>/g,
};

const translator = new Translator();
const DICTIONARY = "https://ord.uib.no/api/articles?w={}&dict=bm&scope=e";
const DESCRIPTION = "https://ord.uib.no/bm/article/{}.json";

const client = new MongoClient(
  `mongodb+srv://${process.env.MONGO_USR}:${process.env.MONGO_PWD}` +
    `@ord.c8trc.mongodb.net/` +
    `?retryWrites=true&w=majority&appName=ord`,
);
const database = client.db("ord").collection("ord");

async function words(letter) {
  const response = await fetch(WORDS.replace("{}", letter));
  if (!response.ok) return [];
  const text = await response.text();
  return [...text.matchAll(PATTERNS.ord)]
    .map((match) => match[1])
    .filter((word) => !word.includes("<") && !word.includes("&"));
}

async function fetchWords(letters = "abcdefghijklmnopqrstuvwxyz") {
  const vocabulary = [];
  for (const letter of letters) {
    const wordsForLetter = await words(letter);
    vocabulary.push(...wordsForLetter);
  }
  return vocabulary;
}

async function translate(vocabulary) {
  return Promise.all(
    vocabulary.map(async (word) => ({
      engelsk: word,
      norsk: (await translator.translate(word, { from: "en", to: "no" })).text,
    })),
  );
}

async function save(vocabulary) {
  const operations = vocabulary.map((word) => ({
    updateOne: {
      filter: { engelsk: word.engelsk },
      update: { $set: word },
      upsert: true,
    },
  }));
  await database.bulkWrite(operations);
}

async function clean() {
  const words = await database.find({ ids: { $exists: false } }, { norsk: 1, _id: 0 }).toArray();
  const operations = [];

  for (const word of words) {
    const response = await fetch(DICTIONARY.replace("{}", word.norsk));
    if (!response.ok) break;
    const data = await response.json();

    if (data.meta.bm.total === 0) {
      operations.push({
        deleteOne: { filter: { norsk: word.norsk } },
      });
      continue;
    }

    operations.push({
      updateOne: {
        filter: { norsk: word.norsk },
        update: { $set: { ids: data.articles } },
      },
    });
  }

  await database.bulkWrite(operations);
}

async function describe() {
  const words = await database.find({}, { norsk: 1, ids: 1, _id: 0 }).limit(10).toArray();
  const operations = [];

  for (const word of words) {
    for (const id of word.ids) {
      const response = await fetch(DESCRIPTION.replace("{}", id));
      if (!response.ok) {
        operations.push({
          deleteOne: { filter: { norsk: word.norsk } },
        });
        continue;
      }

      const { body } = await response.json();
      operations.push({
        updateOne: {
          filter: { norsk: word.norsk },
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

  await database.bulkWrite(operations);
}

// Example usage:
// const vocabulary = await fetchWords("abcdefghijklmnopqrstuvwxyz");
// const translated = await translate(vocabulary);
// await save(translated);
// await clean();
// await describe();
