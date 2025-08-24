"""
server.py — revangeapi (All-in-one Social Downloader + Terabox)

Endpoints:
  - GET /revangeapi/download?url=...           -> Universal downloader (yt-dlp)
  - GET /revangeapi/terabox/download?url=...   -> Terabox proxy (your Cloudflare worker)
  - GET /                                       -> Swagger UI (full API docs)

Run (local):
  pip install -r requirements.txt
  python server.py

Tip (Deploy): Render/Railway/VPS पर चलाएँ; frontend/worker इस API को call करें.
"""

from flask import Flask, request, jsonify, redirect
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

# Your Terabox backend base (append user url)
TERABOX_BACKEND_BASE = "https://teraboxdownloderapi.revangeapi.workers.dev/?url="

# ---------- YouTube/yt-dlp Cookies (embedded) ----------
# ⚠️ आप जो cookies दोगे, वही पास होंगे; ये वही हैं जो आपने भेजे थे.
YTDLP_COOKIES = r"""# Netscape HTTP Cookie File
# http://curl.haxx.se/rfc/cookie_spec.html
# This is a generated file!  Do not edit.

.youtube.com	TRUE	/	FALSE	1790243776	HSID	AHI19-pRZmB8yQ9ST
.youtube.com	TRUE	/	TRUE	1790243776	SSID	A-pLqiAuyz8V5LVFI
.youtube.com	TRUE	/	FALSE	1790243776	APISID	0pHa12CXa5GRKTco/ALXQ3KF1rCJsUgghj
.youtube.com	TRUE	/	TRUE	1790243776	SAPISID	K6vPt3W6T83NLmPK/AxTdOYAaJKl3AVgLM
.youtube.com	TRUE	/	TRUE	1790243776	__Secure-1PAPISID	K6vPt3W6T83NLmPK/AxTdOYAaJKl3AVgLM
.youtube.com	TRUE	/	TRUE	1790243776	__Secure-3PAPISID	K6vPt3W6T83NLmPK/AxTdOYAaJKl3AVgLM
.youtube.com	TRUE	/	TRUE	1783231114	LOGIN_INFO	AFmmF2swRgIhAIs0L0gYORkajT_Te1jC9bwNtbg2W7ZYyGwtYdBoyhuPAiEApBBsqCxoKdazwIhdccRvZ9sKB7RG7h7sgBAxZH-ikns:QUQ3MjNmeEktNDZjV3kzMjI0ZkdGdWMwbWNDQ3p1RDNYcER5T3VlS09oSzVpdVE2OHM5M3VFUlAzNlNfVXo2YXhfb3ZtOU96ci1Nbk4tRGtoYXNzNVhMNDVIMlgwQnM0SGN5Nkd5c09qNDdjRFR5T21sVXlaYkZJWlI4NThjSVg3MFlweUtVQ3UzNWRMSzIyRXd3RkI1NWZHMTJ5a0JkWEVn
.youtube.com	TRUE	/	FALSE	1756690679	_gcl_au	1.1.8000727.1748914679
.youtube.com	TRUE	/	TRUE	1790562356	PREF	f7=100&tz=America.Los_Angeles&repeat=NONE&autoplay=true
.youtube.com	TRUE	/	FALSE	1790243776	SID	g.a0000Qi6mYHbWfL-Wswg1CPYnJRaX3CkK3Kn0XcWHd4_BfTbq59HKba8AtKtt5qo8LD9p_LNpQACgYKAWcSARUSFQHGX2MirU48Is1SlB80xeDSTZpgYxoVAUF8yKoYYX16k-qsyHjWURkte_V50076
.youtube.com	TRUE	/	TRUE	1790243776	__Secure-1PSID	g.a0000Qi6mYHbWfL-Wswg1CPYnJRaX3CkK3Kn0XcWHd4_BfTbq59HNzJWO8obrgkJlNYmldOoqgACgYKAa0SARUSFQHGX2MiKPXoj0kt_TX82tziv1OpvhoVAUF8yKrY_0yG_3htJ3yPnc8dum1H0076
.youtube.com	TRUE	/	TRUE	1790243776	__Secure-3PSID	g.a0000Qi6mYHbWfL-Wswg1CPYnJRaX3CkK3Kn0XcWHd4_BfTbq59Hba92GlazRye7iD7l7f4JxwACgYKAW8SARUSFQHGX2MidNgUrVRRIkHoO2oBUKyUTRoVAUF8yKq0XEgcmZbcOx2B2_SWu7cq0076
.youtube.com	TRUE	/	TRUE	1787538363	__Secure-1PSIDTS	sidts-CjEB5H03PzPxW7ep-JsxOXscQBbymbyDN1e3d-Ul7EsIrOxwnTw0TuCtDVy9kErzgSqWEAA
.youtube.com	TRUE	/	TRUE	1787538363	__Secure-3PSIDTS	sidts-CjEB5H03PzPxW7ep-JsxOXscQBbymbyDN1e3d-Ul7EsIrOxwnTw0TuCtDVy9kErzgSqWEAA
.youtube.com	TRUE	/	FALSE	1787538366	SIDCC	AKEyXzUQg5LSCx1Bl9TwtcSUMchCd_wiswGjt5U_O1U3igRWhj7_VqYyXxiscT8usyOehPG9hQ
.youtube.com	TRUE	/	TRUE	1787538366	__Secure-1PSIDCC	AKEyXzXc8eawJt2v9fN6q2VopiapELsHs3LAp5WQoWjN2sq0YMPyLLpbgKzs11wTsUPvM9k08qY
.youtube.com	TRUE	/	TRUE	1787538366	__Secure-3PSIDCC	AKEyXzXQ5sS7NNEukcjFl1hX94ZoQuv2gr81OqJptIu7VT31oCYeGTb-4B9RkyXBZvoQut9CLhc
.youtube.com	TRUE	/	TRUE	1771554351	VISITOR_INFO1_LIVE	3rtGQjt3kP8
.youtube.com	TRUE	/	TRUE	1771554351	VISITOR_PRIVACY_METADATA	CgJJThIEGgAgBw%3D%3D
.youtube.com	TRUE	/	TRUE	1771492784	__Secure-ROLLOUT_TOKEN	CNi_mfSS2MTIERCv8taL2qWNAxjO9_CVzaCPAw%3D%3D
.youtube.com	TRUE	/	TRUE	0	YSC	AoexCALP8qs
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
            "📥 Universal downloader (YouTube, TikTok, Twitter/X, Facebook, Reddit, etc.) via yt-dlp, "
            "plus a dedicated Terabox endpoint proxied to your Cloudflare Worker.\n\n"
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
            "example": {
                "success": True,
                "site": "youtube",
                "title": "Sample Video",
                "thumbnail": "https://i.ytimg.com/vi/xxxx/maxresdefault.jpg",
                "duration": 123,
                "uploader": "Channel",
                "formats": [
                    {
                        "quality": "720p",
                        "ext": "mp4",
                        "filesize": 123456789,
                        "width": 1280,
                        "height": 720,
                        "fps": 30,
                        "acodec": "mp4a.40.2",
                        "vcodec": "avc1.64001F",
                        "url": "https://...",
                    }
                ],
            },
        },
        "TeraboxResponse": {
            "type": "object",
            "properties": {
                "file_name": {"type": "string"},
                "directlink": {"type": "string"},
                "thumb": {"type": "string"},
                "size": {"type": "string"},
                "sizebytes": {"type": "number"},
            },
            "example": {
                "file_name": "The Wandering Earth (2019) Subtitle Indonesia 720p.mp4",
                "directlink": "https://d.terabox.app/file/....?expires=8h&region=dm",
                "thumb": "https://dm-data.terabox.app/thumbnail/....&size=c850_u580",
                "size": "726.66 MB",
                "sizebytes": 761958949,
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


def run_ytdlp(url: str):
    # cookies temp file बनाते हैं
    with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt", encoding="utf-8") as tf:
        tf.write(YTDLP_COOKIES)
        cookie_file = tf.name

    try:
        cmd = [
            "yt-dlp",
            "-j",  # dumpSingleJson
            "--no-warnings",
            "--no-check-certificates",
            "--cookies", cookie_file,
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # yt-dlp कभी-कभी कई JSON lines देता है; पहले valid JSON को पकड़ो
        stdout = result.stdout.strip()
        # अगर multiple lines हैं, आखिरी json अक्सर main वीडियो का होता है
        try:
            info = json.loads(stdout.splitlines()[-1])
        except Exception:
            info = json.loads(stdout)
        return info
    finally:
        try:
            if os.path.exists(cookie_file):
                os.remove(cookie_file)
        except Exception:
            pass

# ---------- Routes ----------

@app.route(f"/{APP_NAME}/download", methods=["GET"])
def universal_download():
    """
    Universal Social Downloader (yt-dlp)
    ---
    tags:
      - Universal
    parameters:
      - name: url
        in: query
        type: string
        required: true
        description: Public video URL (YouTube, TikTok, Twitter/X, Facebook, Reddit, etc.)
        example: https://www.youtube.com/watch?v=XXXX
    responses:
      200:
        description: OK
        schema:
          $ref: "#/definitions/UniversalResponse"
      400:
        description: Missing/invalid params
        schema:
          $ref: "#/definitions/ErrorResponse"
      500:
        description: Extractor error
        schema:
          $ref: "#/definitions/ErrorResponse"
    """
    video_url = (request.args.get("url") or "").strip()
    if not video_url:
        return jsonify({"success": False, "error": "Missing query param: url"}), 400

    try:
        info = run_ytdlp(video_url)
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
    """
    Terabox Proxy Downloader (Cloudflare Worker upstream)
    ---
    tags:
      - Terabox
    parameters:
      - name: url
        in: query
        type: string
        required: true
        description: Terabox share URL
        example: https://terabox.com/s/1kpYz6J8xalpQtoDk4DH8Aw?pwd=xxxx
    responses:
      200:
        description: OK
        schema:
          $ref: "#/definitions/TeraboxResponse"
      400:
        description: Missing/invalid params
        schema:
          $ref: "#/definitions/ErrorResponse"
      502:
        description: Upstream (worker) error
        schema:
          $ref: "#/definitions/ErrorResponse"
    """
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


# Optional: keep /health for quick checks
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
