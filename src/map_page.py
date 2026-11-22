"""Strona HTML z mapą zdjęć (Leaflet + OpenStreetMap), otwierana w przeglądarce."""
import html
import json
from pathlib import Path

LEAFLET = "https://unpkg.com/leaflet@1.9.4/dist"
CLUSTER = "https://unpkg.com/leaflet.markercluster@1.5.3/dist"


def build(title: str, points: list[dict], labels: dict) -> str:
    data = []
    for p in points:
        thumb = Path(p["thumb"]).as_uri() if p.get("thumb") else ""
        data.append([round(p["lat"], 6), round(p["lon"], 6), p.get("name", ""), p.get("date", ""), thumb])
    t = html.escape(title)
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
.pp img{{display:block;max-width:180px;max-height:180px;border-radius:6px;margin-bottom:4px}}
.pp{{font-size:13px}}
</style></head><body>
<div id="bar"><b>{t}</b> · {html.escape(labels['count'].format(len(data)))}</div>
<div id="map"></div>
<script src="{LEAFLET}/leaflet.js"></script>
<script src="{CLUSTER}/leaflet.markercluster.js"></script>
<script>
const pts = {json.dumps(data)};
const map = L.map('map');
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'}}).addTo(map);
const group = L.markerClusterGroup();
const esc = s => s.replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
for (const [lat, lon, name, date, thumb] of pts) {{
  const img = thumb ? `<img src="${{thumb}}" alt="">` : '';
  group.addLayer(L.marker([lat, lon]).bindPopup(`<div class="pp">${{img}}<b>${{esc(name)}}</b><br>${{esc(date)}}</div>`));
}}
map.addLayer(group);
if (pts.length) map.fitBounds(group.getBounds(), {{padding: [30, 30], maxZoom: 14}});
else map.setView([52, 19], 4);
</script></body></html>
"""
