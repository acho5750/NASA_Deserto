"""Write the map's radar panels (Phase 5) from the committed CSVs.

Usage:  python pipeline/radar_panels.py

Every number in a caption is computed here from:
  data/radar/s1_series.csv, data/radar/nisar_series.csv     (pipeline/radar_showcase.py)
  data/footprint/footprint_summary.csv                       (pipeline/footprint.py)
  data/water/gunw/gunw_WB-MESILLA_48_17.csv, data/sources.csv (pipeline/gunw_aquifer.py, water_chain.py)
Outputs:
  data/radar/map_panels.csv   one row per panel: caption, images, values used, source links
  map/radar_panels.js         window.RADAR_PANELS for map/index.html

Captions describe what the radar measured. They do not say a data center caused any change in a
water source (CLAUDE.md map-copy rule).
"""
import csv
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import footprint as fp                      # noqa: E402
from radar_showcase import CHART_STACK, CONSTRUCTION_START   # noqa: E402

SRC_S1 = "https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc"
SRC_NISAR_GCOV = "https://cmr.earthdata.nasa.gov/search/concepts/C2854338529-ASF.html ; https://cmr.earthdata.nasa.gov/search/concepts/C3622241360-ASF.html"
SRC_GUNW = "https://cmr.earthdata.nasa.gov/search/concepts/C2854335566-ASF.html"
SRC_DISP = "https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-v1-1"
NOTE = {
    "FRONTIER-SHACKELFORD": "",
    "JUPITER-DONAANA": " The outline covers only part of the campus, so the acres are a lower bound.",
    "LORDSTOWN": " Most of the work here is inside an existing plant building; radar sees the roof, not the inside.",
}


def site_panels():
    s1 = pd.read_csv("data/radar/s1_series.csv", parse_dates=["date"])
    ni = pd.read_csv("data/radar/nisar_series.csv", parse_dates=["date"])
    fs = pd.read_csv("data/footprint/footprint_summary.csv").set_index("site_id")
    sites = list(csv.DictReader(open("data/nisar_coverage_sites.csv")))
    rows = []
    for s in sites:
        sid = s["site_id"]
        a = s1[s1.site_id == sid].sort_values("date")
        n = ni[(ni.site_id == sid) & (ni.stack_id == CHART_STACK[sid])].sort_values("date")
        cs = pd.Timestamp(CONSTRUCTION_START[sid])
        base = a[(a.date < cs) & (a.date >= cs - pd.DateOffset(months=12))].campus_vv_db.mean()
        now = a.campus_vv_db.tail(3).mean()
        dh = n.campus_hh_db.tail(2).mean() - n.campus_hh_db.head(2).mean()
        acres = float(fs.loc[sid, "final_acres_site"])
        c = fp.load_campus(f"data/footprint/{sid}_campus.geojson").centroid
        verb = "rose" if now - base >= 1 else "changed little"
        cap = (f"Sentinel-1 radar brightness inside the campus outline {verb}: {base:.1f} dB in the 12 months before "
               f"construction began ({cs:%b %Y}), {now:.1f} dB on the latest dates (to {a.date.max():%d %b %Y}). "
               f"NISAR L-band brightness changed by {dh:+.1f} dB between {n.date.min():%d %b} and {n.date.max():%d %b %Y}. "
               f"Bright means a strong echo, from buildings, steel and equipment. Sentinel-1 counts about "
               f"{round(acres, -1):,.0f} acres of changed land inside the outline plus 200 m."
               + NOTE[sid])
        rows.append({
            "id": sid, "kind": "site", "name": s["name"], "lat": round(c.y, 5), "lon": round(c.x, 5),
            "caption": cap,
            "images": f"img/{sid}_radar.png;img/{sid}_nisar.png;img/{sid}_timeseries.png",
            "values": json.dumps({"s1_vv_baseline_db": round(base, 2), "s1_vv_latest_db": round(now, 2),
                                  "nisar_hh_change_db": round(dh, 2), "final_acres_site": acres}),
            "source": "data/radar/s1_series.csv ; data/radar/nisar_series.csv ; data/footprint/footprint_summary.csv ; "
                      f"{SRC_S1} ; {SRC_NISAR_GCOV} ; {s['active_construction_source']}",
        })
    return rows


def aquifer_panel():
    src = pd.read_csv("data/sources.csv", dtype=str).set_index("source_id").loc["SRC-NM3502507"]
    g = pd.read_csv("data/water/gunw/gunw_WB-MESILLA_48_17.csv")
    pairs = g.dropna(subset=["los_m"])
    total = float(g.cum_los_m.iloc[-1]) * 1000
    unc = float(pairs.los_m.std()) * 1000 * len(pairs) ** 0.5
    d0, d1 = pd.Timestamp(g.date.iloc[0]), pd.Timestamp(g.date.iloc[-1])
    cap = (f"Ground motion over a 6 km x 6 km area of the {src.water_body} aquifer. NISAR L-band, "
           f"{d0:%d %b} to {d1:%d %b %Y}: no motion above about {round(unc / 10):.0f} cm detected "
           f"(measured {total:+.1f} mm, uncertainty about {unc:.0f} mm). Sentinel-1 (OPERA DISP-S1), "
           f"{pd.Timestamp(src.trend_start):%Y} to {pd.Timestamp(src.trend_end):%Y}: {float(src.trend_value):+.1f} mm per year "
           f"along the satellite's line of sight.")
    return [{
        "id": src.water_body_id, "kind": "aquifer", "name": src.water_body, "lat": float(src.lat), "lon": float(src.lon),
        "caption": cap, "images": f"img/{src.water_body_id}_ground_motion.png",
        "values": json.dumps({"nisar_cum_los_mm": round(total, 1), "nisar_uncertainty_mm": round(unc, 1),
                              "disp_s1_mm_per_yr": float(src.trend_value)}),
        "source": f"data/water/gunw/gunw_WB-MESILLA_48_17.csv ; data/sources.csv ; {SRC_GUNW} ; {SRC_DISP}",
    }]


def main():
    rows = site_panels() + aquifer_panel()
    df = pd.DataFrame(rows)
    df.to_csv("data/radar/map_panels.csv", index=False)
    js = "window.RADAR_PANELS = " + json.dumps(
        [{k: r[k] for k in ("id", "kind", "name", "lat", "lon", "caption", "source")} | {"images": r["images"].split(";")}
         for r in rows], indent=1) + ";\n"
    Path("map/radar_panels.js").write_text(js)
    for r in rows:
        print(f"{r['id']}: {r['caption']}\n")
    print("wrote data/radar/map_panels.csv, map/radar_panels.js")


if __name__ == "__main__":
    main()
