# Decisions

Log of judgment calls. Newest at the bottom. Dates are ISO `YYYY-MM-DD`.

## 2026-11-15 · Water chain step 1 queries EPA's ArcGIS service instead of a downloaded file

**What.** `match_utilities()` in `pipeline/water_chain.py` now sends one point query per site to EPA's
Community Water System Service Area Boundaries feature service, instead of a spatial join against a
file in `data/raw/`.

**Why.** The official EPA download zip was blocked from the cloud machine; the ArcGIS service is
public, needs no credentials, and holds the same national layer. A point query also avoids keeping a
large polygon file on disk and drops the geopandas dependency from this step.

**Service.**
- Query URL: `https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/Water_System_Boundaries/FeatureServer/0/query`
- ArcGIS Online item: `80c6912ef14f46e480f5afd807767b4b`, "Community Water Service Area Boundaries",
  owner `ahall05_EPA`, access information "US EPA", MIT license. Landing page:
  https://www.arcgis.com/home/item.html?id=80c6912ef14f46e480f5afd807767b4b
- Layer 0, named "Final", polygon, 44,615 features (count checked 2026-11-15), ArcGIS server version 12, maxRecordCount 2000.
- Method documentation: https://github.com/USEPA/ORD_SAB_Model

**Dataset version.** The item description's latest version note is **Version 3.0, updated 2026-03-17**
(adds transient and non-transient non-community systems to the companion service). The layer's
`editingInfo.dataLastEditDate` is **2026-05-29 14:48 UTC**, so data were edited after the 3.0 note
without a new version entry. The universe of systems is SDWIS 2025 Q2 (per the item description).
Re-check both values before a final run, because the service is live and can change under us.

**Fields used.** `PWSID` (string, written to `pwsid`) and `PWS_Name` (string, printed for review
only). Other fields in the layer, for reference: `OBJECTID, Original_Data_Provider,
Data_Provider_Type, Data_Source, Primacy_Agency, Pop_Cat_5, Population_Served_Count,
Service_Connections_Count, Model_Method, Service_Area_Type, Symbology_Field, Modification_Method,
Feature_Type, Method_Details, Verification_Status, Detailed_Facility_Report,
Original_Data_Created_Date, Confirmed, Area_SqKM, Shape__Area, Shape__Length`.
Note: about 44% of boundaries are modeled, not utility-supplied (`Model_Method` says which); a
match on a modeled polygon is weaker evidence. Not used yet; worth surfacing later.

**Query parameters.** `geometry=<lon>,<lat>`, `geometryType=esriGeometryPoint`, `inSR=4326`,
`spatialRel=esriSpatialRelIntersects`, `outFields=PWSID,PWS_Name`, `returnGeometry=false`, `f=json`.
Retries up to 4 times with backoff on HTTP errors and on ArcGIS `{"error": ...}` replies (which come
back with HTTP 200), then raises.

**Matching rules (unchanged from the file-based version).**
- No polygon contains the site: one row with empty `pwsid`, `match_status = no_utility_check_self_supply`.
- Several polygons contain the site: one row per PWSID, all `matched`, reviewed by hand.
- New: if the service returns several features with the same PWSID, that PWSID is written once.
  Duplicate PWSIDs exist in this layer (the v2.01 note mentions them) and add no information.
- Output columns unchanged: every registry column, plus `pwsid` and `match_status`, in
  `data/site_utility_matches.csv` (new optional `--out` flag for test runs).

**Open item.** `CLAUDE.md` calls the no-match status `self_supplied_check`; the code has always
written `no_utility_check_self_supply`. Kept the code's string because the task said to handle
no-match the same way as before. Pick one name before the projection reads this column.

**Test results (2026-11-15).**
- Demo registry: DEMO-A OK1020418 (TULSA), DEMO-B and DEMO-F AZ0407095 (MESA CITY OF),
  DEMO-D AZ0407093 (GLENDALE CITY OF); DEMO-C, E, G, H no match.
- Real addresses: Phoenix City Hall (33.4484, -112.0740) -> AZ0407025 PHOENIX CITY OF;
  Tulsa City Hall (36.1540, -95.9928) -> OK1020418 TULSA; Omaha City Hall (41.2587, -95.9378) ->
  NE3105507 METROPOLITAN UTILITIES DISTRICT.
- Multiple-match path: (39.013, -77.37375) -> VA6107350 LOUDOUN WATER - CENTRAL SYSTEM and
  VA6059501 FAIRFAX COUNTY WATER AUTHORITY, two rows.

## 2026-11-15 — Footprint engine port (pipeline/footprint.py)

