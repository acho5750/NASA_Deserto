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


# ---------- Step 2: utility -> source (ECHO SDWA files) ----------
SDWA_LINK = "https://echo.epa.gov/files/echodownloads/SDWA_latest_downloads.zip"
SOURCE_FAC = {"WL": "well", "IN": "intake", "SP": "spring", "IG": "infiltration gallery",
              "RS": "reservoir", "SI": "surface impoundment", "WH": "wellhead"}
_SDWA = {}


def _sdwa():
    """Load the two SDWA tables once (only the columns we use)."""
    if not _SDWA:
        sys_cols = ["SUBMISSIONYEARQUARTER", "PWSID", "PWS_NAME", "PWS_TYPE_CODE", "PWS_ACTIVITY_CODE",
                    "PRIMARY_SOURCE_CODE", "POPULATION_SERVED_COUNT", "IS_WHOLESALER_IND", "CITY_NAME", "STATE_CODE"]
        fac_cols = ["PWSID", "FACILITY_ID", "FACILITY_NAME", "FACILITY_ACTIVITY_CODE", "FACILITY_TYPE_CODE",
                    "IS_SOURCE_IND", "WATER_TYPE_CODE", "AVAILABILITY_CODE", "SELLER_PWSID", "SELLER_PWS_NAME"]
        _SDWA["sys"] = pd.read_csv(RAW / "sdwa/SDWA_PUB_WATER_SYSTEMS.csv", dtype=str, usecols=sys_cols).set_index("PWSID")
        _SDWA["fac"] = pd.read_csv(RAW / "sdwa/SDWA_FACILITIES.csv", dtype=str, usecols=fac_cols)
        _SDWA["quarter"] = _SDWA["sys"]["SUBMISSIONYEARQUARTER"].max()
    return _SDWA


def lookup_sources(pwsid: str) -> dict:
    """Primary source, population and active source facilities of one system, from SDWA."""
    d = _sdwa()
    if pwsid not in d["sys"].index:
        return {"pwsid": pwsid, "found": False}
    row = d["sys"].loc[[pwsid]].iloc[-1]
    fac = d["fac"][(d["fac"].PWSID == pwsid) & (d["fac"].FACILITY_ACTIVITY_CODE == "A")]
    src = fac[(fac.IS_SOURCE_IND == "Y") & fac.FACILITY_TYPE_CODE.isin(SOURCE_FAC)]
    # Permanent sources only when there are any; emergency/seasonal wells are not the supply.
    if (src.AVAILABILITY_CODE == "P").any():
        src = src[src.AVAILABILITY_CODE == "P"]
    cc = fac[(fac.FACILITY_TYPE_CODE == "CC") & fac.SELLER_PWSID.notna()]
    sellers = list(dict.fromkeys(cc.SELLER_PWSID))
    return {
        "pwsid": pwsid, "found": True, "name": row.PWS_NAME, "pws_type": row.PWS_TYPE_CODE,
        "active": row.PWS_ACTIVITY_CODE == "A", "primary_source": row.PRIMARY_SOURCE_CODE,
        "purchased": str(row.PRIMARY_SOURCE_CODE).endswith("P"),
        "population_served": pd.to_numeric(row.POPULATION_SERVED_COUNT, errors="coerce"),
        "city": row.CITY_NAME, "state": row.STATE_CODE,
        "n_wells": int((src.FACILITY_TYPE_CODE == "WL").sum()),
        "n_surface_intakes": int(src.FACILITY_TYPE_CODE.isin(["IN", "RS", "SI", "IG"]).sum()),
        "source_facilities": "; ".join(f"{r.FACILITY_NAME} [{r.FACILITY_TYPE_CODE}/{r.WATER_TYPE_CODE}]"
                                       for r in src.itertuples()),
        "sdwa_sellers": "; ".join(f"{p} ({n})" for p, n in cc[["SELLER_PWSID", "SELLER_PWS_NAME"]]
                                 .drop_duplicates("SELLER_PWSID").itertuples(index=False)),
        "_sellers": sellers, "sdwa_quarter": d["quarter"],
    }


