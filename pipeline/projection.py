"""
Projection engine (formulas F2-F8).

Reads the site registry and source table, calibrates ratios from built sites, projects every
site's acres and water draw for 2026-2030 in low / median / high scenarios, computes each
source's demand share and trend score, and writes map/data.js for the prototype map.

Run:
  python pipeline/projection.py --registry data/site_registry_demo.csv --sources data/sources_demo.csv
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

YEARS = list(range(2026, 2031))       # values are "as of December 31" of each year
SCENARIOS = ["low", "median", "high"]
PCT = {"low": 25, "median": 50, "high": 75}

# ---- Parameters to set from real sources before using real data ----
UTILIZATION = 0.7           # average power draw / capacity. Confirm against Epoch's methodology notes.
PER_CAPITA_L_PER_DAY = 400  # DEMO PLACEHOLDER. Replace with USGS public-supply per-capita use per state.
DEFAULT_WUE_L_PER_KWH = None  # used only if no site has a withdrawal figure for calibration


def months_between(a: pd.Timestamp, b: pd.Timestamp) -> float:
    return (b - a).days / 30.44


def build_fraction(months_since_start: float, tau: float) -> float:
    """F8 logistic: 10% -> 90% of the build takes tau months; midpoint at tau / 2."""
    if months_since_start <= 0:
        return 0.0
    s = tau / 4.4
    return 1.0 / (1.0 + math.exp(-(months_since_start - tau / 2) / s))


def calibrate(sites: pd.DataFrame) -> dict:
    """F2: ratios from built sites, as percentiles so every scenario has its own value."""
    built = sites[sites.status == "built"].copy()
    a = (built.a_max_acres / built.mw).dropna()
    k = (built.capex_busd * 1e9 / built.mw).dropna()
    tau = built.build_months.dropna()
    lag = built.apply(lambda r: months_between(r.construction_start, r.operation_date)
                      if pd.notna(r.operation_date) else np.nan, axis=1).dropna()
    energy_kwh = built.mw * UTILIZATION * 8760 * 1000
    wue = (built.withdrawal_ml_per_yr * 1e6 / energy_kwh).dropna()   # liters per kWh

    if len(a) == 0 or len(tau) == 0:
        raise ValueError("Need at least one built site with a_max_acres, mw, and build_months.")
    if len(wue) == 0 and DEFAULT_WUE_L_PER_KWH is None:
        raise ValueError("No withdrawal figures to calibrate WUE; set DEFAULT_WUE_L_PER_KWH.")

    def pct(series, scn):
        return float(np.percentile(series, PCT[scn]))

    cal = {
        # More acres per MW and more water per kWh = higher-impact scenario.
        "acres_per_mw": {s: pct(a, s) for s in SCENARIOS},
        "wue_l_per_kwh": {s: (pct(wue, s) if len(wue) else DEFAULT_WUE_L_PER_KWH) for s in SCENARIOS},
        # Higher $/MW means fewer MW per dollar, so the LOW scenario uses the HIGH k.
        "usd_per_mw": {"low": pct(k, "high"), "median": pct(k, "median"), "high": pct(k, "low")},
        "tau_months": float(np.median(tau)),
        "lag_months": float(np.median(lag)) if len(lag) else float(np.median(tau)),
        "n_built": int(len(built)),
        "n_wue_calibration": int(len(wue)),
    }
    return cal


def project_sites(sites: pd.DataFrame, cal: dict) -> list:
    out = []
    for _, r in sites.iterrows():
        rec = {"id": r.site_id, "name": r["name"], "status": r.status, "lat": r.lat, "lon": r.lon,
               "source_id": r.source_id, "acres": {}, "water_ml": {}, "mw": {}}
        for scn in SCENARIOS:
            # F3: stated MW wins; otherwise convert capex with the scenario's $/MW.
            mw = r.mw if pd.notna(r.mw) else r.capex_busd * 1e9 / cal["usd_per_mw"][scn]
            rec["mw"][scn] = round(float(mw), 1)
            # F1/F2: measured footprint for built sites, ratio for everything else.
            acres_full = r.a_max_acres if pd.notna(r.a_max_acres) else cal["acres_per_mw"][scn] * mw
            # F4: measured withdrawal if disclosed, otherwise MW x utilization x hours x WUE.
            if pd.notna(r.withdrawal_ml_per_yr):
                water_full = r.withdrawal_ml_per_yr
            else:
                water_full = mw * UTILIZATION * 8760 * 1000 * cal["wue_l_per_kwh"][scn] / 1e6
            tau = r.build_months if pd.notna(r.build_months) else cal["tau_months"]
            acres_y, water_y = [], []
            for y in YEARS:
                t = months_between(r.construction_start, pd.Timestamp(f"{y}-12-31"))
                acres_y.append(round(acres_full * build_fraction(t, tau), 1))
                # F8: water ramps on the same curve, centred on the operation date (start + lag).
                water_y.append(round(water_full * build_fraction(t - cal["lag_months"] + tau / 2, tau), 1))
            rec["acres"][scn] = acres_y
            rec["water_ml"][scn] = water_y
        out.append(rec)
    return out


def project_sources(sources: pd.DataFrame, site_recs: list) -> list:
    out = []
    # F6: trend score = percentile rank of decline within each source type (1 = declining fastest).
    sources = sources.copy()
    sources["decline_score"] = sources.groupby("type")["trend_value"].rank(pct=True, ascending=False)
    for _, s in sources.iterrows():
        # F5: supply estimate from population served. Replace with the utility's own figure if known.
        supply_ml = s.population_served * PER_CAPITA_L_PER_DAY * 365 / 1e6
        linked = [r for r in site_recs if r["source_id"] == s.source_id]
        share = {}
        for scn in SCENARIOS:
            share[scn] = [round(sum(r["water_ml"][scn][i] for r in linked) / supply_ml, 4)
                          for i in range(len(YEARS))]
        out.append({
            "id": s.source_id, "name": s["name"], "type": s.type, "lat": s.lat, "lon": s.lon,
            "pwsid": s.utility_pwsid, "supply_ml": round(supply_ml, 1),
            "trend_value": s.trend_value, "trend_unit": s.trend_unit,
            "decline_score": round(float(s.decline_score), 3),
            "stress_norm": round(float(s.aqueduct_stress) / 5.0, 3),   # Aqueduct score 0-5
            "share": share,
        })
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--registry", required=True)
    p.add_argument("--sources", required=True)
    p.add_argument("--out", default="map/data.js")
    a = p.parse_args()

    sites = pd.read_csv(a.registry, parse_dates=["construction_start", "operation_date"])
    sources = pd.read_csv(a.sources)
    cal = calibrate(sites)
    site_recs = project_sites(sites, cal)
    source_recs = project_sources(sources, site_recs)

    demo = "demo" in Path(a.registry).name.lower()
    data = {"demo": demo, "years": YEARS, "scenarios": SCENARIOS, "calibration": cal,
            "params": {"utilization": UTILIZATION, "per_capita_l_per_day": PER_CAPITA_L_PER_DAY},
            "sites": site_recs, "sources": source_recs}
    Path(a.out).write_text("window.PROTO_DATA = " + json.dumps(data, indent=1, default=float) + ";\n")
    print(json.dumps(cal, indent=2))
    print(f"Wrote {a.out}: {len(site_recs)} sites, {len(source_recs)} sources")


if __name__ == "__main__":
    main()
