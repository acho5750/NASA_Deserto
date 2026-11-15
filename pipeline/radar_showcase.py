"""Phase 5 showcase: NISAR L-band (GCOV HH/HV) next to Sentinel-1 C-band (RTC VV/VH) over the
three construction sites in data/nisar_coverage_sites.csv.

Usage:
    python pipeline/radar_showcase.py [--only SITE_ID,...] [--skip-s1] [--skip-nisar] [--plots-only]

Inputs
  data/nisar_coverage_sites.csv        sites (Phase 5 ids)
  data/nisar_gcov_coverage.csv         NISAR granules + usable flag (pipeline/nisar_coverage.py)
  data/footprint/<id>_campus.geojson   campus outline (OSM or hand-drawn, see campus_outlines.csv)
  data/footprint/footprint_summary.csv Sentinel-1 orbit chosen by pipeline/footprint.py (F1)

What it computes, per acquisition
  campus_*_db  10*log10 of the MEAN linear gamma0 inside the campus outline (area-average brightness)
  ref_*_db     10*log10 of the MEDIAN linear gamma0 in a reference ring, 500 m to 1,500 m outside
               the outline. Used to check that the sensor's calibration is steady: the ring is
               mostly untouched land, so it should not jump between product versions.
  NISAR: every usable, non-duplicate GCOV granule (frequency A, 10 m) over the site, all tracks.
  Sentinel-1: every acquisition of the relative orbit footprint.py chose, 12 months before
  construction start to --end.

Calibration check (provisional 1.0.11 vs final 1.0.20 NISAR GCOV)
  For each NISAR stack (track + frame) the step at the version change is
      mean(ref, first 2 final-version dates) - mean(ref, last 3 provisional dates)
  and is compared with the stack's typical date-to-date change (s.d. of consecutive differences
  of the provisional dates). The two versions are mixed in one series only if the median step
  across stacks is within MIX_TOLERANCE_DB for both HH and HV; otherwise final-version points are
  dropped from the charts. Result: data/radar/nisar_calibration.csv.

Outputs
  data/radar/nisar_series.csv, data/radar/s1_series.csv, data/radar/nisar_calibration.csv
  map/img/<id>_nisar.png        NISAR HH and HV, first vs latest date of the chart stack
  map/img/<id>_timeseries.png   campus brightness over time, Sentinel-1 panel above NISAR panel
  data/raw/radar/               cached windows for the images (gitignored)
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import footprint as fp                      # noqa: E402  (Sentinel-1 search, stack, masks)
from nisar_coverage import RangeFile, TokenError   # noqa: E402

OUT = Path("data/radar")
RAW = Path("data/raw/radar")
IMG = Path("map/img")
WINDOW_M = 1500          # read window = outline + 1.5 km
REF_INNER_M = 500        # reference ring 500 m .. 1,500 m outside the outline
MIX_TOLERANCE_DB = 0.5
S1_START_MONTHS_BEFORE = 12
# NISAR stack drawn in the images and charts (most dates at 10 m; see data/nisar_coverage_notes.md)
CHART_STACK = {"FRONTIER-SHACKELFORD": "163_A_018", "JUPITER-DONAANA": "048_A_017", "LORDSTOWN": "090_A_022"}
CONSTRUCTION_START = {"FRONTIER-SHACKELFORD": "2025-08-01", "JUPITER-DONAANA": "2025-10-01", "LORDSTOWN": "2025-10-12"}
# colours: dataviz reference palette slots 1 and 2 (co-pol blue, cross-pol orange)
C_CO, C_X, INK, INK2, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df"


def masks_for(x, y, campus_utm):
    """Boolean masks (campus, reference ring) on a grid with pixel-centre coordinates x, y."""
    from rasterio import features
    from rasterio.transform import from_origin
    res_x, res_y = float(x[1] - x[0]), float(y[0] - y[1])
    tf = from_origin(x[0] - res_x / 2, y[0] + res_y / 2, res_x, res_y)
    shape = (len(y), len(x))
    inside = lambda g: ~features.geometry_mask([g.__geo_interface__], out_shape=shape, transform=tf)
    campus = inside(campus_utm)
    ring = inside(campus_utm.buffer(WINDOW_M)) & ~inside(campus_utm.buffer(REF_INNER_M))
    return campus, ring


def stats(lin, campus, ring):
    ok = np.isfinite(lin) & (lin > 0)
    c, r = ok & campus, ok & ring
    mean_c = float(np.mean(lin[c])) if c.any() else np.nan
    med_r = float(np.median(lin[r])) if r.any() else np.nan
    db = lambda v: round(10 * np.log10(v), 3) if np.isfinite(v) and v > 0 else np.nan
    return db(mean_c), db(med_r), int(c.sum()), round(float(c.sum() / max(campus.sum(), 1)), 3)


# ---------------- NISAR ----------------
def nisar_one(row, campus_ll):
    import h5py
    f = RangeFile(row["download_url"])
    with h5py.File(f, "r") as h:
        g = h["science/LSAR/GCOV/grids/frequencyA"]
        epsg = int(g["projection"][()])
        cu = fp.reproject(campus_ll, 4326, epsg)
        x0, y0, x1, y1 = cu.buffer(WINDOW_M).bounds
        xs, ys = g["xCoordinates"][:], g["yCoordinates"][:]
        j0, j1 = np.searchsorted(xs, x0), np.searchsorted(xs, x1)
        i0, i1 = np.searchsorted(-ys, -y1), np.searchsorted(-ys, -y0)
        sl = (slice(i0, i1), slice(j0, j1))
        hh, hv = g["HHHH"][sl], g["HVHV"][sl]
        campus, ring = masks_for(xs[j0:j1], ys[i0:i1], cu)
    out = {"epsg": epsg}
    for k, a in (("hh", hh), ("hv", hv)):
        out[f"campus_{k}_db"], out[f"ref_{k}_db"], out["campus_px"], out["campus_valid_frac"] = stats(a, campus, ring)
    return out, (hh, hv, campus)


def run_nisar(sites, only):
    import concurrent.futures as cf
    cov = pd.read_csv("data/nisar_gcov_coverage.csv", dtype=str)
    cov = cov[(cov.usable == "True") & cov.duplicate_of.isna()]
    rows, keep = [], {}
    jobs = []
    for s in sites:
        if only and s["site_id"] not in only:
            continue
        campus_ll = fp.load_campus(f"data/footprint/{s['site_id']}_campus.geojson")
        for _, r in cov[cov.site_id == s["site_id"]].iterrows():
            jobs.append((s["site_id"], r, campus_ll))

    def work(job):
        sid, r, campus_ll = job
        try:
            res, arrays = nisar_one(r, campus_ll)
        except TokenError:
            raise
        except Exception as e:
            return sid, r, {"error": f"{type(e).__name__}"}, None
        return sid, r, res, arrays

    with cf.ThreadPoolExecutor(8) as ex:
        for sid, r, res, arrays in ex.map(work, jobs):
            row = {"site_id": sid, "date": r.acq_date, "stack_id": r.stack_id, "track": r.track,
                   "direction": r.direction, "collection": r.collection, "product_version": r.product_version,
                   "granule_ur": r.granule_ur, "source": r.source, **res}
            rows.append(row)
            if arrays is not None and r.stack_id == CHART_STACK.get(sid):
                keep[(sid, r.acq_date)] = arrays
            print(sid, r.acq_date, r.stack_id, res.get("campus_hh_db"), res.get("campus_hv_db"), res.get("error", ""), flush=True)
    RAW.mkdir(parents=True, exist_ok=True)
    for sid in {k[0] for k in keep}:
        dates = sorted(d for s_, d in keep if s_ == sid)
        for tag, d in (("first", dates[0]), ("last", dates[-1])):
            hh, hv, campus = keep[(sid, d)]
            np.savez_compressed(RAW / f"{sid}_nisar_{tag}.npz", hh=hh, hv=hv, campus=campus, date=d)
    df = pd.DataFrame(rows).sort_values(["site_id", "stack_id", "date"])
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "nisar_series.csv"
    if only and path.exists():
        old = pd.read_csv(path, dtype=str)
        df = pd.concat([old[~old.site_id.isin(only)], df.astype(str)], ignore_index=True)
    df.to_csv(path, index=False)
    print(f"wrote {path}: {len(df)} rows")


def calibration():
    df = pd.read_csv(OUT / "nisar_series.csv")
    out = []
    for (sid, st), g in df.groupby(["site_id", "stack_id"]):
        g = g.sort_values("date")
        prov = g[g.collection.str.contains("PROVISIONAL")]
        fin = g[~g.collection.str.contains("PROVISIONAL")]
        if len(prov) < 4 or len(fin) < 1:
            continue
        row = {"site_id": sid, "stack_id": st, "n_provisional": len(prov), "n_final": len(fin),
               "last_provisional": prov.date.iloc[-1], "first_final": fin.date.iloc[0]}
        for k in ("hh", "hv"):
            step = fin[f"ref_{k}_db"].head(2).mean() - prov[f"ref_{k}_db"].tail(3).mean()
            noise = prov[f"ref_{k}_db"].diff().std()
            row[f"step_{k}_db"], row[f"noise_{k}_db"] = round(step, 3), round(noise, 3)
            row[f"step_over_noise_{k}"] = round(abs(step) / noise, 2) if noise > 0 else np.nan
        out.append(row)
    cal = pd.DataFrame(out)
    med = {k: float(cal[f"step_{k}_db"].median()) for k in ("hh", "hv")}
    mix = all(abs(v) <= MIX_TOLERANCE_DB for v in med.values())
    cal.loc[len(cal)] = {"site_id": "ALL", "stack_id": "median", "step_hh_db": round(med["hh"], 3),
                         "step_hv_db": round(med["hv"], 3)}
    cal["decision"] = ""
    cal.loc[cal.site_id == "ALL", "decision"] = (
        f"mix: |median step| <= {MIX_TOLERANCE_DB} dB" if mix else f"do not mix: |median step| > {MIX_TOLERANCE_DB} dB")
    cal.to_csv(OUT / "nisar_calibration.csv", index=False)
    print(cal.to_string(index=False))
    return mix


# ---------------- Sentinel-1 ----------------
def run_s1(sites, only, end):
    summ = pd.read_csv("data/footprint/footprint_summary.csv").set_index("site_id")
    rows = []
    for s in sites:
        sid = s["site_id"]
        if only and sid not in only:
            continue
        campus_ll = fp.load_campus(f"data/footprint/{sid}_campus.geojson")
        cs = pd.Timestamp(CONSTRUCTION_START[sid])
        start = fp.month_add(cs, -S1_START_MONTHS_BEFORE)
        c = campus_ll.centroid
        epsg_guess = 32600 + int((c.x + 180) // 6) + 1
        aoi_ll = fp.reproject(fp.reproject(campus_ll, 4326, epsg_guess).buffer(WINDOW_M), epsg_guess, 4326)
        items = fp.search_items(aoi_ll, start, pd.Timestamp(end))
        st, orb = summ.loc[sid, "orbit_state"], int(summ.loc[sid, "relative_orbit"])
        items = [it for it in items if it.properties["sat:orbit_state"] == st and it.properties["sat:relative_orbit"] == orb]
        print(f"{sid}: Sentinel-1 {st} orbit {orb}, {len(items)} frames {start:%Y-%m-%d}..{end}", flush=True)
        db, aoi_utm, epsg = fp.load_stack_db(items, aoi_ll)
        cu = fp.reproject(campus_ll, 4326, epsg)
        campus, ring = masks_for(db.x.values, db.y.values, cu)
        times = pd.DatetimeIndex(db.time.values)
        for t_i, t in enumerate(times):
            r = {"site_id": sid, "date": f"{t:%Y-%m-%d}", "orbit_state": st, "relative_orbit": orb}
            for b_i, k in enumerate(("vv", "vh")):
                lin = 10 ** (db.values[t_i, b_i] / 10)
                r[f"campus_{k}_db"], r[f"ref_{k}_db"], r["campus_px"], r["campus_valid_frac"] = stats(lin, campus, ring)
            rows.append(r)
        base = db.values[(times >= cs - pd.DateOffset(months=12)) & (times < cs)]
        last = db.values[times >= times[-1] - pd.DateOffset(months=3)]
        RAW.mkdir(parents=True, exist_ok=True)
        with np.errstate(all="ignore"):
            np.savez_compressed(RAW / f"{sid}_s1.npz", before=np.nanmedian(base, axis=0), after=np.nanmedian(last, axis=0),
                                campus=campus, n_before=len(base), n_after=len(last),
                                after_start=f"{times[-1] - pd.DateOffset(months=3):%Y-%m-%d}", after_end=f"{times[-1]:%Y-%m-%d}")
    df = pd.DataFrame(rows)
    path = OUT / "s1_series.csv"
    if only and path.exists():
        old = pd.read_csv(path, dtype=str)
        df = pd.concat([old[~old.site_id.isin(only)], df.astype(str)], ignore_index=True)
    df = df[df.campus_valid_frac.astype(float) >= 0.9]
    df.to_csv(path, index=False)
    print(f"wrote {path}: {len(df)} rows")


# ---------------- images ----------------
def edge(mask):
    e = mask & ~(np.roll(mask, 1, 0) & np.roll(mask, -1, 0) & np.roll(mask, 1, 1) & np.roll(mask, -1, 1))
    e2 = e.copy(); e2[1:, :] |= e[:-1, :]; e2[:, 1:] |= e[:, :-1]
    return e2


def grey(db_img, lo, hi, outline):
    from PIL import Image
    g = np.clip((np.nan_to_num(db_img, nan=lo) - lo) / (hi - lo) * 255, 0, 255).astype("uint8")
    rgb = np.stack([g, g, g], axis=-1)
    rgb[outline] = (0, 220, 255)
    return Image.fromarray(rgb)


def panel_grid(path, panels, title):
    """panels: list of rows, each a list of (PIL image, label)."""
    from PIL import Image, ImageDraw
    w = max(im.width for row in panels for im, _ in row)
    scale = 1 if w >= 300 else int(np.ceil(300 / w))
    rows = [[(im.resize((im.width * scale, im.height * scale), Image.NEAREST), lab) for im, lab in row] for row in panels]
    pad, head = 6, 16
    W = max(sum(im.width for im, _ in row) + pad * (len(row) + 1) for row in rows)
    H = 20 + sum(max(im.height for im, _ in row) + head + pad for row in rows)
    out = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(out)
    d.text((pad, 4), title, fill="black")
    y = 20
    for row in rows:
        x = pad
        for im, lab in row:
            d.text((x, y + 2), lab, fill="black")
            out.paste(im, (x, y + head))
            x += im.width + pad
        y += max(im.height for im, _ in row) + head + pad
    out.save(path, optimize=True)


def images(sites, only):
    for s in sites:
        sid = s["site_id"]
        if only and sid not in only:
            continue
        a, b = np.load(RAW / f"{sid}_nisar_first.npz"), np.load(RAW / f"{sid}_nisar_last.npz")
        out = edge(a["campus"])
        with np.errstate(divide="ignore", invalid="ignore"):
            to_db = lambda v: 10 * np.log10(np.where(v > 0, v, np.nan))
            panels = [[(grey(to_db(a["hh"]), -25, 5, out), f"NISAR HH {a['date']}"),
                       (grey(to_db(b["hh"]), -25, 5, edge(b["campus"])), f"NISAR HH {b['date']}")],
                      [(grey(to_db(a["hv"]), -32, -2, out), f"NISAR HV {a['date']}"),
                       (grey(to_db(b["hv"]), -32, -2, edge(b["campus"])), f"NISAR HV {b['date']}")]]
        panel_grid(IMG / f"{sid}_nisar.png", panels,
                   f"{s['name']}: NISAR L-band, track {CHART_STACK[sid]}, 10 m. Bright = strong echo. Cyan = campus outline.")
        print("wrote", IMG / f"{sid}_nisar.png")


def charts(sites, only, mix):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    s1 = pd.read_csv(OUT / "s1_series.csv", parse_dates=["date"])
    ni = pd.read_csv(OUT / "nisar_series.csv", parse_dates=["date"])
    if not mix:
        ni = ni[ni.collection.str.contains("PROVISIONAL")]
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2})
    for s in sites:
        sid = s["site_id"]
        if only and sid not in only:
            continue
        a = s1[s1.site_id == sid].sort_values("date")
        n = ni[(ni.site_id == sid) & (ni.stack_id == CHART_STACK[sid])].sort_values("date")
        cs = pd.Timestamp(CONSTRUCTION_START[sid])
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.5, 5.2), sharex=True, dpi=150,
                                       gridspec_kw={"height_ratios": [1, 1], "hspace": 0.35})
        for ax, df, (k1, l1), (k2, l2), name in (
                (ax1, a, ("campus_vv_db", "VV"), ("campus_vh_db", "VH"),
                 f"Sentinel-1 C-band (5.6 cm waves), orbit {a.relative_orbit.iloc[0] if len(a) else ''}"),
                (ax2, n, ("campus_hh_db", "HH"), ("campus_hv_db", "HV"),
                 f"NISAR L-band (24 cm waves), track {CHART_STACK[sid]}")):
            for k, lab, col in ((k1, l1, C_CO), (k2, l2, C_X)):
                ax.plot(df.date, df[k], color=col, lw=2, marker="o", ms=3 if ax is ax1 else 4)
                if len(df):
                    ax.annotate(lab, (df.date.iloc[-1], df[k].iloc[-1]), xytext=(4, 0), textcoords="offset points",
                                va="center", color=INK, fontsize=8)
            ax.axvline(cs, color=INK2, lw=1, ls="--")
            ax.set_title(name, loc="left", fontsize=9, color=INK)
            ax.set_ylabel("brightness (dB)")
            ax.grid(axis="y", color=GRID, lw=0.8)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
        ax1.annotate("construction starts", (cs, ax1.get_ylim()[1]), xytext=(3, -10), textcoords="offset points",
                     fontsize=8, color=INK2)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        fig.suptitle(f"{s['name']}: average radar brightness inside the campus outline", x=0.02, ha="left",
                     fontsize=10, color=INK)
        fig.text(0.02, 0.005, "Data: ESA Sentinel-1 RTC (Microsoft Planetary Computer); NASA/ISRO NISAR L2 GCOV (ASF DAAC). "
                 "Co-pol = blue, cross-pol = orange.", fontsize=6.5, color=INK2)
        fig.savefig(IMG / f"{sid}_timeseries.png", bbox_inches="tight")
        plt.close(fig)
        print("wrote", IMG / f"{sid}_timeseries.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--end", default="2026-11-15")
    ap.add_argument("--skip-s1", action="store_true")
    ap.add_argument("--skip-nisar", action="store_true")
    ap.add_argument("--plots-only", action="store_true")
    a = ap.parse_args()
    only = set(filter(None, a.only.split(",")))
    sites = list(csv.DictReader(open("data/nisar_coverage_sites.csv")))
    if not a.plots_only:
        if not a.skip_nisar:
            run_nisar(sites, only)
        if not a.skip_s1:
            run_s1(sites, only, a.end)
    mix = calibration()
    images(sites, only)
    charts(sites, only, mix)


if __name__ == "__main__":
    main()
