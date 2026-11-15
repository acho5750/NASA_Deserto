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

# ---- Sourced parameters (Phase 4; see DECISIONS.md and data/calibration/) ----
# Utilization u = average power draw / IT capacity. Epoch: "the average power consumption of these
# data centers is typically 60-80% of capacity, due to idle time and maintenance"
# (https://epoch.ai/data/ai-data-centers). More draw = more water, so high uses 0.8.
UTILIZATION = {"low": 0.6, "median": 0.7, "high": 0.8}
# F5 per-capita use comes per source from data/sources.csv (column per_capita_l_per_day, USGS 2015
# public-supply withdrawals / population served, by state: data/calibration/per_capita_by_state.csv).
# This national value from the same USGS file is used only for a source without a state value.
PER_CAPITA_L_PER_DAY = 521.3
# WUE comes from data/calibration/wue_google_2025.csv (Google 2025 withdrawals by location matched to
# Epoch IT MW averaged over 2025) plus any withdrawal_ml_per_yr in the registry.
WUE_CALIBRATION = "data/calibration/wue_google_2025.csv"
DEFAULT_WUE_L_PER_KWH = None  # no default: calibration must have at least one site


def months_between(a: pd.Timestamp, b: pd.Timestamp) -> float:
    return (b - a).days / 30.44


def build_fraction(months_since_start: float, tau: float) -> float:
    """F8 logistic: 10% -> 90% of the build takes tau months; midpoint at tau / 2."""
    if months_since_start <= 0:
        return 0.0
    s = tau / 4.4
    return 1.0 / (1.0 + math.exp(-(months_since_start - tau / 2) / s))


def calibrate(sites: pd.DataFrame, wue_calibration: str = WUE_CALIBRATION) -> dict:
    """F2: ratios from built sites, as percentiles so every scenario has its own value."""
    built = sites[sites.status == "built"].copy()
    a = (built.a_max_acres / built.mw).dropna()
    k = (built.capex_busd * 1e9 / built.mw).dropna()
    tau = built.build_months.dropna()
    lag = built.apply(lambda r: months_between(r.construction_start, r.operation_date)
                      if pd.notna(r.operation_date) else np.nan, axis=1).dropna()
    # F2 WUE = withdrawal / (MW x u x 8760 x 1000), with the MW running in the withdrawal year and
    # the median utilization (the year's real draw is not known, only its range).
    u = UTILIZATION["median"]
    energy_kwh = built.mw * u * 8760 * 1000
    wue = (built.withdrawal_ml_per_yr * 1e6 / energy_kwh).dropna()   # liters per kWh
    if wue_calibration and Path(wue_calibration).exists():
        w = pd.read_csv(wue_calibration)
        w = w[w.use_for_wue.astype(str).str.lower() == "true"]
        w_wue = w.withdrawal_ml_2025 * 1e6 / (w.epoch_it_mw_2025_mean * u * 8760 * 1000)
        wue = pd.concat([wue, w_wue.dropna()], ignore_index=True)

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
        "wue_values_l_per_kwh": [round(float(x), 3) for x in wue],
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
                water_full = mw * UTILIZATION[scn] * 8760 * 1000 * cal["wue_l_per_kwh"][scn] / 1e6
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
        per_capita = s.get("per_capita_l_per_day", np.nan)
        per_capita = per_capita if pd.notna(per_capita) else PER_CAPITA_L_PER_DAY
        supply_ml = s.population_served * per_capita * 365 / 1e6
        # F5 (wholesale): the same water over the supply of the systems that sell this utility its
        # water (sellers + their direct buyers, data/sources.csv wholesale_population). Shown next to
        # the local share for utilities that buy their water; None where there is no seller.
        wpop = s.get("wholesale_population", np.nan)
        wsupply_ml = wpop * per_capita * 365 / 1e6 if pd.notna(wpop) and wpop > 0 else None
        linked = [r for r in site_recs if r["source_id"] == s.source_id]
        # Every site linked to any utility inside the wholesale system counts toward its share.
        wsys = {x.strip() for x in str(s.get("wholesale_systems", "") or "").split(";") if x.strip() and x.strip() != "nan"}
        linked_w = [r for r in site_recs if str(r["source_id"]).replace("SRC-", "") in wsys]
        share, share_w = {}, {}
        for scn in SCENARIOS:
            tot = [sum(r["water_ml"][scn][i] for r in linked) for i in range(len(YEARS))]
            share[scn] = [round(x / supply_ml, 4) for x in tot]
            tot_w = [sum(r["water_ml"][scn][i] for r in linked_w) for i in range(len(YEARS))]
            share_w[scn] = [round(x / wsupply_ml, 4) for x in tot_w] if wsupply_ml else None
        out.append({
            "id": s.source_id, "name": s["name"], "type": s.type, "lat": s.lat, "lon": s.lon,
            "pwsid": s.utility_pwsid, "supply_ml": round(supply_ml, 1),
            "trend_value": s.trend_value, "trend_unit": s.trend_unit,
            "decline_score": round(float(s.decline_score), 3),
            "stress_norm": round(float(s.aqueduct_stress) / 5.0, 3),   # Aqueduct score 0-5
            "share": share,
            "wholesale_sellers": s.get("wholesale_sellers") if pd.notna(s.get("wholesale_sellers", np.nan)) else None,
            "wholesale_supply_ml": round(wsupply_ml, 1) if wsupply_ml else None,
            "share_wholesale": share_w if wsupply_ml else None,
        })
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--registry", required=True)
    p.add_argument("--sources", required=True)
    p.add_argument("--out", default="map/data.js")
    p.add_argument("--wue-calibration", default=WUE_CALIBRATION, help="'' to use registry withdrawals only")
    a = p.parse_args()

    sites = pd.read_csv(a.registry, parse_dates=["construction_start", "operation_date"])
    sources = pd.read_csv(a.sources)
    cal = calibrate(sites, a.wue_calibration)
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
