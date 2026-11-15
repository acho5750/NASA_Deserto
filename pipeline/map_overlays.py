"""Turn the F1 converted-pixel masks into image overlays the map drapes on satellite imagery.

Usage:  python pipeline/map_overlays.py

Reads   data/footprint/masks/<SITE_ID>_converted.tif   (pipeline/footprint.py; 10 m, 1 = converted)
Writes  map/overlays/<SITE_ID>.png                      transparent PNG in Web Mercator
        map/overlays.js                                 window.OVERLAYS = {SITE_ID: {file, coords, ...}}

Nothing is computed here beyond reprojection (nearest neighbour, so no pixel changes class) and colouring:
converted pixels are filled lightly, and the edge of solid patches (opened by one pixel) is drawn brighter
so the shape reads on top of a photo without hiding it.
"""
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform as warp_xy

MASK_DIR = Path("data/footprint/masks")
OUT_DIR = Path("map/overlays")
UPSCALE = 4                     # 10 m pixels drawn as 4x4 blocks so the edge line stays thin
FILL = (255, 64, 40, 85)        # converted pixel
EDGE = (255, 196, 90, 235)      # outer boundary of a converted patch
SOURCE = "https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc"


def edge_of(m):
    """Pixels of m with at least one 4-neighbour outside m (numpy only)."""
    p = np.pad(m, 1)
    inner = p[1:-1, 1:-1] & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    return m & ~inner


def one(path):
    site = path.name.replace("_converted.tif", "")
    with rasterio.open(path) as src:
        dst_crs = "EPSG:3857"
        tf, w, h = calculate_default_transform(src.crs, dst_crs, src.width, src.height, *src.bounds)
        out = np.full((h, w), 255, dtype="uint8")
        reproject(rasterio.band(src, 1), out, src_transform=src.transform, src_crs=src.crs, src_nodata=255,
                  dst_transform=tf, dst_crs=dst_crs, dst_nodata=255, resampling=Resampling.nearest)
        threshold = src.tags().get("threshold_db")
    conv = out == 1
    n_src = None
    with rasterio.open(path) as src:
        n_src = int((src.read(1) == 1).sum())
    big = np.kron(conv, np.ones((UPSCALE, UPSCALE), dtype=bool))
    rgba = np.zeros(big.shape + (4,), dtype="uint8")
    rgba[big] = FILL
    # Edge only around patches of 3+ native pixels in each direction, so speckle stays a light fill.
    solid = conv.copy()
    for _ in range(1):
        p = np.pad(solid, 1)
        solid = solid & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]
    grown = solid.copy()
    p = np.pad(grown, 1)
    grown = grown | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    grown &= conv
    bigsolid = np.kron(grown, np.ones((UPSCALE, UPSCALE), dtype=bool))
    rgba[edge_of(bigsolid)] = EDGE
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(OUT_DIR / f"{site}.png", optimize=True)
    left, top = tf.c, tf.f
    right, bottom = left + tf.a * w, top + tf.e * h
    xs, ys = warp_xy("EPSG:3857", "EPSG:4326", [left, right, right, left], [top, top, bottom, bottom])
    coords = [[round(x, 6), round(y, 6)] for x, y in zip(xs, ys)]
    return site, {"file": f"overlays/{site}.png", "coords": coords, "converted_px_10m": n_src,
                  "threshold_db": threshold, "mask": str(path), "source": SOURCE}


def main():
    entries = dict(one(p) for p in sorted(MASK_DIR.glob("*_converted.tif")))
    js = "// Written by pipeline/map_overlays.py from data/footprint/masks/. Do not edit.\nwindow.OVERLAYS = " + \
         json.dumps(entries, indent=1) + ";\n"
    Path("map/overlays.js").write_text(js)
    for k, v in entries.items():
        print(f"{k:32s} {v['converted_px_10m']:6d} px  ({v['converted_px_10m'] * 100 / 4046.86:7.1f} acres)")
    print(f"wrote {len(entries)} overlays to {OUT_DIR}/ and map/overlays.js")


if __name__ == "__main__":
    main()
