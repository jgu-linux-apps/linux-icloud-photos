"""Mapa zdjęć w przeglądarce (Leaflet + OpenStreetMap).

Strona otwiera się od razu, a pinezki dochodzą na bieżąco: aplikacja uruchamia mały serwer HTTP tylko na
127.0.0.1 (losowy port, losowy token w adresie), z którego strona co chwilę pobiera nowe punkty.
Miniatury są pobierane dopiero po kliknięciu pinezki."""
import html
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# słowa w tytułach artykułów: atrakcje (wyżej) i instytucje/ulice (niżej) - pl, en, de, uk
PLACES_GOOD_RE = r"(kości|katedr|bazylik|zamek|zamk|pałac|dwór|muze|pomnik|brama|baszt|wież|ratusz|park|ogród|teatr|kaplic|klasztor|opactw|twierdz|fort|latarn|plaż|molo|rynek|stare miasto|zabyt|church|cathedral|basilica|castle|palace|museum|monument|gate|tower|town hall|garden|theatre|chapel|abbey|monastery|fortress|lighthouse|beach|pier|square|old town|kirche|burg|schloss|denkmal|turm|rathaus|garten|kloster|leuchtturm|strand|altstadt|церкв|собор|замок|палац|музе|пам.ятник|брам|вежа|ратуш|парк|сад|театр|монастир|фортец|маяк|пляж)"
PLACES_BAD_RE = r"(akademi|uniwersytet|politechnik|wydział|szkoła|liceum|związek|stowarzysz|spółka|przedsiębior|stacja kolej|przystan|ulica|osiedle|dzielnic|parafia|university|faculty|school|association|company|station|street|district|parish|universität|schule|verein|gesellschaft|bahnhof|straße|університет|школа|асоціац|компан|станці|вулиц)"
PLACES_VILLAGE_RE = r"(wieś w|osada w|\(województwo|\(gmina|voivodeship\)|kolej|railway|bahn |залізниц|sołectw|gmina |dzielnica |osiedle |village|hamlet|municipality|dorf |ortsteil|gemeinde|село|селище|громад)"
LEAFLET = "https://unpkg.com/leaflet@1.9.4/dist"
CLUSTER = "https://unpkg.com/leaflet.markercluster@1.5.3/dist"


