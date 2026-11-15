"""
Phase 7: build map/data.js from the real data (no demo rows).

Steps:
  1. Registry = data/precedent_sites.csv (built) + data/announced_sites.csv (announced).
     Sites with a location, a construction start and MW or capex are projected with
     pipeline/projection.py (F2-F8, same calibration as `projection.py --registry ...`).
     The others stay on the map without a projection, with the reason.
  2. Each site gets: campus outline (OSM / hand-drawn, simplified), F1 footprint result and
     before/after radar image (Phase 2), land cover before construction (Phase 6), distance to the
     nearest wetland and protected area (Phase 6), and its water-chain match (Phase 3).
  3. Each source gets: local and wholesale shares (F5), trend and the measured series for a chart
     (SWOT water surface elevation or OPERA DISP-S1 ground motion), Aqueduct stress, exposure.
  4. Every number keeps a pointer to its CSV in data/ and the source links from that CSV.

Usage:  python pipeline/build_map.py            -> map/data.js
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).parent))
import projection  # noqa: E402

OUT = Path("map/data.js")
REG_COLS = ["site_id", "name", "status", "lat", "lon", "mw", "capex_busd", "construction_start", "operation_date",
            "a_max_acres", "build_months", "withdrawal_ml_per_yr", "source_id"]
# Phase 5 footprint runs on announced sites used their own ids.
PHASE5_IDS = {"FRONTIER-SHACKELFORD": "ANN-STARGATE-SHACKELFORD", "JUPITER-DONAANA": "ANN-STARGATE-DONAANA",
              "LORDSTOWN": "ANN-STARGATE-LORDSTOWN"}
NLCD_GROUPS = ["developed", "cropland", "pasture_hay", "forest", "shrub_grass", "barren", "wetlands", "water"]


def clean(v):
    """JSON-safe scalar: NaN -> None, numpy -> python."""
    if v is None:
        return None
    if isinstance(v, (np.floating, float)):
        return None if math.isnan(float(v)) else round(float(v), 4)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, str) and v.strip().lower() in ("", "nan"):
        return None
    return v


def links(*vals):
    out = []
    for v in vals:
        for s in str(v or "").split(";"):
            s = s.strip()
            if s.startswith("http") and s not in out:
                out.append(s)
    return out


def outline(site_id, status):
    p = Path(f"data/footprint/{site_id}_campus.geojson") if status == "built" \
        else Path(f"data/footprint/announced/{site_id}_campus.geojson")
    if not p.exists():
        return None, None
    g = unary_union([shape(f["geometry"]) for f in json.loads(p.read_text())["features"]])
    g = g.simplify(0.00005, preserve_topology=True)
    gj = mapping(g)

    def rnd(c):
        return [rnd(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 5), round(c[1], 5)]
    return {"type": gj["type"], "coordinates": rnd(gj["coordinates"])}, str(p)


def mad_keep(res):
    med = np.median(res)
    mad = np.median(np.abs(res - med)) or 1e-9
    return np.abs(res - med) <= 4 * 1.4826 * mad


def swot_series(path):
    """SWOT reach water surface elevation: points, outliers flagged as in water_chain._fit_trend."""
    d = pd.read_csv(path)
    t = pd.to_datetime(d.time, utc=True)
    v = d.wse.to_numpy(float)
    keep = mad_keep(v)
    yrs = ((t - t[keep].min()).dt.total_seconds() / (365.25 * 86400)).to_numpy()
    slope, icpt = np.polyfit(yrs[keep], v[keep], 1)
    return {"kind": "swot_wse", "unit": "m", "label": "Water surface elevation (SWOT), m",
            "t": [x.strftime("%Y-%m-%d") for x in t], "v": [round(float(x), 3) for x in v],
            "keep": [bool(x) for x in keep],
            "fit": {"t0": t[keep].min().strftime("%Y-%m-%d"), "per_year": round(float(slope), 4),
                    "at_t0": round(float(icpt), 3)}, "file": str(path)}


def disp_series(path):
    """DISP-S1 ground motion: segments aligned with the fit's per-segment offsets (as water_chain)."""
    ts = pd.read_csv(path)
    ts = ts[ts.groupby("segment").date.transform("size") >= 3].reset_index(drop=True)
    t = pd.to_datetime(ts.date.astype(str), format="%Y%m%d", utc=True)
    years = ((t - t.min()).dt.total_seconds() / (365.25 * 86400)).to_numpy()
    v = ts.cum_disp_m.to_numpy() * 1000
    seg_ids = sorted(ts.segment.unique())
    segs = pd.get_dummies(ts.segment).to_numpy(float)
    keep = np.ones(len(v), bool)
    for _ in range(2):
        X = np.column_stack([years, segs])[keep]
        coef, *_ = np.linalg.lstsq(X, v[keep], rcond=None)
        res = v - np.column_stack([years, segs]) @ coef
        mad = np.median(np.abs(res[keep] - np.median(res[keep]))) or 1e-9
        keep = np.abs(res - np.median(res[keep])) <= 4 * 1.4826 * mad
    offs = dict(zip(seg_ids, coef[1:]))
    aligned = v - ts.segment.map(offs).to_numpy()   # each segment shifted onto one line through 0
    return {"kind": "disp_los", "unit": "mm", "label": "Ground motion toward the satellite (OPERA DISP-S1), mm",
            "t": [x.strftime("%Y-%m-%d") for x in t], "v": [round(float(x), 1) for x in aligned],
            "keep": [bool(x) for x in keep],
            "fit": {"t0": t.min().strftime("%Y-%m-%d"), "per_year": round(float(coef[0]), 3), "at_t0": 0.0},
            "segments": len(seg_ids), "file": str(path)}


