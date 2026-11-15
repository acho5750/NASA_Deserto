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
- No polygon contains the site: one row with empty `pwsid`, `match_status = self_supplied_check`.
- Several polygons contain the site: one row per PWSID, all `matched`, reviewed by hand.
- New: if the service returns several features with the same PWSID, that PWSID is written once.
  Duplicate PWSIDs exist in this layer (the v2.01 note mentions them) and add no information.
- Output columns unchanged: every registry column, plus `pwsid` and `match_status`, in
  `data/site_utility_matches.csv` (new optional `--out` flag for test runs).

**Resolved 2026-11-15.** The no-match label was `no_utility_check_self_supply` in the code and
`self_supplied_check` in `CLAUDE.md`. Bubba chose `self_supplied_check` everywhere; the code now
writes that. No other file (projection, map, docs) read the old label.

**Test results (2026-11-15).**
- Demo registry: DEMO-A OK1020418 (TULSA), DEMO-B and DEMO-F AZ0407095 (MESA CITY OF),
  DEMO-D AZ0407093 (GLENDALE CITY OF); DEMO-C, E, G, H no match (`self_supplied_check`).
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

## 2026-11-15 · Announced-site list: inclusion rule, dates, coordinates

**What.** `data/announced_sites.csv` (24 rows, all `unverified`). The rules used to build it:
announced projects that are not fully operating, with at least a county-level location. Expansions
of operating campuses are excluded. Only stated values are recorded, and third-party estimates go in
notes. Partial dates are set to the first day of the period for starts and the last day for
operation, with precision kept in `*_basis`. Coordinates are OSM Nominatim town or county centroids.
**Why.** Stated values keep the "never invent data" rule. Expansions would mix land converted before
the build with new conversion. Using period start and end keeps every date ISO and follows the
"as of December 31" convention. Rows with neither MW nor capex are marked `projection_eligible=no`,
per the CLAUDE.md rule. Details and open questions are in `data/announced_sites_notes.md`.

## 2026-11-15 · Announced list revised under the review rules

**What.** Applied the four rules for the announced list in `data/announced_sites.csv`: MW in the
2030 window, estimated construction starts with a `start_estimated` flag, MW and capex only from
company, government or utility sources (with `low_confidence` flags), and a sort by 2030 MW.
Judgment calls:
(a) A stated MW with no completion year counts in full by 2030.
(b) Where a site has both, El Paso capex uses the venture's total development cost ($14B), not
    Meta's own share (more than $10B), because the built-site k is total capex per MW.
(c) Hyperion capex is left blank: the share of the $50B tied to the 2 GW expected by 2030 isn't stated.
(d) For rows without MW, the sort uses capex / $37.88M per MW (Epoch median). That figure is for
    sorting only and is never written to `mw`.
