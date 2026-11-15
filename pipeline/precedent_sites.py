"""Build data/precedent_sites.csv: built US AI data centers from Epoch AI (Phase 1a).

Usage:
    python pipeline/precedent_sites.py [--as-of 2026-11-15] [--max-sites 30] [--no-geocode]

Steps
1. Download Epoch AI's data center bundle (https://epoch.ai/data/data_centers/data_centers.zip,
   CC BY 4.0) into data/raw/epoch/ (gitignored).
2. For every US site, read its timeline (data_center_timelines.csv) and derive:
   - construction_start: date of the first timeline row (Epoch logs land clearing / construction
     start there; the row text is copied to construction_start_evidence for review).
   - operation_date: first timeline date with Power (MW) > 0.
   - mw (IT MW), mw_facility, capex_busd (total, incl. compute) and capex_construction_busd
     (building + power + cooling only) from the last timeline row on or before --as-of.
   - planned_final_mw_facility / planned_final_date from the last timeline row (may be future).
3. Keep sites that are operational by --as-of and whose first timeline row describes greenfield
   land clearing. Exclude conversions of existing buildings and sites that share one campus with
   another Epoch entry (rules and reasons are in EXCLUDE below; each is listed in the notes file).
4. Rank: buildout complete by --as-of first, then earliest operation_date; keep --max-sites.
5. Coordinates: if Epoch's own text for the site holds Google Earth links (".../@lat,lon,..."),
   use the mean of those points (precision "epoch_link"). Otherwise geocode the Epoch address
   with OpenStreetMap Nominatim (1 request/s; precision "street" or "town"). These are pointers
   for Phase 2, which replaces them with a PNNL/OSM campus outline. A "town" point is a town
   centroid and must not be used for the Phase 3 utility match.

No number is invented: every value is copied or derived from an Epoch row named in the output,
and blanks mean Epoch has no value.
"""
import argparse
import io
import re
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "epoch"
OUT = ROOT / "data" / "precedent_sites.csv"
EXCLUDED_OUT = ROOT / "data" / "precedent_sites_excluded.csv"
ZIP_URL = "https://epoch.ai/data/data_centers/data_centers.zip"
DATASET_URL = "https://epoch.ai/data/data-centers"
TIMELINE_URL = "https://epoch.ai/data/data_centers/data_center_timelines.csv"
UA = "nasa-spaceapps-datacenter-water-research/0.1"

# Sites dropped from the precedent set, with the reason. Reasons come from Epoch's own
# first timeline row (copied to data/precedent_sites_excluded.csv).
EXCLUDE = {
    "Colossus 1": "conversion: retrofit of a former Electrolux factory, little new land converted",
    "CoreWeave Chester VA": "conversion: existing Capital One data center refit",
    "CoreWeave Dalton 1 & 2": "conversion: existing Core Scientific crypto-mining buildings",
    "CoreWeave Denton TX": "conversion: existing Bitcoin-mining buildings",
    "CoreWeave Marble NC": "conversion: existing Core Scientific crypto-mining site",
    "Coreweave Helios": "conversion: former crypto-mining site, first building converted",
    "Stream Phoenix": "conversion: renovation of existing building PX1",
    "xAI QTS Atlanta": "conversion: hardware installed in an existing Atlanta data center",
    "Google Pryor (North)": "no construction start: Epoch timeline begins at operation",
    "Core42 Lake Mariner": "shared campus: same address as Anthropic Lake Mariner (7725 Lake Rd, Barker NY)",
    "Anthropic Lake Mariner": "shared campus: same address as Core42 Lake Mariner (7725 Lake Rd, Barker NY)",
}

