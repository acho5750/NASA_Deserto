"""NISAR L-band ground motion (L2 GUNW) over one aquifer source, next to its OPERA DISP-S1 series.

Usage:
    python pipeline/gunw_aquifer.py [--source-id SRC-NM3502507] [--track 48] [--frame 17]

Source: data/sources.csv row (default: Mesilla Bolson, Project Jupiter's groundwater source). The
same 6 km x 6 km window centre as its DISP-S1 trend (data/water/disp/...) is used.

Steps
1. CMR search of NISAR_L2_GUNW_V1 and NISAR_L2_GUNW_PROVISIONAL_V1 granules over the point for the
   given track and frame; keep the longest chain of back-to-back pairs (each pair's secondary date
   is the next pair's reference date), so pair displacements can be added up.
2. For each pair, HTTP Range-read (no download to disk) the 80 m unwrapped grid:
   unwrappedPhase, ionospherePhaseScreen, connectedComponents, coherenceMagnitude, over
     WINDOW: 6 km x 6 km centred on the source point (as the DISP-S1 trend)
     REFERENCE: 40 km x 40 km centred on the same point.
   Good pixel = connected component != 0 and equal to the most common component in the window,
   coherence >= MIN_COH. Pair value = median(window) - median(reference) of (unwrapped - ionosphere)
   phase, converted to line-of-sight distance with d = phase * wavelength / (4 pi), wavelength =
   c / centerFrequency. The reference box removes the arbitrary phase offset of each interferogram,
   so the result is motion of the 6 km window RELATIVE TO ITS 40 km SURROUNDINGS, not absolute
   motion. The same value without the ionosphere correction is kept for comparison.
   Sign: as stored in the product (positive phase -> positive value); not converted to up/down.
3. Cumulative series = running sum along the chain.

Outputs
  data/water/gunw/gunw_<water_body_id>_<track>_<frame>.csv   one row per date (pair rows + cumulative)
  map/img/<water_body_id>_ground_motion.png                 DISP-S1 (C-band) and NISAR (L-band) panels
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent))
from nisar_coverage import RangeFile, TokenError   # noqa: E402

CMR = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
GUNW = {"C3622247503-ASF": "NISAR_L2_GUNW_V1", "C2854335566-ASF": "NISAR_L2_GUNW_PROVISIONAL_V1"}
WINDOW_M, REF_M, MIN_COH = 6000, 40000, 0.4
C = 299792458.0
INK, INK2, GRID, C1, C2 = "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6", "#eb6834"


def find_pairs(lat, lon, track, frame):
    rows = []
    for cid, short in GUNW.items():
        r = requests.get(CMR, params={"concept_id": cid, "point": f"{lon},{lat}", "page_size": 2000,
                                      "sort_key": "start_date"}, timeout=60)
        r.raise_for_status()
        for it in r.json()["items"]:
            u = it["umm"]
            a = {x["Name"]: x["Values"] for x in u["AdditionalAttributes"]}
            if a.get("TRACK_NUMBER", [""])[0] != str(track) or a.get("FRAME_NUMBER", [""])[0] != str(frame):
                continue
            p = u["GranuleUR"].split("_")   # ..._<refstart>_<refend>_<secstart>_<secend>_<CRID>_...
            h5 = [x["URL"] for x in u["RelatedUrls"] if x.get("Type") == "GET DATA" and x["URL"].endswith(".h5")]
            rows.append({"ref": p[11][:8], "sec": p[13][:8], "collection": short, "granule_ur": u["GranuleUR"],
                         "url": h5[0] if h5 else "", "source": f"https://cmr.earthdata.nasa.gov/search/concepts/{it['meta']['concept-id']}.umm_json"})
    df = pd.DataFrame(rows)
    # one product per pair: prefer the final version
    df["rank"] = (df.collection != "NISAR_L2_GUNW_V1").astype(int)
    df = df.sort_values(["ref", "sec", "rank"]).drop_duplicates(["ref", "sec"]).drop(columns="rank")
    # longest back-to-back chain
    by_ref = {r.ref: r for r in df.itertuples()}
    best = []
    for start in df.ref:
        chain, cur = [], start
        while cur in by_ref:
            chain.append(by_ref[cur]._asdict())
            cur = by_ref[cur].sec
        if len(chain) > len(best):
            best = chain
    return pd.DataFrame(best), df


def pair_value(url, lat, lon):
    import h5py
    from pyproj import Transformer
    f = RangeFile(url)
    with h5py.File(f, "r") as h:
        g = h["science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram"]
        lam = C / float(h["science/LSAR/GUNW/grids/frequencyA/centerFrequency"][()])
        epsg = int(g["projection"][()])
        x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(lon, lat)
        xs, ys = g["xCoordinates"][:], g["yCoordinates"][:]
        res = float(xs[1] - xs[0])
        j, i = int(round((x - xs[0]) / res)), int(round((ys[0] - y) / res))
        hr, hw = int(REF_M / 2 / res), int(WINDOW_M / 2 / res)
        sl = (slice(max(i - hr, 0), i + hr + 1), slice(max(j - hr, 0), j + hr + 1))
        unw = g["HH/unwrappedPhase"][sl]
        ion = g["HH/ionospherePhaseScreen"][sl]
        cc = g["HH/connectedComponents"][sl]
        coh = g["HH/coherenceMagnitude"][sl]
    ci, cj = i - sl[0].start, j - sl[1].start
    win = np.zeros(unw.shape, bool)
    win[max(ci - hw, 0):ci + hw + 1, max(cj - hw, 0):cj + hw + 1] = True
    base = np.isfinite(unw) & np.isfinite(ion) & (cc != 0) & (cc != 65535) & (coh >= MIN_COH)
    comps, counts = np.unique(cc[base & win], return_counts=True)
    if not len(comps):
        return {"good_frac_window": 0.0}
    comp = comps[np.argmax(counts)]
    good = base & (cc == comp)
    k = lam / (4 * np.pi)
    corr = unw - ion
    return {
        "los_m": round(float((np.median(corr[good & win]) - np.median(corr[good])) * k), 5),
        "los_no_iono_m": round(float((np.median(unw[good & win]) - np.median(unw[good])) * k), 5),
        "good_frac_window": round(float((good & win).sum() / win.sum()), 3),
        "good_frac_reference": round(float(good.sum() / good.size), 3),
        "median_coherence_window": round(float(np.median(coh[good & win])), 3),
        "wavelength_m": round(lam, 5), "epsg": epsg,
    }


def chart(gw, disp_path, name, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    d = pd.read_csv(disp_path)
    d["date"] = pd.to_datetime(d.date.astype(str))
    d = d[d.date >= d.date.max() - pd.DateOffset(years=3)]
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                         "axes.labelcolor": INK2})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.5, 3.4), dpi=150, gridspec_kw={"width_ratios": [2.2, 1], "wspace": 0.3})
    a1.plot(d.date, (d.cum_disp_m - d.cum_disp_m.iloc[0]) * 100, color=C1, lw=1.5, marker="o", ms=2.5)
    a1.set_title("Sentinel-1 C-band (OPERA DISP-S1), last 3 years", loc="left", fontsize=9, color=INK)
    t = pd.to_datetime(gw.date)
    a2.plot(t, gw.cum_los_m * 100, color=C2, lw=2, marker="o", ms=4)
    a2.set_title("NISAR L-band (GUNW), 2026", loc="left", fontsize=9, color=INK)
    for a in (a1, a2):
        a.set_ylabel("line-of-sight change (cm)")
        a.grid(axis="y", color=GRID, lw=0.8)
        a.axhline(0, color=INK2, lw=0.6)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
    lo = min(a1.get_ylim()[0], a2.get_ylim()[0]); hi = max(a1.get_ylim()[1], a2.get_ylim()[1])
    a1.set_ylim(lo, hi); a2.set_ylim(lo, hi)        # same scale, so the noise levels compare fairly
    a1.xaxis.set_major_locator(mdates.YearLocator()); a1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    a2.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[6, 8, 10]))
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    fig.suptitle(f"{name}: ground motion over the aquifer window (6 km x 6 km)", x=0.02, y=1.03, ha="left", fontsize=10, color=INK)
    fig.text(0.02, -0.04, "Each panel starts at zero on its first date and uses its own reference area, so the two lines "
             "are not joined. Both panels use the same scale. Data: OPERA DISP-S1 (ASF DAAC), NISAR L2 GUNW provisional (ASF DAAC).",
             fontsize=6.5, color=INK2)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-id", default="SRC-NM3502507")
    ap.add_argument("--track", default="48")
    ap.add_argument("--frame", default="17")
    a = ap.parse_args()
    src = pd.read_csv("data/sources.csv", dtype=str).set_index("source_id").loc[a.source_id]
    lat, lon = float(src.lat), float(src.lon)
    chain, allp = find_pairs(lat, lon, a.track, a.frame)
    print(f"{len(allp)} GUNW pairs on track {a.track} frame {a.frame}; longest back-to-back chain {len(chain)} pairs "
          f"{chain.ref.iloc[0]} -> {chain.sec.iloc[-1]}")
    rows = []
    for r in chain.itertuples():
        try:
            v = pair_value(r.url, lat, lon)
        except TokenError:
            raise
        print(r.ref, r.sec, v, flush=True)
        rows.append({"ref_date": r.ref, "date": r.sec, "collection": r.collection, **v,
                     "granule_ur": r.granule_ur, "source": r.source})
    gw = pd.DataFrame(rows)
    if gw.los_m.isna().any():
        sys.exit("a pair has no good pixels in the window: chain broken, not summing")
    gw["cum_los_m"] = gw.los_m.cumsum().round(5)
    gw["cum_los_no_iono_m"] = gw.los_no_iono_m.cumsum().round(5)
    first = pd.DataFrame([{"ref_date": "", "date": chain.ref.iloc[0], "cum_los_m": 0.0, "cum_los_no_iono_m": 0.0}])
    gw = pd.concat([first, gw], ignore_index=True)
    for c in ("date", "ref_date"):
        gw[c] = gw[c].apply(lambda s: f"{s[:4]}-{s[4:6]}-{s[6:]}" if s else "")
    out = Path("data/water/gunw")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"gunw_{src.water_body_id}_{a.track}_{a.frame}.csv"
    gw.to_csv(path, index=False)
    print(f"wrote {path}")
    span_days = (pd.Timestamp(gw.date.iloc[-1]) - pd.Timestamp(gw.date.iloc[0])).days
    print(f"cumulative LOS {gw.cum_los_m.iloc[-1] * 1000:.1f} mm over {span_days} days "
          f"(without ionosphere correction {gw.cum_los_no_iono_m.iloc[-1] * 1000:.1f} mm); "
          f"pair-to-pair s.d. {gw.los_m.std() * 1000:.1f} mm")
    img = Path("map/img") / f"{src.water_body_id}_ground_motion.png"
    try:
        chart(gw, src.trend_series_file, src.water_body, img)
        print(f"wrote {img}")
    except ImportError:
        print("matplotlib not installed: chart skipped (the map draws its own chart from the CSV)")


if __name__ == "__main__":
    main()
