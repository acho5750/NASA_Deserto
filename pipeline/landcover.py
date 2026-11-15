"""
Phase 6: what land each built data center converted, from NLCD land cover before construction.

For each built site, the area measured by F1 (the final cumulative converted pixels inside the
campus outline + 200 m, saved by pipeline/footprint.py as data/footprint/masks/<id>_converted.tif,
10 m UTM) is overlaid on the NLCD land cover map from before construction:

  * NLCD edition = the latest NLCD Land Cover (CONUS) edition whose year is before the site's
    construction start year (editions: 2001, 2004, 2006, 2008, 2011, 2013, 2016, 2019, 2021).
    The gap in years is written in `nlcd_gap_years`.
  * Each 10 m converted pixel takes the NLCD class (30 m) at its centre, so each one counts
    100 m^2 of that class. Acres per class sum to the F1 converted acres.
  * NLCD is read from the MRLC GeoServer WCS 2.0.1 (EPSG:5070, 30 m); the clipped tiles are not kept.

Outputs:
  data/landcover/site_landcover.csv           one row per site: totals and grouped shares
  data/landcover/site_landcover_by_class.csv  one row per site and NLCD class

Usage:  python pipeline/landcover.py [--only ID1,ID2]
"""
import argparse
import io
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import requests
from pyproj import Transformer

WCS = "https://www.mrlc.gov/geoserver/ows"
NLCD_LINK = "https://www.mrlc.gov/data"
EDITIONS = [2001, 2004, 2006, 2008, 2011, 2013, 2016, 2019, 2021]
M2_PER_ACRE = 4046.86
MASK_DIR = Path("data/footprint/masks")
OUT = Path("data/landcover")

NLCD_CLASSES = {
    11: "Open Water", 12: "Perennial Ice/Snow", 21: "Developed, Open Space", 22: "Developed, Low Intensity",
    23: "Developed, Medium Intensity", 24: "Developed, High Intensity", 31: "Barren Land",
    41: "Deciduous Forest", 42: "Evergreen Forest", 43: "Mixed Forest", 52: "Shrub/Scrub",
    71: "Grassland/Herbaceous", 81: "Pasture/Hay", 82: "Cultivated Crops", 90: "Woody Wetlands",
    95: "Emergent Herbaceous Wetlands",
}
GROUPS = {
    "developed": (21, 22, 23, 24), "cropland": (82,), "pasture_hay": (81,), "forest": (41, 42, 43),
    "shrub_grass": (52, 71), "barren": (31,), "wetlands": (90, 95), "water": (11, 12),
}


def edition_for(start: pd.Timestamp) -> int:
    before = [y for y in EDITIONS if y < start.year]
    return before[-1] if before else EDITIONS[0]


def get_nlcd(year, xmin, ymin, xmax, ymax):
    cov = f"mrlc_download__NLCD_{year}_Land_Cover_L48"
    params = [("service", "WCS"), ("version", "2.0.1"), ("request", "GetCoverage"), ("coverageId", cov),
              ("subset", f"X({xmin:.0f},{xmax:.0f})"), ("subset", f"Y({ymin:.0f},{ymax:.0f})"),
              ("format", "image/tiff")]
    for i in range(4):
        r = requests.get(WCS, params=params, timeout=180)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/tiff"):
            break
    else:
        raise RuntimeError(f"NLCD WCS {cov}: HTTP {r.status_code} {r.text[:200]}")
    with rasterio.open(io.BytesIO(r.content)) as src:
        return src.read(1), src.transform, src.crs.to_epsg()


def site_landcover(site_id, start):
    with rasterio.open(MASK_DIR / f"{site_id}_converted.tif") as m:
        mask = m.read(1) == 1
        tf, epsg = m.transform, m.crs.to_epsg()
        res = abs(tf.a)
    rows, cols = np.nonzero(mask)
    year = edition_for(start)
    if len(rows) == 0:
        return year, {}
    xs, ys = rasterio.transform.xy(tf, rows, cols)
    x5070, y5070 = Transformer.from_crs(epsg, 5070, always_xy=True).transform(np.array(xs), np.array(ys))
    pad = 90
    lc, ltf, lepsg = get_nlcd(year, x5070.min() - pad, y5070.min() - pad, x5070.max() + pad, y5070.max() + pad)
    assert lepsg == 5070, lepsg
    r, c = rasterio.transform.rowcol(ltf, x5070, y5070)
    r, c = np.asarray(r), np.asarray(c)
    ok = (r >= 0) & (r < lc.shape[0]) & (c >= 0) & (c < lc.shape[1])
    cls = np.where(ok, lc[np.clip(r, 0, lc.shape[0] - 1), np.clip(c, 0, lc.shape[1] - 1)], 0)
    vals, counts = np.unique(cls, return_counts=True)
    return year, {int(v): n * res * res / M2_PER_ACRE for v, n in zip(vals, counts)}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", default="")
    a = p.parse_args()
    only = set(x for x in a.only.split(",") if x)
    sites = pd.read_csv("data/precedent_sites.csv", parse_dates=["construction_start"])
    OUT.mkdir(parents=True, exist_ok=True)
    summary, long = [], []
    for _, s in sites.iterrows():
        if only and s.site_id not in only:
            continue
        if not (MASK_DIR / f"{s.site_id}_converted.tif").exists():
            summary.append({"site_id": s.site_id, "status": "no_footprint_mask"})
            print(f"{s.site_id}: no footprint mask (F1 not run)")
            continue
        year, acres = site_landcover(s.site_id, s.construction_start)
        total = sum(acres.values())
        row = {"site_id": s.site_id, "status": "ok" if total else "no_converted_pixels",
               "construction_start": s.construction_start.date(), "nlcd_year": year,
               "nlcd_gap_years": s.construction_start.year - year, "converted_acres": round(total, 1)}
        for g, codes in GROUPS.items():
            ga = sum(acres.get(c, 0) for c in codes)
            row[f"{g}_acres"] = round(ga, 1)
            row[f"{g}_pct"] = round(100 * ga / total, 1) if total else np.nan
        if total:
            dom = max(acres, key=acres.get)
            row.update({"dominant_class": NLCD_CLASSES.get(dom, f"code {dom}"),
                        "dominant_pct": round(100 * acres[dom] / total, 1)})
        row["source"] = f"{NLCD_LINK} (NLCD {year} Land Cover L48 via MRLC WCS) ; data/footprint/masks/{s.site_id}_converted.tif"
        summary.append(row)
        for code, ac in sorted(acres.items()):
            long.append({"site_id": s.site_id, "nlcd_year": year, "nlcd_code": code,
                         "nlcd_class": NLCD_CLASSES.get(code, "outside NLCD" if code == 0 else f"code {code}"),
                         "acres": round(ac, 2), "pct": round(100 * ac / total, 1)})
        print(f"{s.site_id:30s} NLCD {year} | {total:7.1f} ac | dominant {row.get('dominant_class')} {row.get('dominant_pct')}%")
    pd.DataFrame(summary).to_csv(OUT / "site_landcover.csv", index=False)
    pd.DataFrame(long).to_csv(OUT / "site_landcover_by_class.csv", index=False)


if __name__ == "__main__":
    main()
