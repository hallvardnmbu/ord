import fs from "fs";
import path from "path";
import { MongoClient } from "mongodb";

const ENCODING = "latin1";
const DICTIONARY = "nob";

// Helper function to read and parse files.
const parseFile = (file, mapper) => {
  try {
    const content = fs.readFileSync(path.join("dictionary", DICTIONARY, file), ENCODING);
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
const parseWords = () =>
  parseFile("lemma.txt", ([_, lemmaid, word]) => ({
    lemmaid: parseInt(lemmaid, 10),
    word,
  }));

// Parse mapping file.
const parseMapping = () =>
  parseFile("lemma_paradigme.txt", ([_, lemmaid, paradigmid]) => ({
    lemmaid: parseInt(lemmaid, 10),
    paradigmid: parseInt(paradigmid, 10),
  }));

// Parse paradigm file.
const parseParadigm = () =>
  parseFile(
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
const main = () => {
  try {
    const words = parseWords();
    const mappings = parseMapping();
    const paradigms = parseParadigm();

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

const words = main();

async function saveToDatabase(words) {
  const uri =
    `mongodb+srv://${process.env.MONGO_USR}:${process.env.MONGO_PWD}` +
    "@ord.c8trc.mongodb.net/" +
    "?retryWrites=true&w=majority&appName=ord";

  const client = new MongoClient(uri);

  try {
    await client.connect();
    const database = client.db("ord");
    const collection = database.collection("ord");

    collection.deleteMany({});

    const bulkOps = words.map((word) => ({
      updateOne: {
        filter: { word: word.word },
        update: { $set: { word: word.word, description: word.description, group: word.wordgroup } },
        upsert: true,
      },
    }));

    await collection.bulkWrite(bulkOps);
  } finally {
    await client.close();
  }
}

// Store all words of wordgroups with `verb` in the name.
const verbs = words.filter((word) => word.wordgroup?.includes("verb") && !word.word?.includes("-"));
saveToDatabase(verbs).catch(console.error);