# Sites whose tracked buildings sit next to older buildings of the same campus. Phase 2 must
# draw the outline around the new parcel only, or the baseline already contains built land.
ADJACENT_EXISTING = {
    "Google The Dalles": "older Google buildings on the same campus since 2006",
    "Google Council Bluffs (East)": "east expansion of an existing Google campus",
    "Google Papillion": "Epoch tracks the expansion (Building 1 of expansion)",
    "AWS New Albany": "Epoch tracks Buildings 5-9 (eastern campus) only",
    "QTS Richmond 1": "site expansion next to existing QTS Richmond buildings",
    "QTS Richmond 2": "QTS Richmond campus; adjacent to QTS Richmond 1 and 3",
    "QTS Richmond 3": "QTS Richmond campus; adjacent to QTS Richmond 1 and 2",
    "Colossus 2": "land clearing next to an existing building",
    "Microsoft SAT40": "first works dug up an existing parking lot",
    "Meta Los Lunas": "new building on an existing Meta campus",
    "Meta-QTS Hillsboro 2": "Hillsboro data center cluster",
}


def slug(name):
    if name == "OpenAI Stargate Abilene":
        return "STARGATE-ABILENE"  # id already used in data/footprint/
    s = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").upper()
    return s


def first_link(md):
    m = re.search(r"\((https?://[^)\s]+)\)", str(md))
    return m.group(1) if m else ""


def download():
    RAW.mkdir(parents=True, exist_ok=True)
    r = requests.get(ZIP_URL, timeout=60, headers={"User-Agent": UA})
    r.raise_for_status()
    (RAW / "data_centers.zip").write_bytes(r.content)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall(RAW)
    return pd.read_csv(RAW / "data_centers.csv"), pd.read_csv(RAW / "data_center_timelines.csv")


STATES = {"AL": "Alabama", "AZ": "Arizona", "GA": "Georgia", "IA": "Iowa", "ID": "Idaho",
          "IN": "Indiana", "MN": "Minnesota", "MS": "Mississippi", "NC": "North Carolina",
          "ND": "North Dakota", "NE": "Nebraska", "NJ": "New Jersey", "NM": "New Mexico",
          "NV": "Nevada", "NY": "New York", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
          "PA": "Pennsylvania", "SC": "South Carolina", "TN": "Tennessee", "TX": "Texas",
          "UT": "Utah", "VA": "Virginia", "WI": "Wisconsin", "WY": "Wyoming", "LA": "Louisiana",
          "MO": "Missouri", "KS": "Kansas"}


def address_state(addr):
    m = re.search(r"\b([A-Z]{2})\s*,?\s*\d{5}\b", addr) or re.search(r",\s*([A-Z]{2})\s*(?:,|$)", addr)
    if m and m.group(1) in STATES:
        return STATES[m.group(1)]
    for full in STATES.values():
        if full.lower() in addr.lower():
            return full
    for ab, full in STATES.items():
        if re.search(rf"\b{ab}\b", addr) or full.lower() in addr.lower():
            return full
    return None


TOWN_TYPES = ("city", "town", "village", "county", "state", "postcode", "hamlet", "municipality")
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def census_geocode(addr, session):
    m = None
    for attempt in range(4):
        try:
            r = session.get(CENSUS_URL, params={"address": addr, "benchmark": "Public_AR_Current",
                                                "format": "json"}, timeout=30)
            r.raise_for_status()
            m = r.json()["result"]["addressMatches"]
            break
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"  census geocoder attempt {attempt + 1} failed for {addr!r}: {e}", file=sys.stderr)
            time.sleep(2 ** attempt)
    if not m:
        return None
    return (round(m[0]["coordinates"]["y"], 5), round(m[0]["coordinates"]["x"], 5),
            "street_census", "US Census geocoder: " + m[0]["matchedAddress"])


