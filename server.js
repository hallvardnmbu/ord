import { serve } from "bun";
import { MongoClient } from "mongodb";
import ejs from "ejs";

const CLIENT = new MongoClient(
  `mongodb+srv://${process.env.MONGO_USR}:${process.env.MONGO_PWD}` +
    "@ord.c8trc.mongodb.net/" +
    "?retryWrites=true&w=majority&appName=ord",
);
await CLIENT.connect();
const COLLECTION = CLIENT.db("ord").collection("ord");

const server = serve({
  port: 3000,
  async fetch(req) {
    const url = new URL(req.url);

    if (url.pathname === "/" || url.pathname === "/page.html") {
      try {
        const words = await COLLECTION.find({}).limit(1).toArray();
        const html = await ejs.renderFile("page.ejs", { words, error: null });
        return new Response(html, {
          headers: {
            "Content-Type": "text/html",
          },
        });
      } catch (error) {
        const html = await ejs.renderFile("page.ejs", {
          words: [],
          error: error.message,
        });
        return new Response(html, {
          headers: { "Content-Type": "text/html" },
          status: 500,
        });
      }
    } else if (url.pathname === "/style.css") {
      try {
        const css = await Bun.file("style.css").text();
        return new Response(css, {
          headers: {
            "Content-Type": "text/css",
          },
        });
      } catch (error) {
        return new Response("CSS file not found", { status: 404 });
      }
    }
    return new Response("Not found.", { status: 404 });
  },
});

console.log(`Server running at http://localhost:${server.port}`);
