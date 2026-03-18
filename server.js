import express from "express";
import fetch from "node-fetch";
import cors from "cors";

const app = express();

// ✅ CORS (THIS FIXES "Failed to fetch")
app.use(cors({
  origin: "*", // you can restrict later
  methods: ["GET", "POST", "OPTIONS"],
  allowedHeaders: ["Content-Type"]
}));

// Handle preflight requests explicitly
app.options("*", cors());

// Body parser
app.use(express.json({ limit: "100mb" }));

const PORT = process.env.PORT || 3000;

// ENV VARIABLES (set in Render)
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const OWNER = "kdidso";
const REPO = "ministering-distric-boundaries";
const BRANCH = "main";
const PATH_IN_REPO = "incoming/district_cells.geojson";
const APP_SECRET = process.env.APP_SECRET;

// Health check
app.get("/", (req, res) => {
  res.send("Backend is running");
});

// Main endpoint
app.post("/save-districts", async (req, res) => {
  try {
    console.log("Incoming request to /save-districts");

    const { geojson, secret } = req.body;

    if (secret !== APP_SECRET) {
      console.log("❌ Unauthorized: bad secret");
      return res.status(401).json({ error: "Unauthorized" });
    }

    if (!geojson) {
      console.log("❌ Missing geojson");
      return res.status(400).json({ error: "Missing geojson" });
    }

    let sha;

    // Check if file already exists
    const getResp = await fetch(
      `https://api.github.com/repos/${OWNER}/${REPO}/contents/${PATH_IN_REPO}?ref=${BRANCH}`,
      {
        headers: {
          Authorization: `Bearer ${GITHUB_TOKEN}`,
          Accept: "application/vnd.github+json"
        }
      }
    );

    if (getResp.ok) {
      const existing = await getResp.json();
      sha = existing.sha;
      console.log("Existing file found, will overwrite");
    } else {
      console.log("No existing file, creating new");
    }

    // Encode GeoJSON
    const contentString = JSON.stringify(geojson, null, 2);
    const contentBase64 = Buffer.from(contentString).toString("base64");

    // Upload to GitHub
    const putResp = await fetch(
      `https://api.github.com/repos/${OWNER}/${REPO}/contents/${PATH_IN_REPO}`,
      {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${GITHUB_TOKEN}`,
          Accept: "application/vnd.github+json",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: "Upload district cells GeoJSON",
          content: contentBase64,
          branch: BRANCH,
          sha
        })
      }
    );

    if (!putResp.ok) {
      const text = await putResp.text();
      console.log("❌ GitHub upload failed:", text);
      return res.status(500).json({ error: text });
    }

    console.log("✅ Successfully saved GeoJSON to GitHub");

    return res.json({ success: true });

  } catch (err) {
    console.log("❌ Server error:", err);
    return res.status(500).json({ error: String(err) });
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
