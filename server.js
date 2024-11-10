import { serve } from "bun";
import { readFileSync } from "fs";
import { MongoClient } from "mongodb";

// Connect to mongo db
let client;
try {
  const uri =  `mongodb+srv://${process.env.MONGO_USR}:${process.env.MONGO_PWD}@ord.c8trc.mongodb.net/`;
  client = new MongoClient(uri);
} catch (error) {
  console.error("Failed to connect to MongoDB", error);
  process.exit(1);
}

async function getRandomWord() {
  try {
    await client.connect();
    const db = client.db("ord");
    const collection = db.collection("ord");

    let randomWord;
    let validDefinition = false;

    let count = 0;
    while (!validDefinition) {
      count++;
      console.log("Attempts to get word with definition", count);
      // Retrieve a random document from the collection
      randomWord = await collection.aggregate([{ $sample: { size: 1 } }]).toArray();

      if (randomWord.length > 0) {
        // Check if the word has a definitions array with an item of type "definition"
        const definitions = randomWord[0].definitions || [];
        const definitionObj = definitions.find(def => def.text != null);

        if (definitionObj) {
          // Found a valid word with a "definition" type
          validDefinition = true;
          const word = randomWord[0].word;
          const group = randomWord[0].group;
          const definition = definitionObj.text;
          console.log("Word with definition found:", randomWord[0]);

          return { word, definition, group };
        }
      }
    }

    // In case no valid word is found (though unlikely in a populated collection)
    return { word: "No words with definition found", definition: "", group: "" };
  } catch (error) {
    console.error("Error fetching data from MongoDB:", error);
    return { word: "Error fetching data", definition: "", group: "" };
  } finally {
    await client.close();
  }
}


const server = serve({
  port: 3000,
  async fetch(req) {
    const url = new URL(req.url);

    // Serve the page.html file when accessing the root path
    if (url.pathname === "/" || url.pathname === "/page.html") {
      try {
        const html = readFileSync("page.html", "utf8");
        return new Response(html, {
          headers: {
            "Content-Type": "text/html",
          },
        });
      } catch (error) {
        return new Response("File not found", { status: 404 });
      }
    }

    // Serve JSON data for the /data route
    if (url.pathname === "/data") {
      const wordData = await getRandomWord();
      console.log("Random word data:", wordData);
      return new Response(JSON.stringify(wordData), {
        headers: { "Content-Type": "application/json" },
      });
    }

    // Return 404 for other routes
    return new Response("Not Found", { status: 404 });
  },
});

console.log(`Server running at http://localhost:${server.port}`);
