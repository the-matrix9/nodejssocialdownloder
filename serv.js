/**
 * server.js — revangeapi (All-in-one Social Downloader + Terabox)
 *
 * Endpoints:
 *   - GET /revangeapi/download?url=...           -> Universal downloader (yt-dlp)
 *   - GET /revangeapi/terabox/download?url=...   -> Terabox proxy (your Cloudflare worker)
 *   - GET /                                       -> Swagger UI (full API docs)
 *
 * Run:
 *   npm init -y
 *   npm i express swagger-ui-express swagger-jsdoc yt-dlp-exec cors
 *   node server.js
 *
 * Tip (Deploy): Render/Railway/VPS पर चलाएँ; frontend/worker इस API को call करें.
 */

import express from "express";
import cors from "cors";
import fetch from "node-fetch";
import swaggerUi from "swagger-ui-express";
import swaggerJsdoc from "swagger-jsdoc";
import youtubedl from "yt-dlp-exec";

const app = express();
app.use(express.json());
app.use(cors());

// ---------- Config ----------
const APP_NAME = "revangeapi";

// Your Terabox backend base (append user url)
const TERABOX_BACKEND_BASE =
  "https://teraboxdownloderapi.revangeapi.workers.dev/?url=";

// ---------- Swagger (OpenAPI) ----------
const swaggerOptions = {
  definition: {
    openapi: "3.0.0",
    info: {
      title: "revangeapi · Social Media Downloader API",
      version: "1.0.0",
      description:
        "📥 Universal downloader (YouTube, TikTok, Twitter/X, Facebook, Reddit, etc.) via yt-dlp, plus a dedicated Terabox endpoint proxied to your Cloudflare Worker.",
      contact: { name: "revangeapi" },
    },
    servers: [
      { url: "https://nodejssocialdownloder.onrender.com/", description: "Local" },
      // Deploy होने पर अपने डोमेन को यहां जोड़ लें
    ],
    tags: [
      { name: "Universal", description: "All social sites via yt-dlp" },
      { name: "Terabox", description: "Terabox direct link generator (proxy)" },
    ],
    components: {
      schemas: {
        UniversalResponse: {
          type: "object",
          properties: {
            success: { type: "boolean" },
            site: { type: "string" },
            title: { type: "string" },
            thumbnail: { type: "string" },
            duration: { type: "number" },
            uploader: { type: "string" },
            formats: {
              type: "array",
              items: {
                type: "object",
                properties: {
                  quality: { type: "string" },
                  ext: { type: "string" },
                  filesize: { type: "number", nullable: true },
                  width: { type: "number", nullable: true },
                  height: { type: "number", nullable: true },
                  fps: { type: "number", nullable: true },
                  acodec: { type: "string", nullable: true },
                  vcodec: { type: "string", nullable: true },
                  url: { type: "string" },
                },
              },
            },
          },
          example: {
            success: true,
            site: "youtube",
            title: "Sample Video",
            thumbnail: "https://i.ytimg.com/vi/xxxx/maxresdefault.jpg",
            duration: 123,
            uploader: "Channel",
            formats: [
              {
                quality: "720p",
                ext: "mp4",
                filesize: 123456789,
                width: 1280,
                height: 720,
                fps: 30,
                acodec: "mp4a.40.2",
                vcodec: "avc1.64001F",
                url: "https://...",
              },
            ],
          },
        },
        TeraboxResponse: {
          type: "object",
          properties: {
            file_name: { type: "string" },
            directlink: { type: "string" },
            thumb: { type: "string" },
            size: { type: "string" },
            sizebytes: { type: "number" },
          },
          example: {
            file_name: "The Wandering Earth (2019) Subtitle Indonesia 720p.mp4",
            directlink:
              "https://d.terabox.app/file/....?expires=8h&region=dm",
            thumb:
              "https://dm-data.terabox.app/thumbnail/....&size=c850_u580",
            size: "726.66 MB",
            sizebytes: 761958949,
          },
        },
        ErrorResponse: {
          type: "object",
          properties: {
            success: { type: "boolean", example: false },
            error: { type: "string" },
          },
        },
      },
    },
    paths: {
      "/revangeapi/download": {
        get: {
          tags: ["Universal"],
          summary:
            "Fetch video/audio info & direct format URLs from any supported platform",
          parameters: [
            {
              in: "query",
              name: "url",
              required: true,
              schema: { type: "string" },
              description:
                "Public video URL (YouTube, TikTok, Twitter/X, Facebook, Reddit, etc.)",
              example: "https://www.youtube.com/watch?v=XXXX",
            },
          ],
          responses: {
            200: {
              description: "OK",
              content: {
                "application/json": {
                  schema: { $ref: "#/components/schemas/UniversalResponse" },
                },
              },
            },
            400: {
              description: "Missing/invalid params",
              content: {
                "application/json": {
                  schema: { $ref: "#/components/schemas/ErrorResponse" },
                },
              },
            },
            500: {
              description: "Extractor error",
              content: {
                "application/json": {
                  schema: { $ref: "#/components/schemas/ErrorResponse" },
                },
              },
            },
          },
        },
      },
      "/revangeapi/terabox/download": {
        get: {
          tags: ["Terabox"],
          summary:
            "Get direct Terabox file link via your Cloudflare Worker proxy",
          parameters: [
            {
              in: "query",
              name: "url",
              required: true,
              schema: { type: "string" },
              description: "Terabox share URL",
              example:
                "https://terabox.com/s/1kpYz6J8xalpQtoDk4DH8Aw?pwd=xxxx",
            },
          ],
          responses: {
            200: {
              description: "OK",
              content: {
                "application/json": {
                  schema: { $ref: "#/components/schemas/TeraboxResponse" },
                },
              },
            },
            400: {
              description: "Missing/invalid params",
              content: {
                "application/json": {
                  schema: { $ref: "#/components/schemas/ErrorResponse" },
                },
              },
            },
            502: {
              description: "Upstream (worker) error",
              content: {
                "application/json": {
                  schema: { $ref: "#/components/schemas/ErrorResponse" },
                },
              },
            },
          },
        },
      },
    },
  },
  apis: [], // (we’re defining the spec inline above)
};
const swaggerSpec = swaggerJsdoc(swaggerOptions);