(e) Wharton TX dates come from the planned dates in the TDLR registrations, so they are not estimated.
**Why.** These follow Bubba's rules 1–4. The figures for (a)–(e) are in `data/announced_sites_notes.md`.
(f) 2026-11-15 update: rule 2 uses the built-site median gap from announcement to start, -0.6
    months (8 sites, `data/precedent_k_summary.csv` in PR #6), applied as -18 days. The sort no
    longer ranks capex-only rows by a derived MW. Stated-MW rows come first, then capex-only rows
    by capex, because F3 depends on k and on capex scope. `capex_includes_compute` is new: only El
    Paso and Wharton are stated as facility-only, the three developer campuses are inferred
    facility-only, and the rest are unknown.
(g) 2026-11-15: rows tagged `no (inferred)` (facility-only, inferred) are treated as facility-only
    for the F3 scenario rule. All three have a stated MW, so this doesn't change any number yet.

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

## 2026-11-15 · k (capex per MW) and announcement gap from built sites

Rule from the person (2026-11-15): k = announced capex / Epoch MW for built sites; Epoch's modeled
capex is not used; if fewer than 8 sites qualify, Epoch's 37.88 $M/MW is the median and the
announced sites give low/high. Script: `pipeline/precedent_k.py`; inputs: `data/precedent_capex.csv`.
- **Case A applied: 8 sites qualify.** Meta Kuna, Jeffersonville, Rosemount, Aiken, Temple; Google
  Mesa (phase 1, $600M vs the 90 IT MW of Building 1); Microsoft Osmium ($1.5-2B city figure, midpoint
  used); Stargate Abilene ($15B committed capital, Crusoe release). k low/median/high =
  p10/p50/p90 = **4.49 / 5.73 / 11.91 $M per IT MW**. Borderline: Osmium (range, page 403 from
  the cloud machine) and Abilene (financing, not a cost report) are the 7th and 8th sites; without
  them the case would be B.
- **Qualifying = same buildings.** Campus-wide, multi-site or cumulative figures (22 sites) are
  listed with the reason in `precedent_capex.csv` and not used. The Dalles' $600M per project is
  only an "illustrative" example in the SIP agreement, so it is excluded.
- **MW basis = Epoch IT MW** for the buildings the capex covers (all Epoch buildings, except Mesa).
- **Gap: median -0.6 months over 8 sites** (official announcement of the same project to Epoch's
  first land clearing). Range -3.6 to +28.9 (Osmium). Sent to the announced-projects thread.
- **Basis warning.** Announced capex excludes chips (Meta's $800M for ~150-180 MW), so k is about a
  sixth of Epoch's 37.88 (which includes compute). F3 on an announced figure that includes compute
  would overstate MW about 6x. Raised with the person.

## 2026-11-15 · k revised to 6 facility-only sites (owner decision)
The owner dropped Osmium (range) and Abilene (financing) and removed the fewer-than-8 fallback,
because Epoch's 37.88 $M/MW includes compute. k = **4.49 / 4.88 / 6.43 $M per IT MW**
(p10/p50/p90, n=6, low confidence), labeled in METHODS.md. `k_use` column added to
`data/precedent_capex.csv`. Sent to the announced-projects thread. Supersedes the "Case A"
numbers in the entry above.
## 2026-11-15 · Phase 5 NISAR coverage check: site choice, coordinates and "usable" rule

**Sites.** Vantage Frontier (Shackelford Co., TX), Project Jupiter (Dona Ana Co., NM) and Stargate
Lordstown (OH), all from `data/announced_sites.csv` (PR 5). Chosen because Epoch's timeline shows
active construction after 2026-06-01 at each (2026-09-04, 2026-06-22, 2026-07-30 entries) and a
campus-level coordinate could be sourced. Meta Hyperion was passed over because no source with a
campus coordinate was found (only the Holly Ridge hamlet centroid). Built sites in
`data/precedent_sites.csv` (PR 6) were not used: all but one are complete by Epoch's timeline.

**Coordinates.** `announced_sites.csv` has only town or county centroids for these sites, which can
fall kilometres from the campus. For this check only, Frontier and Jupiter use Baxtel's campus
points and Lordstown uses the US Census geocode of Epoch's street address (sources per row in
`data/nisar_coverage_sites.csv`). The registry itself is not changed.

**Usable rule.** HH and HV on frequency A, >= 90% valid pixels in a 51 x 51 window at the site, no
input-data anomaly bit, not diagnostic mode. The `inputDataExceptionMask` bits 256/512 mean "HH/HV
fully focused" in V1 products and are not counted as anomalies. Where one acquisition has two
products, the usable one at the track's usual bandwidth is counted and the other is marked
`duplicate_of`.

## 2026-11-15 · Phase 2: footprint (F1) on the built precedent sites

Scripts: `pipeline/campus_outline.py` (outlines), `pipeline/footprint_batch.py` (runs F1 on every site),
`pipeline/footprint.py` (F1). Outputs in `data/footprint/` and `map/img/`.

**Rules from the person (2026-11-15).** Reported acres = converted area inside the campus outline
plus a 200 m buffer (`final_acres_site`, and `a_max_acres` from the logistic fitted to that curve).
The ring from 200 m out to 1 km is reported separately as `spillover_acres`. The 5% noise rule uses
the same outline + 200 m area. Outlines come from OpenStreetMap; hand-drawn only where OSM lacks
the site, and flagged. Each result is checked against publicly reported campus acreage.

**Outlines (`data/footprint/campus_outlines.csv`, one row per site with the OSM ids and why).**
- Overpass is not reachable from the cloud machine (connection closed by the tunnel), so outlines come
  from the main OSM API (`/api/0.6/map`, `/way|relation/<id>/full`) and Nominatim search. Same data.
- Each pick was checked by eye on a cloud-free Sentinel-2 L2A scene (Planetary Computer) from
  2025-2026 with the candidate polygons drawn on top.
- 21 sites: a named OSM data center parcel. 5 sites: an unnamed OSM parcel that contains the owner's
  tagged data center buildings (`osm_unnamed_parcel`). Council Bluffs East: OSM has only the four
  Google buildings of the east expansion, so the outline is their convex hull (`osm_buildings_hull`).
- Stargate Abilene: OSM's "Lancium Clean Campus" misses the cleared southern part of the campus, so it
  is unioned with the PR 3 hand-drawn outline (`osm_incomplete_extended_by_hand`).
- Papillion, Hillsboro 2 and QTS Richmond 1: the parcel also holds older buildings that Epoch does
  not track (`outline_includes_older_buildings`). Richmond 1 and 2 are neighbours; their 200 m
  buffers overlap, so some acres are counted at both.
- 8 town-level coordinates and Kansas City East (no coordinates) were located through OSM by name.
  The OSM parcels sit 2.5 to 12 km from the registry points. `precedent_sites.csv` is not changed.
- **Meta Jeffersonville is not run** (`outline_missing`): no OSM object at River Ridge Commerce
  Center, and public sources give only "619 acres at River Ridge", not a location to draw from.

**Time window per site.** Start = construction start − 24 months (as GEE). End = the date Epoch's
last building came online (`planned_final_date` when `buildout_complete`) + 6 months, at least
construction start + 18 months, capped at 2026-11-01 (Sentinel-1 RTC on Planetary Computer runs to
2026-11-12). Epoch's MW cover the whole campus as of 2026, so the acres must cover the whole buildout.

**Logistic fit grid.** The PR 3 grid had linear k steps of 0.025/month, so build_months could only be
29.5, 44.1, 58.8 or 87.9 months at slow builds. Now k is on a 400-step log grid (0.01-3 per month)
and t0 on a 0.25-month grid reaching 12 months past either end of the data. Fits that land on the
grid edge are flagged `logistic_fit_at_grid_edge`; fits whose 90% point falls after the last month
are flagged `curve_not_saturated`. Formula unchanged.

**Threshold rule outcome.** 25 of 29 sites end at 5 dB with pre-construction acres still above 5%
(`noise_floor_above_5pct_at_max_threshold`), as the rule says to flag. Only SAT14 (4.0 dB),
Fairwater Atlanta (4.0), Storey County (4.5) and Abilene (5.0, 4.0%) pass. Looking at the curves and
radar images, the pre-construction acres have two causes:
1. Real construction before Epoch's start date. Epoch's first timeline row is often a later
   building on a campus that was already being built (Papillion 2018-19, Goodyear 2019-20,
   Gallatin, Sarpy, Osmium). Their pre-construction acres are real change, not noise.
2. Farmland seasonality that lasts two months or more and so passes the persistence rule.
The flagged values are kept and shown with their flag; nothing was dropped.

**Sanity check (`data/footprint/sanity_check.csv`).** final_acres_site / reported campus acreage is
within 0.67-1.5 at 16 sites, above at 6, below at 4; 3 have no public figure; Jeffersonville not run.
Above: small parcels where the 200 m buffer adds more land than the parcel itself (Hillsboro 2, The
Dalles, Richmond 2) and the multi-parcel Microsoft campuses (Goodyear, SAT40). Below: campuses whose
reported acreage includes land not yet built (Storey County 1,210 ac bought, Gallatin 800-900 ac,
Midlothian 375-540 ac, Aiken 300 ac). The reported figures are mostly from trackers and news; each
row has its source link.

**Registry update (`--write-registry`).** `a_max_acres` and `build_months` in `data/precedent_sites.csv`
are filled for 22 sites. They are left blank for 7 sites whose logistic never levels off inside the data
(`curve_not_saturated` or `logistic_fit_at_grid_edge`: New Albany, Eagle Mountain, Nebius NJ,
Midlothian, Arcola, Gallatin, Storey County), because their A_max is an extrapolation (Arcola: fit
400 ac vs 133 ac measured), and for Jeffersonville (not run). `projection.py` drops blanks. Footprint
flags are appended to the `flags` column as `footprint:<flag>`; the noise-flagged values are kept.

## 2026-11-15 · Phase 3: water chain (utility, source, trend) for all 54 sites

**Deliverable.** `data/sources.csv` (one row per utility that serves a site, with its water body,
trend and source links), `data/water/site_sources.csv` (every site -> utility -> source_id, or why
not), and the `source_id` column filled in `data/precedent_sites.csv` and `data/announced_sites.csv`.
Intermediate files in `data/water/`: `site_points.csv`, `site_utility_matches.csv`,
`utility_chain.csv`, `source_assignments.csv` (hand-curated, one evidence note and link per row),
`trends.csv`, and the per-source time series under `swot/` and `disp/`.
Run: `python pipeline/water_chain.py points`, `match`, `lookup`, `sources`.

**Step 1, site point.** Built sites are matched at a point inside their Phase 2 OSM campus outline
(8 registry points are town centroids up to 12 km from the campus). Meta Jeffersonville has no
outline and uses its street-level registry point. Announced sites use the registry point, which is
a town or county centroid for 23 of 24 (Homer City is the plant itself): their matches carry
`matched_approx_location` / `location_approx` and name the town's utility, not necessarily the
campus's.

**Step 1, no match.** 24 sites fall outside every EPA service area polygon (14 of 30 built, 10 of 24
announced). 30 sites are matched (16 at the campus point, 14 announced at an approximate point).
Per CLAUDE.md they are `self_supplied_check`, stay in the footprint model and are excluded from
water shares (`water_share = exclude`). For a later manual check, `candidates_within_2km` lists the
service areas within 2 km (e.g. Council Bluffs Water Works, Des Moines Water Works, Metropolitan
Utilities District, City of The Dalles). These are not treated as matches.

**Step 1, overlapping service areas.** Google Midlothian sits in both Mountain Peak SUD and City of
Midlothian: City of Midlothian is used (it is one of Mountain Peak's own sellers and the only one
with a surface intake). Google Laramie (city centroid) sits in Cheyenne BOPU and Winchester Hills
(1,078 people): Cheyenne BOPU is used. The other PWSID is kept in `other_service_areas`.

**Step 2, purchased water.** SDWA facility rows of type CC carry `SELLER_PWSID`, so purchased
systems are followed to their sellers in SDWA itself (up to 3 hops, `utility_chain.csv`). This is
the same information a CCR gives; where a CCR was found it is linked too. Where a buyer has several
sellers, the water body named in `source_assignments.csv` says which one was chosen and why.

**Step 2, one water body per utility.** F5/F6 take one source per site. Rule used: the largest
share the utility publishes (Mesa: CAP 53%; SAWS: Edwards 47%; El Paso: Hueco Bolson 36-61%; PWC
West: Occoquan 9 MGD vs Lake Manassas 5 MGD); where no split is published, SDWA's
`PRIMARY_SOURCE_CODE` decides (SW vs GW), then the named intake. Each row has a `confidence`
(high / medium / low) and a plain-text basis. Conflicts noted in the basis: Eagle Mountain (SDWA
says purchased surface water, city report lists 5 wells plus CUWCD), Amarillo (SDWA SW, but 121
Ogallala wells), El Paso (SDWA code SW, but wells are the larger supply).

**Step 2, rows per utility.** `sources.csv` has one row per utility (`source_id = SRC-<PWSID>`)
with its own `population_served` (SDWA 2026Q3), because F5 divides by the population that utility
serves. Utilities that share a water body (Goodyear + Mesa on the Colorado/CAP, Port Washington +
Racine on Lake Michigan, Hawley + Fort Griffin on Hubbard Creek) share `water_body_id` and trend.
SAWS Texas Research Park reports population 0 in SDWA; it is left blank and flagged.

**Step 3, SWOT.** Prior Lake Database IDs (needed for Hydrocron `PriorLake`) are only on PO.DAAC's
protected archive (`archive.swot.podaac.earthdata.nasa.gov`), which redirects to an Earthdata
OAuth login that the environment's token does not cover (HTTP 401, checked 2026-11-15). Hydrocron
itself works. So reservoirs and rivers are read with Hydrocron `Reach`, using reach IDs from the
public SWOT River Database (SWORD v17c, Zenodo 23870877). Each reach's prior location returned by
Hydrocron was checked against the water body (James at 37.556,-77.541; Delaware at Morrisville;
Lake Mead Boulder Basin; Old Hickory Lake near Gallatin; Lake Meredith). Reservoirs with no SWORD
reach (Hoover, Occoquan, Hubbard Creek, CUWCD, Joe Pool, Leon/Belton, Cheyenne, Big Water Lake,
Miller Creek, Lake Michigan) are marked `swot_lake_id_unavailable`, not filled. SWORD reaches flagged
as lakes (Lake Mead, Old Hickory Lake) have `reach_q` 3 (bad) on every pass because SWOT measures
lakes in the lake product, and Lake Mead's values (median 359 m) are far from its real level, so they
are `insufficient_swot`. Lake Meredith uses its river-type reach 74242300691 (`reach_q` 1-2, median
881.8 m, close to the lake's level). Delaware at Morrisville has only 6 good passes (most are
`reach_q` 2, head of tide), so its trend is weak.
Window 2023-08-01 to 2026-11-01; good passes are `reach_q` 0-1; points more than 4 scaled MAD from
the median are dropped; trend = least-squares slope in m/yr. Fewer than 4 passes: widen once to
2023-04-01, then `insufficient_swot`. Lake Mead is used for the CAP supply because CAP's intake pool
(Lake Havasu) is held at a fixed level and Lake Mead is the storage that sets CAP shortages.

**Step 3, DISP-S1.** Inspected one real granule first
(`OPERA_L3_DISP-S1_IW_F28482_VV_20250418T003512Z_20251108T003508Z_v1.0_20260629T200309Z.nc`, 445 MB):
30 m UTM grid, 256x256 gzip chunks, `/displacement` in metres along line of sight (positive =
towards the satellite) relative to `/identification/reference_datetime` and the frame's reference
point, `/recommended_mask` 1 = good. The reader (`aquifer_trend`) reads only a 6 km x 6 km window by
HTTP range requests (no full downloads), takes the median of good pixels per date (dates with under
30% good pixels skipped), keeps the latest version of each reference/secondary pair, chains
ministacks by adding the displacement at each new reference date, and fits mm/yr. It uses the frame
with the most dates at that point. Window centre = a point inside the utility's EPA service area,
because SDWA's public files do not give well locations. Values are line-of-sight, relative to the
frame reference point, and not corrected for ionosphere or tides; they are a relative subsidence
indicator, not an aquifer water-level measurement. Older granules store displacement as float32 and
inline small chunks in the reference file; the reader handles both. If a date that later serves as a
reference is masked, the chain breaks; each piece then gets its own offset and the fit shares one
slope (Boling 6 pieces, Montgomery City 5, the rest 1). Some series show steps at ministack changes
(Lebanon: +60 mm between 2018 and 2019), so a value is a screening number to read with its series
file, not a measured subsidence rate.

**Result (2026-11-15).** 29 utility rows, 26 water bodies. Trend `ok` for 16 rows: 6 SWOT (James
-0.057, Potomac -0.063, Missouri +0.048, Delaware -0.448, Lake Meredith -0.122 m/yr) and 10 DISP-S1
(Edwards +2.95, SAWS Texas Research Park +8.45, Ohio River Outwash -10.44, Lebanon +19.75, Hueco
Bolson -1.69, Mesilla Bolson -2.36, Montgomery City -14.59, West Memphis -14.07, Boling -1.13 mm/yr
LOS). Missing: 11 rows `swot_lake_id_unavailable`, 3 `insufficient_swot` (Colorado/CAP x2, Old
Hickory).

**Aqueduct stress** is left blank (`aqueduct_pending`) for Phase 4.

## 2026-11-15 · Phase 4: calibration values replace the placeholders in projection.py

No formula changed. Every value below is in a committed file with its source link.

**Utilization u (F2, F4).** Epoch: "the average power consumption of these data centers is
typically 60-80% of capacity, due to idle time and maintenance" (https://epoch.ai/data/ai-data-centers,
read 2026-11-15). The single 0.7 placeholder becomes low 0.6 / median 0.7 / high 0.8, following the
"every scenario value comes in low / median / high" convention; more draw means more water, so the
high scenario uses 0.8. WUE calibration uses the median 0.7, because the real draw in the year the
withdrawal was measured is not known.

