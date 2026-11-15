"""
Run pipeline/footprint.py (F1) on every built precedent site that has a campus outline.

Inputs
  data/precedent_sites.csv          construction_start, operation_date, name (Epoch, PR 6)
  data/footprint/campus_outlines.csv OSM ids per site (pipeline/campus_outline.py builds the GeoJSON)

Window per site
  start = construction_start - 24 months (12 of them are the baseline year)
  end   = (last building operational) + 6 months, at least construction_start + 18 months, never
          after DATA_END. "Last building operational" = planned_final_date when Epoch marks the
          buildout complete (it is then the date the final building came online), else DATA_END.
  Epoch's MW are the whole campus as of 2026, so the acres must cover the whole buildout too, not
  just the first building. The 6 extra months let the last cleared land show as persistent change.

Outputs
  data/footprint/<site_id>_area_curve.csv, data/footprint/footprint_summary.csv (via footprint.py)
  map/img/<site_id>_radar.png       before/after Sentinel-1 image for the map
  data/footprint/batch_log.csv      one row per site: ok / skipped / error and why

Usage:  python pipeline/footprint_batch.py [--only ID1,ID2] [--skip-done]
        python pipeline/footprint_batch.py --refit     # redo only the logistic fit from saved curves
"""
import argparse
import sys
import time
import traceback
from argparse import Namespace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import footprint  # noqa: E402

DATA_END = pd.Timestamp("2026-11-01")   # last full month of sentinel-1-rtc when this was run
MONTHS_BEFORE = 24
MONTHS_AFTER_OPERATION = 6
MIN_MONTHS_AFTER = 18
LOG = Path("data/footprint/batch_log.csv")


def months_between(a, b):
    return (b.year - a.year) * 12 + (b.month - a.month)


def refit(summary_path=Path("data/footprint/footprint_summary.csv")):
    import numpy as np
    sm = pd.read_csv(summary_path)
    for i, r in sm.iterrows():
        c = pd.read_csv(f"data/footprint/{r.site_id}_area_curve.csv")
        amax, t0, k, build, edge = footprint.fit_logistic(c.months_from_start, c.acres_site)
        noise = "noise_floor_above_5pct_at_max_threshold" if "noise_floor" in str(r.flag) else ""
        sm.loc[i, ["a_max_acres", "logistic_t0_months", "build_months"]] = [round(amax, 1), round(t0, 1), round(build, 1)]
        sm.loc[i, "flag"] = footprint.fit_flags(noise, edge, t0, k, list(c.months_from_start))
        print(f"{r.site_id:30s} A_max {amax:8.1f} ac  t0 {t0:+6.1f} mo  build {build:6.1f} mo  {sm.loc[i, 'flag']}")
    sm.to_csv(summary_path, index=False)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sites", default="data/precedent_sites.csv")
    p.add_argument("--outlines", default="data/footprint/campus_outlines.csv")
    p.add_argument("--only", default="")
    p.add_argument("--skip-done", action="store_true")
    p.add_argument("--refit", action="store_true", help="refit the logistic from saved area curves, no download")
    a = p.parse_args()
    if a.refit:
        return refit()

    sites = pd.read_csv(a.sites)
    outl = pd.read_csv(a.outlines, dtype=str).fillna("").set_index("site_id")
    only = {s for s in a.only.split(",") if s}
    done = set()
    if a.skip_done and Path("data/footprint/footprint_summary.csv").exists():
        done = set(pd.read_csv("data/footprint/footprint_summary.csv").site_id)
    log = pd.read_csv(LOG).to_dict("records") if LOG.exists() else []

    for r in sites.itertuples():
        if (only and r.site_id not in only) or r.site_id in done:
            continue
        row = {"site_id": r.site_id, "run_at": time.strftime("%Y-%m-%d %H:%M"), "status": "", "detail": ""}
        o = outl.loc[r.site_id] if r.site_id in outl.index else None
        if o is None or not o.osm:
            row.update(status="skipped", detail=(o.outline_flag if o is not None else "no outline row"))
        else:
            cs = pd.Timestamp(r.construction_start)
            op = pd.Timestamp(r.operation_date)
            last = pd.Timestamp(r.planned_final_date) if r.buildout_complete and pd.notna(r.planned_final_date) else DATA_END
            last = max(last, op)
            end = min(max(last + pd.DateOffset(months=MONTHS_AFTER_OPERATION), cs + pd.DateOffset(months=MIN_MONTHS_AFTER)), DATA_END)
            args = Namespace(
                site_id=r.site_id, name=r.name, campus=f"data/footprint/{r.site_id}_campus.geojson",
                construction_start=r.construction_start, months_before=MONTHS_BEFORE,
                months_after=months_between(cs, end), thresh_db=footprint.THRESH_START_DB,
                source=f"https://epoch.ai/data/data-centers ; outline: OpenStreetMap {o.osm} (ODbL)",
                quicklook="", radar_png=f"map/img/{r.site_id}_radar.png",
            )
            print(f"\n=== {r.site_id}  start {r.construction_start}  operation {r.operation_date}  "
                  f"window to {end:%Y-%m-%d} ({args.months_after} months after start)", flush=True)
            t = time.time()
            try:
                footprint.run(args)
                row.update(status="ok", detail=f"{time.time() - t:.0f} s")
            except SystemExit as e:
                row.update(status="error", detail=str(e)[:300])
            except Exception as e:  # keep going; one bad site must not stop the batch
                traceback.print_exc()
                row.update(status="error", detail=f"{type(e).__name__}: {e}"[:300])
        print(f"--> {r.site_id}: {row['status']} {row['detail']}", flush=True)
        log = [x for x in log if x["site_id"] != r.site_id] + [row]
        pd.DataFrame(log).to_csv(LOG, index=False)


if __name__ == "__main__":
    main()
