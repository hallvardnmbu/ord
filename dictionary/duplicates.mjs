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
    const collection = database.collection("ordbok");

    // Remove duplicates (on `id`), keeping those with `{lemmas: {$exists: true}}`
    const duplicates = await collection
      .aggregate([
        { $group: { _id: "$word", count: { $sum: 1 }, docs: { $push: "$$ROOT" } } },
        { $match: { count: { $gt: 1 } } },
      ])
      .toArray();

    // Log duplicates
    console.log(duplicates);

    for (const group of duplicates) {
      // Sort docs to keep the one with both `nb` and `nn` first
      const sorted = group.docs.sort((a, b) => {
        // If a has both and b doesn't, a should come first (-1)
        if (a.nb && a.nn && (!b.nb || !b.nn)) return -1;
        // If b has both and a doesn't, b should come first (1)
        if (b.nb && b.nn && (!a.nb || !a.nn)) return 1;
        // If a has either and b has neither, a should come first (-1)
        if ((a.nb || a.nn) && !b.nb && !b.nn) return -1;
        // If b has either and a has neither, b should come first (1)
        if ((b.nb || b.nn) && !a.nb && !a.nn) return 1;
        // Otherwise, keep original order
        return 0;
      });
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