**WUE (F2), `data/calibration/wue_google_2025.csv`.** Google's 2026 Environmental Report (FY2025,
p. 96 "Water use by data center location") gives 2025 withdrawals by location. Nine locations match
built sites; five are used, four are not:
- Used: Lancaster OH (307.1 Mgal), New Albany OH (1,008.1), Bristow VA (359.6), Mesa AZ (19.4),
  Storey County NV (66.7). Each is the only Google campus at that location and the Epoch site is
  that campus.
- Not used: Midlothian (Epoch shows 0 MW in 2025 but Google reports water and a PUE since 2023, so
  Epoch tracks a later building), Papillion and The Dalles (Epoch does not track the older buildings
  on the campus), Council Bluffs (Epoch site is the east expansion; Google's figure covers all
  campuses). Using them would divide a whole campus's water by part of its MW.
- MW is Epoch's IT power averaged over calendar 2025 (timeline rows held as steps until the next
  row), because the withdrawal is a 2025 total and every used site grew during 2025. Results, in
  L per IT kWh at u = 0.7: Lancaster 2.38, New Albany 2.91, Bristow 1.52, Mesa 0.26 (first building
  online July 2025), Storey County 0.34. Low / median / high (25th / 50th / 75th percentile) =
  0.34 / 1.52 / 2.38.
