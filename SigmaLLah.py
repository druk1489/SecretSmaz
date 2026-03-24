import os, threading, time, base64, uuid
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

# ── Старый роут ───────────────────────────────────────────────
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

# ── Новый роут /render ────────────────────────────────────────
# Принимает JSON: {w, h, scale, pixels: [{xi,yi,r,g,b},...]}
# Возвращает PNG как base64
@app.route("/render", methods=["POST"])
def render():
    try:
        data   = request.get_json(force=True)
        width  = int(data.get("w", 40))
        height = int(data.get("h", 22))
        scale  = int(data.get("scale", 8))
        pixels = data.get("pixels", [])

        # Ограничения чтобы сервер не умер
        width  = max(1, min(width,  200))
        height = max(1, min(height, 200))
        scale  = max(1, min(scale,  16))

        img_w = width  * scale
        img_h = height * scale

        img = Image.new("RGB", (img_w, img_h), (8, 8, 16))

        for px in pixels:
            xi = int(px.get("xi", 0))
            yi = int(px.get("yi", 0))
            r  = max(0, min(255, int(float(px.get("r", 0)) * 255)))
            g  = max(0, min(255, int(float(px.get("g", 0)) * 255)))
            b  = max(0, min(255, int(float(px.get("b", 0)) * 255)))

            x0 = xi * scale
            y0 = yi * scale
            x1 = x0 + scale
            y1 = y0 + scale

            # Быстрая заливка прямоугольника через paste
            block = Image.new("RGB", (scale, scale), (r, g, b))
            img.paste(block, (x0, y0, x1, y1))

        # PNG → base64
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        return jsonify({
            "ok":     True,
            "b64":    b64,
            "width":  img_w,
            "height": img_h,
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── Роут /renderwh — отправляет сразу в Discord webhook ───────
# Принимает JSON: {w, h, scale, pixels, webhook, reason, player, position}
@app.route("/renderwh", methods=["POST"])
def renderwh():
    try:
        data       = request.get_json(force=True)
        width      = int(data.get("w", 40))
        height     = int(data.get("h", 22))
        scale      = int(data.get("scale", 8))
        pixels     = data.get("pixels", [])
        webhook    = data.get("webhook", "")
        reason     = data.get("reason", "scan")
        player     = data.get("player", "Unknown")
        position   = data.get("position", "0, 0, 0")

        if not webhook:
            return jsonify({"ok": False, "error": "no webhook"}), 400

        width  = max(1, min(width,  200))
        height = max(1, min(height, 200))
        scale  = max(1, min(scale,  16))

        img_w = width  * scale
        img_h = height * scale

        img = Image.new("RGB", (img_w, img_h), (8, 8, 16))

        for px in pixels:
            xi = int(px.get("xi", 0))
            yi = int(px.get("yi", 0))
            r  = max(0, min(255, int(float(px.get("r", 0)) * 255)))
            g  = max(0, min(255, int(float(px.get("g", 0)) * 255)))
            b  = max(0, min(255, int(float(px.get("b", 0)) * 255)))
            block = Image.new("RGB", (scale, scale), (r, g, b))
            img.paste(block, (xi*scale, yi*scale, xi*scale+scale, yi*scale+scale))

        # Сохраняем в буфер
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        png_bytes = buf.getvalue()

        # Отправляем в Discord как файл + embed
        import json as json_mod
        payload = {
            "embeds": [{
                "title":       "📷 Lord Hub Ray Scan",
                "color":       0x64A0FF,
                "image":       {"url": "attachment://scan.png"},
                "fields": [
                    {"name": "Reason",   "value": reason,   "inline": True},
                    {"name": "Player",   "value": player,   "inline": True},
                    {"name": "Position", "value": position, "inline": True},
                    {"name": "Size",     "value": f"{width}x{height} ({img_w}x{img_h}px)", "inline": True},
                ],
                "footer": {"text": "Lord Hub Scanner"},
            }]
        }

        resp = requests.post(
            webhook,
            files={
                "file":    ("scan.png", png_bytes, "image/png"),
                "payload_json": (None, json_mod.dumps(payload), "application/json"),
            },
            timeout=15,
        )

        if resp.status_code in (200, 204):
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": False, "error": resp.text}), 500

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── Прочее ────────────────────────────────────────────────────
@app.route("/ping")
def ping():
    return "pong"

@app.route("/")
def index():
    return """
    <h2>LordHub Proxy OK</h2>
    <p>GET  /px?url=URL&w=32 — пиксели изображения</p>
    <p>POST /render — {w,h,scale,pixels} → PNG base64</p>
    <p>POST /renderwh — {w,h,scale,pixels,webhook,...} → PNG в Discord</p>
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
