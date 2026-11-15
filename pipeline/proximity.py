"""
Phase 6: distance from each site and each water source to the nearest wetland (NWI) and the nearest
protected area (PAD-US).

Services (public, no credentials):
  NWI      USFWS National Wetlands Inventory, layer 0 "Wetlands"
           https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0
  PAD-US   USGS Protected Areas Database of the US 4.1, Fee layer
           https://edits.nationalmap.gov/arcgis/rest/services/PAD-US/PAD_US_4_1/MapServer/0

What is measured (see DECISIONS.md, Phase 6):
  * From: a site's campus outline (OSM, data/footprint/<id>_campus.geojson for built sites,
    data/footprint/announced/<id>_campus.geojson for announced ones) where there is one, else the
    registry point; a source's point from data/sources.csv (its location_basis says what the point is).
    Distance 0 means the feature touches or overlaps the outline.
  * Wetland, any type: the nearest NWI polygon of any type (includes lakes, ponds and rivers).
  * Wetland, vegetated: the nearest NWI polygon whose WETLAND_TYPE is a marsh, swamp or bog type
    (Freshwater Emergent Wetland, Freshwater Forested/Shrub Wetland, Estuarine and Marine Wetland).
  * Protected area: the nearest PAD-US Fee polygon with GAP status 1, 2 or 3 (managed for
    biodiversity or for multiple uses with protection; GAP 4 = no known mandate is left out).
  * Distances are in metres, measured in the site's UTM zone. Search widens 1 -> 5 -> 25 -> 100 km;
    nothing within 100 km is written as blank with status none_within_100km.

Usage:
  python pipeline/proximity.py            # all sites + all sources -> data/proximity/*.csv
  python pipeline/proximity.py --only GOOGLE-LANCASTER
"""
import argparse
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform as shp_transform, unary_union

NWI = "https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0/query"
PADUS = "https://edits.nationalmap.gov/arcgis/rest/services/PAD-US/PAD_US_4_1/MapServer/0/query"
NWI_LINK = "https://www.fws.gov/program/national-wetlands-inventory"
PADUS_LINK = "https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview"
RADII_KM = [1, 5, 25, 100]
VEGETATED = ("Freshwater Emergent Wetland", "Freshwater Forested/Shrub Wetland", "Estuarine and Marine Wetland")
OUT = Path("data/proximity")
UA = {"User-Agent": "nasa-spaceapps-proximity/0.1 (research)"}


def _query(url, bbox, where, fields, page=1000):
    """All polygons intersecting a lon/lat bbox, as (geometry, attributes); pages through results."""
    feats, offset = [], 0
    while True:
        params = {"geometry": ",".join(f"{v:.6f}" for v in bbox), "geometryType": "esriGeometryEnvelope",
                  "inSR": 4326, "outSR": 4326, "spatialRel": "esriSpatialRelIntersects", "where": where,
                  "outFields": fields, "returnGeometry": "true", "f": "geojson",
                  "resultOffset": offset, "resultRecordCount": page, "maxAllowableOffset": 0.0001}
        for i in range(5):
            try:
                r = requests.post(url, data=params, headers=UA, timeout=180)
                if r.status_code == 200 and r.text.lstrip().startswith("{"):
                    d = r.json()
                    if "error" not in d:
                        break
            except requests.RequestException:
                pass
            time.sleep(2 ** i)
        else:
            raise RuntimeError(f"{url} failed for bbox {bbox}: {r.status_code} {r.text[:200]}")
        got = d.get("features", [])
        feats += [(shape(f["geometry"]), f.get("properties", {})) for f in got if f.get("geometry")]
        if len(got) < page and not d.get("exceededTransferLimit") and not d.get("properties", {}).get("exceededTransferLimit"):
            return feats
        offset += len(got)
        if not got:
            return feats


