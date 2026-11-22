import os, sys
sys.path.insert(0, os.environ["PROJECT_ROOT"])
import backend

# 1.0.0: przywracanie, usuwanie na zawsze, ukrywanie, usuwanie z albumu, albumy, udostępnione, mapa.
class Asset:
    def __init__(s, i, zone="PrimarySync", lat=None):
        s.id = f"id{i}"; s.filename = f"IMG_{i}.HEIC"; s.asset_id = f"A{i}"
        fields = {}
        if lat is not None:
            fields = {"locationLatitude": {"value": lat}, "locationLongitude": {"value": 19.0}}
        s._asset_record = {"recordName": s.id, "recordType": "CPLAsset", "zoneID": {"zoneName": zone},
                           "fields": fields}
        s.versions = {}
        s.asset_date = None
class Err:
    def __init__(s, name): s.serverErrorCode = "CONFLICT"; s.reason = "oops"; s.recordName = name
class Resp:
    def __init__(s, records): s.records = records
class Client:
    def __init__(s, fail_names=(), boom=False):
        s.ops = []; s.fail = set(fail_names); s.boom = boom; s.atomic = []
    def modify(s, *, operations, zone_id, atomic=None):
        s.atomic.append(atomic)
        if s.boom: raise RuntimeError("HTTP 503")
        recs = []
        for op in operations:
            r = op.record
            s.ops.append((op.operationType, r.recordType, r.recordName, zone_id.zoneName,
                          {k: v.value if hasattr(v, "value") else v for k, v in dict(r.fields).items()}))
            recs.append(Err(r.recordName) if r.recordName in s.fail else {"recordName": r.recordName})
        return Resp(recs)
class PhotoAlbum:
    _record_id = "ALB1"; _zone_id = {"zoneName": "PrimarySync"}; name = "Wakacje"
    def __init__(s, assets=()): s.assets = list(assets); s.renamed = None; s.deleted = False
    @staticmethod
    def _relation_item_id(p): return p.asset_id
    def rename(s, v): s.renamed = v
    def delete(s): s.deleted = True; return True
    def __iter__(s): return iter(s.assets)
class Stream:
    def __init__(s, name): s.name = name
def make(client, shared=None, shared_fail=False):
    class Photos:
        private_client = client
        created = []
        def create_album(s, name): Photos.created.append(name); return PhotoAlbum()
        @property
        def shared_streams(s):
            if shared_fail: raise RuntimeError("no shared streams")
            return shared or []
    class Api: photos = Photos()
    ic = backend.ICloud(); ic.api = Api(); return ic, Api.photos
def step(name, fn):
    try: r = fn()
    except Exception as e: r = "EXC " + type(e).__name__ + ": " + str(e)
    print(name, "->", r, flush=True)
ids = lambda l: [a.id for a in l]

c = Client(); ic, _ = make(c); A = [Asset(i) for i in range(3)]
d, e = ic.restore_assets(A)
step("restore", lambda: (ids(d), e, c.ops[0], c.atomic))
c = Client(fail_names={"id1"}); ic, _ = make(c); d, e = ic.purge_assets(A)
step("purge_one_conflict", lambda: (ids(d), e, c.ops[1][4]))
c = Client(); ic, _ = make(c); d, e = ic.set_hidden(A[:1], True); d2, e2 = ic.set_hidden(A[:1], False)
step("hide_unhide", lambda: (c.ops[0][4], c.ops[1][4], ids(d), ids(d2)))
c = Client(); ic, _ = make(c); d, e = ic.remove_from_album(PhotoAlbum(), A[:2])
step("remove_from_album", lambda: ([o[:3] for o in c.ops], c.ops[0][4], ids(d)))
c = Client(); ic, _ = make(c)
step("remove_from_smart_album", lambda: ic.remove_from_album(object(), A))
c = Client(boom=True); ic, _ = make(c); d, e = ic.restore_assets(A)
step("modify_network_error", lambda: (ids(d), len(e)))
c = Client(); ic, _ = make(c); B = [Asset(i) for i in range(250)] + [Asset(900, zone="SharedSync-1")]
prog = []; d, e = ic.restore_assets(B, lambda k, n: prog.append((k, n)))
step("batches_and_zones", lambda: (len(d), len(c.atomic), sorted({o[3] for o in c.ops}), prog[-1]))
c = Client(); ic, ph = make(c)
step("create_album", lambda: (type(ic.create_album("  Nowy  ")).__name__, ph.created))
step("create_album_empty", lambda: ic.create_album("   "))
al = PhotoAlbum(); step("rename_album", lambda: (ic.rename_album(al, " Lato "), al.renamed))
al = PhotoAlbum(); step("delete_album", lambda: (ic.delete_album(al), al.deleted))
step("is_user_album", lambda: (backend.ICloud.is_user_album(PhotoAlbum()), backend.ICloud.is_user_album(object())))
ic, _ = make(c, shared=[Stream("Rodzina"), Stream(""), Stream("ania")])
step("shared_sorted", lambda: [n for n, _a in ic.shared_albums()])
ic, _ = make(c, shared_fail=True); step("shared_unavailable", lambda: ic.shared_albums())
ic, _ = make(c); al = PhotoAlbum([Asset(1, lat=50.06), Asset(2), Asset(3, lat=0.0)])
step("geo_points", lambda: [(p["name"], p["lat"], p["lon"]) for p in ic.geo_points(al)])
backend.READ_ONLY = True
step("read_only_guard", lambda: ic.restore_assets(A))
backend.READ_ONLY = False
import map_page, urllib.request, json as _j
html = map_page.build("A <b>", {"count": "n: {0}", "loading": "l {0}", "none": "0"})
step("map_page", lambda: ("A &lt;b&gt;" in html, "leaflet@1.9.4" in html, "points?from=" in html))
ms = map_page.MapSession("T", {"count": "{0}", "loading": "{0}", "none": "-"}, lambda a: b"JPEGDATA")
ms.add(Asset(1), 50.0, 19.0, "IMG_1.HEIC", "2024-01-01 10:00"); ms.checked = 7
get = lambda path: urllib.request.urlopen(ms.url + path, timeout=5).read()
step("map_server_page", lambda: b"<title>T</title>" in get(""))
step("map_server_points", lambda: _j.loads(get("points?from=0")))
ms.done = True
step("map_server_points_from", lambda: _j.loads(get("points?from=1")))
step("map_server_thumb", lambda: get("thumb/0"))
step("map_server_bad_token", lambda: urllib.request.urlopen(ms.url.replace(ms.token, "x"), timeout=5).status)
import plistlib
class MA(Asset):
    def __init__(s, i, gps):
        super().__init__(i); s._master_record = {"fields": {"mediaMetaDataEnc": {"value": plistlib.dumps({"{GPS}": gps})}}}
step("gps_from_metadata", lambda: [backend.ICloud.asset_gps(MA(1, {"Latitude": 54.48, "LatitudeRef": "N", "Longitude": 18.56, "LongitudeRef": "E"})),
                                   backend.ICloud.asset_gps(MA(2, {"Latitude": 33.9, "LatitudeRef": "S", "Longitude": 151.2, "LongitudeRef": "W"})),
                                   backend.ICloud.asset_gps(MA(3, {}))])
ms2 = map_page.MapSession("T", {"count": "{0}", "loading": "{0}", "none": "-"}, lambda a: b"")
step("map_dedupe", lambda: (ms2.add(None, 1, 2, "a", "d", key="x"), ms2.add(Asset(1), 1, 2, "a", "d", key="x"), len(ms2.points), ms2.assets[0] is not None))
ms2.close()
ms.close()
