"""
Water chain (steps 1-3): data center site -> water utility -> water source -> source trend.

Step 1  match_utilities(): point query of each site against EPA's service area ArcGIS service (gets PWSID)
Step 2  lookup_sources(): source type, population served, and facility names from ECHO SDWA files
Step 3  reservoir_trend(): SWOT lake time series from Hydrocron, fitted to a yearly trend
        aquifer_trend(): placeholder for DISP-S1 velocity over a wellfield (see notes in function)

Inputs you download once (see README for links):
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
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

RAW = Path("data/raw")
COLS = {
    "service_area_pwsid": "PWSID",          # EPA service area layer fields (checked 2026-11-15)
    "service_area_name": "PWS_Name",
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
# EPA Community Water System Service Area Boundaries, queried live by point (see DECISIONS.md for
# the dataset version and why we use the service instead of a downloaded file).
EPA_SERVICE_AREAS = ("https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/"
                     "Water_System_Boundaries/FeatureServer/0/query")
NO_MATCH = "self_supplied_check"
SA_FIELDS = "PWSID,PWS_Name,Population_Served_Count,Service_Area_Type,Symbology_Field"
NEAR_M = 2000  # search radius for a nearest-candidate note on unmatched sites (not a match)  # label set in CLAUDE.md decision rules


def _query_service_areas(lat: float, lon: float, retries: int = 4, distance_m: float = 0) -> list:
    """Attribute dicts of every service area polygon that contains (lat, lon), or that lies
    within distance_m of it when distance_m > 0."""
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": SA_FIELDS,
        "returnGeometry": "false",
        "f": "json",
    }
    if distance_m:
        params.update({"distance": distance_m, "units": "esriSRUnit_Meter"})
    for attempt in range(retries):
        try:
            r = requests.get(EPA_SERVICE_AREAS, params=params, timeout=60)
            r.raise_for_status()
            payload = r.json()
            # ArcGIS reports query errors with HTTP 200 and an "error" key.
            if "error" in payload:
                raise RuntimeError(f"ArcGIS error: {payload['error']}")
            return [f["attributes"] for f in payload.get("features", [])]
        except (requests.RequestException, RuntimeError, ValueError):
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def build_site_points(precedent_csv: str, announced_csv: str,
                      out_csv: str = "data/water/site_points.csv") -> pd.DataFrame:
    """One point per site for the utility match.

    Built sites: a point inside the Phase 2 campus outline (data/footprint/<id>_campus.geojson),
    because 8 registry points are town centroids up to 12 km from the campus. Sites without an
    outline keep the registry point. Announced sites keep the registry point, which is a
    town/county centroid (location_basis says so); their matches are flagged location_approx.
    """
    import geopandas as gpd
    rows = []
    for _, s in pd.read_csv(precedent_csv).iterrows():
        geo = Path(f"data/footprint/{s.site_id}_campus.geojson")
        if geo.exists():
            pt = gpd.read_file(geo).to_crs(4326).union_all().representative_point()
            rows.append({"site_id": s.site_id, "list": "precedent", "lat": round(pt.y, 6), "lon": round(pt.x, 6),
                         "point_basis": f"inside OSM campus outline ({geo})", "location_approx": False})
        else:
            rows.append({"site_id": s.site_id, "list": "precedent", "lat": s.lat, "lon": s.lon,
                         "point_basis": f"registry point ({s.geocode_precision})",
                         "location_approx": s.geocode_precision in ("town", "none")})
    for _, s in pd.read_csv(announced_csv).iterrows():
        rows.append({"site_id": s.site_id, "list": "announced", "lat": s.lat, "lon": s.lon,
                     "point_basis": f"registry point: {s.location_basis}",
                     "location_approx": "not the campus" in str(s.location_basis)})
    out = pd.DataFrame(rows)
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv}: {len(out)} sites, {int(out.location_approx.sum())} with approximate location")
    return out


SELLERS = ("https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/"
           "Water_System_Boundaries/FeatureServer/2/query")


def _sellers(pwsid: str) -> list:
    """Seller systems listed for a buyer PWSID in EPA's Buyer_Seller table."""
    r = requests.get(SELLERS, params={"where": f"Buyer_PWSID='{pwsid}'", "outFields": "SELLER_PWSID,SELLER_NAME",
                                      "returnGeometry": "false", "f": "json"}, timeout=60)
    r.raise_for_status()
    return [f["attributes"] for f in r.json().get("features", [])]


def match_utilities(points_csv: str, out_csv: str = "data/water/site_utility_matches.csv") -> pd.DataFrame:
    sites = pd.read_csv(points_csv)
    rows = []
    for _, site in sites.iterrows():
        if pd.isna(site["lat"]):
            rows.append({"site_id": site["site_id"], "match_status": "no_coordinates"})
            print(f"{site['site_id']}: no coordinates")
            continue
        hits = _query_service_areas(site["lat"], site["lon"])
        seen = {}
        for h in hits:  # one PWSID can be split into several polygons; count it once
            if h.get("PWSID") and h["PWSID"] not in seen:
                seen[h["PWSID"]] = h
        if not seen:
            # Outside every polygon: probably self-supplied (own wells). Flag for a manual check.
            near = _query_service_areas(site["lat"], site["lon"], distance_m=NEAR_M)
            near = list(dict.fromkeys(f"{h['PWSID']} ({h.get('PWS_Name')}, {h.get('Service_Area_Type')})" for h in near))
            rows.append({"site_id": site["site_id"], "match_status": NO_MATCH,
                         "candidates_within_2km": "; ".join(near)})
        for pwsid, h in seen.items():
            sel = _sellers(pwsid)
            rows.append({"site_id": site["site_id"], "pwsid": pwsid, "pws_name": h.get("PWS_Name"),
                         "sa_population": h.get("Population_Served_Count"),
                         "service_area_type": h.get("Service_Area_Type"),
                         "boundary_basis": h.get("Symbology_Field"),
                         "epa_sellers": "; ".join(f"{x['SELLER_PWSID']} ({x['SELLER_NAME']})" for x in sel),
                         "match_status": "matched_approx_location" if site["location_approx"] else "matched"})
        print(f"{site['site_id']}: " + (", ".join(f"{p} ({h.get('PWS_Name')})" for p, h in seen.items()) or "no match"))
    out = sites[["site_id", "list", "lat", "lon", "point_basis", "location_approx"]].merge(
        pd.DataFrame(rows), on="site_id", how="left")
    out["match_source"] = EPA_SERVICE_AREAS.rsplit("/query", 1)[0]
    out.to_csv(out_csv, index=False)
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
    pt = sub.add_parser("points"); pt.add_argument("--precedent", default="data/precedent_sites.csv")
    pt.add_argument("--announced", default="data/announced_sites.csv"); pt.add_argument("--out", default="data/water/site_points.csv")
    m = sub.add_parser("match"); m.add_argument("--points", default="data/water/site_points.csv"); m.add_argument("--out", default="data/water/site_utility_matches.csv")
    l = sub.add_parser("lookup"); l.add_argument("--pwsid", required=True)
    s = sub.add_parser("swot"); s.add_argument("--lake-id", required=True)
    s.add_argument("--start", required=True); s.add_argument("--end", required=True)
    a = p.parse_args()
    if a.cmd == "points":
        build_site_points(a.precedent, a.announced, a.out)
    elif a.cmd == "match":
        match_utilities(a.points, a.out)
    elif a.cmd == "lookup":
        lookup_sources(a.pwsid)
    elif a.cmd == "swot":
        reservoir_trend(a.lake_id, a.start, a.end)


if __name__ == "__main__":
    main()