def build(title: str, labels: dict, points_url: str = "points", thumb_url: str = "thumb/", dark: bool = False) -> str:
    """Strona mapy. labels: count ('{0}' = liczba pinezek), loading ('{0}' = sprawdzone zdjęcia), none."""
    t = html.escape(title)
    lab = json.dumps(labels)
    # kafelki OpenStreetMap stonowane filtrem: ciemny motyw = odwrócona, granatowa mapa z konturami,
    # jasny = szara, przygaszona (pinezki są wtedy najbardziej wyraźnym elementem)
    tile_filter = ("invert(1) hue-rotate(200deg) brightness(0.78) contrast(1.15) saturate(0.35)" if dark
                   else "grayscale(0.9) brightness(1.04) contrast(0.82)")
    acc = "#22d3ee" if dark else "#7c5cff"
    acc_fg = "#06121f" if dark else "#ffffff"  # na jasnym turkusie liczby muszą być ciemne
    lang = labels.get("lang", "en")
    bar_bg, bar_fg = ("#161a2e", "#ecebff") if dark else ("#ffffff", "#1f1a3a")
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<link rel="stylesheet" href="{LEAFLET}/leaflet.css">
<link rel="stylesheet" href="{CLUSTER}/MarkerCluster.css">
<link rel="stylesheet" href="{CLUSTER}/MarkerCluster.Default.css">
<style>
html,body,#map{{height:100%;margin:0}} body{{font-family:system-ui,sans-serif}}
#bar{{position:absolute;z-index:1000;top:10px;left:56px;background:{bar_bg};color:{bar_fg};padding:6px 12px;
border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.25);font-size:14px}}
.leaflet-container{{background:{"#0e1016" if dark else "#f2f2f0"}}}
.leaflet-tile-pane{{filter:{tile_filter}}}
.marker-cluster,.marker-cluster div{{background:transparent}}
.marker-cluster div{{background:{acc};color:{acc_fg};font-weight:800;border:2px solid #fff;
box-shadow:0 0 0 4px {acc}55}}
.pp img{{display:block;width:180px;max-height:180px;object-fit:cover;border-radius:6px;margin-bottom:4px;
background:#eee;min-height:120px}}
.pp{{font-size:13px}}
#nb{{position:absolute;z-index:1000;top:10px;right:10px;background:{acc};color:{acc_fg};border:none;
border-radius:999px;padding:8px 14px;font:600 14px system-ui;box-shadow:0 2px 10px rgba(0,0,0,.3);cursor:pointer;display:none}}
#panel{{position:absolute;z-index:1001;top:0;right:0;bottom:0;width:340px;max-width:85%;background:{bar_bg};color:{bar_fg};
box-shadow:-4px 0 18px rgba(0,0,0,.3);transform:translateX(105%);transition:transform .25s ease;overflow:auto;
font-family:system-ui}}
#panel.open{{transform:none}}
#panel h3{{margin:0;padding:14px 44px 6px 16px;font-size:16px}}
#panel .x{{position:absolute;top:8px;right:10px;background:none;border:none;color:inherit;font-size:22px;cursor:pointer}}
#panel .st{{padding:0 16px 8px;font-size:12px;opacity:.7}}
.card{{display:block;margin:8px 12px;border-radius:12px;overflow:hidden;background:{"#1f2440" if dark else "#f3f1ff"};
color:inherit;text-decoration:none}}
.card img{{width:100%;height:150px;object-fit:cover;display:block;background:#888}}
.card b{{display:block;padding:8px 12px 2px;font-size:14px}}
.card p{{margin:0;padding:0 12px 10px;font-size:12.5px;line-height:1.4;opacity:.85}}
.card .d{{padding:0 12px 10px;font-size:11px;opacity:.6}}
.noimg{{height:110px;display:flex;align-items:center;justify-content:center;font-size:44px;
background:{"#2a3156" if dark else "#e6e1ff"}}}
.card .adr{{padding:0 12px 4px;font-size:12px;opacity:.8}}
.card .n{{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;
background:#f59e0b;color:#1a1200;font-size:12px;font-weight:800;margin-right:6px;border:2px solid #fff}}
.poi{{background:none;border:none}}
.poi div{{position:relative;width:30px;height:30px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:#f59e0b;
border:3px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,.55)}}
.poi span{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;transform:rotate(45deg);
color:#1a1200;font:800 13px system-ui}}
.gal{{display:grid;grid-template-columns:repeat(4,96px);gap:4px;max-height:320px;overflow:auto}}
.gal img{{width:96px;height:96px;object-fit:cover;border-radius:6px;background:#ccc}}
</style></head><body>
<div id="bar"><b>{t}</b> · <span id="st"></span></div>
<div id="map"></div>
<button id="nb">{html.escape(labels.get("nearby", "Nearby"))}</button>
<div id="panel"><button class="x" aria-label="close">×</button><h3>{html.escape(labels.get("nearby", "Nearby"))}</h3>
<div class="st" id="pst"></div><div id="cards"></div></div>
<script src="{LEAFLET}/leaflet.js"></script>
<script src="{CLUSTER}/leaflet.markercluster.js"></script>
<script>
const LAB = {lab};
const map = L.map('map').setView([52, 19], 4);
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'}}).addTo(map);
const group = L.markerClusterGroup({{chunkedLoading: true, zoomToBoundsOnClick: false,
  spiderfyOnMaxZoom: false, showCoverageOnHover: false}});
const app = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.photos;
function show(ids, latlng) {{
  if (app) {{ app.postMessage(JSON.stringify(ids)); return; }}
  const imgs = ids.slice(0, 60).map(i => `<img loading="lazy" src="{thumb_url}${{i}}" alt="">`).join('');
  L.popup({{maxWidth: 420}}).setLatLng(latlng).setContent(
    `<div class="gal">${{imgs}}</div><div class="pp">${{ids.length}}</div>`).openOn(map);
}}
group.on('clusterclick', e => show(e.layer.getAllChildMarkers().map(m => m.pid), e.latlng));
group.on('click', e => show([e.layer.pid], e.latlng));
map.addLayer(group);
const esc = s => String(s).replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
const st = document.getElementById('st');
let have = 0, fitted = false, userMoved = false;
map.on('dragstart zoomstart', () => {{ if (fitted) userMoved = true; }});
function add(list) {{
  const ms = list.map(([i, lat, lon, name, date]) => {{
    const m = L.circleMarker([lat, lon], {{radius: 7, weight: 2, color: '#ffffff', fillColor: '{acc}',
      fillOpacity: 0.95}});
    m.pid = i;
    m.bindTooltip(`${{esc(name)}}<br>${{esc(date)}}`);
    return m;
  }});
  group.addLayers(ms);
}}
async function poll() {{
  let r;
  try {{ r = await (await fetch('{points_url}?from=' + have)).json(); }}
  catch (e) {{ setTimeout(poll, 3000); return; }}
  if (r.points.length) {{
    add(r.points); have += r.points.length;
    if (!userMoved) {{ map.fitBounds(group.getBounds(), {{padding: [30, 30], maxZoom: 14}}); fitted = true; }}
  }}
  st.textContent = r.done ? (have ? LAB.count.replace('{{0}}', have) : LAB.none)
                          : LAB.loading.replace('{{0}}', r.checked) + ' · ' + LAB.count.replace('{{0}}', have);
  if (!r.done) setTimeout(poll, 1200);
}}
poll();
const nb = document.getElementById('nb'), panel = document.getElementById('panel');
const NB_ZOOM = 11;
function nbVis() {{ nb.style.display = map.getZoom() >= NB_ZOOM && !panel.classList.contains('open') ? 'block' : 'none'; }}
map.on('zoomend', nbVis); nbVis();
panel.querySelector('.x').onclick = () => {{ panel.classList.remove('open'); nbVis(); }};
const GOOD = /{PLACES_GOOD_RE}/i;
const BAD = /{PLACES_BAD_RE}/i;
const VILLAGE = /{PLACES_VILLAGE_RE}/i;
function km(a, b) {{ return map.distance(a, b) / 1000; }}
async function wikiPlaces(c) {{
  const u = 'https://{lang}.wikipedia.org/w/api.php?action=query&format=json&origin=*&generator=geosearch'
    + `&ggscoord=${{c.lat}}|${{c.lng}}&ggsradius=10000&ggslimit=40&prop=pageimages|extracts|coordinates|info&coprop=type`
    + '&inprop=url&piprop=thumbnail&pithumbsize=400&exintro=1&explaintext=1&exsentences=2&exlimit=40';
  const r = await (await fetch(u)).json();
  return Object.values((r.query || {{}}).pages || {{}}).filter(p => p.thumbnail && p.extract && p.coordinates).map(p => {{
    const t = (p.title + ' ' + p.extract.slice(0, 120)).toLowerCase(), ty = p.coordinates[0].type;
    let s = (ty === 'landmark' ? 3 : ty === 'building' ? 2 : 0);
    if (GOOD.test(t)) s += 3;
    if (BAD.test(t) || VILLAGE.test(t) || ['city', 'adm1st', 'adm2nd', 'country'].includes(ty)) s -= 6;
    return {{title: p.title, lat: p.coordinates[0].lat, lon: p.coordinates[0].lon, img: p.thumbnail.source,
            text: p.extract, url: p.fullurl, score: s, src: 'wiki'}};
  }});
}}
// OpenStreetMap: in small towns it knows far more sights (viewpoints, observation towers, ruins) than Wikipedia
const OSM_SCORE = {{tower: 8, viewpoint: 7, attraction: 6, museum: 6, castle: 6, fort: 5, ruins: 5, zoo: 6,
  theme_park: 6, aquarium: 6, gallery: 4, manor: 4, monument: 3, archaeological_site: 4, memorial: 0, artwork: 0}};
async function osmPlaces(c, rad) {{
  const q = `[out:json][timeout:20];(`
    + `nwr(around:${{rad}},${{c.lat}},${{c.lng}})["tourism"~"^(attraction|viewpoint|museum|gallery|zoo|theme_park|aquarium)$"];`
    + `nwr(around:${{rad}},${{c.lat}},${{c.lng}})["man_made"="tower"]["tower:type"="observation"];`
    + `nwr(around:${{rad}},${{c.lat}},${{c.lng}})["historic"~"^(castle|fort|ruins|manor|monument|archaeological_site)$"]["name"];`
    + `node(around:${{rad}},${{c.lat}},${{c.lng}})["natural"="peak"]["name"];`
    + `);out center tags 150;`;
  // the app fetches it (same-origin endpoint): Overpass rejects some browser requests, and the app sends its own name
  const resp = await fetch('osm', {{method: 'POST', body: q}});
  if (!resp.ok) throw new Error('overpass ' + resp.status);
  const r = await resp.json();
  const els = (r.elements || []).map(e => ({{...e, lat: e.lat ?? (e.center || {{}}).lat, lon: e.lon ?? (e.center || {{}}).lon}}))
    .filter(e => e.lat != null);
  const peaks = els.filter(e => (e.tags || {{}}).natural === 'peak');
  const out = [];
  for (const e of els) {{
    const t = e.tags || {{}};
    if (t.natural === 'peak') continue;
    const kind = t['tower:type'] === 'observation' ? 'tower' : (t.tourism || t.historic);
    let name = t['name:{lang}'] || t.name || '';
    if (kind === 'tower' || kind === 'viewpoint') {{
      const pk = peaks.map(p => [map.distance([e.lat, e.lon], [p.lat, p.lon]), p]).sort((a, b) => a[0] - b[0])[0];
      if (pk && pk[0] < 500) {{
        const peak = pk[1].tags.name;
        name = !name ? `${{LAB.types[kind] || ''}} \u2013 ${{peak}}` : (name.includes(peak) ? name : `${{name}} (${{peak}})`);
      }}
    }}
    if (!name && kind !== 'tower') continue;
    const label = LAB.types[kind] || '';
    let img = '';
    const file = t.wikimedia_commons && t.wikimedia_commons.startsWith('File:') ? t.wikimedia_commons.slice(5)
      : (t.image && t.image.includes('File:') ? t.image.split('File:')[1] : '');
    if (file) img = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + encodeURIComponent(file) + '?width=400';
    out.push({{title: name || label, lat: e.lat, lon: e.lon, img, text: [label, t.description || t.inscription || '']
      .filter(Boolean).join(' \u2013 ').slice(0, 220), url: `https://www.openstreetmap.org/${{e.type}}/${{e.id}}`,
      score: (OSM_SCORE[kind] ?? 1) + (img ? 1 : 0) + (t.wikipedia || t.wikidata ? 1 : 0), src: 'osm',
      wiki: (t.wikipedia || '').split(':').slice(1).join(':')}});
  }}
  return out;
}}
function rank(c, wiki, osm) {{
  // the same place from both sources: keep the Wikipedia entry (it has a photo and a description)
  const titles = new Set(wiki.map(w => w.title));
  const all = wiki.concat(osm.filter(o => !titles.has(o.wiki) &&
    !wiki.some(w => map.distance([w.lat, w.lon], [o.lat, o.lon]) < 60)));
  const seen = [];
  return all.filter(x => x.score > -3).map(x => [x.score, km(c, [x.lat, x.lon]), x])
    .sort((a, b) => (b[0] - a[0]) || (a[1] - b[1])).map(x => x[2])
    .filter(x => {{
      const nx = x.title.toLowerCase().replace(/\\s*\\(.*\\)\\s*$/, '');
      if (seen.some(y => map.distance([y.lat, y.lon], [x.lat, x.lon]) < 40 || y.title.toLowerCase().includes(nx)
          || nx.includes(y.title.toLowerCase().replace(/\\s*\\(.*\\)\\s*$/, '')))) return false;
      seen.push(x); return true;
    }})
    .slice(0, 6);
}}
let nbRun = 0;
function render(c, items, note) {{
  const cards = document.getElementById('cards'), pst = document.getElementById('pst');
  cards.innerHTML = ''; poiLayer.clearLayers();
  if (!items.length) {{ pst.textContent = note || LAB.nb_none; return; }}
  pst.textContent = note || LAB.nb_source;
  const bounds = [];
  items.forEach((p, k) => {{
    const ll = [p.lat, p.lon]; bounds.push(ll);
    const d = km(c, ll), n = k + 1;
    const m = L.marker(ll, {{icon: L.divIcon({{className: 'poi', html: `<div><span>${{n}}</span></div>`,
      iconSize: [30, 30], iconAnchor: [4, 34], popupAnchor: [12, -30]}}), zIndexOffset: 1000}})
      .bindPopup(`<b>${{n}}. ${{esc(p.title)}}</b><br><span class="adr-${{k}}">&hellip;</span>`);
    poiLayer.addLayer(m);
    const a = document.createElement('a'); a.className = 'card'; a.href = p.url; a.target = '_blank';
    const pic = p.img ? `<img src="${{p.img}}" alt="" onerror="this.replaceWith(Object.assign(document.createElement('div'),{{className:'noimg',textContent:'\\u{{1F4CD}}'}}))">`
      : `<div class="noimg">\\u{{1F3DE}}</div>`;
    a.innerHTML = pic + `<b><span class="n">${{n}}</span>${{esc(p.title)}}</b>`
      + `<div class="adr adr-${{k}}">&hellip;</div><p>${{esc(p.text)}}</p><div class="d">${{d.toFixed(1)}} km`
      + ` &middot; ${{{{wiki: 'Wikipedia', wikidata: 'Wikidata'}}[p.src] || 'OpenStreetMap'}}</div>`;
    a.addEventListener('mouseenter', () => m.openPopup());
    cards.appendChild(a);
  }});
  map.fitBounds(L.latLngBounds(bounds.concat([[c.lat, c.lng]])).pad(0.25), {{maxZoom: 16, paddingBottomRight: [360, 0]}});
  addresses(items);
}}
async function appPlaces(kind, c) {{
  // wd = Wikidata, nom = Nominatim; the app fetches them (its own name, rate limits, no browser restrictions)
  const r = await fetch(`${{kind}}?lat=${{c.lat}}&lon=${{c.lng}}&lang={lang}`);
  if (!r.ok) throw new Error(kind + ' ' + r.status);
  return (await r.json()).map(x => ({{...x, text: x.text || LAB.types[x.kind] || ''}}));
}}
async function nearby() {{
  panel.classList.add('open'); nbVis();
  const run = ++nbRun, c = map.getCenter();
  document.getElementById('cards').innerHTML = ''; poiLayer.clearLayers();
  document.getElementById('pst').textContent = LAB.nb_loading;
  const got = {{wiki: null, wd: null, nom: null, osm: null}}, failed = new Set();
  let shown = '';
  const update = () => {{
    if (run !== nbRun) return;
    const others = [].concat(got.wd || [], got.nom || [], got.osm || []);
    const pending = Object.keys(got).filter(k => got[k] === null && !failed.has(k)).length;
    const items = rank(c, got.wiki || [], others);
    const note = pending ? LAB.nb_more : (failed.size === 4 ? LAB.nb_error : LAB.nb_source);
    const key = items.map(x => x.title).join('|') + note;
    if (key === shown) return;  // nothing new: do not redraw (no flicker, addresses keep loading)
    shown = key;
    render(c, items, note);
  }};
  const go = (k, p) => p.then(v => {{ got[k] = v; }}, () => {{ failed.add(k); }}).then(update);
  go('wiki', wikiPlaces(c)); go('wd', appPlaces('wd', c)); go('nom', appPlaces('nom', c)); go('osm', osmPlaces(c, 5000));
}}
nb.onclick = nearby;
const poiLayer = L.layerGroup().addTo(map);
panel.querySelector('.x').addEventListener('click', () => poiLayer.clearLayers());
let addrRun = 0;
async function addresses(pages) {{
  const my = ++addrRun;  // a newer list replaced this one: stop writing addresses into it
  // addresses from OpenStreetMap (Nominatim): one by one, at most 1 request per second (service policy)
  for (let k = 0; k < pages.length; k++) {{
    const p = pages[k], u = 'https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=18&addressdetails=1'
      + `&accept-language={lang}&lat=${{p.lat}}&lon=${{p.lon}}`;
    let txt = '';
    try {{
      const r = await (await fetch(u)).json(), a = r.address || {{}};
      const street = [a.road || a.pedestrian || a.square || a.footway, a.house_number].filter(Boolean).join(' ');
      const town = a.city || a.town || a.village || a.suburb || '';
      txt = [street, [a.postcode, town].filter(Boolean).join(' ')].filter(Boolean).join(', ') || r.display_name || '';
    }} catch (e) {{ txt = ''; }}
    if (my !== addrRun) return;
    document.querySelectorAll('.adr-' + k).forEach(el => el.textContent = txt ? '\\u{{1F4CD}} ' + txt : '');
    await new Promise(res => setTimeout(res, 1100));
  }}
}}
</script></body></html>
"""


OVERPASS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter")
_OSM_CACHE = {}  # zapytanie -> odpowiedź (te same okolice nie obciążają serwerów drugi raz)
USER_AGENT = "linux-icloud-photos (https://github.com/jgu-linux-apps/linux-icloud-photos)"


def overpass(query: str) -> bytes:
    """Zapytanie Overpass (OpenStreetMap) wysłane przez aplikację; przy błędzie próbuje serwera zapasowego."""
    import urllib.parse
    import urllib.request

    if query in _OSM_CACHE:
        return _OSM_CACHE[query]
    last = None
    for srv in OVERPASS:
        try:
            req = urllib.request.Request(srv, data=urllib.parse.urlencode({"data": query}).encode(),
                                         headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as r:
                data = r.read()
            if data.lstrip().startswith(b"{"):
                _OSM_CACHE[query] = data
                return data
            last = RuntimeError("overpass: no JSON")
        except Exception as e:  # noqa: BLE001
            last = e
    raise last or RuntimeError("overpass")


WD_GOOD_RE = ("wieża widokowa", "observation tower", "aussichtsturm", "оглядова вежа", "góra", "szczyt", "wzgórze",
           "mountain", "hill", "summit", "berg", "гора", "zamek", "castle", "burg", "schloss", "замок", "pałac",
           "palace", "палац", "muzeum", "museum", "музей", "kościół", "church", "kirche", "церква", "ruiny",
           "ruin", "руїни", "pomnik", "monument", "denkmal", "пам", "park", "rezerwat", "reserve", "jezioro",
           "lake", "see", "озеро", "wodospad", "waterfall", "latarnia", "lighthouse", "plaża", "beach", "zabyt",
           "grodzisko", "hillfort", "fort", "twierdza", "fortress", "amfiteatr", "punkt widokowy", "viewpoint",
           "ogród", "garden", "zoo", "akwarium", "aquarium", "katedr", "cathedral", "bazylik", "basilica",
           "klasztor", "monastery", "kaplica", "chapel", "dwór", "manor", "młyn", "mill", "skansen", "open-air")
WD_TOP_RE = ("wieża widokowa", "observation tower", "aussichtsturm", "góra", "szczyt", "wzgórze", "mountain", "hill",
          "summit", "punkt widokowy", "viewpoint", "zamek", "castle", "burg", "ruiny", "ruin", "rezerwat", "reserve",
          "latarnia", "lighthouse", "plaża", "beach", "wodospad", "waterfall", "grodzisko", "skansen")
WD_BAD_RE = ("stacja", "station", "przystanek", "stop", "wieś", "village", "część", "dzielnica", "district",
          "osiedle", "gmina", "municipality", "ulica", "street", "szkoła", "school", "miasto", "city", "town",
          "powiat", "county", "osada", "hamlet", "parafia", "parish", "przedsiębiorstw", "company", "zajezdnia",
          "depot", "cmentarz", "cemetery", "linia kolejowa", "railway")


def _get_json(url: str, timeout: int = 20):
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def wikidata_places(lat: float, lon: float, lang: str = "en", radius_km: float = 6) -> list:
    """Obiekty z Wikidata w promieniu (z typem, opisem i zdjęciem). Wieże, szczyty, zamki itp. są też
    w małych miejscowościach, gdzie Wikipedia ma mało artykułów."""
    import urllib.parse

    q = f"""SELECT ?item ?itemLabel ?itemDescription ?typeLabel ?img ?loc ?article WHERE {{
  SERVICE wikibase:around {{ ?item wdt:P625 ?loc . bd:serviceParam wikibase:center "Point({lon} {lat})"^^geo:wktLiteral .
    bd:serviceParam wikibase:radius "{radius_km}" . }}
  OPTIONAL {{ ?item wdt:P31 ?type . }}
  OPTIONAL {{ ?item wdt:P18 ?img . }}
  OPTIONAL {{ ?article schema:about ?item ; schema:isPartOf <https://{lang}.wikipedia.org/> . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "{lang},en,pl". }}
}} LIMIT 300"""
    data = _get_json("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q), timeout=25)
    items = {}
    for b in data.get("results", {}).get("bindings", []):
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        it = items.setdefault(qid, {"qid": qid, "title": b.get("itemLabel", {}).get("value", ""),
                                    "text": b.get("itemDescription", {}).get("value", ""), "types": set(),
                                    "img": "", "url": b.get("article", {}).get("value") or f"https://www.wikidata.org/wiki/{qid}"})
        if "typeLabel" in b:
            it["types"].add(b["typeLabel"]["value"].lower())
        if "img" in b and not it["img"]:
            it["img"] = b["img"]["value"].replace("http://", "https://") + "?width=400"
        if "loc" in b and "lat" not in it:
            pt = b["loc"]["value"].replace("Point(", "").rstrip(")").split()
            it["lon"], it["lat"] = float(pt[0]), float(pt[1])
    out = []
    for it in items.values():
        if "lat" not in it or not it["title"] or it["title"] == it["qid"]:
            continue
        kinds = " ".join(it["types"]) + " " + it["text"].lower() + " " + it["title"].lower()
        score = ((5 if any(g in kinds for g in WD_GOOD_RE) else 0) + (2 if any(g in kinds for g in WD_TOP_RE) else 0)
                 + (1 if it["img"] else 0))
        if any(x in " ".join(it["types"]) for x in WD_BAD_RE):
            score -= 8
        if score <= 0:
            continue
        typ = sorted(it["types"])[0] if it["types"] else ""
        out.append({"title": it["title"], "lat": it["lat"], "lon": it["lon"], "img": it["img"],
                    "text": (it["text"] or typ)[:220], "url": it["url"], "score": score, "src": "wikidata",
                    "wiki": urllib.parse.unquote(it["url"].rsplit("/", 1)[-1]).replace("_", " ")
                    if "wikipedia.org" in it["url"] else ""})
    return out


NOM_QUERIES = ("viewpoint", "attraction", "museum", "ruins", "castle", "observation tower")


def nominatim_places(lat: float, lon: float, lang: str = "en", radius_km: float = 5) -> list:
    """Wyszukiwarka OpenStreetMap (Nominatim): punkty widokowe, atrakcje, muzea, ruiny, zamki w okolicy.
    Kolejne zapytania co 1,1 s (zasady usługi: najwyżej 1 na sekundę)."""
    import math
    import time
    import urllib.parse

    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
    box = f"{lon - dlon},{lat + dlat},{lon + dlon},{lat - dlat}"
    out, seen = [], set()
    for k, q in enumerate(NOM_QUERIES):
        if k:
            time.sleep(1.1)
        try:
            rows = _get_json("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
                {"q": q, "format": "jsonv2", "viewbox": box, "bounded": 1, "limit": 8, "accept-language": lang,
                 "extratags": 1}), timeout=12)
        except Exception:  # noqa: BLE001
            continue
        for r in rows:
            key = (r.get("osm_type"), r.get("osm_id"))
            if key in seen or not r.get("name"):
                continue
            seen.add(key)
            kind = r.get("type") or r.get("category") or ""
            ex = r.get("extratags") or {}
            img = ""
            if (ex.get("wikimedia_commons") or "").startswith("File:"):
                img = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(ex["wikimedia_commons"][5:]) + "?width=400"
            out.append({"title": r["name"], "lat": float(r["lat"]), "lon": float(r["lon"]), "img": img,
                        "kind": kind, "text": "", "url": f"https://www.openstreetmap.org/{r.get('osm_type')}/{r.get('osm_id')}",
                        "score": {"viewpoint": 7, "tower": 8, "attraction": 6, "museum": 6, "castle": 6,
                                  "ruins": 5}.get(kind, 3) + (1 if img else 0), "src": "osm",
                        "wiki": (ex.get("wikipedia") or "").split(":", 1)[-1]})
    return out


class MapSession:
    """Punkty mapy zbierane w tle + serwer HTTP, z którego czyta je strona."""

    def __init__(self, title, labels, thumb_fn):
        self.title, self.labels, self.thumb_fn = title, labels, thumb_fn
        self.points, self.assets, self.keys = [], [], {}
        self.checked, self.done = 0, False
        self.lock = threading.Lock()
        self.token = secrets.token_urlsafe(12)
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, ctype, body):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _json_endpoint(self, fn, q):
                try:
                    lat, lon = float(q["lat"][0]), float(q["lon"][0])
                    lang = (q.get("lang") or ["en"])[0][:5]
                    return self._send(200, "application/json", json.dumps(fn(lat, lon, lang)).encode())
                except Exception as e:  # noqa: BLE001
                    return self._send(502, "text/plain", str(e).encode())

            def do_POST(self):
                parts = urlparse(self.path).path.strip("/").split("/")
                if len(parts) != 2 or parts[0] != outer.token or parts[1] != "osm":
                    return self._send(404, "text/plain", b"not found")
                n = min(int(self.headers.get("Content-Length") or 0), 20000)
                q = self.rfile.read(n).decode("utf-8", "replace")
                try:
                    return self._send(200, "application/json", overpass(q))
                except Exception as e:  # noqa: BLE001
                    return self._send(502, "text/plain", str(e).encode())

            def do_GET(self):
                u = urlparse(self.path)
                parts = u.path.strip("/").split("/")
                if not parts or parts[0] != outer.token:
                    return self._send(404, "text/plain", b"not found")
                try:
                    if len(parts) == 1:
                        dark = parse_qs(u.query).get("dark", ["0"])[0] == "1"
                        page = build(outer.title, outer.labels, dark=dark)
                        return self._send(200, "text/html; charset=utf-8", page.encode())
                    if parts[1] in ("wd", "nom"):
                        return self._json_endpoint(wikidata_places if parts[1] == "wd" else nominatim_places,
                                                   parse_qs(u.query))
                    if parts[1] == "points":
                        start = int(parse_qs(u.query).get("from", ["0"])[0])
                        with outer.lock:
                            body = json.dumps({"points": outer.points[start:], "done": outer.done,
                                               "checked": outer.checked}).encode()
                        return self._send(200, "application/json", body)
                    if parts[1] == "thumb" and len(parts) == 3:
                        i = int(parts[2])
                        with outer.lock:
                            asset = outer.assets[i] if 0 <= i < len(outer.assets) else None
                        if asset is None:
                            return self._send(404, "text/plain", b"no photo")
                        return self._send(200, "image/jpeg", outer.thumb_fn(asset))
                except (BrokenPipeError, ConnectionResetError):
                    return None
                except Exception as e:  # noqa: BLE001
                    try:
                        return self._send(500, "text/plain", str(e).encode())
                    except Exception:  # noqa: BLE001
                        return None
                return self._send(404, "text/plain", b"not found")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}/{self.token}/"

    def add(self, asset, lat, lon, name, date, key=None):
        """Dodaje pinezkę; key (id zdjęcia) zapobiega dublom, gdy punkt był już w pamięci podręcznej."""
        with self.lock:
            if key is not None:
                if key in self.keys:
                    j = self.keys[key]
                    if self.assets[j] is None:
                        self.assets[j] = asset  # punkt z pamięci: teraz wiadomo, skąd wziąć miniaturę
                    return False
                self.keys[key] = len(self.assets)
            i = len(self.assets)
            self.assets.append(asset)
            self.points.append([i, round(lat, 6), round(lon, 6), name, date])
            return True

    def close(self):
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:  # noqa: BLE001
            pass
