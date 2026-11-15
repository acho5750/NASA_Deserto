"""
Story data for the map (map/story.js): numbers the chapters show that are not per-site rows of map/data.js.

- Land under the radar: acres converted at the built campuses, by what the land was before
  (NLCD class under the F1 converted pixels), summed from data/landcover/site_landcover.csv.
- Which satellite saw what: for the three campuses NISAR covers, the Sentinel-1 VV series
  (data/radar/s1_series.csv) and the NISAR HH series of the stack with the most dates
  (data/radar/nisar_series.csv), both as average brightness inside the campus outline, in dB.
- Sensor spans: first and last date of every satellite record the map uses, read from the CSVs.

Run: python pipeline/map_story.py   (after build_map.py)
"""
import json
from pathlib import Path

import pandas as pd

OUT = Path("map/story.js")
GROUPS = ["cropland", "pasture_hay", "forest", "shrub_grass", "wetlands", "water", "barren", "developed"]
PHASE5_IDS = {"FRONTIER-SHACKELFORD": "ANN-STARGATE-SHACKELFORD", "JUPITER-DONAANA": "ANN-STARGATE-DONAANA",
              "LORDSTOWN": "ANN-STARGATE-LORDSTOWN"}


def main():
    lc = pd.read_csv("data/landcover/site_landcover.csv")
    lc = lc[lc.status == "ok"]
    land = {"n_sites": int(len(lc)), "total_acres": round(float(lc.converted_acres.sum()), 1),
            "acres": {g: round(float(lc[f"{g}_acres"].sum()), 1) for g in GROUPS},
            "nlcd_years": [int(lc.nlcd_year.min()), int(lc.nlcd_year.max())],
            "file": "data/landcover/site_landcover.csv", "source": "https://www.mrlc.gov/data"}

    s1 = pd.read_csv("data/radar/s1_series.csv")
    ni = pd.read_csv("data/radar/nisar_series.csv")
    nisar = {}
    for rid, site_id in PHASE5_IDS.items():
        a = s1[s1.site_id == rid].sort_values("date")
        b = ni[ni.site_id == rid]
        stack = b.groupby("stack_id").size().sort_values(ascending=False).index[0]
        b = b[b.stack_id == stack].sort_values("date")
        nisar[site_id] = {
            "radar_id": rid,
            "s1": {"orbit": f"{a.orbit_state.iloc[0]} {int(a.relative_orbit.iloc[0])}",
                   "t": a.date.tolist(), "v": [round(float(x), 2) for x in a.campus_vv_db]},
            "nisar": {"stack": stack, "t": b.date.tolist(), "v": [round(float(x), 2) for x in b.campus_hh_db],
                      "n_acq_all_stacks": int((ni.site_id == rid).sum())},
            "file": "data/radar/s1_series.csv ; data/radar/nisar_series.csv"}

    cov = pd.read_csv("data/nisar_gcov_coverage.csv")
    cov = cov[(cov.usable.astype(str) == "True") & cov.duplicate_of.isna()]
    src = pd.read_csv("data/sources.csv")
    ok = src[src.trend_status == "ok"]
    swot = ok[ok.trend_method.astype(str).str.contains("swot")]
    disp = ok[~ok.trend_method.astype(str).str.contains("swot")]
    curves = sorted(Path("data/footprint").glob("*_area_curve.csv"))
    s1_dates = pd.concat([pd.read_csv(p)["date"] for p in curves])
    sensors = {
        "sentinel1": {"from": str(pd.to_datetime(s1_dates).min().date()), "to": str(pd.to_datetime(s1_dates).max().date()),
                      "file": "data/footprint/*_area_curve.csv"},
        "nisar": {"from": str(cov.acq_date.min()), "to": str(cov.acq_date.max()), "n_usable": int(len(cov)),
                  "file": "data/nisar_gcov_coverage.csv"},
        "swot": {"from": str(swot.trend_start.min()), "to": str(swot.trend_end.max()), "n_sources": int(len(swot)),
                 "file": "data/sources.csv"},
        "opera": {"from": str(disp.trend_start.min()), "to": str(disp.trend_end.max()), "n_sources": int(len(disp)),
                  "file": "data/sources.csv"},
    }
    data = {"land": land, "nisar": nisar, "sensors": sensors}
    OUT.write_text("// Written by pipeline/map_story.py. Do not edit.\nwindow.STORY = " + json.dumps(data, separators=(",", ":")) + ";\n")
    print(f"Wrote {OUT}: land {land['total_acres']} ac at {land['n_sites']} campuses; sensors {json.dumps(sensors)}")
    for k, v in nisar.items():
        print(k, "S1", len(v["s1"]["t"]), "dates; NISAR", v["nisar"]["stack"], len(v["nisar"]["t"]), "dates")


if __name__ == "__main__":
    main()
