import os, threading, time, base64
from flask import Flask, request, jsonify
from PIL import Image
import requests
import io
import qrcode

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

# ── Images tab ────────────────────────────────────────────────
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

# ── Ray Scanner рендер ────────────────────────────────────────
@app.route("/render", methods=["POST"])
def render():
    import traceback
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"ok": False, "error": "no json"}), 400

        width  = max(1, min(int(data.get("w",  40)), 200))
        height = max(1, min(int(data.get("h",  22)), 200))
        scale  = max(1, min(int(data.get("scale", 8)), 16))
        pixels = data.get("pixels", [])

        print(f"[render] {width}x{height} scale={scale} px={len(pixels)}")

        img_w = width  * scale
        img_h = height * scale
        img   = Image.new("RGB", (img_w, img_h), (8, 8, 16))

        for px in pixels:
            xi = int(px.get("xi", 0))
            yi = int(px.get("yi", 0))
            r  = max(0, min(255, int(float(px.get("r", 0)) * 255)))
            g  = max(0, min(255, int(float(px.get("g", 0)) * 255)))
            b  = max(0, min(255, int(float(px.get("b", 0)) * 255)))
            if 0 <= xi < width and 0 <= yi < height:
                block = Image.new("RGB", (scale, scale), (r, g, b))
                img.paste(block, (xi * scale, yi * scale))

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        print(f"[render] ok b64={len(b64)}")
        return jsonify({"ok": True, "b64": b64})

    except Exception as e:
        print(f"[render] ERROR: {traceback.format_exc()}")
        return jsonify({"ok": False, "error": str(e)}), 500

# ── QR Code ───────────────────────────────────────────────────
@app.route("/qr")
def qr_code():
    import traceback
    try:
        text = request.args.get("text", "").strip()
        if not text:
            return jsonify({"ok": False, "error": "text param missing"}), 400

        print(f"[qr] generating for: {text[:80]}")

        # генерируем QR
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=1,
            border=0,
        )
        qr.add_data(text)
        qr.make(fit=True)

        # получаем матрицу (список списков True/False)
        modules = qr.modules  # list of list of bool
        size = len(modules)

        # конвертируем в 0/1
        matrix = []
        for row in modules:
            matrix.append([1 if cell else 0 for cell in row])

        print(f"[qr] ok size={size}x{size}")
        return jsonify({
            "ok": True,
            "size": size,
            "matrix": matrix,
        })

    except Exception as e:
        print(f"[qr] ERROR: {traceback.format_exc()}")
        return jsonify({"ok": False, "error": str(e)}), 500

# ── Прочее ───────────────────────────────────────────────────
@app.route("/ping")
def ping():
    return "pong"

@app.route("/")
def index():
    return """
    <h2>LordHub Proxy OK</h2>
    <p>GET  /px?url=URL&w=32       — пиксели для Images tab</p>
    <p>POST /render                 — рейскан PNG</p>
    <p>GET  /qr?text=TEXT           — QR матрица</p>
    """
def keep_alive():
    time.sleep(30)
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
