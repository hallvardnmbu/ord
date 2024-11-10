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

async function getRandomWord(){
  try {
    await client.connect();
    const db = client.db("ord");
    const collection = db.collection("ord");

    // Retrieve a random document from the collection
    const randomWord = await collection.aggregate([{ $sample: { size: 1 } }]).toArray();
    console.log("Random word:", randomWord);


    // Check if we have a result and return the word data or a default message
    if (randomWord.length > 0) {
      const { word, description, group } = randomWord[0];
      return { word, description, group };
    } else {
      return { word: "No words found", meaning: "", type: "" };
    }
    } catch (error) {
    console.error("Error fetching data from MongoDB:", error);
    return { word: "Error fetching data", meaning: "", type: "" };
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