def _utm(lon, lat):
    epsg = (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1
    fwd = Transformer.from_crs(4326, epsg, always_xy=True).transform
    return fwd


def nearest(geom_ll, url, where, fields, keep=None):
    """Distance (m) from geom_ll to the nearest returned polygon, with that polygon's attributes."""
    c = geom_ll.centroid
    fwd = _utm(c.x, c.y)
    g = shp_transform(fwd, geom_ll)
    for km in RADII_KM:
        minx, miny, maxx, maxy = geom_ll.bounds
        dlat = km / 111.0
        dlon = km / (111.0 * max(np.cos(np.radians(c.y)), 0.2))
        feats = _query(url, (minx - dlon, miny - dlat, maxx + dlon, maxy + dlat), where, fields)
        if keep:
            feats = [f for f in feats if keep(f[1])]
        best = None
        for fg, attrs in feats:
            try:
                d = g.distance(shp_transform(fwd, fg))
            except Exception:
                continue
            if best is None or d < best[0]:
                best = (d, attrs)
        if best and best[0] <= km * 1000:
            return round(best[0]), best[1], f"found_within_{km}km"
    return np.nan, {}, "none_within_100km"


def measure(geom_ll):
    out = {}
    d, a, st = nearest(geom_ll, NWI, "1=1", "ATTRIBUTE,WETLAND_TYPE")
    out.update({"wetland_any_m": d, "wetland_any_type": a.get("WETLAND_TYPE"), "wetland_any_code": a.get("ATTRIBUTE"),
                "wetland_any_status": st})
    w = "WETLAND_TYPE IN (" + ",".join(f"'{t}'" for t in VEGETATED) + ")"
    d, a, st = nearest(geom_ll, NWI, w, "ATTRIBUTE,WETLAND_TYPE")
    out.update({"wetland_vegetated_m": d, "wetland_vegetated_type": a.get("WETLAND_TYPE"),
                "wetland_vegetated_code": a.get("ATTRIBUTE"), "wetland_vegetated_status": st})
    d, a, st = nearest(geom_ll, PADUS, "GAP_Sts IN ('1','2','3')", "Unit_Nm,Mang_Name,Des_Tp,GAP_Sts")
    out.update({"protected_m": d, "protected_name": a.get("Unit_Nm"), "protected_manager": a.get("Mang_Name"),
                "protected_designation": a.get("Des_Tp"), "protected_gap_status": a.get("GAP_Sts"),
                "protected_status": st})
    return out


def _outline(path):
    p = Path(path)
    if not p.exists():
        return None
    gj = json.loads(p.read_text())
    return unary_union([shape(f["geometry"]) for f in gj["features"]])


def site_geoms():
    rows = []
    for _, s in pd.read_csv("data/precedent_sites.csv").iterrows():
        g = _outline(f"data/footprint/{s.site_id}_campus.geojson")
        rows.append((s.site_id, "built", g if g is not None else Point(s.lon, s.lat),
                     "OSM campus outline" if g is not None else f"registry point ({s.geocode_precision})"))
    for _, s in pd.read_csv("data/announced_sites.csv").iterrows():
        prec = s.get("location_precision", "")
        if prec == "missing" or pd.isna(s.lat):
            rows.append((s.site_id, "announced", None, "location_missing"))
            continue
        g = _outline(f"data/footprint/announced/{s.site_id}_campus.geojson")
        rows.append((s.site_id, "announced", g if g is not None else Point(s.lon, s.lat),
                     "OSM campus outline" if g is not None else f"registry point ({prec})"))
    return rows


def _write(rows, path, key, upsert):
    """Write rows; with --only, replace just those rows in the existing file."""
    if not rows:
        return
    new = pd.DataFrame(rows)
    if upsert and path.exists():
        old = pd.read_csv(path)
        new = pd.concat([old[~old[key].isin(new[key])], new], ignore_index=True)
    new.to_csv(path, index=False)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", default="", help="comma-separated site_id / source_id")
    a = p.parse_args()
    only = set(x for x in a.only.split(",") if x)
    OUT.mkdir(parents=True, exist_ok=True)

    rows = []
    for sid, lst, g, basis in site_geoms():
        if only and sid not in only:
            continue
        r = {"site_id": sid, "list": lst, "measured_from": basis}
        if g is not None:
            r.update(measure(g))
        else:
            r.update({"wetland_any_status": "location_missing", "wetland_vegetated_status": "location_missing",
                      "protected_status": "location_missing"})
        r["source"] = f"{NWI_LINK} ; {PADUS_LINK}"
        print(sid, {k: r.get(k) for k in ("wetland_any_m", "wetland_vegetated_m", "protected_m", "protected_name")})
        rows.append(r)
    _write(rows, OUT / "site_proximity.csv", "site_id", bool(only))

    rows = []
    for _, s in pd.read_csv("data/sources.csv").iterrows():
        if only and s.source_id not in only:
            continue
        r = {"source_id": s.source_id, "water_body": s.water_body, "measured_from": s.location_basis}
        r.update(measure(Point(s.lon, s.lat)))
        r["source"] = f"{NWI_LINK} ; {PADUS_LINK}"
        print(s.source_id, {k: r.get(k) for k in ("wetland_any_m", "wetland_vegetated_m", "protected_m", "protected_name")})
        rows.append(r)
    _write(rows, OUT / "source_proximity.csv", "source_id", bool(only))


if __name__ == "__main__":
    main()
