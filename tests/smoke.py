"""Интеграционная проверка запущенного приложения. Только стандартная библиотека."""
import json
import os
import urllib.request
from urllib.error import HTTPError
BASE = os.getenv('APP_URL', 'http://127.0.0.1:8080')


def request(path, method='GET', data=None, expected=200):
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(BASE + '/api' + path, data=body, method=method,
        headers={'Content-Type': 'application/json'})
    try:
        response = urllib.request.urlopen(req, timeout=15)
    except HTTPError as exc:
        response = exc
    with response:
        assert response.status == expected, (path, response.status, response.read())
        return json.load(response)


zones = request('/zones')
assert len(zones) >= 3
zone = request('/zones', 'POST', {'name':'Тестовая зона', 'latitude':55.75, 'longitude':37.61}, 201)
zid = zone['id']
try:
    measurement = request(f'/zones/{zid}/check','POST',expected=201)
    assert 0 <= measurement['aqi'] <= 500 and measurement['simulated'] is True
    history = request('/history')
    assert any(m['id'] == measurement['id'] and m['zone_id'] == zid for m in history)
    current = next(z for z in request('/zones') if z['id'] == zid)
    assert current['aqi'] == measurement['aqi']
    updated = request(f'/zones/{zid}','PUT',{**zone,'name':'Переименованная зона'})
    assert updated['name'] == 'Переименованная зона'
    request(f'/zones/{zid}','PUT',{**zone,'latitude':10},400)
    request('/zones','POST',{'name':'Ошибка','latitude':91,'longitude':0},400)
    request('/zones','POST',{'name':'Ошибка','latitude':float('nan'),'longitude':0},400)
    request('/zones','POST',{'name':'   ','latitude':0,'longitude':0},400)
    request('/zones/99999999/check','POST',expected=404)
finally:
    request(f'/zones/{zid}','DELETE')
assert all(z['id'] != zid for z in request('/zones'))
assert all(m['zone_id'] != zid for m in request('/history'))
print('PASS: начальные данные, создание, AQI, запись и чтение истории, переименование, валидация, удаление и каскадная очистка.')
