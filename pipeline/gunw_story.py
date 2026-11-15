"""
NISAR ground motion over every linked aquifer, for the map (map/gunw.js) and a summary CSV.

Reads data/water/gunw/gunw_<water_body_id>_<track>_<frame>.csv (written by pipeline/gunw_aquifer.py, one per
aquifer source) and data/sources.csv (the OPERA DISP-S1 10-year rate of the same 6 km window).

Per aquifer
  change_mm      cumulative line-of-sight change over the NISAR chain (ionosphere-corrected), relative to the
                 40 km surroundings
  noise_mm       pair-to-pair standard deviation x sqrt(number of pairs): the 1-sigma error of a sum of
                 independent pair errors. Conservative: the pair spread also contains any real motion.
  opera_same_span_mm  the OPERA DISP-S1 10-year rate scaled to the NISAR span (rate x days / 365.25)
  verdict
    too_noisy    pair s.d. > NOISY_SD_MM or a pair with under MIN_GOOD of the window usable: not read
    no_clear     |change| < 2 x noise: no movement NISAR can tell apart from noise yet
    toward/away  |change| >= 2 x noise
Run: python pipeline/gunw_story.py   (after gunw_aquifer.py)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT_JS = Path("map/gunw.js")
OUT_CSV = Path("data/water/gunw/gunw_summary.csv")
NOISY_SD_MM, MIN_GOOD = 15.0, 0.3


def main():
    src = pd.read_csv("data/sources.csv", dtype={"trend_value": float})
    rows, js = [], {}
    for f in sorted(Path("data/water/gunw").glob("gunw_WB-*.csv")):
        g = pd.read_csv(f)
        wb, track, frame = f.stem[5:].rsplit("_", 2)
        s = src[src.water_body_id == wb].iloc[0]
        pr = g[g.ref_date.notna()]
        n = len(pr)
        sd = float(pr.los_m.std() * 1000)
        change = float(g.cum_los_m.iloc[-1] * 1000)
        noise = sd * np.sqrt(n)
        days = (pd.Timestamp(g.date.iloc[-1]) - pd.Timestamp(g.date.iloc[0])).days
        opera = float(s.trend_value) * days / 365.25 if s.trend_status == "ok" else None
        min_good = float(pr.good_frac_window.min())
        if sd > NOISY_SD_MM or min_good < MIN_GOOD:
            verdict = "too_noisy"
        elif abs(change) < 2 * noise:
            verdict = "no_clear"
        else:
            verdict = "toward" if change > 0 else "away"
        row = {"source_id": s.source_id, "water_body_id": wb, "water_body": s.water_body, "track": track,
               "frame": frame, "first_date": g.date.iloc[0], "last_date": g.date.iloc[-1], "days": days,
               "n_pairs": n, "change_mm": round(change, 1), "pair_sd_mm": round(sd, 1), "noise_mm": round(noise, 1),
               "min_good_frac_window": round(min_good, 3), "verdict": verdict,
               "opera_rate_mm_yr": round(float(s.trend_value), 2) if opera is not None else None,
               "opera_same_span_mm": round(opera, 1) if opera is not None else None,
               "opera_span": f"{s.trend_start} to {s.trend_end}",
               "file": str(f), "source": "https://cmr.earthdata.nasa.gov/search/concepts/C2854335566-ASF.html ; "
                                         "https://cmr.earthdata.nasa.gov/search/concepts/C3622247503-ASF.html"}
        rows.append(row)
        js[s.source_id] = {**{k: row[k] for k in ("water_body", "track", "frame", "first_date", "last_date", "days",
                                                  "n_pairs", "change_mm", "noise_mm", "verdict", "opera_rate_mm_yr",
                                                  "opera_same_span_mm")},
                           "t": g.date.tolist(), "v": [round(x * 1000, 1) for x in g.cum_los_m], "file": str(f)}
        print(f"{wb:24s} {track}/{frame} {g.date.iloc[0]}..{g.date.iloc[-1]} pairs {n:2d} change {change:7.1f} mm "
              f"noise {noise:5.1f} mm  OPERA same span {opera if opera is None else round(opera, 1)} mm -> {verdict}")
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)
    OUT_JS.write_text("// Written by pipeline/gunw_story.py. Do not edit.\nwindow.GUNW = " + json.dumps(js, separators=(",", ":")) + ";\n")
    print("wrote", OUT_CSV, OUT_JS)


if __name__ == "__main__":
    main()