def geocode(address, session):
    """Return (lat, lon, precision, display_name) from Nominatim, or blanks.

    A hit is accepted only if its display name contains the state named in the address."""
    if not isinstance(address, str) or not address.strip():
        return None, None, "none", ""
    addr = " ".join(address.split())
    state = address_state(addr)
    tries = [addr]
    # fallback: drop the street part and keep "City, ST ZIP"
    parts = [p.strip() for p in addr.split(",") if p.strip() and p.strip().upper() not in ("USA", "US")]
    if len(parts) >= 2:
        tries.append(", ".join(parts[1:]))
    if state:  # "... Papillion Nebraska" -> "Papillion, Nebraska"
        m = re.search(rf"([A-Za-z]+)\s*,?\s*{state}", addr)
        if m:
            tries.append(f"{m.group(1)}, {state}")
    zm = re.search(r"\b(\d{5})\b", addr)
    queries = tries + ([f"zip:{zm.group(1)}"] if zm else [])
    town_hit = None
    for i, q in enumerate(queries):
        if i == 1:  # full address gave no street-level hit: try the Census address-range geocoder
            c = census_geocode(addr, session)
            if c:
                return c
            if town_hit:
                return town_hit
        time.sleep(1.1)
        params = ({"postalcode": q[4:], "country": "us"} if q.startswith("zip:") else {"q": q})
        params.update({"format": "json", "countrycodes": "us", "limit": 1})
        r = session.get("https://nominatim.openstreetmap.org/search", params=params, timeout=30)
        r.raise_for_status()
        js = r.json()
        if not js or (state is not None and state not in js[0]["display_name"]):
            continue
        hit = (round(float(js[0]["lat"]), 5), round(float(js[0]["lon"]), 5))
        if i == 0 and js[0].get("addresstype") not in TOWN_TYPES:
            return hit + ("street", js[0]["display_name"])
        if i == 0:
            town_hit = hit + ("town", js[0]["display_name"])
            continue
        return hit + ("town", js[0]["display_name"])
    if len(queries) == 1:
        c = census_geocode(addr, session)
        if c:
            return c
    if town_hit:
        return town_hit
    return None, None, "none", ""


