import fs from "fs";
import path from "path";
import { MongoClient } from "mongodb";

const ENCODING = "latin1";
const DICTIONARIES = { bm: "nob", nn: "nno" };

// Helper function to read and parse files.
const parseFile = (dictionary, file, mapper) => {
  try {
    const content = fs.readFileSync(
      path.join("dictionary", DICTIONARIES[dictionary], file),
      ENCODING,
    );
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

const processDictionary = (dictionary) => {
  let words = getWords(dictionary);

  words = words.filter(
    (word) =>
      /^\p{L}+$/u.test(word.word) &&
      word.word?.length > 5 &&
      /^(verb|interjeksjon|subjunksjon)\b/.test(word.wordgroup),
  );

  return words;
};

async function saveToDatabase(dictionary) {
  const uri = `mongodb+srv://${process.env.MONGO_USR}:${process.env.MONGO_PWD}@ord.c8trc.mongodb.net/?retryWrites=true&w=majority&appName=ord`;

  const client = new MongoClient(uri);

  try {
    await client.connect();
    const database = client.db("ord");
    const collection = database.collection(dictionary);

    await collection.deleteMany({});

    const words = processDictionary(dictionary);
    const bulkOps = words.map((word) => ({
      updateOne: {
        filter: { word: word.word },
        update: { $set: { word: word.word, wordgroup: word.wordgroup, dictionary: dictionary } },
        upsert: true,
      },
    }));

    await collection.bulkWrite(bulkOps);
  } catch (error) {
    console.log(`Error: ${error}`);
  } finally {
    await client.close();
  }
}

for (const dictionary of ["bm", "nn"]) {
  await saveToDatabase(dictionary).catch(console.error);
}