def trace_chain(pwsid: str, max_depth: int = 3) -> list:
    """Follow purchased water to the sellers named in SDWA, up to max_depth hops.
    Returns one dict per system visited, with depth 0 = the utility serving the site."""
    out, frontier, seen = [], [(pwsid, 0, None)], set()
    while frontier:
        p, depth, buyer = frontier.pop(0)
        if p in seen:
            continue
        seen.add(p)
        info = lookup_sources(p)
        info.update({"depth": depth, "buyer_pwsid": buyer})
        out.append(info)
        if info.get("found") and info["purchased"] and depth < max_depth:
            frontier += [(s, depth + 1, p) for s in info["_sellers"]]
    return out


def lookup_all(matches_csv: str, out_csv: str = "data/water/utility_chain.csv") -> pd.DataFrame:
    m = pd.read_csv(matches_csv, dtype={"pwsid": str})
    rows = []
    for pwsid in m.pwsid.dropna().unique():
        for info in trace_chain(pwsid):
            info = {k: v for k, v in info.items() if not k.startswith("_")}
            rows.append({"site_pwsid": pwsid, **info})
    out = pd.DataFrame(rows)
    out["source_link"] = SDWA_LINK
    out.to_csv(out_csv, index=False)
    print(out[["site_pwsid", "depth", "pwsid", "name", "primary_source", "population_served",
               "n_wells", "n_surface_intakes", "sdwa_sellers"]].to_string(index=False))
    return out


# ---------- Step 3a: reservoir / river trend from SWOT via Hydrocron ----------
# Prior Lake Database IDs (needed for feature=PriorLake) come from files on PO.DAAC's protected
# archive, which this environment cannot log in to (see DECISIONS.md). Reservoirs and rivers that
# have a SWOT River Database (SWORD) reach are read with feature=Reach instead. The reach's
# prior location returned by Hydrocron is checked against the expected water body.
SWOT_START, SWOT_END = "2023-08-01", "2026-11-01"
SWOT_WIDEN_START = "2023-04-01"  # widen once (start of SWOT science orbit data) before insufficient_swot
HYDROCRON_LINK = "https://podaac.github.io/hydrocron/"
SWORD_LINK = "https://zenodo.org/records/23870877"


def _hydrocron(feature: str, fid: str, start: str, end: str, fields: str) -> pd.DataFrame:
    params = {"feature": feature, "feature_id": fid, "start_time": f"{start}T00:00:00Z",
              "end_time": f"{end}T00:00:00Z", "output": "csv", "fields": fields}
    for attempt in range(4):
        r = requests.get(HYDROCRON, params=params, timeout=120)
        if r.status_code == 400 and "not found" in r.text:
            return pd.DataFrame()
        if r.ok:
            return pd.read_csv(io.StringIO(r.json()["results"]["csv"]))
        time.sleep(2 ** attempt)
    r.raise_for_status()


def _fit_trend(t: pd.Series, v: pd.Series) -> tuple:
    """Least-squares slope per year, after dropping points more than 4 MAD from the median."""
    med = v.median(); mad = (v - med).abs().median() or 1e-9
    keep = (v - med).abs() <= 4 * 1.4826 * mad
    t, v = t[keep], v[keep]
    years = (t - t.min()).dt.total_seconds() / (365.25 * 86400)
    slope, _ = np.polyfit(years, v, 1)
    return float(slope), int(keep.sum()), int((~keep).sum())


