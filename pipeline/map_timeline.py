"""Time data for the map's Play animation (Phase 7 map, third design).

Usage:  python pipeline/map_timeline.py

Reads   data/footprint/masks/<id>_first_converted.tif   (pipeline/conversion_dates.py)
        data/footprint/<id>_area_curve.csv               (pipeline/footprint.py, F1)
Writes  map/pixels/<id>.json    GeoJSON per site (loaded when that campus is opened): converted Sentinel-1
                                pixels merged into polygons by the month they first changed.
                                Property t = month index (year*12 + month-1).
        map/timeline.js         window.TIMELINE = {curves: {site: [[t, acres_site], ...]}, pixels: [site, ...], t0, t1}

No new numbers: polygons are the committed mask's pixels grouped by month, and the curves are the saved
area curves. The script checks that the polygons' area per month reproduces each curve.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio import features
from pyproj import Transformer

MASKS = Path("data/footprint/masks")
OFFSET = 100
M2_PER_ACRE = 4046.86


def month_index(ts):
    return ts.year * 12 + ts.month - 1


def site_pixels(path):
    sid = path.name.replace("_first_converted.tif", "")
    with rasterio.open(path) as src:
        a = src.read(1)
        cs = pd.Timestamp(src.tags()["construction_start"])
        tf, crs = src.transform, src.crs
    to_ll = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    base = month_index(cs)
    feats, px = [], 0
    for geom, v in features.shapes(a, mask=a != 255, transform=tf, connectivity=4):
        v = int(v)
        rings = []
        for ring in geom["coordinates"]:
            xs, ys = zip(*ring)
            lon, lat = to_ll.transform(xs, ys)
            rings.append([[round(x, 5), round(y, 5)] for x, y in zip(lon, lat)])
        feats.append({"type": "Feature", "properties": {"t": base + v - OFFSET},
                      "geometry": {"type": "Polygon", "coordinates": rings}})
    # Check against the area curve: cumulative pixels by month = acres_site.
    curve = pd.read_csv(f"data/footprint/{sid}_area_curve.csv")
    vals = a[a != 255].astype(int) - OFFSET
    mine = np.array([(vals <= m).sum() * 100 / M2_PER_ACRE for m in curve.months_from_start])
    worst = float(np.max(np.abs(mine - curve.acres_site.values)))
    assert worst <= 0.02, f"{sid}: pixel months disagree with area curve by {worst:.2f} ac"
    pts = [[month_index(pd.Timestamp(d)), round(float(ac), 2)] for d, ac in zip(curve.date, curve.acres_site)]
    return sid, feats, pts, len(vals)


def main():
    curves, total = {}, 0
    Path("map/pixels").mkdir(exist_ok=True)
    for p in sorted(MASKS.glob("*_first_converted.tif")):
        sid, f, pts, n = site_pixels(p)
        curves[sid] = pts
        out = Path(f"map/pixels/{sid}.json")
        out.write_text(json.dumps({"type": "FeatureCollection", "features": f}, separators=(",", ":")))
        total += out.stat().st_size
        print(f"{sid:32s} {n:6d} px  {len(f):5d} polygons  {out.stat().st_size / 1e6:4.1f} MB  "
              f"curve {pts[0][1]:.1f} -> {pts[-1][1]:.1f} ac")
    # Curves for every site with a saved F1 area curve, including announced sites that have no pixel mask.
    for c in sorted(Path("data/footprint").glob("*_area_curve.csv")):
        sid = c.name.replace("_area_curve.csv", "")
        if sid not in curves:
            df = pd.read_csv(c)
            curves[sid] = [[month_index(pd.Timestamp(d)), round(float(ac), 2)] for d, ac in zip(df.date, df.acres_site)]
    pix = sorted(p.stem for p in Path("map/pixels").glob("*.json"))
    t_all = [t for c in curves.values() for t, _ in c]
    js = ("// Written by pipeline/map_timeline.py from data/footprint/. Do not edit.\n"
          "// t = year*12 + month-1 (month of the composite). acres = acres_site from <id>_area_curve.csv.\n"
          f"window.TIMELINE = {json.dumps({'t0': min(t_all), 't1': max(t_all), 'pixels': pix, 'curves': curves}, separators=(',', ':'))};\n")
    Path("map/timeline.js").write_text(js)
    print(f"wrote map/pixels/ ({total / 1e6:.1f} MB) and map/timeline.js ({len(curves)} sites)")


if __name__ == "__main__":
    main()
