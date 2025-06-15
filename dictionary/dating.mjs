// Assign a random (unique) date to each document in the collection starting from today.

import { MongoClient } from "mongodb";
import dotenv from "dotenv";

dotenv.config();

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

async function date() {
  const uri =
    `mongodb+srv://${process.env.MONGO_USR}:${process.env.MONGO_PWD}` +
    "@ord.c8trc.mongodb.net/" +
    "?retryWrites=true&w=majority&appName=ord";

  const client = new MongoClient(uri);

  try {
    await client.connect();
    const database = client.db("ord");
    const dictionaries = {
      bm: database.collection("bm"),
      nn: database.collection("nn"),
    };

    for (const dictionary of Object.keys(dictionaries)) {
      // 1. For the records where date already exists, set a flag for all dates before today.
      const today = formatDate(new Date());
      await dictionaries[dictionary].updateMany(
        { date: { $exists: true }, past: { $or: [{ $exists: false }, { $eq: false }] } },
        [
          {
            $set: {
              past: {
                $lte: [
                  {
                    $dateFromString: {
                      dateString: "$date",
                      format: "%d-%m-%Y",
                    },
                  },
                  {
                    $dateFromString: {
                      dateString: today,
                      format: "%d-%m-%Y",
                    },
                  },
                ],
              },
            },
          },
        ],
      );

      // 2. Get the count of all (unused) documents.
      const count = await dictionaries[dictionary].countDocuments({ past: false });

      // 3. Generate sequence of dates and shuffle them.
      const dates = shuffleArray(
        Array.from({ length: count }, (_, i) => {
          const date = new Date();
          date.setDate(date.getDate() + i);
          return formatDate(date);
        }),
      );

      // 4. Bulk assign the pre-shuffled unique dates.
      const documents = await dictionaries[dictionary]
        .find({ past: false }, { _id: 0, word: 1 })
        .toArray();
      const operations = documents.map((doc, i) => {
        return {
          updateOne: {
            filter: { word: doc.word },
            update: { $set: { date: dates[i] } },
          },
        };
      });

      await dictionaries[dictionary].bulkWrite(operations);
      await dictionaries[dictionary].createIndex({ date: 1 });
    }
  } catch (error) {
    console.log(`Error: ${error}`);
  } finally {
    await client.close();
  }
}

await date();
