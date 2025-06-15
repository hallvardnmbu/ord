// Remove duplicated `id`'s, keeping the one with `lemmas` if it exists.

import { MongoClient } from "mongodb";
import dotenv from "dotenv";

dotenv.config();

async function duplicates() {
  const uri =
    `mongodb+srv://${process.env.MONGO_USR}:${process.env.MONGO_PWD}` +
    "@ord.c8trc.mongodb.net/" +
    "?retryWrites=true&w=majority&appName=ord";

  const client = new MongoClient(uri);

  try {
    await client.connect();
    const database = client.db("dev");

    for (const dictionary of ["bm", "nn"]) {
      const collection = database.collection(dictionary);

      // Remove duplicates (on `id`), keeping those with `{lemmas: {$exists: true}}`
      const duplicates = await collection
        .aggregate([
          { $group: { _id: "$id", count: { $sum: 1 }, docs: { $push: "$$ROOT" } } },
          { $match: { count: { $gt: 1 } } },
        ])
        .toArray();

      // Log duplicates
      console.log(duplicates);

      for (const group of duplicates) {
        // Sort docs to keep the one with lemmas.
        const sorted = group.docs.sort((a, b) => {
          if (a.lemmas && !b.lemmas) return -1;
          if (!a.lemmas && b.lemmas) return 1;
          return 0;
        });
        const [keep, ...remove] = sorted;

        // Delete all except the one to keep
        await collection.deleteMany({
          _id: { $in: remove.map((doc) => doc._id) },
        });
      }
    }
  } catch (error) {
    console.log(`Error: ${error}`);
  } finally {
    await client.close();
  }
}

await duplicates();
