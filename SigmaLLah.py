"""
LordHub Image Proxy Server
Конвертирует изображение по URL в JSON пикселей для Image Loader

Установка:
    pip install flask pillow requests

Запуск:
    python lordhub_img_proxy.py

Сервер запустится на http://localhost:5000
Для публичного доступа используй ngrok:
    ngrok http 5000
"""

from flask import Flask, request, jsonify
from PIL import Image
import requests
import io

app = Flask(__name__)

@app.route("/px")
def pixels():
    url = request.args.get("url", "")
    w   = int(request.args.get("w", 32))
    w   = max(1, min(w, 128))  # лимит 128 блоков

    if not url:
        return jsonify({"error": "url param missing"}), 400

    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Масштабируем с сохранением пропорций
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
    return """
    <h2>LordHub Image Proxy</h2>
    <p>Использование: <code>/px?url=URL_КАРТИНКИ&w=32</code></p>
    <p>w = ширина в блоках (1-128)</p>
    <p>Пример: <a href="/px?url=https://i.imgur.com/example.png&w=32">/px?url=...&w=32</a></p>
    """

if __name__ == "__main__":
    print("=" * 50)
    print("LordHub Image Proxy запущен!")
    print("Локальный URL: http://localhost:5000/px?url=")
    print("Для публичного доступа: ngrok http 5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
