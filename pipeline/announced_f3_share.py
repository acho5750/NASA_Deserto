"""Share of total 2030 MW in the announced list that depends on F3 (capex / k), per scenario.

Rule (Bubba, 2026-11-15): rows with a stated MW skip F3. Rows whose capex is tagged facility-only
use k (from built facility-only sites) in every scenario. Rows tagged as including compute use
Epoch's $37.88M/MW in every scenario. Rows with unstated capex scope use $37.88M/MW in the low and
median scenarios and k in the high scenario. As in projection.py, the LOW scenario uses the HIGH
$/MW (fewer MW per dollar).

  python pipeline/announced_f3_share.py --announced data/announced_sites.csv --k k_low k_median k_high
"""
import argparse
import pandas as pd

EPOCH_K_MUSD = 37.88  # Epoch median $M per MW, includes compute
SCN = ["low", "median", "high"]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--announced", default="data/announced_sites.csv")
    p.add_argument("--k", nargs=3, type=float, required=True, metavar=("LOW", "MEDIAN", "HIGH"),
                   help="facility-only k in $M per IT MW (low, median, high)")
    p.add_argument("--out", default="data/announced_f3_share.csv")
    a = p.parse_args()
    k = dict(zip(SCN, a.k))
    k_for_scn = {"low": k["high"], "median": k["median"], "high": k["low"]}  # low scenario -> high $/MW
    d = pd.read_csv(a.announced)
    d = d[d.projection_eligible == "yes"].copy()
    tag = d.capex_includes_compute.fillna("").str.strip()
    rows = []
    for scn in SCN:
        mw = []
        for t, m, c in zip(tag, d.mw, d.capex_busd):
            if pd.notna(m):
                mw.append((m, False)); continue
            if t.startswith("no"):          # facility-only (stated or inferred)
                kk = k_for_scn[scn]
            elif t == "yes":                # includes compute
                kk = EPOCH_K_MUSD
            else:                           # unstated
                kk = EPOCH_K_MUSD if scn in ("low", "median") else k_for_scn[scn]
            mw.append((c * 1e3 / kk, True))
        d[f"mw_{scn}"] = [round(x[0], 1) for x in mw]
        tot = sum(x[0] for x in mw); f3 = sum(x[0] for x in mw if x[1])
        rows.append({"scenario": scn, "total_mw_2030": round(tot), "f3_mw": round(f3),
                     "f3_share": round(f3 / tot, 3), "n_rows": len(d), "n_f3_rows": int(d.mw.isna().sum()),
                     "k_facility_musd_per_mw": k_for_scn[scn], "k_epoch_musd_per_mw": EPOCH_K_MUSD})
    out = pd.DataFrame(rows)
    out.to_csv(a.out, index=False)
    print(out.to_string(index=False))
    print(d[["site_id", "mw", "capex_busd", "capex_includes_compute"] + [f"mw_{s}" for s in SCN]].to_string(index=False))

if __name__ == "__main__":
    main()
