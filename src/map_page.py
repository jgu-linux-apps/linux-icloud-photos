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
const GOOD = /(kości|katedr|bazylik|zamek|zamk|pałac|dwór|muze|pomnik|brama|baszt|wież|ratusz|park|ogród|teatr|kaplic|klasztor|opactw|twierdz|fort|latarn|plaż|molo|rynek|stare miasto|zabyt|church|cathedral|basilica|castle|palace|museum|monument|gate|tower|town hall|garden|theatre|chapel|abbey|monastery|fortress|lighthouse|beach|pier|square|old town|kirche|burg|schloss|denkmal|turm|rathaus|garten|kloster|leuchtturm|strand|altstadt|церкв|собор|замок|палац|музе|пам.ятник|брам|вежа|ратуш|парк|сад|театр|монастир|фортец|маяк|пляж)/i;
const BAD = /(akademi|uniwersytet|politechnik|wydział|szkoła|liceum|związek|stowarzysz|spółka|przedsiębior|stacja kolej|przystan|ulica|osiedle|dzielnic|parafia|university|faculty|school|association|company|station|street|district|parish|universität|schule|verein|gesellschaft|bahnhof|straße|університет|школа|асоціац|компан|станці|вулиц)/i;
function km(a, b) {{ return map.distance(a, b) / 1000; }}
async function nearby() {{
  panel.classList.add('open'); nbVis();
  const c = map.getCenter(), cards = document.getElementById('cards'), pst = document.getElementById('pst');
  cards.innerHTML = ''; pst.textContent = LAB.nb_loading;
  const u = 'https://{lang}.wikipedia.org/w/api.php?action=query&format=json&origin=*&generator=geosearch'
    + `&ggscoord=${{c.lat}}|${{c.lng}}&ggsradius=10000&ggslimit=40&prop=pageimages|extracts|coordinates|info&coprop=type`
    + '&inprop=url&piprop=thumbnail&pithumbsize=400&exintro=1&explaintext=1&exsentences=2&exlimit=40';
  try {{
    const r = await (await fetch(u)).json();
    let pages = Object.values((r.query || {{}}).pages || {{}});
    const score = p => {{
      const t = (p.title + ' ' + p.extract.slice(0, 120)).toLowerCase(), ty = p.coordinates[0].type;
      let s = (ty === 'landmark' ? 3 : ty === 'building' ? 2 : 0);
      if (GOOD.test(t)) s += 3;
      if (BAD.test(t) || ['city', 'adm1st', 'adm2nd', 'country'].includes(ty)) s -= 6;
      return s;
    }};
    pages = pages.filter(p => p.thumbnail && p.extract && p.coordinates).map(p => [score(p),
      km(c, [p.coordinates[0].lat, p.coordinates[0].lon]), p]).filter(x => x[0] > -3)
      .sort((a, b) => (b[0] - a[0]) || (a[1] - b[1])).slice(0, 5).map(x => x[2]);
    if (!pages.length) {{ pst.textContent = LAB.nb_none; return; }}
    pst.textContent = LAB.nb_source;
    for (const p of pages) {{
      const d = km(c, [p.coordinates[0].lat, p.coordinates[0].lon]);
      const a = document.createElement('a'); a.className = 'card'; a.href = p.fullurl; a.target = '_blank';
      a.innerHTML = `<img src="${{p.thumbnail.source}}" alt=""><b>${{esc(p.title)}}</b><p>${{esc(p.extract)}}</p>`
        + `<div class="d">${{d.toFixed(1)}} km</div>`;
      cards.appendChild(a);
    }}
  }} catch (e) {{ pst.textContent = LAB.nb_error; }}
}}
nb.onclick = nearby;
</script></body></html>
"""


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
