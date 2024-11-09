import { serve } from "bun";
import { readFileSync } from "fs";

const server = serve({
  port: 3000,
  fetch(req) {
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

    // Return 404 for other routes
    return new Response("Not Found", { status: 404 });
  },
});

console.log(`Server running at http://localhost:${server.port}`);