// Serve Swagger UI at root
app.use("/", swaggerUi.serve, swaggerUi.setup(swaggerSpec, { explorer: true }));

// ---------- Helpers ----------
function mapFormats(info) {
  const out = [];
  const formats = Array.isArray(info.formats) ? info.formats : [];
  for (const f of formats) {
    if (!f || !f.url) continue;
    out.push({
      quality: f.format_note || String(f.format_id || ""),
      ext: f.ext || null,
      filesize: f.filesize ?? f.filesize_approx ?? null,
      width: f.width ?? null,
      height: f.height ?? null,
      fps: f.fps ?? null,
      acodec: f.acodec ?? null,
      vcodec: f.vcodec ?? null,
      url: f.url,
    });
  }
  // Prefer higher resolutions first (if width/height exist)
  out.sort((a, b) => (b.height || 0) - (a.height || 0));
  return out;
}

// ---------- Routes ----------

/**
 * GET /revangeapi/download?url=
 * Universal downloader via yt-dlp (supports 1000+ sites).
 */
app.get(`/${APP_NAME}/download`, async (req, res) => {
  try {
    const videoUrl = req.query.url?.trim();
    if (!videoUrl) {
      return res
        .status(400)
        .json({ success: false, error: "Missing query param: url" });
    }

    // yt-dlp-exec downloads & caches the binary automatically.
    const info = await youtubedl(videoUrl, {
      dumpSingleJson: true,
      // Helpful flags (safer defaults)
      noCheckCertificates: true,
      noWarnings: true,
      preferFreeFormats: true,
      // You can add cookies via headers/cookies file if needed in future.
    });

    const data = {
      success: true,
      site: info.extractor || null,
      title: info.title || null,
      thumbnail: info.thumbnail || null,
      duration: info.duration ?? null,
      uploader: info.uploader || null,
      formats: mapFormats(info),
    };
    return res.json(data);
  } catch (err) {
    return res
      .status(500)
      .json({ success: false, error: String(err?.stderr || err?.message || err) });
  }
});

/**
 * GET /revangeapi/terabox/download?url=
 * Proxies to your Cloudflare Worker terabox API and returns its JSON.
 */
app.get(`/${APP_NAME}/terabox/download`, async (req, res) => {
  try {
    const tbUrl = req.query.url?.trim();
    if (!tbUrl) {
      return res
        .status(400)
        .json({ success: false, error: "Missing query param: url" });
    }

    const upstream = `${TERABOX_BACKEND_BASE}${encodeURIComponent(tbUrl)}`;
    const r = await fetch(upstream, { timeout: 30000 });

    if (!r.ok) {
      const text = await r.text().catch(() => "");
      return res.status(502).json({
        success: false,
        error: `Upstream error (${r.status})`,
        detail: text.slice(0, 500),
      });
    }

    const json = await r.json();
    return res.json(json);
  } catch (err) {
    return res
      .status(502)
      .json({ success: false, error: String(err?.message || err) });
  }
});

// ---------- Start ----------
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`✅ ${APP_NAME} running at http://localhost:${PORT}`);
  console.log(`   • Docs:        GET /`);
  console.log(`   • Universal:   GET /${APP_NAME}/download?url=...`);
  console.log(`   • Terabox:     GET /${APP_NAME}/terabox/download?url=...`);
});
