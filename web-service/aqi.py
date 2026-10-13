"""Учебный эмулятор: значения не являются измерениями или прогнозом."""
import hashlib
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs


def simulate(latitude, longitude):
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError("Координаты должны быть конечными числами")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("Широта: от −90 до 90; долгота: от −180 до 180")
    digest = hashlib.sha256(f"{latitude:.6f},{longitude:.6f}".encode()).digest()
    aqi = int.from_bytes(digest[:2], "big") % 301
    category = next(label for upper, label in [(50, "Хороший"), (100, "Умеренный"),
        (150, "Неблагоприятный для чувствительных групп"), (200, "Неблагоприятный"),
        (300, "Очень неблагоприятный"), (500, "Опасный")] if aqi <= upper)
    return {"aqi": aqi, "category": category, "source": "Учебный эмулятор AQI", "simulated": True}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        try:
            if url.path == "/health":
                status, data = 200, {"status": "ok"}
            elif url.path == "/aqi":
                q = parse_qs(url.query)
                status, data = 200, simulate(float(q["latitude"][0]), float(q["longitude"][0]))
            else:
                status, data = 404, {"error": "Маршрут не найден"}
        except (ValueError, KeyError):
            status, data = 400, {"error": "Некорректные координаты"}
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8001), Handler).serve_forever()
