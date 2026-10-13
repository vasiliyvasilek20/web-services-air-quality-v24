const $ = id => document.getElementById(id);
let zones = [];
let busy = false;
async function api(path, method = 'GET', data) {
  let response;
  try { response = await fetch('/api' + path, {method, headers: {'Content-Type':'application/json'}, body: data === undefined ? undefined : JSON.stringify(data)}); }
  catch { throw new Error('Нет соединения с сервером. Проверьте, что контейнеры запущены, и повторите запрос.'); }
  let result;
  try { result = await response.json(); } catch { throw new Error('Сервер вернул некорректный ответ.'); }
  if (!response.ok) throw new Error(result.error || 'Ошибка запроса');
  return result;
}
function td(row, value) { const cell = document.createElement('td'); cell.textContent = value ?? '—'; row.append(cell); return cell; }
function empty(tbody, text) { tbody.replaceChildren(); const row = document.createElement('tr'); const cell = td(row,text); cell.colSpan = 5; cell.className = 'empty'; tbody.append(row); }
async function run(task) {
  if (busy) return;
  busy = true;
  document.querySelectorAll('button').forEach(b => b.disabled = true);
  $('status').textContent = 'Выполняется запрос…'; $('status').className = '';
  try { await task(); $('status').textContent = 'Готово. Данные получены и отображены.'; }
  catch (e) { $('status').textContent = e.message; $('status').className = 'error'; }
  finally { busy = false; document.querySelectorAll('button').forEach(b => b.disabled = false); $('check').disabled = !$('zone').value; }
}
async function loadZones() {
  const selected = $('zone').value;
  zones = await api('/zones');
  $('zones').replaceChildren(); $('zone').replaceChildren();
  if (!zones.length) { empty($('zones'), 'Зон нет. Добавьте место наблюдения.'); const o = new Option('Добавьте зону', ''); $('zone').append(o); }
  for (const z of zones) {
    $('zone').append(new Option(z.name,String(z.id)));
    const row = document.createElement('tr');
    td(row,z.name); td(row,`${z.latitude.toFixed(4)}, ${z.longitude.toFixed(4)}`); td(row,z.aqi); td(row,z.category);
    const actions = td(row,'');
    const rename = document.createElement('button'); rename.textContent = 'Название'; rename.className = 'small secondary';
    rename.onclick = () => { const name = prompt('Новое название зоны',z.name); if (name === null) return; run(async () => { await api(`/zones/${z.id}`, 'PUT', {...z,name}); await loadZones(); await loadHistory(); }); };
    const del = document.createElement('button'); del.textContent = 'Удалить'; del.className = 'small danger';
    del.onclick = () => { if (!confirm(`Удалить зону «${z.name}» и её историю?`)) return; run(async () => { await api(`/zones/${z.id}`,'DELETE'); $('result').hidden = true; await loadZones(); await loadHistory(); }); };
    actions.append(rename,del); $('zones').append(row);
  }
  if (zones.some(z => String(z.id) === selected)) $('zone').value = selected;
}
async function loadHistory() {
  const rows = await api('/history'); $('history-rows').replaceChildren();
  if (!rows.length) empty($('history-rows'),'Наблюдений пока нет. Запросите AQI для выбранной зоны.');
  for (const m of rows) { const row = document.createElement('tr'); td(row,new Date(m.checked_at).toLocaleString('ru-RU')); td(row,m.name); td(row,m.aqi); td(row,m.category); td(row,m.source); $('history-rows').append(row); }
}
$('load').onclick = () => run(loadZones);
$('history').onclick = () => run(loadHistory);
$('zone').onchange = () => { $('check').disabled = busy || !$('zone').value; $('result').hidden = true; };
$('check').onclick = () => run(async () => {
  const result = await api(`/zones/${$('zone').value}/check`,'POST');
  $('result').hidden = false; $('result').textContent = `AQI ${result.aqi} · ${result.category} · ${result.name}. Учебное значение сохранено в БД.`;
  await loadZones(); await loadHistory();
});
$('add').onsubmit = event => { event.preventDefault(); run(async () => {
  const created = await api('/zones','POST',{name:$('name').value,latitude:Number($('lat').value),longitude:Number($('lon').value)});
  $('add').reset(); await loadZones(); $('zone').value = String(created.id); $('result').hidden = true;
}); };