- `withdrawal_ml_per_yr` in the registry stays blank: no site ran at its full 2026 MW through all of
  2025, so the 2025 total is not its full-build withdrawal. F4 uses MW x u x 8760 x WUE for all sites.
- `projection.py` reads the table through `--wue-calibration` (default the file above) and adds
  those values to any registry withdrawals. `DEFAULT_WUE_L_PER_KWH` stays `None`.

**Per-capita use (F5), `data/calibration/per_capita_by_state.csv`.** USGS 2015 county data
(Dieter et al. 2018, https://doi.org/10.5066/F7TB15V5, the latest national compilation): total
public-supply withdrawals (`PS-Wtotl`, Mgal/d) divided by population served by public supply
(`PS-TOPop`), summed by state. This counts everything a utility withdraws (homes, businesses, losses),
which is the right denominator for "share of the utility's supply". Each row of `data/sources.csv`
now has `state` and `per_capita_l_per_day`, and F5 uses that. The single 400 L placeholder is
replaced by the national value from the same file (521.3 L/person/day), used only for a source with
no state value (the demo CSV).

**Aqueduct stress (F7), `aqueduct_stress` in `data/sources.csv`.** WRI Aqueduct 4.0 baseline annual
`bws_score` (0-5), from the downloaded geodatabase (`Aqueduct40_waterrisk_download_Y2023M07D05`),
taken at the source's point: the SWORD reach location for SWOT sources, otherwise a point inside the
utility's service area. `aqueduct_label`, `aqueduct_pfaf_id` and `aqueduct_string_id` are kept for
tracing. Note: the Colorado/CAP rows take Lake Mead's own catchment, which Aqueduct scores Low (0.67),
while the Mesa and Goodyear service areas score higher; the point rule is applied as written.

**Run on real data (precedent + announced, 45 sites with coordinates, a start date and MW or capex).**
WUE n = 5; acres/MW 0.80 / 1.32 / 1.77; tau 47.9 months. The largest 2030 median shares are small
rural utilities matched to large announced campuses at county-centroid points (Fort Griffin SUD 25x
its supply, Camino Real 8.9x, Hawley WSC 6.0x). These rows are flagged `location_approx` and need real
campus locations before the map shows them as shares.

## 2026-11-15 Announced campus locations (coordinates only; same 24 sites)

**Why.** 23 of the 24 announced rows sat at a town or county centroid (`location_basis` said "not the
campus"), so the utility match put several large campuses inside tiny rural utilities that are not
near them (Fort Griffin SUD 25x its supply in 2030, median).

**Sources and precision.** Every row now has `location_precision` and `location_source` in
`data/announced_sites.csv`; the full list with both links, the old point and the distance moved is
`data/locations/announced_locations.csv`. Precision levels, best first:
- `osm_outline` (11): a point inside an OpenStreetMap polygon for the campus itself (named for the
  project or tagged with the operator). Outlines saved in `data/footprint/announced/` with
  `pipeline/campus_outline.py build --out-dir data/footprint/announced`. Hyperion, Saline (The Barn),
  Lebanon (Project Domino), El Paso, Port Washington (Lighthouse), Dona Ana (Project Jupiter), Laramie
  (Project Jade, now Google's Project Tembo on the same Switchgrass site), Montgomery MO (Project
  Green), Fairwater WI phase 2, Fermi Matador, Southaven (OSM "Microhard", the former Southaven
  training facility = the Gun Range site; the Spam site address was not found).
- `osm_anchor` (5): a point inside an OSM object the campus is built on or around, not the campus
  outline: Keystone Trade Center (Falls Twp), AWS PHL next to Susquehanna (Salem Twp), Birchwood Power
  Facility (King George), the "Stargate Project" building (Lordstown; Epoch's address geocodes 0.6 km
  away), Homer City Generating Station (unchanged).
- `address` (1): Milam, US Census geocoder on 1899 County Road 133, Burlington (Baxtel listing).
- `road` (5, about 1-2 km): Shackelford (TX-351 at FM 604, listings), Richmond County NC (Airport Road
  next to the Smith Energy Complex), Jasper IN (Schahfer plant, campus is half a mile away on NIPSCO
  land), West Memphis (Bollinger Road, south side), Wharton (FM 1301 at FM 442; TDLR's Eaglewood Rd is
  not mapped). These are matched but keep the `location_approx` flag.
- `missing` (2): Armstrong County (Epoch's 10001 Lima Rd, Claude can't be geocoded and Lima Road has two
  segments 20 km apart; the county's tax abatement exhibit is a scanned plan with no coordinates) and
  Haskell County (one row covers two campuses, Journey and Thelma, 15-20 km apart). They keep the old
  county centroid for map display only, are not matched to any utility (`match_status =
  location_missing`) and are excluded from water shares.

**Code.** `water_chain.py points` reads `location_precision`: `road` and `missing` set
`location_approx`, `missing` also sets `location_missing`, and `match` skips those sites.
`campus_outline.py build` gained `--out-dir`.

**Rerun.** `points` -> `match` -> `lookup` -> `sources` -> projection on the combined registry (45
sites, same filter as Phase 4). Matches that changed for announced sites:
- Shackelford: Fort Griffin SUD -> Hamby WSC (TX2210006, buys from the City of Abilene).
- Milam: no match -> Bell Milam Falls WSC (TX0140007, buys Brazos River Authority lake water).
- Montgomery MO: Montgomery City PWS -> Montgomery Co PWSD 1 (MO6024406, 3 wells; DISP-S1 +1.56 mm/yr).
- Richmond NC: Hamlet Water System -> Richmond County Water System (NC0377109, Pee Dee River).
- Lordstown: no match -> Lordstown Village PWS (OH7804403, buys Meander Creek Reservoir water from
  MVSD per its 2026 CCR).
- Now unmatched (`self_supplied_check`): Lebanon (was Lebanon Utilities), Port Washington (was Port
  Washington Waterworks), Laramie (was Cheyenne BOPU), Fermi Matador (was Amarillo). Southaven stays
  unmatched. Armstrong and Haskell are `location_missing` (Haskell was City of Haskell).
The 5 new utilities have rows in `data/water/source_assignments.csv`. Assignments for the 8 utilities
no site matches any more stay in that file but `sources` now skips them (it used to fail on them).

**Result: largest 2030 median shares (water linked to sites / the utility's own supply).**
Before: Fort Griffin SUD 25.1x, Camino Real 8.9x, Hawley WSC 6.0x, Port Washington 3.9x, Montgomery
City 3.9x, Lebanon 3.0x, Boling 2.2x, Hamlet 1.3x.
After: Hamby WSC 39.8x (Shackelford, road-level point), Bell Milam Falls WSC 10.3x (Milam), Camino Real
8.9x, Hawley WSC 6.0x, Montgomery Co PWSD 1 2.8x, Boling 2.2x, Richmond County 0.63x; everything else
below 0.3x.
Fort Griffin is gone, but shares above 1x remain where a campus really does sit inside a small rural
water co-op. F5 divides by the co-op's own retail supply, although Hamby and Bell Milam Falls buy
their water wholesale from much larger systems (Abilene serves about 130,000 people). Whether the
share should use the wholesale seller's supply is a formula question for the person; nothing changed.

## 2026-11-15 F5: wholesale-system share shown next to the local share (person's decision)

The person chose "Show both numbers" for utilities that buy their water. Nothing about the local share
changed. Added:
- `wholesale_sellers` in `data/water/source_assignments.csv`, filled by hand only where the
  assignment's basis names the seller(s): 8 utilities (Prince William West, Hawley, Eagle Mountain,
  Castalian Springs, Falls Twp, Hamby, Bell Milam Falls, Lordstown). SAWS is SWP in SDWA, but its
  assigned source is its own Edwards wells, so it gets no seller.
- `water_chain.wholesale_population`: the sellers' own retail population plus every active system SDWA
  lists as buying from them (active CC facility with that SELLER_PWSID), each PWSID once, buyers of
  buyers not followed. It writes `wholesale_population` and `wholesale_systems` to `data/sources.csv`.
- `projection.py`: `share_wholesale` = water of every site linked to any utility in that wholesale
  system / (wholesale_population x the utility's state per-capita x 365). It is `null` where there is
  no seller. The map popup shows it on a second line.

2030 median, local share -> wholesale share: Hamby 39.8x -> 0.69x and Hawley 6.0x -> 0.68x (both on the
Abilene system, so both count Shackelford + Stargate Abilene); Bell Milam Falls 10.3x -> 1.16x (Central
Texas WSC + East Bell WSC system, about 61,000 people); Castalian Springs 0.28x -> 0.04x; PWCSA West
0.12x -> 0.009x.

## 2026-11-15 · Phase 5 showcase: outlines, NISAR version mixing, GUNW reference

- **Outlines.** Jupiter: OSM way/1476734418 "Project Jupiter" (613 ac); it misses graded land to
  the west, so its acres are a lower bound (`outline_partial_campus`). Lordstown: OSM
  way/473431363 "Stargate Project", the existing plant building (`outline_existing_building`).
  Frontier: no OSM object within 8 km, so hand-drawn around the cleared campus on Sentinel-2 L2A
  2026-10-08 (`hand_drawn_no_osm`, 1,440 ac vs 1,200 ac reported). Rows in
  `data/footprint/campus_outlines.csv`. Registry coordinates are not changed (another thread owns them).
- **Sentinel-1 is the pre-construction baseline.** NISAR's first GCOV over these sites is from late
  October 2025, after construction began, so F1 uses Sentinel-1 only (`pipeline/footprint.py`,
  `--months-after 16` so the window ends near today). The CLAUDE.md orbit rule picked ascending 5
  (Frontier), descending 56 (Jupiter) and ascending 77 (Lordstown).
- **Provisional and final NISAR GCOV are mixed.** No date exists in both versions. On the reference
  ring (500 m to 1.5 km outside each outline), the step at the switch has a median of -0.28 dB (HH)
  and -0.19 dB (HV) across 10 stacks. That is inside the 0.5 dB tolerance set before the check and
  smaller than the normal date-to-date change on 9 of 10 stacks (`data/radar/nisar_calibration.csv`).
  Recheck once ASF reprocesses the older dates as version 1.0.20.
- **NISAR chart stack per site** = the stack with the most 10 m dates: Frontier 163 A/18, Jupiter
  48 A/17, Lordstown 90 A/22. The series CSV holds every stack.
- **GUNW reference.** Each pair is referenced to the median of a 40 km box around the aquifer
  window, after subtracting the product's ionosphere phase screen. The result is motion relative to
  the surroundings, not absolute, and is summed only along an unbroken chain of back-to-back pairs.
- **Map.** The new images are in `map/img/`; wiring them into `map/index.html` needs captions,
  which are map copy, so that waits for the person.

## 2026-11-15 Phase 6: land cover converted, wetlands and protected areas

**Converted-pixel maps.** F1 kept only acre curves, so `footprint.py` now also writes the final
cumulative converted pixels inside the site (outline + 200 m) as `data/footprint/masks/<id>_converted.tif`
(10 m UTM, 172 KB for all 29). All 29 sites were rerun. Thresholds, final acres, A_max and build
months came out identical to the committed summary, so nothing in F1 changed. The mask is the
`final_acres_site` area. That is the measured converted area; A_max is the logistic fit's asymptote,
usually close to it (Osmium: 300.5 measured vs 275.1 fitted). Meta Jeffersonville has no outline, so
it has no mask and is listed as `no_footprint_mask`.

**Land cover (`pipeline/landcover.py`, `data/landcover/`).**
- Source: NLCD Land Cover L48 from the MRLC GeoServer WCS (official USGS/MRLC, 30 m).
- Edition: the latest one whose year is before the site's construction start year. The 2001-2021
  editions are on the WCS. Annual NLCD years are only offered there as a 2024 test layer, and the
  per-year bundles are 1.4 GB each, so they were not used. The gap is 1-3 years (mean 2.0), in
  `nlcd_gap_years`.
- Method: each 10 m converted pixel takes the NLCD class at its centre.
- Grouped results over the 29 sites (8,462 acres converted):
  - shrub/grassland 31.3% (Abilene and Storey County alone are 1,600 ac)
  - cropland 30.5%
  - developed 18.6%
  - forest 9.8%
  - pasture/hay 6.8%
  - barren 1.9%
  - NLCD wetlands 0.9% (79 ac)
  - water 0.3%
- "Developed" before construction partly means roads, older buildings or earlier phases inside the
  outline (Arcola, The Dalles, Midlothian, Eagle Mountain), not necessarily new land.
- Sites where NLCD mapped wetland under converted pixels: QTS Richmond 1 (18.2 ac), Nebius New
  Jersey (16.5), QTS Richmond 2 (11.9), Bristow (11.2), Hillsboro 2 (10.7), plus small amounts at
  three others. These are NLCD classes at 30 m, not a delineation.

**Distances (`pipeline/proximity.py`, `data/proximity/`).**
- Wetlands: USFWS NWI layer 0 (public ArcGIS service).
- Protected areas: USGS PAD-US 4.1 Fee layer at edits.nationalmap.gov.
- What counts as protected: GAP status 1-3 only (managed for biodiversity, or multiple use with
  protection). GAP 4 (no known mandate) is left out. Easement, designation and marine layers are not
  queried; this is a lower bound on nearby protected land.
- Wetland types: NWI "any type" includes lakes, ponds and rivers. A second distance keeps only
  marsh/swamp types: Freshwater Emergent, Freshwater Forested/Shrub, Estuarine and Marine Wetland.
- Measured from: the campus outline where there is one, else the registry point; announced sites with
  `location_missing` are not measured. Sources are measured from the point in `data/sources.csv`
  (`measured_from` says what it is).
- Search widens 1, 5, 25, then 100 km.
- Results:
  - 20 of 52 located sites have an NWI marsh/swamp polygon touching or inside the outline. Median
    distance for sites is 50 m. NWI maps are often older than the construction, so this says where
    NWI mapped a wetland, not that one was filled.
  - 8 sites have GAP 1-3 protected land within 1 km. Meta Kuna is 3 m from BLM Four Rivers Field
    Office land. The Laramie outline touches a Wyoming state land parcel.
  - For sources, the median distance to a marsh/swamp wetland is 731 m.


**Shackelford location upgraded (found while merging the Phase 5 branch).** The Phase 5 thread
hand-drew the Vantage Frontier campus from Sentinel-2 (2026-10-08, 1,440 ac,
`data/footprint/FRONTIER-SHACKELFORD_campus.geojson`). The TX-351 / FM 604 road point used for
`ANN-STARGATE-SHACKELFORD` sits on its north-west edge, inside Hamby WSC's service area. A point inside
the drawn campus falls in no EPA service area, so the site is now `self_supplied_check`
(`location_precision = image_outline`). Hamby WSC drops out of `data/sources.csv`, and its 39.8x share
is gone. The largest 2030 median local shares are now Bell Milam Falls 10.3x (Milam), Camino Real 8.9x
(Dona Ana), Hawley 6.0x (Stargate Abilene), Montgomery Co PWSD 1 2.8x and Boling 2.2x.
`proximity.py --only` now updates just those rows.

## Phase 7: live map on real data (2026-11-15)

**Data.** `pipeline/build_map.py` builds `map/data.js` from the real CSVs only (`demo: false`):
54 campuses (29 built, 25 announced; 46 have what F2-F8 need), 25 water sources, 12 with a
SWOT or DISP-S1 series. It calls `projection.calibrate / project_sites / project_sources`, so the
map uses the same F2-F8 code as `projection.py`. The demo CSVs stay in `data/` for the quick test
in the README but are not shipped: only `map/` is published.

**Built-site markers sit inside the OSM campus outline** (representative point), as the water chain
already does, because some registry points are town centroids and Google Kansas City East has none.
Effect: KC East now has a location, so it joins the projection and the F2 calibration (45 -> 46 sites).
Calibration moved from acres/MW 0.80 / 1.32 / 1.77, tau 47.9 months (checked: identical without KC
East) to acres/MW 0.80 / 1.38 / 2.03, WUE 0.34 / 1.52 / 2.38 L/kWh, tau 46.2 months. KC East keeps
its F1 flag (noise floor above 5% at 5 dB); flagged sites stayed in calibration in Phase 4 too, so the
rule is unchanged.

**Not projected (8):** shown on the map with the reason (no location, or no MW, capex or construction
start). Armstrong and Haskell have no known location and are listed in a note, not drawn.

**Trend charts.** Each source with a series shows the points used by `water_chain.py` and a straight
line fit (segment-aligned for DISP-S1, MAD outliers drawn hollow). Values come from the saved series
files listed in each source's `file`.

**Wording.** No sentence says a data center caused a change in a water source. Shares say "estimated
water for the linked campuses divided by estimated supply". DISP-S1 text: "Moving away often means
sinking, which can come from pumping groundwater, but this measurement alone does not say why." The
About box: "A trend describes the water body; it does not show what caused the change."

**Exposure badges.** W = vegetated NWI wetland within 100 m of the outline or point; P = GAP 1-3
protected land within 1 km. Thresholds are display choices only; the distances are in the panels.

**Fix.** `proximity.py` labelled every announced outline "OSM campus outline"; Shackelford's is the
Sentinel-2 image outline. Label fixed in code and in `data/proximity/site_proximity.csv` (no
distance changed).

**Hosting.** `.github/workflows/pages.yml` publishes `map/` to GitHub Pages on every push to main.

## 2026-11-15: Map redesign (look and feel only)

**Why.** The person asked for a more advanced, polished map. Data, formulas, sites and wording rules are unchanged:
`map/data.js` and `map/radar_panels.js` are untouched, and every panel text about water sources keeps its earlier wording.

**Rendering.** Leaflet replaced by MapLibre GL 4.7.1 with a deck.gl 9.0.38 overlay (both from unpkg, still a static
page on GitHub Pages). Basemaps: CARTO Dark Matter (no key) and Esri World Imagery with Esri reference labels (no key).
CARTO's raster label tiles were tried and rejected: they now show "API key required".

**Display-only choices (no number shown to a reader depends on them).**
- Campus column height = 6,000 m + 5,000 m x sqrt(acres converted in the selected year and scenario), scaled with zoom so
  columns stay readable, then fading out past zoom ~9 where the extruded campus outlines take over. Square root so
  small campuses stay visible next to the largest.
- Water links are drawn as raised curves from the water source to the campus with moving pulses; pulses run only on
  links whose campus has converted land in the selected year (or is built). The curve height is cosmetic.
- Source color = F7 pressure index on a cyan-violet-rose ramp; the KPI counters animate between values but always
  settle on the exact totals.
- Added per-campus charts of the existing low/median/high water and acres series (2026-2030) and a top-6 list by
  pressure index; both read the same `data.js` values the tables show.

## 2026-11-15: Map redesign, second version (replaces the 3D-column design above)

**Why.** The person rejected the dark 3D-column look ("looks like SimCity") and asked for a Google Earth feel:
data drawn on real imagery, not shapes on a line map. Data, formulas, sites and water wording are unchanged.

**Base.** MapLibre GL 5.6.0 globe projection with Esri World Imagery as the only basemap, Esri reference labels and
roads (toggle), and 3D terrain from the public Mapzen/AWS Terrain Tiles (terrarium, 1.4x exaggeration). deck.gl and the
dark CARTO basemap are removed. All data layers are native MapLibre layers, so they drape on the terrain.

**Radar change on the photo.** New `pipeline/map_overlays.py` reprojects each `data/footprint/masks/<id>_converted.tif`
(29 built campuses) to Web Mercator with nearest-neighbour resampling, so no pixel changes class, and writes a transparent
PNG: converted pixels in light red, with a brighter edge around solid patches (the mask opened by one pixel; display only).
Check: pixel counts x 100 m^2 match `final_acres` (e.g. Osmium 12,159 px = 300.5 acres vs 300.46; Abilene 1,094.0 vs 1,094.01).
The three announced Stargate sites have no F1 mask, so they show only their outline.

**Display choices.** Campus markers are circles sized by sqrt(acres in the selected year and scenario); they fade out
past zoom ~12 where the outline and radar pixels take over. Campus-to-source lines appear only for the selected campus or
source, to keep the imagery clear. Source color = F7 pressure index (blue-yellow-red). Imagery dates vary by place, and the
About box says so.