def reservoir_trend(feature_id: str, feature: str = "Reach", start: str = SWOT_START, end: str = SWOT_END,
                    out_dir: str = "data/water/swot") -> dict:
    if feature == "Reach":
        fields, qcol = "reach_id,time_str,wse,reach_q,p_lat,p_lon,river_name", "reach_q"
    else:
        fields, qcol = "lake_id,time_str,wse,area_total,quality_f", "quality_f"
    result = {"trend_feature_id": feature_id, "trend_feature": feature}
    for attempt_start in (start, SWOT_WIDEN_START):
        df = _hydrocron(feature, feature_id, attempt_start, end, fields)
        if df.empty:
            return {**result, "trend_status": "swot_feature_not_found"}
        df["time"] = pd.to_datetime(df["time_str"], errors="coerce", utc=True)
        df["wse"] = pd.to_numeric(df["wse"], errors="coerce")
        df[qcol] = pd.to_numeric(df[qcol], errors="coerce")
        # Good passes: reach_q 0-1 (nominal / suspect) for rivers, quality_f 0 for lakes; drop fill values.
        good = df[(df["wse"] > -1000) & df["time"].notna() & (df[qcol] <= (1 if feature == "Reach" else 0))]
        if len(good) >= 4:
            break
    if len(good) < 4:
        return {**result, "trend_status": "insufficient_swot", "trend_n": len(good)}
    slope, n, dropped = _fit_trend(good["time"], good["wse"])
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    series = Path(out_dir) / f"swot_{feature.lower()}_{feature_id}.csv"
    good[["time", "wse", qcol]].sort_values("time").to_csv(series, index=False)
    out = {**result, "trend_status": "ok", "trend_value": round(slope, 3), "trend_unit": "m/yr",
           "trend_n": n, "trend_outliers_dropped": dropped,
           "trend_start": good["time"].min().date().isoformat(), "trend_end": good["time"].max().date().isoformat(),
           "trend_series_file": str(series)}
    if feature == "Reach":
        out.update({"feature_lat": float(df["p_lat"].iloc[0]), "feature_lon": float(df["p_lon"].iloc[0]),
                    "feature_name": df["river_name"].iloc[0]})
    print(json.dumps(out, indent=2))
    return out


# ---------- Step 3b: aquifer trend from OPERA DISP-S1 ----------
# Inspected file (2026-11-15): OPERA_L3_DISP-S1_IW_F28482_VV_20250418T003512Z_20251108T003508Z_v1.0.
# HDF5/netCDF, 7969 x 9584 grid at 30 m in UTM (spatial_ref: crs_wkt + GeoTransform), chunks 256x256.
# /displacement: LOS displacement in metres, positive = towards the satellite, relative to
# /identification/reference_datetime (the ministack reference, which changes every few months) and
# to the frame's spatial reference point. /recommended_mask: 1 = good pixel.
# Reader: read only a small window by HTTP range requests, take the median of good pixels per date,
# chain ministacks (displacement at a new reference date is added to every later date), fit mm/yr.
CMR_GRANULES = "https://cmr.earthdata.nasa.gov/search/granules.json"
DISP_COLLECTION = "OPERA_L3_DISP-S1_V1"
DISP_LINK = "https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-v1-1"
DISP_HALF_WINDOW_PX = 100   # 200 x 200 pixels = 6 km x 6 km
DISP_MIN_GOOD = 0.3         # skip a date if fewer than 30% of window pixels are good


