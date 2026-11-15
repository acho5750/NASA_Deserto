"""
Phase 4 calibration inputs for projection.py. Every value written here has a source link.

  python pipeline/calibration.py per-capita   # USGS 2015 public supply per person, by state
  python pipeline/calibration.py wue          # Google 2025 per-site withdrawal matched to Epoch IT MW
  (Aqueduct stress per source is looked up by water_chain.py sources, through aqueduct_lookup())

Raw inputs (data/raw/, not committed):
  data/raw/usgs/usco2015v2.0.csv        https://doi.org/10.5066/F7TB15V5 (ScienceBase 5af3311be4b0da30c1b245d8)
  data/raw/aqueduct/Aqueduct40_waterrisk_download_Y2023M07D05/   https://files.wri.org/aqueduct/aqueduct-4-0-water-risk-data.zip
  data/raw/google/g2026.pdf             Google 2026 Environmental Report (FY2025)
  data/raw/epoch/timelines.csv          https://epoch.ai/data/data_centers/data_center_timelines.csv
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

L_PER_GAL = 3.785411784
USGS_CSV = Path("data/raw/usgs/usco2015v2.0.csv")
USGS_LINK = "https://doi.org/10.5066/F7TB15V5"
AQ_GDB = Path("data/raw/aqueduct/Aqueduct40_waterrisk_download_Y2023M07D05/GDB/Aq40_Y2023D07M05.gdb")
AQ_LINK = "https://www.wri.org/data/aqueduct-global-maps-40-data ; https://files.wri.org/aqueduct/aqueduct-4-0-water-risk-data.zip"
GOOGLE_LINK = ("https://sustainability.google/reports/google-2026-environmental-report/ ; "
               "https://sustainability.google/files/1699a2e19277e478b38a659f00cb38398a836e8c/download-1699a2e1.pdf (p. 96, Water use by data center location)")
EPOCH_TIMELINES = Path("data/raw/epoch/timelines.csv")
EPOCH_LINK = "https://epoch.ai/data/data_centers/data_center_timelines.csv"
UTILIZATION_LINK = "https://epoch.ai/data/ai-data-centers"


# ---------- Per-capita public supply by state (F5) ----------
def per_capita_by_state(out_csv: str = "data/calibration/per_capita_by_state.csv") -> pd.DataFrame:
    """Total public-supply withdrawals (fresh + saline, Mgal/d) / population served by public
    supply (thousands), summed over counties: gallons per person per day, then litres."""
    d = pd.read_csv(USGS_CSV, skiprows=1, low_memory=False)
    for c in ("PS-TOPop", "PS-Wtotl"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    s = d.groupby("STATE")[["PS-Wtotl", "PS-TOPop"]].sum()
    s["gal_per_person_day"] = s["PS-Wtotl"] * 1e6 / (s["PS-TOPop"] * 1e3)
    s["l_per_person_day"] = (s.gal_per_person_day * L_PER_GAL).round(1)
    s["year"] = 2015
    s["source"] = f"{USGS_LINK} (columns PS-Wtotl / PS-TOPop, summed by state)"
    s = s.reset_index().rename(columns={"STATE": "state", "PS-Wtotl": "ps_withdrawal_mgd", "PS-TOPop": "ps_pop_thousands"})
    s["gal_per_person_day"] = s.gal_per_person_day.round(1)
    s.to_csv(out_csv, index=False)
    print(s[["state", "gal_per_person_day", "l_per_person_day"]].to_string(index=False))
    return s


# ---------- Aqueduct 4.0 baseline water stress at a point (F7) ----------
_AQ = {}


def aqueduct_lookup(lat: float, lon: float) -> dict:
    """Baseline annual water stress (bws) of the Aqueduct 4.0 unit containing the point."""
    import geopandas as gpd
    from shapely.geometry import Point
    if "g" not in _AQ:
        _AQ["g"] = gpd.read_file(AQ_GDB, layer="baseline_annual", bbox=(-125, 24, -66, 50),
                                 columns=["string_id", "pfaf_id", "name_1", "bws_raw", "bws_score", "bws_label"])
    g = _AQ["g"]
    hit = g[g.contains(Point(lon, lat))]
    if hit.empty:
        return {"aqueduct_stress": np.nan, "aqueduct_label": "no_aqueduct_unit"}
    h = hit.iloc[0]
    return {"aqueduct_stress": float(h.bws_score), "aqueduct_label": h.bws_label,
            "aqueduct_pfaf_id": int(h.pfaf_id), "aqueduct_string_id": h.string_id}


# ---------- WUE calibration: Google 2025 withdrawals matched to Epoch MW (F2) ----------
# Google reports withdrawal by location for calendar 2025 (Environmental Report 2026, p. 96).
# A location is used only if the Epoch site in data/precedent_sites.csv is all of Google's capacity
# there in 2025 (see DECISIONS.md); MW is Epoch's IT power averaged over 2025 (step function on
# the timeline rows), because the withdrawal is a 2025 total.
GOOGLE_2025_MG = {  # location as printed -> (withdrawal, million gallons)
    "Lancaster, OH": 307.1, "New Albany, OH": 1008.1, "Bristow, VA": 359.6, "Mesa, AZ": 19.4,
    "Storey County, NV": 66.7, "Midlothian, TX": 263.6, "Papillion, NE": 677.8, "The Dalles, OR": 654.3,
    "Council Bluffs, IA": 1746.4,
}
MATCH = [  # site_id, Epoch name, Google location, use?, reason
    ("GOOGLE-LANCASTER", "Google Lancaster", "Lancaster, OH", True, "single Google campus at the location"),
    ("GOOGLE-NEW-ALBANY", "Google New Albany", "New Albany, OH", True, "single Google campus at the location"),
    ("GOOGLE-BRISTOW", "Google Bristow", "Bristow, VA", True, "single Google campus at the location"),
    ("GOOGLE-MESA", "Google Mesa", "Mesa, AZ", True, "single Google campus; first building online 2025-07"),
    ("GOOGLE-STOREY-COUNTY", "Google Storey County", "Storey County, NV", True, "single Google campus at the location"),
    ("GOOGLE-MIDLOTHIAN", "Google Midlothian", "Midlothian, TX", False,
     "Epoch shows 0 MW through 2025 but Google reports 263.6 Mgal and a PUE since 2023, so Epoch tracks a later building only"),
    ("GOOGLE-PAPILLION", "Google Papillion", "Papillion, NE", False, "Epoch tracks the expansion only; Google's figure covers the whole campus"),
    ("GOOGLE-THE-DALLES", "Google The Dalles", "The Dalles, OR", False, "older Google buildings on the campus are not in Epoch"),
    ("GOOGLE-COUNCIL-BLUFFS-EAST", None, "Council Bluffs, IA", False, "Epoch site is the east expansion only; Google's figure covers all Council Bluffs campuses"),
]


def epoch_mean_it_mw(name: str, year: int = 2025) -> float:
    t = pd.read_csv(EPOCH_TIMELINES, parse_dates=["Date"])
    s = t[t["Data center"] == name].sort_values("Date").set_index("Date")["IT power (MW)"]
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31")
    st = s.reindex(s.index.union(days)).ffill().fillna(0.0)
    st = st[~st.index.duplicated(keep="last")]
    return float(st.loc[days].mean())


def wue_table(out_csv: str = "data/calibration/wue_google_2025.csv") -> pd.DataFrame:
    rows = []
    for site_id, epoch_name, loc, use, reason in MATCH:
        mg = GOOGLE_2025_MG[loc]
        mw = epoch_mean_it_mw(epoch_name) if epoch_name else np.nan
        rows.append({"site_id": site_id, "google_location": loc, "withdrawal_mgal_2025": mg,
                     "withdrawal_ml_2025": round(mg * L_PER_GAL, 1), "epoch_it_mw_2025_mean": round(mw, 1),
                     "use_for_wue": use, "reason": reason,
                     "source": f"{GOOGLE_LINK} ; {EPOCH_LINK}"})
    out = pd.DataFrame(rows)
    out.to_csv(out_csv, index=False)
    print(out[["site_id", "withdrawal_ml_2025", "epoch_it_mw_2025_mean", "use_for_wue"]].to_string(index=False))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["per-capita", "wue"])
    a = p.parse_args()
    {"per-capita": per_capita_by_state, "wue": wue_table}[a.cmd]()


if __name__ == "__main__":
    main()
