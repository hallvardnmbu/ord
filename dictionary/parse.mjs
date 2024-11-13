import fs from "fs";
import path from "path";
import { MongoClient } from "mongodb";

const ENCODING = "latin1";
const DICTIONARIES = ["nob", "nno"];

// Helper function to read and parse files.
const parseFile = (dictionary, file, mapper) => {
  try {
    const content = fs.readFileSync(path.join("dictionary", dictionary, file), ENCODING);
    return content
      .trim()
      .split("\n")
      .filter((line) => line.length > 0)
      .map((line) => line.split("\t"))
      .map(mapper);
  } catch (error) {
    console.error(`Error reading file ${file}:`, error);
    throw error;
  }
};

// Parse words file.
const parseWords = (dictionary) =>
  parseFile(dictionary, "lemma.txt", ([_, lemmaid, word]) => ({
    lemmaid: parseInt(lemmaid, 10),
    word,
  }));

// Parse mapping file.
const parseMapping = (dictionary) =>
  parseFile(dictionary, "lemma_paradigme.txt", ([_, lemmaid, paradigmid]) => ({
    lemmaid: parseInt(lemmaid, 10),
    paradigmid: parseInt(paradigmid, 10),
  }));

// Parse paradigm file.
const parseParadigm = (dictionary) =>
  parseFile(
    dictionary,
    "paradigme.txt",
    ([_, paradigmid, wordgroup, boygroup, wordclass, classinfo, description, doeme, id]) => ({
      paradigmid: parseInt(paradigmid, 10),
      wordgroup,
      boygroup,
      wordclass,
      classinfo,
      description,
      doeme,
      id,
    }),
  );

// Create indexes for faster lookups.
const createLookupMap = (array, key) => {
  return new Map(array.map((item) => [item[key], item]));
};

// Assign the paradigms to the words based on their mapping.
const getWords = (dictionary) => {
  try {
    const words = parseWords(dictionary);
    const mappings = parseMapping(dictionary);
    const paradigms = parseParadigm(dictionary);

    // Create lookup maps.
    const mappingsByLemmaId = createLookupMap(mappings, "lemmaid");
    const paradigmsById = createLookupMap(paradigms, "paradigmid");

    // Assign paradigms to words.
    return words.map((word) => {
      const mapping = mappingsByLemmaId.get(word.lemmaid);
      if (mapping) {
        const paradigm = paradigmsById.get(mapping.paradigmid);
        if (paradigm) {
          return { ...word, ...paradigm };
        }
      }
      return word;
    });
  } catch (error) {
    console.error("Error processing dictionary files:", error);
    throw error;
  }
};

// Process both dictionaries and merge results
const processAllDictionaries = () => {
  const wordMap = new Map();

  DICTIONARIES.forEach((dictionary) => {
    const dictionaryWords = getWords(dictionary);

    dictionaryWords.forEach((word) => {
      if (!wordMap.has(word.word)) {
        wordMap.set(word.word, {
          word: word.word,
          bm: {},
          nn: {},
        });
      }

      // Store dictionary-specific data under the appropriate key
      wordMap.get(word.word)[{ nob: "bm", nno: "nn" }[dictionary]] = {
        wordgroup: word.wordgroup,
      };
    });
  });

  return Array.from(wordMap.values());
};

let words = processAllDictionaries();
words = words.filter(
  (word) =>
    /^\p{L}+$/u.test(word.word) &&
    word.word?.length > 5 &&
    (/^(verb|interjeksjon|subjunksjon)\b/.test(word.bm?.wordgroup) ||
      /^(verb|interjeksjon|subjunksjon)\b/.test(word.nn?.wordgroup)),
);

async function saveToDatabase(words) {
  const uri = `mongodb+srv://${process.env.MONGO_USR}:${process.env.MONGO_PWD}@ord.c8trc.mongodb.net/?retryWrites=true&w=majority&appName=ord`;

  const client = new MongoClient(uri);

  try {
    await client.connect();
    const database = client.db("ord");
    const collection = database.collection("ordbok");

    await collection.deleteMany({});

    const bulkOps = words.map((word) => ({
      updateOne: {
        filter: { word: word.word },
        update: { $set: word },
        upsert: true,
      },
    }));

    await collection.bulkWrite(bulkOps);
  } finally {
    await client.close();
  }
}

await saveToDatabase(words).catch(console.error);
