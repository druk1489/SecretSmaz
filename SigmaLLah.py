import os, threading, time
from flask import Flask, request, jsonify
from PIL import Image
import requests
import io

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

@app.route("/px")
def pixels():
    url = request.args.get("url", "").strip()
    w   = int(request.args.get("w", 32))
    w   = max(1, min(w, 128))

    if not url:
        return jsonify({"error": "url param missing"}), 400

    try:
        resp = requests.get(url, timeout=15, headers=HEADERS, allow_redirects=True)
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

@app.route("/ping")
def ping():
    return "pong"

@app.route("/")
def index():
    return "<h2>LordHub Image Proxy OK</h2><p>/px?url=URL&w=32</p>"

# Пингуем себя каждые 14 минут чтобы не засыпать
def keep_alive():
    time.sleep(30)  # ждём пока сервер стартует
    own_url = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:5000")
    while True:
        try:
            requests.get(f"{own_url}/ping", timeout=5)
        except:
            pass
        time.sleep(14 * 60)

threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
