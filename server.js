import express from "express";
import { MongoClient, ServerApiVersion } from "mongodb";
import path from "path";
import { fileURLToPath } from "url";
import dotenv from "dotenv";

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const port = 3000;

app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));
app.use(express.static(path.join(__dirname, "public")));

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
const db = client.db("ord");
let collection = db.collection("ord");

function formatDefinition(definition) {
  if (Array.isArray(definition.text)) {
    return definition.text.flatMap((subDef) => formatDefinition(subDef)).filter(Boolean);
  }
  return [definition.text];
}

function processDefinitions(words) {
  for (const word of words) {
    const definitions = word.definitions;
    const formattedDefinitions = {};
    for (const definition of definitions) {
      if (Array.isArray(definition.text)) {
        for (const element of definition.text) {
          const formattedDefinition = formatDefinition(element);
          formattedDefinitions[element.type] = formattedDefinitions[element.type]
            ? formattedDefinitions[element.type].concat(formattedDefinition)
            : formattedDefinition;
        }
      } else {
        const formattedDefinition = formatDefinition(definition);
        formattedDefinitions[definition.type] = formattedDefinitions[definition.type]
          ? formattedDefinitions[definition.type].concat(formattedDefinition)
          : formattedDefinition;
      }
    }
    word.definitions = formattedDefinitions;
  }
  return words;
}

app.get("/", async (req, res) => {
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
    const words = await collection.find({ date: today }).toArray();
    res.render("page", {
      words: processDefinitions(words),
      date: today,
      week: week,
      day: day,
      error: null,
    });
  } catch (error) {
    res.status(500).render("page", {
      words: [],
      date: today,
      week: week,
      day: day,
      error: error.message,
    });
  }
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
