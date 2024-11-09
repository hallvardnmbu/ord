import fs from "fs";
import path from "path";
import { MongoClient } from "mongodb";

// Extract all words from the books and count their frequency

const books = fs.readdirSync("books").map((book) => {
  const content = fs.readFileSync(path.join("books", book), "utf-8").toLowerCase();
  return content.match(/\b\w+\b/g) || [];
});

const words = books.flat().filter((word) => word.length > 5 && !word.includes("_"));

const frequency = {};
words.forEach((word) => {
  frequency[word] = (frequency[word] || 0) + 1;
});

const uncommon = Object.fromEntries(Object.entries(frequency).filter(([_, count]) => count < 5));

// Save the frequency of each word to the database

async function saveToDatabase() {
  const uri =
    `mongodb+srv://${process.env.MONGO_USR}:${process.env.MONGO_PWD}` +
    "@ord.c8trc.mongodb.net/" +
    "?retryWrites=true&w=majority&appName=ord";

  const client = new MongoClient(uri);

  try {
    await client.connect();
    const database = client.db("ord");
    const collection = database.collection("books");

    const bulkOps = Object.entries(frequency).map(([word, count]) => ({
      updateOne: {
        filter: { word: word },
        update: { $set: { word: word, frequency: count } },
        upsert: true,
      },
    }));

    await collection.bulkWrite(bulkOps);
  } finally {
    await client.close();
  }
}

saveToDatabase().catch(console.error);