def main():
    prec = pd.read_csv("data/precedent_sites.csv", parse_dates=["construction_start", "operation_date"])
    ann = pd.read_csv("data/announced_sites.csv", parse_dates=["construction_start", "operation_date"])
    # Built sites: the marker goes inside the OSM campus outline (as the water chain's site point),
    # because several registry points are town centroids and one has none.
    for i, r in prec.iterrows():
        p = Path(f"data/footprint/{r.site_id}_campus.geojson")
        if p.exists():
            pt = unary_union([shape(f["geometry"]) for f in json.loads(p.read_text())["features"]]).representative_point()
            prec.loc[i, ["lat", "lon"]] = [round(pt.y, 5), round(pt.x, 5)]
    reg = pd.concat([prec[REG_COLS], ann[REG_COLS]], ignore_index=True)
    has_loc = reg.lat.notna()
    projectable = has_loc & (reg.mw.notna() | reg.capex_busd.notna()) & reg.construction_start.notna()
    ann_missing = set(ann[ann.get("location_precision", pd.Series(dtype=str)) == "missing"].site_id)
    sources = pd.read_csv("data/sources.csv")

    cal = projection.calibrate(reg[projectable].copy())
    proj = {r["id"]: r for r in projection.project_sites(reg[projectable].copy(), cal)}
    src_proj = {r["id"]: r for r in projection.project_sources(sources, list(proj.values()))}

    fp = pd.read_csv("data/footprint/footprint_summary.csv")
    fp["site_id"] = fp.site_id.replace(PHASE5_IDS)
    fp = fp.set_index("site_id")
    lc = pd.read_csv("data/landcover/site_landcover.csv").set_index("site_id")
    px = pd.read_csv("data/proximity/site_proximity.csv").set_index("site_id")
    spx = pd.read_csv("data/proximity/source_proximity.csv").set_index("source_id")
    links_df = pd.read_csv("data/water/site_sources.csv").set_index("site_id")

    site_recs = []
    for _, r in pd.concat([prec.assign(_list="precedent"), ann.assign(_list="announced")], ignore_index=True).iterrows():
        sid = r.site_id
        geom, gpath = outline(sid, r.status)
        rec = {"id": sid, "name": r["name"], "status": r.status, "lat": clean(r.lat), "lon": clean(r.lon),
               "outline": geom, "outline_file": gpath,
               "location": {"precision": clean(r.get("location_precision")) or clean(r.get("geocode_precision")),
                            "basis": clean(r.get("location_basis")) or clean(r.get("geocode_display_name")),
                            "missing": sid in ann_missing},
               "construction_start": r.construction_start.date().isoformat() if pd.notna(r.construction_start) else None,
               "operation_date": r.operation_date.date().isoformat() if pd.notna(r.operation_date) else None,
               "mw_stated": clean(r.mw), "capex_busd": clean(r.capex_busd),
               "links": links(r.get("source"), r.get("source_2"), r.get("location_source"))}
        if sid in proj:
            p = proj[sid]
            rec.update({"projected": True, "mw": p["mw"], "acres": p["acres"], "water_ml": p["water_ml"],
                        "source_id": clean(p["source_id"])})
        else:
            why = ("location missing" if sid in ann_missing else
                   "no construction start date" if pd.isna(r.construction_start) else
                   "no MW and no capex figure" if pd.isna(r.mw) and pd.isna(r.capex_busd) else "not projected")
            rec.update({"projected": False, "not_projected_reason": why, "source_id": clean(r.source_id)})
        if sid in links_df.index:
            l = links_df.loc[sid]
            rec["water_match"] = {"status": clean(l.match_status), "pwsid": clean(l.pwsid),
                                  "nearby_utilities": clean(l.candidates_within_2km),
                                  "other_service_areas": clean(l.other_service_areas)}
        if sid in fp.index:
            f = fp.loc[sid]
            img = str(f.radar_png).replace("map/", "") if pd.notna(f.radar_png) and Path(str(f.radar_png)).exists() else None
            rec["footprint"] = {"final_acres": clean(f.final_acres_site), "a_max_acres": clean(f.a_max_acres),
                                "build_months": clean(f.build_months), "threshold_db": clean(f.thresh_db),
                                "spillover_acres": clean(f.spillover_acres), "window_end": clean(f.window_end),
                                "orbit": f"{f.orbit_state} {int(f.relative_orbit)}" if pd.notna(f.relative_orbit) else None,
                                "flag": clean(f.flag), "radar_png": img,
                                "file": "data/footprint/footprint_summary.csv"}
        if sid in lc.index and lc.loc[sid, "status"] == "ok":
            x = lc.loc[sid]
            rec["landcover"] = {"nlcd_year": int(x.nlcd_year), "converted_acres": clean(x.converted_acres),
                                "dominant": clean(x.dominant_class), "dominant_pct": clean(x.dominant_pct),
                                "pct": {g: clean(x[f"{g}_pct"]) for g in NLCD_GROUPS},
                                "acres": {g: clean(x[f"{g}_acres"]) for g in NLCD_GROUPS},
                                "file": "data/landcover/site_landcover.csv"}
        if sid in px.index:
            rec["exposure"] = exposure(px.loc[sid], "data/proximity/site_proximity.csv")
        site_recs.append(rec)

    src_recs = []
    for _, s in sources.iterrows():
        p = src_proj[s.source_id]
        series = None
        f = s.trend_series_file
        if isinstance(f, str) and Path(f).exists():
            series = swot_series(f) if "/swot/" in f else disp_series(f)
        rec = {k: clean(v) if not isinstance(v, (dict, list)) else v for k, v in p.items()}
        rec.update({"water_body": s.water_body, "utility": s.utility_name, "population_served": clean(s.population_served),
                    "wholesale_population": clean(s.wholesale_population), "trend_status": s.trend_status,
                    "trend_method": s.trend_method, "trend_start": clean(s.trend_start), "trend_end": clean(s.trend_end),
                    "trend_n": clean(s.trend_n), "aqueduct_label": clean(s.aqueduct_label),
                    "aqueduct_stress": clean(s.aqueduct_stress), "per_capita_l_per_day": clean(s.per_capita_l_per_day),
                    "location_basis": s.location_basis, "identification_basis": s.identification_basis,
                    "confidence": s.confidence, "flags": clean(s["flags"]), "series": series,
                    "links": links(s.source), "file": "data/sources.csv"})
        if s.source_id in spx.index:
            rec["exposure"] = exposure(spx.loc[s.source_id], "data/proximity/source_proximity.csv")
        src_recs.append(rec)

    data = {"demo": False, "built": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d"), "years": projection.YEARS,
            "scenarios": projection.SCENARIOS, "calibration": cal,
            "params": {"utilization": projection.UTILIZATION}, "sites": site_recs, "sources": src_recs}
    txt = json.dumps(sanitize(data), separators=(",", ":"))
    assert "NaN" not in txt, "NaN in output"
    OUT.write_text("window.PROTO_DATA = " + txt + ";\n")
    n_proj = sum(1 for r in site_recs if r["projected"])
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} kB): {len(site_recs)} sites ({n_proj} projected), "
          f"{len(src_recs)} sources, {sum(1 for r in src_recs if r['series'])} with a trend series")
    print("acres/MW", {k: round(v, 2) for k, v in cal["acres_per_mw"].items()},
          "WUE", {k: round(v, 2) for k, v in cal["wue_l_per_kwh"].items()}, "tau", round(cal["tau_months"], 1))


def sanitize(o):
    """Recursively make an object JSON-safe (numpy -> python, NaN -> None, dates -> ISO)."""
    if isinstance(o, dict):
        return {str(k): sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [sanitize(v) for v in o]
    if isinstance(o, (pd.Timestamp,)):
        return o.isoformat()
    if isinstance(o, np.generic):
        o = o.item()
    if isinstance(o, float):
        return None if math.isnan(o) or math.isinf(o) else o
    return o


def exposure(x, file):
    return {"wetland_vegetated_m": clean(x.wetland_vegetated_m), "wetland_vegetated_type": clean(x.wetland_vegetated_type),
            "wetland_any_m": clean(x.wetland_any_m), "wetland_any_type": clean(x.wetland_any_type),
            "protected_m": clean(x.protected_m), "protected_name": clean(x.protected_name),
            "protected_manager": clean(x.protected_manager), "protected_gap": clean(x.protected_gap_status),
            "measured_from": clean(x.measured_from), "file": file}


if __name__ == "__main__":
    main()
