"""
Footprint engine (formula F1) for one site, on Microsoft Planetary Computer Sentinel-1 RTC.

Python port of gee/footprint_engine.js. Same logic, different data source:
  * Collection `sentinel-1-rtc` (radiometrically terrain corrected gamma0, LINEAR power).
    Values are converted to dB with 10*log10 before any median, difference or threshold.
  * One orbit direction and one relative orbit for the whole series (viewing geometry fixed).
  * Baseline = per-pixel median of the 12 months before construction start.
  * Monthly composites = per-pixel median of each calendar-offset month; empty months dropped.
  * Flag = |VV - baseline VV| > theta OR |VH - baseline VH| > theta.
  * Persistence = flagged this composite AND the previous composite.
  * Cumulative footprint = a pixel stays converted once it has been converted. Area is summed over
      - the SITE = campus outline buffered by 200 m                -> `acres_site` (reported acres)
      - the SPILLOVER ring = AOI minus the site (out to 1 km)      -> `acres_spillover`
      - the AOI = campus outline buffered by 1 km (as in GEE)      -> `acres_aoi`
      - the bare outline, for reference                            -> `acres_campus`
    The 5% noise rule and the logistic fit both use `acres_site` (rule set by the person,
    2026-11-15: report acres within the outline + 200 m, the 1 km ring separately as spillover,
    and apply the noise rule to the same area as the reported acres).

Decision rules from CLAUDE.md that this script applies itself:
  * Orbit: most frequent descending relative orbit; fall back to ascending if that orbit has
    fewer than 12 images in the baseline year.
  * Threshold: start at 3 dB. If pre-construction converted acres exceed 5% of the final
    footprint, raise by 0.5 dB and rerun. Stop at 5 dB and flag the site.
  * F1 "fit logistic": A(t) = A_max / (1 + exp(-k (t - t0))); build_months = 10% -> 90% time.

Outputs (small, committed):
  data/footprint/<site_id>_area_curve.csv   one row per monthly composite
  data/footprint/footprint_summary.csv       one row per site (upserted)

Usage:
  python pipeline/footprint.py --site-id STARGATE-ABILENE --name "OpenAI Stargate Abilene" \
      --campus data/footprint/STARGATE-ABILENE_campus.geojson --construction-start 2024-05-31 \
      --source "https://epoch.ai/data/data-centers" --quicklook data/raw/abilene_quicklook.png
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "sentinel-1-rtc"
COLLECTION_LINK = "https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc"
M2_PER_ACRE = 4046.86
OUT_DIR = Path("data/footprint")

THRESH_START_DB = 3.0
THRESH_STEP_DB = 0.5
THRESH_MAX_DB = 5.0
NOISE_FRACTION = 0.05      # pre-construction acres / final acres that triggers a higher threshold
MIN_BASELINE_IMAGES = 12   # descending -> ascending fallback
BUFFER_M = 1000            # campus.buffer(1000) in the GEE script
SITE_BUFFER_M = 200        # reported footprint = campus outline + 200 m
AFTER_MONTHS = 6           # "after" radar image = median of the last 6 months of the window


# ---------- inputs ----------
def load_campus(path: str):
    """Campus outline as a shapely geometry in EPSG:4326 (GeoJSON Feature, FeatureCollection or geometry)."""
    from shapely.geometry import shape
    from shapely.ops import unary_union

    gj = json.loads(Path(path).read_text())
    if gj.get("type") == "FeatureCollection":
        return unary_union([shape(f["geometry"]) for f in gj["features"]])
    if gj.get("type") == "Feature":
        return shape(gj["geometry"])
    return shape(gj)


def reproject(geom, src, dst):
    from pyproj import Transformer
    from shapely import transform

    tf = Transformer.from_crs(src, dst, always_xy=True)
    return transform(geom, lambda xy: np.column_stack(tf.transform(xy[:, 0], xy[:, 1])))


def month_add(ts: pd.Timestamp, months: int) -> pd.Timestamp:
    """ee.Date.advance(n, 'month'): same day of month, n months later."""
    return ts + pd.DateOffset(months=months)


# ---------- Sentinel-1 search and orbit choice ----------
def search_items(aoi_ll, start, end):
    import planetary_computer as pc
    import pystac_client

    cat = pystac_client.Client.open(STAC_URL, modifier=pc.sign_inplace)
    search = cat.search(
        collections=[COLLECTION],
        intersects=aoi_ll.__geo_interface__,
        datetime=f"{start:%Y-%m-%d}T00:00:00Z/{end:%Y-%m-%d}T00:00:00Z",  # composites drop t >= end
    )
    items = []
    for it in search.items():
        p = it.properties
        pols = p.get("sar:polarizations", [])
        if p.get("sar:instrument_mode") == "IW" and "VV" in pols and "VH" in pols:
            items.append(it)
    return items


def choose_orbit(items, base_start, base_end):
    """Return (orbit_state, relative_orbit, items_for_that_orbit, note)."""
    def item_time(it):
        return pd.Timestamp(it.datetime).tz_convert(None)

    def best(state):
        sel = [it for it in items if it.properties["sat:orbit_state"] == state]
        if not sel:
            return None, [], 0
        # Count acquisitions (days), not frames, so a site on a frame edge is not double counted.
        days = {(it.properties["sat:relative_orbit"], item_time(it).date()) for it in sel}
        hist = Counter(o for o, _ in days)
        base_hist = Counter(o for o, d in days if base_start <= pd.Timestamp(d) < base_end)
        # Most frequent over the whole window (as GEE aggregate_histogram); ties -> more baseline
        # images, then lowest orbit number, so the choice is deterministic.
        orbit = sorted(hist, key=lambda o: (-hist[o], -base_hist[o], o))[0]
        return orbit, [it for it in sel if it.properties["sat:relative_orbit"] == orbit], base_hist[orbit]

    d_orbit, d_items, d_base = best("descending")
    if d_orbit is not None and d_base >= MIN_BASELINE_IMAGES:
        return "descending", d_orbit, d_items, f"descending orbit {d_orbit}: {d_base} baseline images"
    a_orbit, a_items, a_base = best("ascending")
    if a_orbit is None or a_base < MIN_BASELINE_IMAGES:
        sys.exit(f"Not enough Sentinel-1 data: descending best={d_orbit} ({d_base} baseline images), "
                 f"ascending best={a_orbit} ({a_base} baseline images); need {MIN_BASELINE_IMAGES}.")
    note = (f"fell back to ascending orbit {a_orbit} ({a_base} baseline images): best descending "
            f"orbit {d_orbit} had {d_base} baseline images (< {MIN_BASELINE_IMAGES})")
    return "ascending", a_orbit, a_items, note


# ---------- raster stack ----------
def load_stack_db(items, aoi_ll):
    """Per-acquisition VV/VH in dB on a 10 m UTM grid covering the AOI: (time, band, y, x)."""
    import stackstac

    epsg = int(items[0].properties["proj:code"].split(":")[1])
    aoi_utm = reproject(aoi_ll, 4326, epsg)
    da = stackstac.stack(
        items, assets=["vv", "vh"], epsg=epsg, resolution=10, bounds=aoi_utm.bounds,
        dtype="float32", fill_value=np.float32(np.nan), rescale=False,
    )
    # Same-day frames from one relative orbit are adjacent slices of one pass: mosaic them.
    day = pd.DatetimeIndex(da.time.values).normalize()
    da = da.assign_coords(day=("time", day))
    da = da.groupby("day").map(stackstac.mosaic, dim="time").rename(day="time")
    lin = da.compute()
    vals = lin.values
    vals[(vals <= 0) | (vals == -32768)] = np.nan
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10.0 * np.log10(vals)   # linear gamma0 -> dB, BEFORE any compositing or threshold
    lin.values = db
    return lin, aoi_utm, epsg


def aoi_mask(da, aoi_utm):
    from rasterio import features
    from rasterio.transform import from_origin

    x, y = da.x.values, da.y.values
    res = float(x[1] - x[0])
    tf = from_origin(x[0] - res / 2, y[0] + res / 2, res, res)
    inside = ~features.geometry_mask([aoi_utm.__geo_interface__], out_shape=(len(y), len(x)), transform=tf)
    return inside, res * res


# ---------- F1 ----------
def monthly_composites(db, start, n_months):
    times = pd.DatetimeIndex(db.time.values)
    comps, dates, counts = [], [], []
    for m in range(n_months):
        d0, d1 = month_add(start, m), month_add(start, m + 1)
        sel = (times >= d0) & (times < d1)
        if sel.sum() == 0:
            continue   # .filter(ee.Filter.gt('n_images', 0))
        with np.errstate(all="ignore"):
            comps.append(np.nanmedian(db.values[sel], axis=0))
        dates.append(d0)
        counts.append(int(sel.sum()))
    return np.stack(comps), dates, counts


def cumulative_converted(comps, baseline, thresh_db):
    """Cumulative converted mask for each composite after the first (persistence needs a previous one)."""
    with np.errstate(invalid="ignore"):
        flags = (np.abs(comps - baseline[None]) > thresh_db).any(axis=1)   # max over VV, VH
    persistent = flags[1:] & flags[:-1]
    return np.logical_or.accumulate(persistent, axis=0)


def acres_in(cumulative, mask, pixel_m2):
    return (cumulative & mask[None]).sum(axis=(1, 2)) * pixel_m2 / M2_PER_ACRE


def fit_logistic(t_months, acres):
    """A(t) = A_max / (1 + exp(-k (t - t0))) by grid search on (k, t0) with A_max solved in closed form.
    Returns A_max, t0 (months from construction start), k, build_months (10% -> 90% = ln(81)/k)."""
    t = np.asarray(t_months, float)
    a = np.asarray(acres, float)
    best = (np.inf, None)
    for k in np.linspace(0.05, 3.0, 120):
        for t0 in np.linspace(t.min(), t.max(), 241):
            s = 1.0 / (1.0 + np.exp(-k * (t - t0)))
            amax = float(s @ a / (s @ s))
            sse = float(((a - amax * s) ** 2).sum())
            if sse < best[0]:
                best = (sse, (amax, t0, k))
    amax, t0, k = best[1]
    return amax, t0, k, float(np.log(81.0) / k)


def write_radar_png(path, before_vv, after_vv, site_edge, labels):
    """Side-by-side before | after Sentinel-1 VV backscatter (dB, -25..+5 stretch), site outline in cyan."""
    from PIL import Image, ImageDraw

    def grey(vv):
        g = np.clip((np.nan_to_num(vv, nan=-25.0) + 25) / 30 * 255, 0, 255).astype("uint8")
        rgb = np.stack([g, g, g], axis=-1)
        rgb[site_edge] = (0, 220, 255)
        return Image.fromarray(rgb)

    a, b = grey(before_vv), grey(after_vv)
    scale = max(1, int(np.ceil(360 / max(a.size))))
    a = a.resize((a.width * scale, a.height * scale), Image.NEAREST)
    b = b.resize((b.width * scale, b.height * scale), Image.NEAREST)
    pad, head = 6, 18
    out = Image.new("RGB", (a.width * 2 + pad * 3, a.height + head + pad), "white")
    out.paste(a, (pad, head)); out.paste(b, (a.width + pad * 2, head))
    d = ImageDraw.Draw(out)
    d.text((pad, 3), labels[0], fill="black"); d.text((a.width + pad * 2, 3), labels[1], fill="black")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    out.save(path, optimize=True)


def write_quicklook(path, baseline, converted, inside):
    from PIL import Image

    vv = np.nan_to_num(baseline[0], nan=-25.0)
    g = np.clip((vv + 25) / 25 * 255, 0, 255).astype("uint8")
    rgb = np.stack([g, g, g], axis=-1)
    rgb[converted] = (255, 170, 0)
    rgb[~inside] = (rgb[~inside] * 0.5).astype("uint8")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb).save(path)


def run(args):
    campus = load_campus(args.campus)
    cs = pd.Timestamp(args.construction_start)
    start, end = month_add(cs, -args.months_before), month_add(cs, args.months_after)
    base_start = month_add(cs, -12)

    # Buffer in metres in the local UTM zone, then back to lon/lat for the search.
    c = campus.centroid
    epsg_guess = (32600 if c.y >= 0 else 32700) + int((c.x + 180) // 6) + 1
    aoi_ll = reproject(reproject(campus, 4326, epsg_guess).buffer(BUFFER_M), epsg_guess, 4326)

    items = search_items(aoi_ll, start, end)
    print(f"{len(items)} {COLLECTION} IW VV+VH frames intersect the AOI {start:%Y-%m-%d}..{end:%Y-%m-%d}")
    state, orbit, items, orbit_note = choose_orbit(items, base_start, cs)
    print(f"Orbit: {orbit_note}")

    db, aoi_utm, epsg = load_stack_db(items, aoi_ll)
    inside, pixel_m2 = aoi_mask(db, aoi_utm)
    campus_utm = reproject(campus, 4326, epsg)
    inside_campus, _ = aoi_mask(db, campus_utm)
    site_utm = campus_utm.buffer(SITE_BUFFER_M)
    inside_site, _ = aoi_mask(db, site_utm)
    inside_spill = inside & ~inside_site
    times = pd.DatetimeIndex(db.time.values)
    print(f"Images used {len(times)}, {state} relative orbit {orbit}, grid {db.sizes['y']}x{db.sizes['x']} @10 m EPSG:{epsg}")

    base_sel = (times >= base_start) & (times < cs)
    with np.errstate(all="ignore"):
        baseline = np.nanmedian(db.values[base_sel], axis=0)   # (band, y, x) in dB
    comps, dates, counts = monthly_composites(db, start, args.months_before + args.months_after)

    pre = np.array([d < cs for d in dates[1:]])
    thresh, flag = args.thresh_db, ""
    while True:
        cumulative = cumulative_converted(comps, baseline, thresh)
        acres = acres_in(cumulative, inside, pixel_m2)
        campus_acres = acres_in(cumulative, inside_campus, pixel_m2)
        site_acres = acres_in(cumulative, inside_site, pixel_m2)
        spill_acres = acres_in(cumulative, inside_spill, pixel_m2)
        final = float(site_acres[-1])
        pre_acres = float(site_acres[pre][-1]) if pre.any() else 0.0
        ratio = pre_acres / final if final > 0 else np.inf
        print(f"  theta={thresh:.1f} dB: site (outline+{SITE_BUFFER_M} m) pre-construction {pre_acres:.1f} ac, "
              f"final {final:.1f} ac, ratio {ratio:.1%} | spillover ring final {spill_acres[-1]:.1f} ac")
        if ratio <= NOISE_FRACTION:
            break
        if thresh + THRESH_STEP_DB > THRESH_MAX_DB + 1e-9:
            flag = "noise_floor_above_5pct_at_max_threshold"
            break
        thresh += THRESH_STEP_DB

    t_months = [(d.year - cs.year) * 12 + (d.month - cs.month) for d in dates[1:]]
    curve = pd.DataFrame({
        "site_id": args.site_id,
        "date": [f"{d:%Y-%m-%d}" for d in dates[1:]],
        "months_from_start": t_months,
        "n_images": counts[1:],
        "acres_site": np.round(site_acres, 2),
        "acres_spillover": np.round(spill_acres, 2),
        "acres_campus": np.round(campus_acres, 2),
        "acres_aoi": np.round(acres, 2),
        "thresh_db": thresh,
        "source": COLLECTION_LINK,
    })
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    curve_path = OUT_DIR / f"{args.site_id}_area_curve.csv"
    curve.to_csv(curve_path, index=False)

    amax, t0, k, build_months = fit_logistic(t_months, site_acres)
    if t0 + np.log(9.0) / k > max(t_months):   # 90% point after the last composite
        flag = ";".join(x for x in (flag, "curve_not_saturated") if x)

    site_area = site_utm.area / M2_PER_ACRE
    after_sel = times >= month_add(end, -AFTER_MONTHS)
    with np.errstate(all="ignore"):
        after = np.nanmedian(db.values[after_sel], axis=0)
    radar_png = ""
    if args.radar_png:
        m = inside_site
        interior = m.copy()
        interior[1:, :] &= m[:-1, :]; interior[:-1, :] &= m[1:, :]
        interior[:, 1:] &= m[:, :-1]; interior[:, :-1] &= m[:, 1:]
        b0, b1 = times[base_sel].min(), times[base_sel].max()
        a0, a1 = times[after_sel].min(), times[after_sel].max()
        write_radar_png(args.radar_png, baseline[0], after[0], m & ~interior,
                        (f"BEFORE  {b0:%Y-%m} to {b1:%Y-%m}", f"AFTER  {a0:%Y-%m} to {a1:%Y-%m}"))
        radar_png = args.radar_png
    summary = pd.DataFrame([{
        "site_id": args.site_id, "name": args.name, "construction_start": f"{cs:%Y-%m-%d}",
        "orbit_state": state, "relative_orbit": orbit, "n_images": len(times),
        "baseline_images": int(base_sel.sum()), "thresh_db": thresh,
        "campus_outline_acres": round(campus_utm.area / M2_PER_ACRE, 1), "site_area_acres": round(site_area, 1),
        "pre_construction_acres_site": round(pre_acres, 2), "final_acres_site": round(final, 2),
        "spillover_acres": round(float(spill_acres[-1]), 2), "final_acres_campus": round(float(campus_acres[-1]), 2),
        "final_acres_aoi": round(float(acres[-1]), 2), "window_end": f"{end:%Y-%m-%d}",
        "radar_png": radar_png,
        "a_max_acres": round(amax, 1), "logistic_t0_months": round(t0, 1),
        "build_months": round(build_months, 1), "flag": flag,
        "source": f"{COLLECTION_LINK} ; {args.source}" if args.source else COLLECTION_LINK,
    }])
    sum_path = OUT_DIR / "footprint_summary.csv"
    if sum_path.exists():
        old = pd.read_csv(sum_path)
        summary = pd.concat([old[old.site_id != args.site_id], summary], ignore_index=True)
    summary.to_csv(sum_path, index=False)

    if args.quicklook:
        write_quicklook(args.quicklook, baseline, cumulative[-1] & inside, inside)

    print(f"\nWrote {curve_path} and {sum_path}")
    print(curve[["date", "months_from_start", "n_images", "acres_site", "acres_spillover"]].to_string(index=False))
    print(f"\nthreshold {thresh} dB | final {final:.1f} ac (site = outline+{SITE_BUFFER_M} m) | "
          f"spillover {spill_acres[-1]:.1f} ac (ring to {BUFFER_M} m) | "
          f"logistic A_max {amax:.1f} ac, t0 {t0:+.1f} mo, build 10->90% {build_months:.1f} mo"
          + (f" | FLAG {flag}" if flag else ""))
    return curve, summary


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--site-id", required=True)
    p.add_argument("--name", default="")
    p.add_argument("--campus", required=True, help="GeoJSON outline of the campus (EPSG:4326)")
    p.add_argument("--construction-start", required=True, help="YYYY-MM-DD, e.g. Epoch's land-clearing date")
    p.add_argument("--months-before", type=int, default=24)
    p.add_argument("--months-after", type=int, default=30)
    p.add_argument("--thresh-db", type=float, default=THRESH_START_DB)
    p.add_argument("--source", default="", help="link for the outline / construction date")
    p.add_argument("--quicklook", default="", help="optional PNG of converted pixels (write under data/raw/)")
    p.add_argument("--radar-png", default="", help="before/after Sentinel-1 VV image for the map, e.g. map/img/<id>_radar.png")
    run(p.parse_args())


if __name__ == "__main__":
    main()
