"""
server.py — revangeapi (All-in-one Social Downloader + Terabox)

Endpoints:
  - GET /revangeapi/download?url=...           -> Universal downloader (yt-dlp, Instagram auto: no-cookies + fallback cookies)
  - GET /revangeapi/terabox/download?url=...   -> Terabox proxy (your Cloudflare worker)
  - GET /                                       -> Swagger UI (full API docs)

Run (local):
  pip install -r requirements.txt
  python server.py

Tip (Deploy): Render/Railway/VPS पर चलाएँ; frontend/worker इस API को call करें.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
import subprocess
import json
import requests
import tempfile
import os
from urllib.parse import quote

# ---------- Config ----------
APP_NAME = "revangeapi"

TERABOX_BACKEND_BASE = "https://teraboxdownloderapi.revangeapi.workers.dev/?url="

# ---------- YouTube/yt-dlp Cookies (embedded) ----------
YTDLP_COOKIES = r"""# Netscape HTTP Cookie File
# http://curl.haxx.se/rfc/cookie_spec.html
# This is a generated file!  Do not edit.

.youtube.com	TRUE	/	FALSE	1790243776	HSID	xxxx
.youtube.com	TRUE	/	TRUE	1790243776	SSID	xxxx
"""

# ---------- Flask ----------
app = Flask(__name__)
CORS(app)

# ---------- Swagger (UI at "/") ----------
swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "revangeapi · Social Media Downloader API",
        "version": "1.0.0",
        "description": (
            "📥 Universal downloader (YouTube, TikTok, Twitter/X, Facebook, Reddit, Instagram, etc.) via yt-dlp.\n\n"
            "Servers:\n"
            " - http://localhost:5000 (Local Dev)\n"
            " - https://nodejssocialdownloder.onrender.com (Render Deploy)\n"
        ),
        "contact": {"name": "revangeapi"},
    },
    "host": "localhost:5000",
    "basePath": "/",
    "tags": [
        {"name": "Universal", "description": "All social sites via yt-dlp"},
        {"name": "Terabox", "description": "Terabox direct link generator (proxy)"},
    ],
    "definitions": {
        "Format": {
            "type": "object",
            "properties": {
                "quality": {"type": "string"},
                "ext": {"type": "string"},
                "filesize": {"type": "number"},
                "width": {"type": "number"},
                "height": {"type": "number"},
                "fps": {"type": "number"},
                "acodec": {"type": "string"},
                "vcodec": {"type": "string"},
                "url": {"type": "string"},
            },
        },
        "UniversalResponse": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "site": {"type": "string"},
                "title": {"type": "string"},
                "thumbnail": {"type": "string"},
                "duration": {"type": "number"},
                "uploader": {"type": "string"},
                "formats": {"type": "array", "items": {"$ref": "#/definitions/Format"}},
            },
        },
        "ErrorResponse": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": False},
                "error": {"type": "string"},
                "detail": {"type": "string"},
            },
        },
    },
    "schemes": ["http", "https"],
}
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec_1",
            "route": "/apispec_1.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/",  # Root पर Swagger UI
}
Swagger(app, template=swagger_template, config=swagger_config)

# ---------- Helpers ----------
def map_formats(info):
    out = []
    formats = info.get("formats", []) or []
    for f in formats:
        if not f or not f.get("url"):
            continue
        out.append({
            "quality": f.get("format_note") or str(f.get("format_id") or ""),
            "ext": f.get("ext"),
            "filesize": f.get("filesize") if f.get("filesize") is not None else f.get("filesize_approx"),
            "width": f.get("width"),
            "height": f.get("height"),
            "fps": f.get("fps"),
            "acodec": f.get("acodec"),
            "vcodec": f.get("vcodec"),
            "url": f.get("url"),
        })
    out.sort(key=lambda x: x.get("height") or 0, reverse=True)
    return out

def run_ytdlp(url: str, use_cookies=True):
    cookie_file = None
    cmd = [
        "yt-dlp",
        "-j",
        "--no-warnings",
        "--no-check-certificates",
    ]

    if use_cookies:
        with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt", encoding="utf-8") as tf:
            tf.write(YTDLP_COOKIES)
            cookie_file = tf.name
        cmd += ["--cookies", cookie_file]

    cmd.append(url)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        stdout = result.stdout.strip()
        try:
            info = json.loads(stdout.splitlines()[-1])
        except Exception:
            info = json.loads(stdout)
        return info
    finally:
        if cookie_file:
            try:
                if os.path.exists(cookie_file):
                    os.remove(cookie_file)
            except Exception:
                pass

# ---------- Routes ----------

@app.route(f"/{APP_NAME}/download", methods=["GET"])
def universal_download():
    video_url = (request.args.get("url") or "").strip()
    if not video_url:
        return jsonify({"success": False, "error": "Missing query param: url"}), 400

    try:
        # Instagram special handling
        if "instagram.com" in video_url.lower():
            try:
                info = run_ytdlp(video_url, use_cookies=False)  # try without cookies
            except Exception:
                info = run_ytdlp(video_url, use_cookies=True)   # fallback with cookies
        else:
            info = run_ytdlp(video_url, use_cookies=True)

        data = {
            "success": True,
            "site": info.get("extractor"),
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "formats": map_formats(info),
        }
        return jsonify(data)
    except subprocess.CalledProcessError as e:
        return jsonify({"success": False, "error": e.stderr or str(e)}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route(f"/{APP_NAME}/terabox/download", methods=["GET"])
def terabox_download():
    tb_url = (request.args.get("url") or "").strip()
    if not tb_url:
        return jsonify({"success": False, "error": "Missing query param: url"}), 400

    upstream = f"{TERABOX_BACKEND_BASE}{quote(tb_url, safe='')}"
    try:
        r = requests.get(upstream, timeout=30)
        if not r.ok:
            return jsonify({
                "success": False,
                "error": f"Upstream error ({r.status_code})",
                "detail": (r.text or "")[:500],
            }), 502
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 502

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "name": APP_NAME})

# ---------- Start ----------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"✅ {APP_NAME} running at http://localhost:{port}")
    print(f"   • Docs:        GET /")
    print(f"   • Universal:   GET /{APP_NAME}/download?url=...")
    print(f"   • Terabox:     GET /{APP_NAME}/terabox/download?url=...")
    app.run(host="0.0.0.0", port=port)
