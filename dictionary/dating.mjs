// Assign a random (unique) date to each document in the collection starting from today.

import { MongoClient } from "mongodb";

async function date() {
  const uri =
    `mongodb+srv://${process.env.MONGO_USR}:${process.env.MONGO_PWD}` +
    "@ord.c8trc.mongodb.net/" +
    "?retryWrites=true&w=majority&appName=ord";

  const client = new MongoClient(uri);

  try {
    await client.connect();
    const database = client.db("ord");
    const collection = database.collection("ordbok");

    // 1. First get count of documents
    const count = await collection.countDocuments();

    // 2. Generate sequence of dates and shuffle them
    function shuffleArray(array) {
      for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
      }
      return array;
    }
    function formatDate(date) {
      const day = date.getDate().toString().padStart(2, "0");
      const month = (date.getMonth() + 1).toString().padStart(2, "0");
      const year = date.getFullYear();
      return `${day}-${month}-${year}`;
    }
    const dates = shuffleArray(
      Array.from({ length: count }, (_, i) => {
        const date = new Date();
        date.setDate(date.getDate() + i);
        return formatDate(date);
      }),
    );

    // 3. Bulk assign the pre-shuffled unique dates
    const documents = await collection.find({}, { _id: 0, word: 1 }).toArray();
    const operations = documents.map((doc, i) => ({
      updateOne: {
        filter: { word: doc.word },
        update: { $set: { date: dates[i] } },
      },
    }));

    await collection.bulkWrite(operations);
    await collection.createIndex({ date: 1 }, { unique: true });
  } finally {
    await client.close();
  }
}

await date();
