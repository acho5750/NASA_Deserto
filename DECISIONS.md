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
