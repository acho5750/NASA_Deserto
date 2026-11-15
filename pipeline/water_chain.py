"""
Water chain (steps 1-3): data center site -> water utility -> water source -> source trend.

Step 1  match_utilities(): spatial join of sites against EPA service area polygons (gets PWSID)
Step 2  lookup_sources(): source type, population served, and facility names from ECHO SDWA files
Step 3  reservoir_trend(): SWOT lake time series from Hydrocron, fitted to a yearly trend
        aquifer_trend(): placeholder for DISP-S1 velocity over a wellfield (see notes in function)

Inputs you download once (see README for links):
  data/raw/epa_service_areas.(gpkg|shp|geojson)   EPA Public Water System Service Areas
  data/raw/SDWA_PUB_WATER_SYSTEMS.csv              from the ECHO SDWA download zip
  data/raw/SDWA_FACILITIES.csv                     from the ECHO SDWA download zip

Column names below follow the ECHO data dictionary and EPA attribute tables at the time of
writing. Check them against the files you download and edit COLS if anything differs.

Usage:
  python pipeline/water_chain.py match   --registry data/site_registry.csv
  python pipeline/water_chain.py lookup  --pwsid TX0000000
  python pipeline/water_chain.py swot    --lake-id 6350036102 --start 2023-08-01 --end 2026-11-01
"""
import argparse
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import requests

RAW = Path("data/raw")
COLS = {
    "service_area_pwsid": "PWSID",
    "pws_id": "PWSID",
    "pws_name": "PWS_NAME",
    "pws_source": "PRIMARY_SOURCE_CODE",      # e.g. GW, SW, GWP, SWP (P = purchased)
    "pws_population": "POPULATION_SERVED_COUNT",
    "fac_pwsid": "PWSID",
    "fac_name": "FACILITY_NAME",
    "fac_type": "FACILITY_TYPE_CODE",
    "fac_water_type": "WATER_TYPE_CODE",       # GW, SW, GU
}
HYDROCRON = "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries"


# ---------- Step 1: site -> utility ----------
def match_utilities(registry_csv: str, service_areas_path: str = None) -> pd.DataFrame:
    import geopandas as gpd  # imported here so the other steps run without geopandas

    sites = pd.read_csv(registry_csv)
    pts = gpd.GeoDataFrame(sites, geometry=gpd.points_from_xy(sites.lon, sites.lat), crs="EPSG:4326")
    path = service_areas_path or next(RAW.glob("epa_service_areas.*"))
    areas = gpd.read_file(path).to_crs("EPSG:4326")
    joined = gpd.sjoin(pts, areas[[COLS["service_area_pwsid"], "geometry"]], how="left", predicate="within")
    joined = joined.rename(columns={COLS["service_area_pwsid"]: "pwsid"})
    # Sites outside every polygon are probably self-supplied (own wells). Flag them for a manual check.
    joined["match_status"] = np.where(joined["pwsid"].isna(), "no_utility_check_self_supply", "matched")
    # A site inside overlapping polygons gets several rows; keep them all and review by hand.
    out = pd.DataFrame(joined.drop(columns=["geometry", "index_right"], errors="ignore"))
    out.to_csv("data/site_utility_matches.csv", index=False)
    print(out[["site_id", "pwsid", "match_status"]].to_string(index=False))
    return out


# ---------- Step 2: utility -> source ----------
def lookup_sources(pwsid: str) -> dict:
    systems = pd.read_csv(RAW / "SDWA_PUB_WATER_SYSTEMS.csv", dtype=str, low_memory=False)
    facilities = pd.read_csv(RAW / "SDWA_FACILITIES.csv", dtype=str, low_memory=False)

    sys_rows = systems[systems[COLS["pws_id"]] == pwsid]
    if sys_rows.empty:
        raise ValueError(f"{pwsid} not found in SDWA_PUB_WATER_SYSTEMS.csv")
    row = sys_rows.iloc[-1]  # files can hold several reporting periods; take the last row

    fac = facilities[facilities[COLS["fac_pwsid"]] == pwsid]
    fac = fac[[COLS["fac_name"], COLS["fac_type"], COLS["fac_water_type"]]].drop_duplicates()

    result = {
        "pwsid": pwsid,
        "name": row.get(COLS["pws_name"]),
        "primary_source": row.get(COLS["pws_source"]),
        "purchased": str(row.get(COLS["pws_source"], "")).endswith("P"),
        "population_served": row.get(COLS["pws_population"]),
        "facilities": fac.to_dict(orient="records"),
    }
    # If purchased, the real source sits with the selling utility: find it in the utility's
    # water quality report (CCR) and run lookup_sources() again on the seller's PWSID.
    print(json.dumps(result, indent=2))
    return result