def _disp_granules(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    rows, headers = [], {}
    while True:
        r = requests.get(CMR_GRANULES, params={"short_name": DISP_COLLECTION, "point": f"{lon},{lat}",
                                               "temporal": f"{start}T00:00:00Z,{end}T00:00:00Z", "page_size": 2000},
                         headers=headers, timeout=120)
        r.raise_for_status()
        entries = r.json()["feed"]["entry"]
        for e in entries:
            url = next((l["href"] for l in e["links"] if l["href"].endswith(".nc") and l["href"].startswith("https")), None)
            parts = e["title"].split("_")  # OPERA_L3_DISP-S1_IW_F28482_VV_<ref>_<sec>_v1.0_<prod>
            rows.append({"title": e["title"], "url": url, "frame": parts[4], "ref": parts[6][:8],
                         "sec": parts[7][:8], "prod": parts[9]})
        if len(entries) < 2000 or "CMR-Search-After" not in r.headers:
            break
        headers = {"CMR-Search-After": r.headers["CMR-Search-After"]}
    return pd.DataFrame(rows)


def _unshuffle(raw: bytes, itemsize: int) -> bytes:
    if itemsize == 1:
        return raw
    return np.frombuffer(raw, np.uint8).reshape(itemsize, -1).T.tobytes()


def _disp_window(url: str, lat: float, lon: float, session) -> tuple:
    """Median good-pixel displacement (m) in the window, read through the granule's kerchunk
    reference file (<granule>.zarr.json.gz): one small GET for the chunk index, then HTTP range
    reads of only the 256x256 chunks that cover the window."""
    import gzip, zlib, pyproj
    refs = json.loads(gzip.decompress(session.get(url[:-3] + ".zarr.json.gz", timeout=120).content))["refs"]
    sr = json.loads(refs["spatial_ref/.zattrs"])
    gt = [float(v) for v in sr["GeoTransform"].split()]
    crs = pyproj.CRS.from_wkt(sr["crs_wkt"])
    x, y = pyproj.Transformer.from_crs(4326, crs, always_xy=True).transform(lon, lat)
    c, r, h = int((x - gt[0]) / gt[1]), int((y - gt[3]) / gt[5]), DISP_HALF_WINDOW_PX
    ny, nx = json.loads(refs["displacement/.zarray"])["shape"]
    if not (h <= r < ny - h and h <= c < nx - h):
        return np.nan, 0.0
    # Resolve the redirect to the signed S3 URL once, then range-read chunks from it.
    loc = session.get(url, headers={"Range": "bytes=0-0"}, allow_redirects=False, timeout=120)
    signed = loc.headers.get("Location", url) if loc.is_redirect else url

    def mosaic(var, fill):
        za = json.loads(refs[f"{var}/.zarray"])  # chunk shape and dtype differ between product versions
        dtype = za["dtype"]
        cy, cx = za["chunks"]
        isz = next((f["elementsize"] for f in za["filters"] if f["id"] == "shuffle"), 1)
        rows, cols = range((r - h) // cy, (r + h - 1) // cy + 1), range((c - h) // cx, (c + h - 1) // cx + 1)
        big = np.full((len(rows) * cy, len(cols) * cx), fill, dtype=dtype)
        for i, cr in enumerate(rows):
            for j, cc in enumerate(cols):
                ref = refs.get(f"{var}/{cr}.{cc}")
                if ref is None:
                    continue
                if isinstance(ref, str):  # small chunks are stored inline in the reference file
                    import base64
                    raw = base64.b64decode(ref[7:]) if ref.startswith("base64:") else ref.encode()
                else:
                    _, off, ln = ref
                    raw = session.get(signed, headers={"Range": f"bytes={off}-{off + ln - 1}"}, timeout=120).content
                big[i * cy:(i + 1) * cy, j * cx:(j + 1) * cx] = np.frombuffer(
                    _unshuffle(zlib.decompress(raw), isz), dtype=dtype).reshape(cy, cx)
        r0, c0 = r - h - rows[0] * cy, c - h - cols[0] * cx
        return big[r0:r0 + 2 * h, c0:c0 + 2 * h]

    d = mosaic("displacement", np.nan)
    m = mosaic("recommended_mask", 255)
    good = (m == 1) & np.isfinite(d)
    return (float(np.median(d[good])) if good.mean() >= DISP_MIN_GOOD else np.nan), float(good.mean())


def aquifer_trend(name: str, lat: float, lon: float, start: str = "2016-07-01", end: str = "2026-11-15",
                  out_dir: str = "data/water/disp", workers: int = 16) -> dict:
    """LOS velocity (mm/yr) over a 6 km window centred on (lat, lon), from every DISP-S1 date of the
    frame with the most dates there."""
    from concurrent.futures import ThreadPoolExecutor
    g = _disp_granules(lat, lon, start, end)
    base = {"trend_method": "disp_s1", "feature_lat": lat, "feature_lon": lon}
    if g.empty:
        return {**base, "trend_status": "no_disp_s1_coverage"}
    frame = g.groupby("frame").sec.nunique().idxmax()
    g = g[g.frame == frame].sort_values("prod").drop_duplicates(["ref", "sec"], keep="last").sort_values(["sec", "ref"])
    session = requests.Session()  # requests honours HTTPS_PROXY, which adds the Earthdata token for ASF

    def one(u):
        for attempt in range(3):
            try:
                return _disp_window(u, lat, lon, session)
            except Exception as e:  # network hiccup or a granule without a reference file
                err = e
                time.sleep(2 ** attempt)
        print(f"  skipped {u.rsplit('/', 1)[-1]}: {err}")
        return np.nan, 0.0
    with ThreadPoolExecutor(workers) as ex:
        vals = list(ex.map(one, g.url))
    g["disp_m"], g["good_frac"] = [v[0] for v in vals], [v[1] for v in vals]
    # Chain ministacks: cumulative(sec) = disp(ref -> sec) + cumulative(ref). The first reference is 0.
    # When a date that later serves as a reference is missing (masked or skipped), the chain breaks;
    # the next ministack then starts a new segment with its own unknown offset.
    cum, seg = {}, {}
    rows = []
    for r in g.itertuples():
        if not np.isfinite(r.disp_m):
            continue
        if r.ref not in cum:
            cum[r.ref], seg[r.ref] = 0.0, len(set(seg.values()))
        if r.sec not in cum:
            cum[r.sec], seg[r.sec] = r.disp_m + cum[r.ref], seg[r.ref]
            rows.append({"date": r.sec, "cum_disp_m": cum[r.sec], "segment": seg[r.sec], "ref": r.ref,
                         "good_frac": r.good_frac})
    ts = pd.DataFrame(rows, columns=["date", "cum_disp_m", "segment", "ref", "good_frac"])
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    series = Path(out_dir) / f"disp_{name}_{frame}.csv"
    ts.to_csv(series, index=False)
    # Segments with fewer than 3 dates carry no slope information.
    ts = ts[ts.groupby("segment").date.transform("size") >= 3]
    if len(ts) < 10:
        return {**base, "trend_status": "insufficient_disp_s1", "trend_n": len(ts), "trend_feature_id": frame,
                "granules_read": int(len(g)), "granules_masked": int((~np.isfinite(g.disp_m)).sum())}
    t = pd.to_datetime(ts.date, format="%Y%m%d", utc=True)
    years = ((t - t.min()).dt.total_seconds() / (365.25 * 86400)).to_numpy()
    v = ts.cum_disp_m.to_numpy() * 1000
    segs = pd.get_dummies(ts.segment).to_numpy(float)
    keep = np.ones(len(v), bool)
    for _ in range(2):  # common slope, one offset per segment; second pass drops >4 MAD residuals
        X = np.column_stack([years, segs])[keep]
        coef, *_ = np.linalg.lstsq(X, v[keep], rcond=None)
        res = v - np.column_stack([years, segs]) @ coef
        mad = np.median(np.abs(res[keep] - np.median(res[keep]))) or 1e-9
        keep = np.abs(res - np.median(res[keep])) <= 4 * 1.4826 * mad
    slope, n, dropped = float(coef[0]), int(keep.sum()), int((~keep).sum())
    out = {**base, "trend_status": "ok", "trend_value": round(slope, 2), "trend_unit": "mm/yr LOS",
           "trend_n": n, "trend_outliers_dropped": dropped, "trend_feature_id": frame,
           "trend_start": t.min().date().isoformat(), "trend_end": t.max().date().isoformat(),
           "trend_series_file": str(series), "granules_read": int(len(g)),
           "granules_masked": int((~np.isfinite(g.disp_m)).sum()), "segments": int(ts.segment.nunique())}
    print(json.dumps(out, indent=2))
    return out


def _service_area_point(pwsid: str) -> tuple:
    import shapely.geometry as sg
    r = requests.get(EPA_SERVICE_AREAS, params={"where": f"PWSID='{pwsid}'", "outFields": "PWSID",
                                                "returnGeometry": "true", "outSR": 4326, "f": "geojson"}, timeout=120)
    r.raise_for_status()
    geoms = [sg.shape(f["geometry"]) for f in r.json()["features"] if f.get("geometry")]
    from shapely.ops import unary_union
    pt = unary_union(geoms).representative_point()
    return round(pt.y, 5), round(pt.x, 5)


# ---------- Build data/sources.csv ----------
def build_sources(matches_csv="data/water/site_utility_matches.csv", chain_csv="data/water/utility_chain.csv",
                  assign_csv="data/water/source_assignments.csv", out_csv="data/sources.csv",
                  site_out="data/water/site_sources.csv", trends_cache="data/water/trends.csv", refresh=False):
    m = pd.read_csv(matches_csv, dtype={"pwsid": str})
    chain = pd.read_csv(chain_csv, dtype=str)
    assign = pd.read_csv(assign_csv, dtype=str)
    top = chain[chain.depth == "0"].drop_duplicates("pwsid").set_index("pwsid")

    # Trends: one per water body (shared by every utility that draws on it), cached on disk.
    cache = pd.read_csv(trends_cache, dtype={"water_body_id": str, "trend_feature_id": str}) \
        if Path(trends_cache).exists() and not refresh else pd.DataFrame(columns=["water_body_id"])
    trends = {r.water_body_id: r._asdict() for r in cache.itertuples(index=False)}
    for wb, grp in assign.groupby("water_body_id"):
        if wb in trends:
            continue
        a = grp.iloc[0]
        if a.trend_method == "swot_reach":
            t = reservoir_trend(a.trend_feature_id, "Reach")
        elif a.trend_method == "swot_lake":
            t = {"trend_status": "swot_lake_id_unavailable"}
        else:  # disp_s1 over the service area of the (single) utility using this aquifer
            lat, lon = _service_area_point(grp.pwsid.iloc[0])
            t = aquifer_trend(wb, lat, lon)
        trends[wb] = {"water_body_id": wb, "trend_method": a.trend_method, **t}
        pd.DataFrame(trends.values()).to_csv(trends_cache, index=False)
    tr = pd.DataFrame(trends.values()).set_index("water_body_id")

    rows = []
    for a in assign.itertuples(index=False):
        t = tr.loc[a.water_body_id] if a.water_body_id in tr.index else pd.Series(dtype=object)
        u = top.loc[a.pwsid]
        pop = pd.to_numeric(u.population_served, errors="coerce")
        links = [a.source, SDWA_LINK]
        if a.trend_method.startswith("swot"):
            links += [HYDROCRON_LINK, SWORD_LINK]
        else:
            links += [DISP_LINK]
        sites = m[m.pwsid == a.pwsid].site_id.tolist()
        lat, lon = t.get("feature_lat"), t.get("feature_lon")
        if pd.notna(lat) and a.trend_method.startswith("swot"):
            loc_basis = "SWORD reach prior location (Hydrocron p_lat/p_lon)"
        elif pd.notna(lat):
            loc_basis = "DISP-S1 window centre: point inside the utility's EPA service area"
        else:
            lat, lon = _service_area_point(a.pwsid)
            loc_basis = "point inside the utility's EPA service area (water body location not in data)"
        rows.append({
            "source_id": f"SRC-{a.pwsid}", "name": f"{a.water_body} for {u['name'].title()}",
            "water_body_id": a.water_body_id, "water_body": a.water_body, "type": a.type,
            "lat": lat, "lon": lon, "location_basis": loc_basis,
            "utility_pwsid": a.pwsid, "utility_name": u["name"],
            "population_served": pop if pop and pop > 0 else np.nan,
            "trend_value": t.get("trend_value"), "trend_unit": t.get("trend_unit"),
            "trend_status": t.get("trend_status"), "trend_method": a.trend_method,
            "trend_feature_id": t.get("trend_feature_id", a.trend_feature_id),
            "trend_n": t.get("trend_n"), "trend_start": t.get("trend_start"), "trend_end": t.get("trend_end"),
            "trend_series_file": t.get("trend_series_file"),
            "aqueduct_stress": np.nan,  # Phase 4
            "sites": "; ".join(sites), "identification_basis": a.basis, "confidence": a.confidence,
            "flags": ";".join(f for f in [
                "population_missing" if not (pop and pop > 0) else "",
                "location_approx" if m[m.pwsid == a.pwsid].location_approx.any() else "",
                "aqueduct_pending"] if f),
            "sdwa_quarter": u.sdwa_quarter, "source": " ; ".join(dict.fromkeys(links)),
        })
    src = pd.DataFrame(rows)
    src.to_csv(out_csv, index=False)

    # Site -> source link. Overlapping service areas: keep the utility that has an assignment.
    assigned = set(assign.pwsid)
    links = []
    for sid, grp in m.groupby("site_id", sort=False):
        hit = grp[grp.pwsid.isin(assigned)]
        r0 = grp.iloc[0]
        if len(hit):
            h = hit.iloc[0]
            others = [p for p in grp.pwsid.dropna() if p != h.pwsid]
            links.append({"site_id": sid, "list": r0.list, "match_status": h.match_status, "pwsid": h.pwsid,
                          "source_id": f"SRC-{h.pwsid}", "other_service_areas": "; ".join(others),
                          "candidates_within_2km": "", "water_share": "include"})
        else:
            links.append({"site_id": sid, "list": r0.list, "match_status": r0.match_status, "pwsid": "",
                          "source_id": "", "other_service_areas": "",
                          "candidates_within_2km": r0.get("candidates_within_2km", ""), "water_share": "exclude"})
    links = pd.DataFrame(links)
    links.to_csv(site_out, index=False)
    # Fill the registries' source_id column (blank = self_supplied_check, excluded from water shares).
    sid = dict(zip(links.site_id, links.source_id))
    for reg in ("data/precedent_sites.csv", "data/announced_sites.csv"):
        df = pd.read_csv(reg, dtype=str, keep_default_na=False)
        df["source_id"] = df.site_id.map(sid).fillna("")
        df.to_csv(reg, index=False)
    print(src[["source_id", "water_body", "type", "population_served", "trend_value", "trend_unit", "trend_status"]].to_string(index=False))
    return src


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pt = sub.add_parser("points"); pt.add_argument("--precedent", default="data/precedent_sites.csv")
    pt.add_argument("--announced", default="data/announced_sites.csv"); pt.add_argument("--out", default="data/water/site_points.csv")
    m = sub.add_parser("match"); m.add_argument("--points", default="data/water/site_points.csv"); m.add_argument("--out", default="data/water/site_utility_matches.csv")
    l = sub.add_parser("lookup"); l.add_argument("--pwsid"); l.add_argument("--matches", default="data/water/site_utility_matches.csv")
    l.add_argument("--out", default="data/water/utility_chain.csv")
    so = sub.add_parser("sources"); so.add_argument("--refresh", action="store_true")
    s = sub.add_parser("swot"); s.add_argument("--feature-id", required=True); s.add_argument("--feature", default="Reach", choices=["Reach", "PriorLake"])
    s.add_argument("--start", required=True); s.add_argument("--end", required=True)
    a = p.parse_args()
    if a.cmd == "points":
        build_site_points(a.precedent, a.announced, a.out)
    elif a.cmd == "match":
        match_utilities(a.points, a.out)
    elif a.cmd == "lookup":
        if a.pwsid:
            print(json.dumps({k: v for k, v in trace_chain(a.pwsid)[0].items() if not k.startswith("_")}, indent=2, default=str))
        else:
            lookup_all(a.matches, a.out)
    elif a.cmd == "swot":
        reservoir_trend(a.feature_id, a.feature, a.start, a.end)
    elif a.cmd == "sources":
        build_sources(refresh=a.refresh)


if __name__ == "__main__":
    main()
