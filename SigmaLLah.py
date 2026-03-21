import os
from flask import Flask, request, jsonify
from PIL import Image
import requests
import io

app = Flask(__name__)

@app.route("/px")
def pixels():
    url = request.args.get("url", "")
    w   = int(request.args.get("w", 32))
    w   = max(1, min(w, 128))

    if not url:
        return jsonify({"error": "url param missing"}), 400

    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    orig_w, orig_h = img.size
    h = max(1, round(w * orig_h / orig_w))
    img = img.resize((w, h), Image.LANCZOS)

    pixels_out = []
    for y in range(h):
        for x in range(w):
            r, g, b = img.getpixel((x, y))
            pixels_out.append([r, g, b])

    return jsonify({"w": w, "h": h, "pixels": pixels_out})

@app.route("/")
def index():
    return "<h2>LordHub Image Proxy OK</h2><p>/px?url=URL&w=32</p>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