# ---------- Step 3a: reservoir trend from SWOT via Hydrocron ----------
def reservoir_trend(lake_id: str, start: str, end: str) -> dict:
    params = {
        "feature": "PriorLake",
        "feature_id": lake_id,
        "start_time": f"{start}T00:00:00Z",
        "end_time": f"{end}T00:00:00Z",
        "output": "csv",
        "fields": "lake_id,time_str,wse,area_total,quality_f",
    }
    r = requests.get(HYDROCRON, params=params, timeout=120)
    r.raise_for_status()
    payload = r.json()
    csv_text = payload.get("results", {}).get("csv") if isinstance(payload, dict) else None
    if not csv_text:
        raise RuntimeError(f"Unexpected Hydrocron response: {str(payload)[:300]}")

    df = pd.read_csv(io.StringIO(csv_text))
    df["time"] = pd.to_datetime(df["time_str"], errors="coerce", utc=True)
    df["wse"] = pd.to_numeric(df["wse"], errors="coerce")
    df["quality_f"] = pd.to_numeric(df["quality_f"], errors="coerce")
    # Drop fill values and poor-quality passes (0 = good in the SWOT quality flag).
    df = df[(df["wse"] > -1000) & (df["quality_f"] == 0) & df["time"].notna()]
    if len(df) < 4:
        raise RuntimeError(f"Only {len(df)} usable SWOT passes for lake {lake_id}; widen the dates.")

    years = (df["time"] - df["time"].min()).dt.total_seconds() / (365.25 * 86400)
    slope, intercept = np.polyfit(years, df["wse"], 1)
    out_path = Path(f"data/swot_{lake_id}.csv")
    df[["time", "wse", "area_total"]].to_csv(out_path, index=False)
    result = {"lake_id": lake_id, "passes": int(len(df)), "trend_m_per_yr": float(slope),
              "series_file": str(out_path)}
    print(json.dumps(result, indent=2))
    return result


# ---------- Step 3b: aquifer trend from OPERA DISP-S1 ----------
def aquifer_trend(wellfield_geojson: str, frame_files: list) -> dict:
    """
    Placeholder. DISP-S1 granules are HDF5 files on a UTM grid with cumulative line-of-sight
    displacement per acquisition. To finish this step:
      1. Find the frame(s) covering the wellfield in ASF Vertex (dataset: OPERA DISP-S1) or with
         earthaccess, and download them into data/raw/disp/.
      2. Open one file with h5py and list its datasets to confirm the displacement layer name and
         units in the product specification before writing the reader.
      3. Reproject the wellfield polygon to the file's UTM zone, average displacement inside it
         for each date, then fit a linear velocity (mm/yr). Negative = moving away from the
         satellite, usually sinking.
    """
    raise NotImplementedError("Implement after inspecting a real DISP-S1 file (see docstring).")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("match"); m.add_argument("--registry", required=True); m.add_argument("--areas")
    l = sub.add_parser("lookup"); l.add_argument("--pwsid", required=True)
    s = sub.add_parser("swot"); s.add_argument("--lake-id", required=True)
    s.add_argument("--start", required=True); s.add_argument("--end", required=True)
    a = p.parse_args()
    if a.cmd == "match":
        match_utilities(a.registry, a.areas)
    elif a.cmd == "lookup":
        lookup_sources(a.pwsid)
    elif a.cmd == "swot":
        reservoir_trend(a.lake_id, a.start, a.end)


if __name__ == "__main__":
    main()
