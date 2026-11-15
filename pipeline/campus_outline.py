"""
Campus outlines from OpenStreetMap, for pipeline/footprint.py.

The Overpass API is not reachable from the cloud session, so this script uses the two public
OpenStreetMap services that are: the main editing API (api.openstreetmap.org, `map` and
`way|relation/<id>/full` calls) and Nominatim search. Data (c) OpenStreetMap contributors, ODbL.

Two steps:

  1. candidates: list every closed way / multipolygon near a point that looks like a data center
     campus (data_center tags, an owner keyword in name/operator, or landuse=industrial/construction),
     with its area and distance, so a person can pick the right one.
       python pipeline/campus_outline.py candidates --lat 36.41 --lon -86.37 --owner Meta,Facebook
       python pipeline/campus_outline.py search --q "Meta Gallatin Data Center"

  2. build: fetch the chosen OSM objects and write their union as the campus GeoJSON.
       python pipeline/campus_outline.py build --site-id META-GALLATIN --osm way/1312795639,way/1312795640

Every outline is recorded, with the OSM ids and why they were chosen, in
data/footprint/campus_outlines.csv (written by hand from the `build` output; see DECISIONS.md).
"""
import argparse
import json
import math
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

API = "https://api.openstreetmap.org/api/0.6"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
UA = {"User-Agent": "nasa-spaceapps-footprint/0.1 (research; OSM read only)"}
M2_PER_ACRE = 4046.86
OUT_DIR = Path("data/footprint")

AREA_TAGS = {"landuse", "building", "telecom", "man_made", "amenity", "industrial", "barrier", "area"}


def get(url, params=None, tries=4):
    for i in range(tries):
        r = requests.get(url, params=params, headers=UA, timeout=90)
        if r.status_code == 200:
            return r
        if r.status_code in (400, 404, 410):
            r.raise_for_status()
        time.sleep(2 ** i)
    r.raise_for_status()


# ---------- OSM XML -> shapely ----------
def parse(xml_text):
    root = ET.fromstring(xml_text)
    nodes = {n.get("id"): (float(n.get("lon")), float(n.get("lat"))) for n in root.iter("node")}
    ways, rels = {}, {}
    for w in root.iter("way"):
        ways[w.get("id")] = ([nd.get("ref") for nd in w.iter("nd")],
                             {t.get("k"): t.get("v") for t in w.iter("tag")})
    for r in root.iter("relation"):
        rels[r.get("id")] = ([(m.get("type"), m.get("ref"), m.get("role")) for m in r.iter("member")],
                             {t.get("k"): t.get("v") for t in r.iter("tag")})
    return nodes, ways, rels


def way_polygon(refs, nodes):
    from shapely.geometry import Polygon
    if len(refs) < 4 or refs[0] != refs[-1] or any(r not in nodes for r in refs):
        return None
    p = Polygon([nodes[r] for r in refs])
    return p if p.is_valid else p.buffer(0)


def relation_polygon(members, ways, nodes):
    from shapely.geometry import LineString
    from shapely.ops import polygonize, unary_union
    outer, inner = [], []
    for typ, ref, role in members:
        if typ != "way" or ref not in ways:
            continue
        pts = [nodes[r] for r in ways[ref][0] if r in nodes]
        if len(pts) >= 2:
            (inner if role == "inner" else outer).append(LineString(pts))
    if not outer:
        return None
    o = unary_union(list(polygonize(unary_union(outer))))
    if inner:
        o = o.difference(unary_union(list(polygonize(unary_union(inner)))))
    return o if not o.is_empty else None