- **Data source: Planetary Computer `sentinel-1-rtc` instead of Earth Engine `COPERNICUS/S1_GRD`.**
  Earth Engine is not available to this project (CLAUDE.md). RTC values are linear gamma0; every
  acquisition is converted with `10*log10` to dB before the baseline median, the monthly medians,
  the difference and the threshold. RTC is terrain-flattened gamma0 while GEE's GRD is sigma0 with
  no terrain flattening, so absolute dB levels differ slightly; F1 only uses differences against a
  same-orbit baseline, so the logic is unchanged.
  Link: https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc

- **Same-day frames are mosaicked into one acquisition.** A campus on a slice boundary appears in
  two adjacent frames of the same pass; counting both would double-weight that date in the medians.
  Orbit histograms also count acquisition days, not frames.

- **Orbit tie-break.** GEE takes the first maximum of `aggregate_histogram` (string-sorted keys).
  The port picks: most acquisitions over the whole window, then most in the baseline year, then the
  lowest relative-orbit number. Deterministic and documented.

- **First test site: OpenAI Stargate Abilene (Epoch AI), construction start 2024-05-31.**
  Epoch's timeline row for 2024-05-31 reads "Land clearing begins for northern two buildings
  (Building 1-2)"; it is a greenfield site, is listed as operational (824 MW current power), and
  has a clear 2026 footprint. Source: https://epoch.ai/data/data-centers (data_centers.zip,
  `data_center_timelines.csv`, retrieved 2026-11-15). Epoch gives an address, not an outline.

- **Campus outline for Stargate Abilene is hand-drawn** around the cleared campus visible in a
  Sentinel-2 L2A true-colour scene of 2026-10-08 (0% cloud), checked against 2023-11-23 (bare
  ranch land). File: `data/footprint/STARGATE-ABILENE_campus.geojson` (~1,422 acres inside the
  outline). OpenStreetMap (Overpass) was not reachable from the cloud session. Approximate; replace
  with a parcel or permit outline if one is found.

- **Orbit rule applied: descending -> ascending fallback.** Over Abilene there are 0 descending
  Sentinel-1 acquisitions in the baseline year (2023-05-31 to 2024-05-31), so the script fell back to
  ascending. Relative orbits 5 and 107 tie (28 baseline days each); orbit 5 has more acquisitions over
  the full window and was used (130 acquisition days).

- **Threshold rule is evaluated on the campus outline, not on the 1 km AOI ring.** The GEE script
  sums area over `campus.buffer(1000)`. Around Abilene that ring holds tilled fields and other new
  parcels, so AOI pre-construction acres stay above 5% even at 5 dB (13.5%), while the campus is
  clean at 4.5 dB (2.5%). The rule's "final footprint" is the site's footprint, so the campus is the
  right denominator. Both curves are written: `acres_aoi` (GEE-identical) and `acres_campus`.
  The logistic fit (a_max_acres, build_months) also uses `acres_campus`.
  Threshold run: 3.0 dB 30.6% -> 3.5 dB 13.5% -> 4.0 dB 5.7% -> **4.5 dB 2.5% (kept)**. Not flagged.

- **Logistic fit without scipy.** Grid search over (k, t0) with A_max solved in closed form by least
  squares; build_months = ln(81)/k (10% -> 90%). Result for Abilene: A_max 1,163 acres,
  t0 = +15.4 months after construction start, build_months 22.1.

## 2026-11-15 · Precedent sites from Epoch AI (Phase 1a)

Details and per-site table: `data/precedent_sites_notes.md`. Script: `pipeline/precedent_sites.py`.
- **construction_start = first Epoch timeline row; operation_date = first row with Power > 0.**
  Epoch's timelines are satellite-image logs whose first row is land clearing; this is the closest
  thing to a construction start the dataset has. Row text kept in `*_evidence` columns.
- **mw = Epoch IT power as of 2026-11-15**, facility power kept in `mw_facility`. WUE is per IT kWh.
- **Greenfield only.** Conversions of existing buildings convert little land and would bias acres/MW
  down. Two sites at one address (Lake Mariner) both dropped: one footprint cannot be split.
- **30 sites, buildout-complete first.** Sites still expanding after 2026-11-15 mix finished and
  unfinished buildings in one footprint. Storey County (expanding) fills slot 30.
- **Coordinates**: Epoch's own Google Earth links first, then Nominatim street hit, then Census
  geocoder, then town centroid; a geocode must name the address's state or it is rejected.
- **withdrawal_ml_per_yr left blank** although Epoch has "Water use (MGD)" for 10 of the 30 sites: Epoch
  doesn't say whether it is withdrawal or consumption. Kept raw in `epoch_water_use_mgd`.
- **Open:** Epoch capex is a constant 37.88 $M per IT MW (modeled), so k has no spread. Asked the
  person how to source k.
