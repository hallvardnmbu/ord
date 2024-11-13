import express from "express";
import { MongoClient, ServerApiVersion } from "mongodb";
import path from "path";
import { fileURLToPath } from "url";
import dotenv from "dotenv";

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ord = express();
const port = 3000;

ord.set("view engine", "ejs");
ord.set("views", path.join(__dirname, "views"));
ord.use(express.static(path.join(__dirname, "public")));

let client;
try {
  client = await MongoClient.connect(
    `mongodb+srv://${process.env.MONGO_USR}:${process.env.MONGO_PWD}@ord.c8trc.mongodb.net/?retryWrites=true&w=majority&appName=ord`,
    {
      serverApi: {
        version: ServerApiVersion.v1,
        strict: false,
        deprecationErrors: true,
      },
    },
  );
} catch (err) {
  console.error("Failed to connect to MongoDB", err);
  process.exit(1);
}
const dbWord = client.db("ord");
let collectionWord = dbWord.collection("ordbok");

ord.get("/random", async (req, res) => {
  try {
    const words = await collectionWord.aggregate([{ $sample: { size: 1 } }]).toArray();
    res.render("page", {
      words: words,
      dictionary: req.query.dictionary || "bm",
      date: null,
      week: null,
      day: null,
      error: null,
    });
  } catch (error) {
    res.status(500).render("page", {
      words: [],
      dictionary: req.query.dictionary || "bm",
      date: null,
      week: null,
      day: null,
      error: error.message,
    });
  }
});

ord.get("/search", async (req, res) => {
  const word = req.query.word.trim().toLowerCase();
  try {
    const words = await collectionWord
      .aggregate([
        {
          $search: {
            index: "word",
            compound: {
              should: [
                {
                  text: {
                    query: word,
                    path: "word",
                    score: { boost: { value: 10 } },
                  },
                },
                {
                  text: {
                    query: word,
                    path: "word",
                    fuzzy: {
                      maxEdits: 2,
                      prefixLength: 1,
                      maxExpansions: 1,
                    },
                  },
                },
              ],
            },
          },
        },
        { $limit: 1 },
      ])
      .toArray();
    res.render("page", {
      words: words,
      dictionary: req.query.dictionary || "bm",
      date: null,
      week: null,
      day: word,
      error: null,
    });
  } catch (error) {
    res.status(500).render("page", {
      words: [],
      dictionary: req.query.dictionary || "bm",
      date: null,
      week: null,
      day: word,
      error: error.message,
    });
  }
});

ord.get("/", async (req, res) => {
  const dictionary = req.query.dictionary || "bm";
  const date = new Date();
  const week = Math.ceil(((date - new Date(date.getFullYear(), 0, 1)) / 86400000 + 1) / 7);
  const day = date.toLocaleDateString("no-NB", { weekday: "long" }).toLowerCase();
  const today = date
    .toLocaleDateString("no-NB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    })
    .split(".")
    .join("-");
  try {
    const words = await collectionWord.find({ date: today }).toArray();
    res.render("page", {
      words: words,
      dictionary: dictionary,
      date: today,
      week: week,
      day: day,
      error: null,
    });
  } catch (error) {
    res.status(500).render("page", {
      words: [],
      dictionary: dictionary,
      date: today,
      week: week,
      day: day,
      error: error.message,
    });
  }
});

ord.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
