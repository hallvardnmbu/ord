// Remove duplicated `id`'s, keeping the one with `lemmas` if it exists.

import { MongoClient } from "mongodb";

async function duplicates() {
  const uri =
    `mongodb+srv://${process.env.MONGO_USR}:${process.env.MONGO_PWD}` +
    "@ord.c8trc.mongodb.net/" +
    "?retryWrites=true&w=majority&appName=ord";

  const client = new MongoClient(uri);

  try {
    await client.connect();
    const database = client.db("ord");
    const collection = database.collection("ord");

    // Remove duplicates (on `id`), keeping those with `{lemmas: {$exists: true}}`
    const duplicates = await collection
      .aggregate([
        { $group: { _id: "$id", count: { $sum: 1 }, docs: { $push: "$$ROOT" } } },
        { $match: { count: { $gt: 1 } } },
      ])
      .toArray();

    for (const group of duplicates) {
      // Sort docs to keep the one with lemmas if it exists
      const sorted = group.docs.sort((a, b) => (b.lemmas ? 1 : 0) - (a.lemmas ? 1 : 0));
      const [keep, ...remove] = sorted;

      // Delete all except the one to keep
      await collection.deleteMany({
        _id: { $in: remove.map((doc) => doc._id) },
      });
    }
  } finally {
    await client.close();
  }
}

await duplicates();
