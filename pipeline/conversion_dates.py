"""When each converted pixel first changed: a per-pixel month for the map's time animation.

Usage:  python pipeline/conversion_dates.py [--only ID1,ID2] [--skip-done]

For each built site in data/footprint/footprint_summary.csv this re-runs F1 exactly as
pipeline/footprint_batch.py did (same window, same orbit choice, same threshold that the summary
recorded) and keeps one extra thing F1 already computes but did not save: the first monthly composite
at which each pixel became "converted" (cumulative, persistent change > threshold).

Check before writing: the final cumulative mask must equal the committed
data/footprint/masks/<id>_converted.tif pixel for pixel, and the orbit must equal the summary's.
If either differs (for example, Planetary Computer reprocessed scenes), the site is skipped and
reported; nothing is written for it.

Writes  data/footprint/masks/<id>_first_converted.tif   uint8, value = months from construction start
        + 100 (so -23 -> 77); 255 = not converted. Same grid as <id>_converted.tif.
        data/footprint/conversion_dates_log.csv           one row per site: ok / skipped and why
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

sys.path.insert(0, str(Path(__file__).parent))
import footprint as fp  # noqa: E402
from footprint_batch import DATA_END, MIN_MONTHS_AFTER, MONTHS_AFTER_OPERATION, MONTHS_BEFORE, months_between  # noqa: E402

MASKS = Path("data/footprint/masks")
LOG = Path("data/footprint/conversion_dates_log.csv")
OFFSET = 100


def window(r):
    cs = pd.Timestamp(r.construction_start)
    op = pd.Timestamp(r.operation_date)
    last = pd.Timestamp(r.planned_final_date) if r.buildout_complete and pd.notna(r.planned_final_date) else DATA_END
    last = max(last, op)
    end = min(max(last + pd.DateOffset(months=MONTHS_AFTER_OPERATION), cs + pd.DateOffset(months=MIN_MONTHS_AFTER)), DATA_END)
    return cs, months_between(cs, end)


def one(r, sm):
    cs, months_after = window(r)
    start, end = fp.month_add(cs, -MONTHS_BEFORE), fp.month_add(cs, months_after)
    campus = fp.load_campus(f"data/footprint/{r.site_id}_campus.geojson")
    c = campus.centroid
    epsg_guess = (32600 if c.y >= 0 else 32700) + int((c.x + 180) // 6) + 1
    aoi_ll = fp.reproject(fp.reproject(campus, 4326, epsg_guess).buffer(fp.BUFFER_M), epsg_guess, 4326)
    items = fp.search_items(aoi_ll, start, end)
    state, orbit, items, _ = fp.choose_orbit(items, fp.month_add(cs, -12), cs)
    if (state, int(orbit)) != (sm.orbit_state, int(sm.relative_orbit)):
        return "skipped", f"orbit now {state} {orbit}, summary has {sm.orbit_state} {sm.relative_orbit}"
    db, _, epsg = fp.load_stack_db(items, aoi_ll)
    site_utm = fp.reproject(campus, 4326, epsg).buffer(fp.SITE_BUFFER_M)
    inside_site, _ = fp.aoi_mask(db, site_utm)
    times = pd.DatetimeIndex(db.time.values)
    base_sel = (times >= fp.month_add(cs, -12)) & (times < cs)
    with np.errstate(all="ignore"):
        baseline = np.nanmedian(db.values[base_sel], axis=0)
    comps, dates, _ = fp.monthly_composites(db, start, MONTHS_BEFORE + months_after)
    cum = fp.cumulative_converted(comps, baseline, float(sm.thresh_db))
    final = cum[-1] & inside_site

    with rasterio.open(MASKS / f"{r.site_id}_converted.tif") as src:
        ref = src.read(1) == 1
        profile = src.profile
    if ref.shape != final.shape or not np.array_equal(ref, final):
        diff = int((ref != final).sum()) if ref.shape == final.shape else -1
        return "skipped", f"final mask differs from committed mask ({diff} pixels; shapes {ref.shape} vs {final.shape})"

    t_months = np.array([(d.year - cs.year) * 12 + (d.month - cs.month) for d in dates[1:]])
    first_idx = np.argmax(cum, axis=0)
    out = np.full(final.shape, 255, dtype="uint8")
    out[final] = (t_months[first_idx[final]] + OFFSET).astype("uint8")
    # Same acres as the saved area curve at every month (cumulative count inside the site).
    curve = pd.read_csv(f"data/footprint/{r.site_id}_area_curve.csv")
    mine = [(out[final] <= m + OFFSET).sum() * 100 / fp.M2_PER_ACRE for m in curve.months_from_start]
    worst = float(np.max(np.abs(np.array(mine) - curve.acres_site.values)))
    if worst > 0.02:
        return "skipped", f"monthly acres differ from area curve by up to {worst:.2f} ac"
    profile.update(dtype="uint8", nodata=255, compress="deflate")
    with rasterio.open(MASKS / f"{r.site_id}_first_converted.tif", "w", **profile) as dst:
        dst.write(out, 1)
        dst.update_tags(value=f"months from construction start ({cs:%Y-%m-%d}) + {OFFSET}; 255 = not converted",
                        construction_start=f"{cs:%Y-%m-%d}", threshold_db=str(sm.thresh_db), source=fp.COLLECTION_LINK)
    return "ok", f"{int(final.sum())} px, curve match within {worst:.2f} ac"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", default="")
    p.add_argument("--skip-done", action="store_true")
    a = p.parse_args()
    sites = pd.read_csv("data/precedent_sites.csv").set_index("site_id")
    summ = pd.read_csv("data/footprint/footprint_summary.csv").set_index("site_id")
    only = {s for s in a.only.split(",") if s}
    log = pd.read_csv(LOG).to_dict("records") if LOG.exists() else []
    for sid in summ.index:
        if (only and sid not in only) or sid not in sites.index or not (MASKS / f"{sid}_converted.tif").exists():
            continue
        if a.skip_done and (MASKS / f"{sid}_first_converted.tif").exists():
            continue
        r = sites.loc[sid].copy(); r["site_id"] = sid
        t = time.time()
        try:
            status, detail = one(r, summ.loc[sid])
        except Exception as e:   # one bad site must not stop the rest
            status, detail = "error", f"{type(e).__name__}: {e}"[:300]
        print(f"{sid:32s} {status:8s} {detail}  ({time.time() - t:.0f} s)", flush=True)
        log = [x for x in log if x["site_id"] != sid] + [{"site_id": sid, "status": status, "detail": detail,
                                                           "run_at": time.strftime("%Y-%m-%d %H:%M")}]
        pd.DataFrame(log).to_csv(LOG, index=False)


if __name__ == "__main__":
    main()