def build(as_of, max_sites, do_geocode):
    d, t = download()
    t["Date"] = t["Date"].astype(str)
    us = d[d["Country"] == "United States"]
    keep, dropped = [], []
    for _, s in us.iterrows():
        tl = t[t["Data center"] == s["Name"]].sort_values("Date")
        if tl.empty:
            dropped.append(dict(epoch_name=s["Name"], reason="no timeline rows")); continue
        op = tl[tl["Power (MW)"] > 0]
        op_date = op["Date"].iloc[0] if len(op) else ""
        first = tl.iloc[0]
        if not op_date or op_date > as_of:
            dropped.append(dict(epoch_name=s["Name"], reason=f"not operational by {as_of}"
                                f" (first power {op_date or 'none'})")); continue
        if s["Name"] in EXCLUDE:
            dropped.append(dict(epoch_name=s["Name"], reason=EXCLUDE[s["Name"]],
                                epoch_first_row=f"{first['Date']}: {first['Construction status']}")); continue
        cur = tl[tl["Date"] <= as_of].iloc[-1]
        last = tl.iloc[-1]
        complete = last["Date"] <= as_of or float(last["Power (MW)"]) <= float(cur["Power (MW)"])
        water = tl["Water use (MGD)"].dropna()
        keep.append(dict(
            site_id=slug(s["Name"]), name=s["Name"], status="built", lat=None, lon=None,
            mw=float(cur["IT power (MW)"]),
            capex_busd=round(float(cur["Total capital cost (2025 USD billions)"]), 3),
            construction_start=first["Date"], operation_date=op_date,
            a_max_acres="", build_months="", withdrawal_ml_per_yr="", source_id="",
            owner=str(s["Owner"]).replace(" #confident", "").replace(" #likely", " (likely)"),
            address=" ".join(str(s["Address"]).split()) if pd.notna(s["Address"]) else "",
            values_as_of=cur["Date"],
            mw_facility=float(cur["Power (MW)"]),
            capex_construction_busd=round(float(cur["Construction cost (2025 USD billions)"]), 3),
            buildings_operational=int(cur["Buildings operational"]),
            buildout_complete=bool(complete),
            planned_final_mw_facility=float(last["Power (MW)"]),
            planned_final_date=last["Date"],
            epoch_water_use_mgd=float(water.iloc[-1]) if len(water) else "",
            epoch_water_use_date=tl.loc[water.index[-1], "Date"] if len(water) else "",
            construction_start_evidence=" ".join(str(first["Construction status"]).split())[:300],
            operation_evidence=" ".join(str(op["Construction status"].iloc[0]).split())[:300],
            campus_note=ADJACENT_EXISTING.get(s["Name"], ""),
            calc_sheet=s["Calculations sheet"] if pd.notna(s["Calculations sheet"]) else "",
            first_cited_source=first_link(s["Selected Sources"]),
        ))
    df = pd.DataFrame(keep)
    df = df.sort_values(["buildout_complete", "operation_date"], ascending=[False, True])
    over = df.iloc[max_sites:]
    for _, r in over.iterrows():
        dropped.append(dict(epoch_name=r["name"], reason=f"beyond --max-sites {max_sites} "
                            f"(buildout_complete={r['buildout_complete']}, operation {r['operation_date']})"))
    df = df.iloc[:max_sites].reset_index(drop=True)

    df["geocode_precision"], df["geocode_display_name"] = "none", ""
    sess = requests.Session(); sess.headers["User-Agent"] = UA
    for i, r in df.iterrows():
        txt = " ".join(t.loc[t["Data center"] == r["name"], "Construction status"].astype(str))
        txt += " " + str(d.loc[d["Name"] == r["name"], "Selected Sources"].iloc[0])
        pts = [(float(a), float(b)) for a, b in re.findall(r"@(-?\d+\.\d+),(-?\d+\.\d+)", txt)]
        if pts:
            df.loc[i, ["lat", "lon", "geocode_precision", "geocode_display_name"]] = [
                round(sum(p[0] for p in pts) / len(pts), 5), round(sum(p[1] for p in pts) / len(pts), 5),
                "epoch_link", f"mean of {len(pts)} Google Earth link(s) in Epoch's text"]
        elif do_geocode:
            lat, lon, prec, disp = geocode(r["address"], sess)
            df.loc[i, ["lat", "lon", "geocode_precision", "geocode_display_name"]] = [lat, lon, prec, disp]

    flags = []
    for _, r in df.iterrows():
        f = []
        if not r["buildout_complete"]:
            f.append("expanding_after_as_of")
        if r["campus_note"]:
            f.append("outline_new_parcel_only")
        if r["geocode_precision"] not in ("street", "street_census", "epoch_link"):
            f.append("coords_approx_" + r["geocode_precision"])
        if r["construction_start"] < "2016-01-01":
            f.append("baseline_before_s1_coverage")
        lag = (pd.Timestamp(r["operation_date"]) - pd.Timestamp(r["construction_start"])).days / 30.44
        if lag > 48:
            f.append(f"long_lag_{lag:.0f}_months")
        flags.append(";".join(f))
    df["flags"] = flags
    df["verification"] = "epoch_derived_unreviewed"
    df["source"] = df.apply(lambda r: " ; ".join(x for x in [
        DATASET_URL, TIMELINE_URL, r["calc_sheet"], r["first_cited_source"]] if x), axis=1)
    df["geocode_source"] = df["geocode_precision"].map(lambda p: {
        "none": "", "epoch_link": TIMELINE_URL, "street_census": CENSUS_URL}.get(p, "https://nominatim.openstreetmap.org (OpenStreetMap, ODbL)"))
    df = df.drop(columns=["calc_sheet", "first_cited_source"])
    df.to_csv(OUT, index=False)
    pd.DataFrame(dropped).to_csv(EXCLUDED_OUT, index=False)
    return df, pd.DataFrame(dropped)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as-of", default="2026-11-15")
    ap.add_argument("--max-sites", type=int, default=30)
    ap.add_argument("--no-geocode", action="store_true")
    a = ap.parse_args()
    df, dropped = build(a.as_of, a.max_sites, not a.no_geocode)
    pd.set_option("display.width", 200)
    print(df[["site_id", "mw", "capex_busd", "construction_start", "operation_date",
              "buildout_complete", "geocode_precision", "flags"]].to_string())
    print(f"\nkept {len(df)} sites -> {OUT.relative_to(ROOT)}; "
          f"dropped {len(dropped)} -> {EXCLUDED_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
