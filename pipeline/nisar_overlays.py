"""
NISAR pictures for the map: radar frames on the ground every 12 days, and where the ground got brighter.

Usage:  python pipeline/nisar_overlays.py [--only SITE_ID,...]

For each of the three NISAR campuses (data/nisar_coverage_sites.csv) and its chart stack (the track
with the most dates, same as pipeline/radar_showcase.py), this reads the HH backscatter of every usable,
non-duplicate GCOV granule (frequency A, 10 m) in a window = campus outline + 1.5 km, with HTTP Range
requests (no full download; windows are cached in data/raw/radar/nisar_frames/, gitignored).

Writes
  map/nisar/<id>_<date>.png     one greyscale HH frame per date (-25..5 dB), transparent outside data
  map/nisar/<id>_change.png     violet where HH got much brighter: mean of the last 3 dates minus mean of
                                the first 3 dates > THRESH_DB, after a 3 x 3 boxcar in linear power.
                                Averaging 3 dates and 3 x 3 pixels damps speckle; the threshold is F1's
                                starting threshold (3 dB).
  map/nisar.js                  frame list, image corners (lon/lat) and the numbers below, for the map
  data/radar/nisar_change.csv   per site: dates compared, pixels and acres brighter by > THRESH_DB inside
                                the campus outline, the outline's acres, and the granule links

Brighter by several dB at L-band means a stronger echo: new buildings, steel, fences or equipment.
It does not say what was built.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import footprint as fp  # noqa: E402
from nisar_coverage import RangeFile, TokenError  # noqa: E402
from radar_showcase import CHART_STACK, WINDOW_M, masks_for  # noqa: E402

RAW = Path("data/raw/radar/nisar_frames")
OUT_IMG = Path("map/nisar")
OUT_JS = Path("map/nisar.js")
OUT_CSV = Path("data/radar/nisar_change.csv")
THRESH_DB = 3.0
N_AVG = 3
SQM_PER_ACRE = 4046.8564224
MAP_IDS = {"FRONTIER-SHACKELFORD": "ANN-STARGATE-SHACKELFORD", "JUPITER-DONAANA": "ANN-STARGATE-DONAANA",
           "LORDSTOWN": "ANN-STARGATE-LORDSTOWN"}


def read_window(url, campus_ll):
    """HH linear power in the window, on a grid fixed by the window (NaN past the frame edge)."""
    import h5py
    with h5py.File(RangeFile(url), "r") as h:
        g = h["science/LSAR/GCOV/grids/frequencyA"]
        epsg = int(g["projection"][()])
        cu = fp.reproject(campus_ll, 4326, epsg)
        xs, ys = g["xCoordinates"][:], g["yCoordinates"][:]
        res = float(xs[1] - xs[0])
        x0, y0, x1, y1 = cu.buffer(WINDOW_M).bounds
        # snap the window to the product grid so every date of a stack lands on the same pixels
        x0 = xs[0] + np.floor((x0 - xs[0]) / res) * res
        y1 = ys[0] - np.floor((ys[0] - y1) / res) * res
        nx, ny = int(np.ceil((x1 - x0) / res)), int(np.ceil((y1 - y0) / res))
        gx, gy = x0 + res * np.arange(nx), y1 - res * np.arange(ny)
        j = np.round((gx - xs[0]) / res).astype(int)
        i = np.round((ys[0] - gy) / res).astype(int)
        jv, iv = (j >= 0) & (j < len(xs)), (i >= 0) & (i < len(ys))
        out = np.full((ny, nx), np.nan, dtype="float32")
        if jv.any() and iv.any():
            sub = g["HHHH"][i[iv].min():i[iv].max() + 1, j[jv].min():j[jv].max() + 1]
            out[np.ix_(iv, jv)] = sub
    return out, gx, gy, epsg, cu


def boxcar(a, k=3):
    """Mean over a k x k window, ignoring NaN (needs more than half the window valid)."""
    ok = np.isfinite(a)
    v = np.where(ok, a, 0.0)
    num = np.zeros_like(v, dtype="float64")
    den = np.zeros_like(v, dtype="float64")
    lo, hi = -(k // 2), k - k // 2
    pv, po = np.pad(v, k), np.pad(ok.astype(float), k)
    H, W = a.shape
    for di in range(lo, hi):
        for dj in range(lo, hi):
            num += pv[k + di:k + di + H, k + dj:k + dj + W]
            den += po[k + di:k + di + H, k + dj:k + dj + W]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > k * k / 2, num / den, np.nan)


def to_db(a):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10 * np.log10(np.where(a > 0, a, np.nan))


def corners(gx, gy, epsg):
    """Lon/lat of the image's outer corners: top-left, top-right, bottom-right, bottom-left."""
    from pyproj import Transformer
    res = gx[1] - gx[0]
    xl, xr, yt, yb = gx[0] - res / 2, gx[-1] + res / 2, gy[0] + res / 2, gy[-1] - res / 2
    t = Transformer.from_crs(epsg, 4326, always_xy=True)
    return [[round(v, 6) for v in t.transform(x, y)] for x, y in ((xl, yt), (xr, yt), (xr, yb), (xl, yb))]


def save_grey(db, path, lo=-25, hi=5, max_px=520):
    from PIL import Image
    g = np.clip((np.nan_to_num(db, nan=lo) - lo) / (hi - lo) * 255, 0, 255).astype("uint8")
    alpha = np.where(np.isfinite(db), 255, 0).astype("uint8")
    im = Image.fromarray(np.dstack([g, alpha]), "LA")
    if max(im.size) > max_px:
        f = max_px / max(im.size)
        im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
    im.save(path, optimize=True)