def utm_epsg(lon, lat):
    return (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1


def area_acres(geom):
    from pyproj import Transformer
    import numpy as np
    from shapely import transform
    c = geom.centroid
    tf = Transformer.from_crs(4326, utm_epsg(c.x, c.y), always_xy=True)
    return transform(geom, lambda xy: np.column_stack(tf.transform(xy[:, 0], xy[:, 1]))).area / M2_PER_ACRE


def dist_km(lon1, lat1, lon2, lat2):
    dx = (lon2 - lon1) * 111.32 * math.cos(math.radians((lat1 + lat2) / 2))
    dy = (lat2 - lat1) * 110.57
    return math.hypot(dx, dy)


# ---------- commands ----------
def cmd_search(a):
    r = get(NOMINATIM, {"q": a.q, "format": "jsonv2", "limit": 10})
    for x in r.json():
        print(f"{x['osm_type']}/{x['osm_id']}\t{x['category']}={x['type']}\t{float(x['lat']):.5f},{float(x['lon']):.5f}\t{x['display_name'][:110]}")


def cmd_candidates(a):
    dlat = a.radius_km / 110.57
    dlon = a.radius_km / (111.32 * math.cos(math.radians(a.lat)))
    bbox = f"{a.lon - dlon:.5f},{a.lat - dlat:.5f},{a.lon + dlon:.5f},{a.lat + dlat:.5f}"
    nodes, ways, rels = parse(get(f"{API}/map", {"bbox": bbox}).text)
    keys = [k.strip().lower() for k in a.owner.split(",") if k.strip()]
    rows = []
    objs = [("way", i, way_polygon(refs, nodes), tags) for i, (refs, tags) in ways.items() if tags]
    objs += [("relation", i, relation_polygon(m, ways, nodes), tags) for i, (m, tags) in rels.items()
             if tags.get("type") == "multipolygon"]
    for typ, i, g, tags in objs:
        if g is None or not (AREA_TAGS & set(tags)):
            continue
        text = " ".join(f"{k}={v}" for k, v in tags.items()).lower()
        dc = "data_center" in text or "data center" in text or "datacenter" in text or "data centre" in text
        owner = any(k in text for k in keys)
        lu = tags.get("landuse") in ("industrial", "construction", "brownfield", "commercial")
        acres = area_acres(g)
        if not (dc or owner or (lu and acres >= a.min_acres)):
            continue
        c = g.representative_point()
        rows.append((dist_km(a.lon, a.lat, c.x, c.y), typ, i, acres, dc, owner, tags))
    rows.sort()
    small = [r for r in rows if r[3] < a.min_acres]
    if small:
        from shapely.ops import unary_union
        from shapely.geometry import MultiPoint
        print(f"# {len(small)} small tagged objects (< {a.min_acres} ac, e.g. buildings): ids " +
              ",".join(f"{r[1]}/{r[2]}" for r in small[:60]))
    for d, typ, i, acres, dc, owner, tags in [r for r in rows if r[3] >= a.min_acres][: a.limit]:
        t = {k: v for k, v in tags.items() if k in ("name", "operator", "landuse", "building", "telecom",
                                                     "man_made", "construction", "barrier", "description")}
        print(f"{typ}/{i}\t{d:5.2f} km\t{acres:8.1f} ac\t{'DC ' if dc else ''}{'OWNER ' if owner else ''}{t}")


def fetch_object(ref):
    typ, oid = ref.split("/")
    nodes, ways, rels = parse(get(f"{API}/{typ}/{oid}/full").text)
    if typ == "way":
        return way_polygon(ways[oid][0], nodes), ways[oid][1]
    return relation_polygon(rels[oid][0], ways, nodes), rels[oid][1]


def cmd_build(a):
    from shapely.geometry import mapping
    from shapely.ops import unary_union
    geoms, feats = [], []
    for ref in a.osm.split(","):
        g, tags = fetch_object(ref.strip())
        if g is None:
            sys.exit(f"{ref}: not a closed polygon")
        geoms.append(g)
        print(f"{ref}\t{area_acres(g):.1f} ac\t{tags}")
    if a.extra_geojson:
        sys.path.insert(0, str(Path(__file__).parent))
        from footprint import load_campus
        g = load_campus(a.extra_geojson)
        geoms.append(g)
        print(f"{a.extra_geojson}\t{area_acres(g):.1f} ac\t(hand-drawn extension)")
    u = unary_union(geoms)
    if a.hull:
        u = u.convex_hull
    feat = {"type": "Feature", "geometry": mapping(u), "properties": {
        "site_id": a.site_id, "osm": a.osm, "hull": bool(a.hull), "extra": a.extra_geojson,
        "source": " ; ".join(f"https://www.openstreetmap.org/{r.strip()}" for r in a.osm.split(",")),
        "license": "(c) OpenStreetMap contributors, ODbL 1.0",
        "retrieved": time.strftime("%Y-%m-%d"), "acres": round(area_acres(u), 1)}}
    out_dir = Path(a.out_dir) if a.out_dir else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{a.site_id}_campus.geojson"
    out.write_text(json.dumps({"type": "FeatureCollection", "features": [feat]}))
    print(f"wrote {out}: {feat['properties']['acres']} ac")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("--q", required=True)
    c = sub.add_parser("candidates")
    c.add_argument("--lat", type=float, required=True); c.add_argument("--lon", type=float, required=True)
    c.add_argument("--radius-km", type=float, default=2.0)
    c.add_argument("--owner", default="")
    c.add_argument("--min-acres", type=float, default=40)
    c.add_argument("--limit", type=int, default=25)
    b = sub.add_parser("build")
    b.add_argument("--site-id", required=True); b.add_argument("--osm", required=True)
    b.add_argument("--hull", action="store_true", help="use the convex hull of the objects (buildings only)")
    b.add_argument("--out-dir", default="", help="default data/footprint; announced sites use data/footprint/announced")
    b.add_argument("--extra-geojson", default="", help="hand-drawn polygon unioned in where OSM is incomplete (flag it)")
    a = p.parse_args()
    {"search": cmd_search, "candidates": cmd_candidates, "build": cmd_build}[a.cmd](a)


if __name__ == "__main__":
    main()
