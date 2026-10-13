import json
import logging
import math
import os
import re
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, urlencode
import psycopg
from psycopg.rows import dict_row
from aqi import simulate

logging.basicConfig(level=logging.INFO)


def connect():
    return psycopg.connect(host=os.environ['DB_HOST'], dbname=os.environ['DB_NAME'],
        user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'],
        connect_timeout=5, row_factory=dict_row)


def zone_fields(data):
    name = data.get('name')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError('Название зоны должно содержать от 1 до 100 символов')
    if isinstance(data.get('latitude'), bool) or isinstance(data.get('longitude'), bool):
        raise ValueError('Координаты должны быть числами')
    try:
        lat, lon = float(data['latitude']), float(data['longitude'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('Укажите числовые координаты')
    if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Широта: от −90 до 90; долгота: от −180 до 180')
    return name.strip(), lat, lon


class Handler(BaseHTTPRequestHandler):
    def do_GET(self): self.handle_api('GET')
    def do_POST(self): self.handle_api('POST')
    def do_PUT(self): self.handle_api('PUT')
    def do_DELETE(self): self.handle_api('DELETE')

    def body(self):
        size = int(self.headers.get('Content-Length', 0))
        if not 0 < size <= 8192:
            raise ValueError('Некорректный размер запроса')
        data = json.loads(self.rfile.read(size))
        if not isinstance(data, dict):
            raise ValueError('Ожидается JSON-объект')
        return data

    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_api(self, method):
        path = urlparse(self.path).path
        try:
            with connect() as db:
                if method == 'GET' and path == '/health':
                    db.execute('SELECT 1')
                    return self.reply(200, {'status': 'ok', 'mode': 'separate-service' if os.getenv('AQI_SERVICE_URL') else 'embedded-emulator'})
                if method == 'GET' and path == '/api/zones':
                    rows = db.execute('''SELECT z.*, m.aqi, m.category, m.source, m.checked_at
                        FROM zones z LEFT JOIN LATERAL
                        (SELECT * FROM measurements WHERE zone_id=z.id ORDER BY id DESC LIMIT 1) m ON true
                        ORDER BY z.id''').fetchall()
                    return self.reply(200, rows)
                if method == 'GET' and path == '/api/history':
                    return self.reply(200, db.execute('''SELECT m.*, z.name, z.latitude, z.longitude
                        FROM measurements m JOIN zones z ON z.id=m.zone_id
                        ORDER BY m.id DESC LIMIT 100''').fetchall())
                if method == 'POST' and path == '/api/zones':
                    values = zone_fields(self.body())
                    row = db.execute('INSERT INTO zones(name,latitude,longitude) VALUES (%s,%s,%s) RETURNING *', values).fetchone()
                    db.commit()
                    return self.reply(201, row)
                match = re.fullmatch(r'/api/zones/(\d+)(/check)?', path)
                if match:
                    zone_id, check = int(match[1]), match[2]
                    zone = db.execute('SELECT * FROM zones WHERE id=%s', (zone_id,)).fetchone()
                    if not zone: return self.reply(404, {'error': 'Зона не найдена'})
                    if method == 'POST' and check:
                        url = os.getenv('AQI_SERVICE_URL')
                        if url:
                            query = urlencode({'latitude': zone['latitude'], 'longitude': zone['longitude']})
                            try:
                                with urllib.request.urlopen(f'{url}/aqi?{query}', timeout=5) as response:
                                    result = json.load(response)
                            except Exception:
                                logging.exception('AQI service unavailable')
                                return self.reply(502, {'error': 'Сервис AQI недоступен. Попробуйте позже.'})
                        else:
                            result = simulate(zone['latitude'], zone['longitude'])
                        row = db.execute('''INSERT INTO measurements(zone_id,aqi,category,source)
                            VALUES (%s,%s,%s,%s) RETURNING *''',
                            (zone_id, result['aqi'], result['category'], result['source'])).fetchone()
                        db.commit()
                        return self.reply(201, {**row, 'name': zone['name'], 'simulated': True})
                    if method == 'PUT' and not check:
                        values = zone_fields(self.body())
                        if values[1:] != (zone['latitude'], zone['longitude']):
                            raise ValueError('Для других координат создайте новую зону: история привязана к месту')
                        row = db.execute('UPDATE zones SET name=%s WHERE id=%s RETURNING *', (values[0], zone_id)).fetchone()
                        db.commit()
                        return self.reply(200, row)
                    if method == 'DELETE' and not check:
                        db.execute('DELETE FROM zones WHERE id=%s', (zone_id,))
                        db.commit()
                        return self.reply(200, {'deleted': zone_id})
                return self.reply(404, {'error': 'Маршрут не найден'})
        except (ValueError, UnicodeDecodeError) as exc:
            self.reply(400, {'error': str(exc)})
        except psycopg.Error:
            logging.exception('Database error')
            self.reply(503, {'error': 'База данных недоступна. Попробуйте позже.'})
        except Exception:
            logging.exception('Unexpected error')
            self.reply(500, {'error': 'Внутренняя ошибка сервера'})


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