def save_change(d, path, max_px=900):
    """Violet where the ground got brighter by more than the threshold; stronger = more opaque."""
    from PIL import Image
    a = np.clip((np.nan_to_num(d, nan=0) - THRESH_DB) / 6.0, 0, 1)
    on = np.nan_to_num(d, nan=0) > THRESH_DB
    alpha = np.where(on, 150 + 105 * a, 0).astype("uint8")
    rgb = np.zeros(d.shape + (3,), "uint8")
    rgb[...] = (176, 92, 255)
    im = Image.fromarray(np.dstack([rgb, alpha]), "RGBA")
    if max(im.size) > max_px:
        f = max_px / max(im.size)
        im = im.resize((round(im.width * f), round(im.height * f)), Image.NEAREST)
    im.save(path, optimize=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", default="")
    a = p.parse_args()
    only = {x for x in a.only.split(",") if x}
    cov = pd.read_csv("data/nisar_gcov_coverage.csv", dtype=str)
    cov = cov[(cov.usable == "True") & cov.duplicate_of.isna()]
    RAW.mkdir(parents=True, exist_ok=True)
    OUT_IMG.mkdir(parents=True, exist_ok=True)
    js = json.loads(OUT_JS.read_text().split("=", 1)[1].rstrip().rstrip(";")) if OUT_JS.exists() and only else {}
    rows = pd.read_csv(OUT_CSV).to_dict("records") if OUT_CSV.exists() and only else []
    rows = [r for r in rows if r["site_id"] not in only]
    for sid, stack in CHART_STACK.items():
        if only and sid not in only:
            continue
        campus_ll = fp.load_campus(f"data/footprint/{sid}_campus.geojson")
        g = cov[(cov.site_id == sid) & (cov.stack_id == stack)].sort_values("acq_date")
        frames, stackd = [], []
        for _, r in g.iterrows():
            cache = RAW / f"{sid}_{r.acq_date}.npz"
            if cache.exists():
                z = np.load(cache)
                hh, gx, gy, epsg = z["hh"], z["gx"], z["gy"], int(z["epsg"])
                cu = fp.reproject(campus_ll, 4326, epsg)
            else:
                try:
                    hh, gx, gy, epsg, cu = read_window(r.download_url, campus_ll)
                except TokenError as e:
                    sys.exit(f"stopped: {e}")
                np.savez_compressed(cache, hh=hh, gx=gx, gy=gy, epsg=epsg)
            if stackd and hh.shape != stackd[0].shape:
                print(sid, r.acq_date, "grid differs, skipped"); continue
            stackd.append(hh)
            png = OUT_IMG / f"{sid}_{r.acq_date}.png"
            save_grey(to_db(boxcar(hh, 2)), png)
            frames.append({"date": r.acq_date, "png": str(png.relative_to("map")), "version": r.product_version,
                           "granule": r.source})
            print(sid, r.acq_date, hh.shape, "valid", round(float(np.isfinite(hh).mean()), 3), flush=True)
        arr = np.stack(stackd)
        first = np.nanmean(arr[:N_AVG], axis=0)
        last = np.nanmean(arr[-N_AVG:], axis=0)
        d = to_db(boxcar(last)) - to_db(boxcar(first))
        campus, _ = masks_for(gx, gy, cu)
        res = float(gx[1] - gx[0])
        bright = np.nan_to_num(d, nan=0) > THRESH_DB
        n_in = int((bright & campus).sum())
        save_change(np.where(np.isfinite(d), d, np.nan), OUT_IMG / f"{sid}_change.png")
        row = {"site_id": sid, "map_site_id": MAP_IDS[sid], "stack_id": stack,
               "first_dates": ";".join(frames[i]["date"] for i in range(N_AVG)),
               "last_dates": ";".join(frames[-N_AVG + i]["date"] for i in range(N_AVG)),
               "threshold_db": THRESH_DB, "pixel_m": res,
               "brighter_px_in_outline": n_in,
               "brighter_acres_in_outline": round(n_in * res * res / SQM_PER_ACRE, 1),
               "outline_acres": round(float(campus.sum()) * res * res / SQM_PER_ACRE, 1),
               "median_change_in_outline_db": round(float(np.nanmedian(d[campus])), 2),
               "median_change_ring_db": round(float(np.nanmedian(d[~campus])), 2),
               "source": "data/nisar_gcov_coverage.csv ; https://cmr.earthdata.nasa.gov/search/concepts/C3622241360-ASF.html"}
        rows.append(row)
        js[MAP_IDS[sid]] = {"radar_id": sid, "stack": stack, "corners": corners(gx, gy, epsg), "frames": frames,
                            "change_png": f"nisar/{sid}_change.png", **{k: row[k] for k in (
                                "first_dates", "last_dates", "threshold_db", "brighter_acres_in_outline",
                                "outline_acres", "median_change_in_outline_db", "median_change_ring_db")},
                            "file": str(OUT_CSV)}
        print(sid, {k: row[k] for k in ("brighter_acres_in_outline", "outline_acres", "median_change_in_outline_db", "median_change_ring_db")})
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)
    OUT_JS.write_text("// Written by pipeline/nisar_overlays.py. Do not edit.\nwindow.NISAR = " + json.dumps(js, separators=(",", ":")) + ";\n")
    print("wrote", OUT_CSV, OUT_JS)


if __name__ == "__main__":
    main()
