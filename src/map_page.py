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


def build(title: str, labels: dict, points_url: str = "points", thumb_url: str = "thumb/") -> str:
    """Strona mapy. labels: count ('{0}' = liczba pinezek), loading ('{0}' = sprawdzone zdjęcia), none."""
    t = html.escape(title)
    lab = json.dumps(labels)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<link rel="stylesheet" href="{LEAFLET}/leaflet.css">
<link rel="stylesheet" href="{CLUSTER}/MarkerCluster.css">
<link rel="stylesheet" href="{CLUSTER}/MarkerCluster.Default.css">
<style>
html,body,#map{{height:100%;margin:0}} body{{font-family:system-ui,sans-serif}}
#bar{{position:absolute;z-index:1000;top:10px;left:56px;background:#fff;padding:6px 12px;border-radius:10px;
box-shadow:0 2px 10px rgba(0,0,0,.25);font-size:14px}}
.pp img{{display:block;width:180px;max-height:180px;object-fit:cover;border-radius:6px;margin-bottom:4px;
background:#eee;min-height:120px}}
.pp{{font-size:13px}}
</style></head><body>
<div id="bar"><b>{t}</b> · <span id="st"></span></div>
<div id="map"></div>
<script src="{LEAFLET}/leaflet.js"></script>
<script src="{CLUSTER}/leaflet.markercluster.js"></script>
<script>
const LAB = {lab};
const map = L.map('map').setView([52, 19], 4);
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'}}).addTo(map);
const group = L.markerClusterGroup({{chunkedLoading: true}});
map.addLayer(group);
const esc = s => String(s).replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
const st = document.getElementById('st');
let have = 0, fitted = false, userMoved = false;
map.on('dragstart zoomstart', () => {{ if (fitted) userMoved = true; }});
function add(list) {{
  const ms = list.map(([i, lat, lon, name, date]) => L.marker([lat, lon]).bindPopup(
    `<div class="pp"><img loading="lazy" src="{thumb_url}${{i}}" alt=""><b>${{esc(name)}}</b><br>${{esc(date)}}</div>`));
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
                        page = build(outer.title, outer.labels)
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
