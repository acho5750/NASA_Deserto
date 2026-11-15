"""Dated aerial photos for each campus, so the map's Play can show the ground itself changing.

Usage:  python pipeline/map_wayback.py

Esri World Imagery Wayback keeps every published version of the World Imagery basemap since 2014
(https://livingatlas.arcgis.com/wayback/). Most versions reuse the same photo at a given place, so for each campus
this script fetches the zoom-16 tile at the campus centre from every version, keeps the versions where the tile
actually changed, and asks that version's metadata layer for the capture date of the photo at the centre.

Reads   map/data.js                         campus ids, names, lat/lon
Writes  data/wayback_captures.csv           site_id, release, release_date, capture_date, resolution_m, source
        map/wayback.js                      window.WAYBACK = {url, sites: {id: [[t, release, "capture date"], ...]}}
                                            t = year*12 + month-1 of the capture date (same clock as map/timeline.js)
Nothing here is estimated: every row is a published photo and its date as Esri's metadata states it.
"""
import hashlib
import json
import math
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

CONFIG = "https://s3-us-west-2.amazonaws.com/config.maptiles.arcgis.com/waybackconfig.json"
TILE = "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile/{r}/{z}/{y}/{x}"
SOURCE = "https://livingatlas.arcgis.com/wayback/"
Z = 16


def get(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def tile_xy(lat, lon, z=Z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def capture(meta_url, lat, lon):
    q = (f"{meta_url}/identify?geometry={lon},{lat}&geometryType=esriGeometryPoint&sr=4326&layers=all&tolerance=0"
         f"&mapExtent={lon - .01},{lat - .01},{lon + .01},{lat + .01}&imageDisplay=256,256,96&returnGeometry=false&f=json")
    res = json.loads(get(q)).get("results", [])
    # Layers are ordered fine to coarse; the first hit is the photo shown at high zoom.
    for r in res:
        a = r.get("attributes", {})
        d = str(a.get("SRC_DATE", ""))
        if len(d) == 8 and d.isdigit():
            return f"{d[:4]}-{d[4:6]}-{d[6:]}", a.get("SRC_RES")
    return None, None


def one_site(s, releases):
    x, y = tile_xy(s["lat"], s["lon"])
    with ThreadPoolExecutor(8) as ex:
        hashes = list(ex.map(lambda r: hashlib.md5(get(TILE.format(r=r["id"], z=Z, y=y, x=x))).hexdigest(), releases))
    changed, last_h = [], None
    for r, h in zip(releases, hashes):           # releases sorted oldest first
        if h != last_h:
            changed.append(r)
        last_h = h
    with ThreadPoolExecutor(8) as ex:
        caps = list(ex.map(lambda r: capture(r["meta"], s["lat"], s["lon"]), changed))
    rows, last_cap = [], None
    for r, (cap, res) in zip(changed, caps):
        if not cap or cap == last_cap:
            continue
        last_cap = cap
        rows.append({"site_id": s["id"], "release": r["id"], "release_date": r["date"], "capture_date": cap,
                     "resolution_m": res, "source": SOURCE})
    return rows


def main():
    cfg = json.loads(get(CONFIG))
    releases = sorted(({"id": int(k), "date": v["itemTitle"][-11:-1], "meta": v["metadataLayerUrl"]} for k, v in cfg.items()),
                      key=lambda r: r["date"])
    js = Path("map/data.js").read_text()
    sites = json.loads(js[js.index("{"):js.rstrip().rstrip(";").rindex("}") + 1])["sites"]
    rows = []
    todo = [s for s in sites if s.get("lat") is not None]
    cache = Path("data/raw/wayback_cache.json")      # resume after a network failure; not committed
    cache.parent.mkdir(parents=True, exist_ok=True)
    done = json.loads(cache.read_text()) if cache.exists() else {}

    def run(s):
        if s["id"] not in done:
            try:
                done[s["id"]] = one_site(s, releases)
            except Exception as e:
                print(f"{s['id']:40s} failed: {type(e).__name__}", flush=True)
                return s, None
            cache.write_text(json.dumps(done))
        return s, done[s["id"]]

    with ThreadPoolExecutor(4) as ex:
        found = [x for x in ex.map(run, todo) if x[1] is not None]
    missing = [s["id"] for s in todo if s["id"] not in done]
    if missing:
        raise SystemExit(f"{len(missing)} campuses failed ({', '.join(missing)}); run again to resume")
    for s, r in found:
        # Keep photos in capture order; a later release can carry an older photo after a reprocess.
        r = sorted({x["capture_date"]: x for x in r}.values(), key=lambda x: x["capture_date"])
        print(f"{s['id']:40s} {len(r):2d} photos  {', '.join(x['capture_date'][:7] for x in r)}", flush=True)
        rows += r
    df = pd.DataFrame(rows)
    df.to_csv("data/wayback_captures.csv", index=False)
    out = {}
    for sid, g in df.groupby("site_id"):
        out[sid] = [[int(c[:4]) * 12 + int(c[5:7]) - 1, int(rel), c] for c, rel in zip(g.capture_date, g.release)]
    Path("map/wayback.js").write_text(
        "// Written by pipeline/map_wayback.py from data/wayback_captures.csv. Do not edit.\n"
        "// Per campus: [t (capture month, year*12+month-1), Wayback release id, capture date].\n"
        f"window.WAYBACK = {json.dumps({'url': TILE.replace('{r}', '{release}').replace('{z}/{y}/{x}', '{z}/{y}/{x}'), 'source': SOURCE, 'sites': out}, separators=(',', ':'))};\n")
    print(f"wrote data/wayback_captures.csv ({len(df)} photos, {df.site_id.nunique()} campuses) and map/wayback.js")


if __name__ == "__main__":
    main()
