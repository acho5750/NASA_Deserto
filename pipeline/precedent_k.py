"""F2 inputs from built sites: capex per MW (k) and announcement-to-construction gap.

Usage: python pipeline/precedent_k.py

Reads data/precedent_sites.csv (Epoch-derived) and data/precedent_capex.csv (hand-researched
announced capex, one source link per row). Writes data/precedent_k_summary.csv.

k rule (set by the project owner, 2026-11-15):
- k_i = announced capex / Epoch IT MW for built sites whose announced capex covers the same
  buildings Epoch tracks (capex_scope_match = yes, or phase with the matching Epoch MW).
  Epoch's own modeled capex is never used for k.
- Case A, >= 8 such sites: low / median / high = 10th / 50th / 90th percentile of k_i.
- Case B, < 8: median = Epoch's 37.88 $M/MW; low / high = min / max of k_i.
Where a source gives a range, k_i uses the midpoint.

Gap: months from the official announcement date to Epoch's construction_start, for rows where
the announcement names the same project Epoch tracks (same_project_announcement = True) and the
date is a full YYYY-MM-DD. Negative = Epoch saw land clearing before the announcement.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EPOCH_K_MUSD_PER_MW = 37.88  # Epoch modeled total capex / IT MW, constant across sites
MIN_SITES = 8


def main():
    s = pd.read_csv(ROOT / "data" / "precedent_sites.csv")
    c = pd.read_csv(ROOT / "data" / "precedent_capex.csv")
    df = c.merge(s[["site_id", "construction_start", "mw"]], on="site_id", how="left")

    k = df[df["capex_scope_match"].isin(["yes", "phase"]) & df["k_mw_basis"].notna()].copy()
    k["capex_mid_busd"] = (k["announced_capex_busd_low"] + k["announced_capex_busd_high"]) / 2
    k["k_musd_per_mw"] = k["capex_mid_busd"] * 1000 / k["k_mw_basis"]
    n = len(k)
    vals = k["k_musd_per_mw"].to_numpy()
    if n >= MIN_SITES:
        case = "A"
        low, med, high = np.percentile(vals, [10, 50, 90])
    else:
        case = "B"
        low, med, high = vals.min(), EPOCH_K_MUSD_PER_MW, vals.max()

    g = df[df["same_project_announcement"] & df["announcement_date"].astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}")].copy()
    g["gap_months"] = (pd.to_datetime(g["construction_start"]) - pd.to_datetime(g["announcement_date"])).dt.days / 30.44
    gmed = float(g["gap_months"].median())

    pd.set_option("display.width", 200)
    print(k[["site_id", "capex_mid_busd", "k_mw_basis", "k_musd_per_mw", "source"]].round(2).to_string(index=False))
    print(f"\nk: {n} qualifying sites -> case {case}; low {low:.2f} / median {med:.2f} / high {high:.2f} $M per IT MW")
    print(g[["site_id", "announcement_date", "construction_start", "gap_months"]].round(1).to_string(index=False))
    print(f"\nannouncement -> construction start: median {gmed:.1f} months over {len(g)} sites "
          f"(range {g['gap_months'].min():.1f} to {g['gap_months'].max():.1f})")

    rows = [
        dict(parameter="k_musd_per_it_mw", scenario="low", value=round(low, 2), n_sites=n, case=case),
        dict(parameter="k_musd_per_it_mw", scenario="median", value=round(med, 2), n_sites=n, case=case),
        dict(parameter="k_musd_per_it_mw", scenario="high", value=round(high, 2), n_sites=n, case=case),
        dict(parameter="announcement_to_start_months", scenario="median", value=round(gmed, 1), n_sites=len(g), case=""),
    ]
    out = pd.DataFrame(rows)
    out["source"] = "data/precedent_capex.csv ; data/precedent_sites.csv ; https://epoch.ai/data/data-centers"
    out.to_csv(ROOT / "data" / "precedent_k_summary.csv", index=False)


if __name__ == "__main__":
    main()
