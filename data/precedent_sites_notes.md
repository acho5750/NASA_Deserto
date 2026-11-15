# Precedent sites (Phase 1a): built US AI data centers from Epoch AI

Status: **for review, not yet merged into `data/site_registry.csv`.** Every row is
`verification = epoch_derived_unreviewed`.

Files
- `data/precedent_sites.csv`: 30 built sites. Columns 1-13 match `site_registry_demo.csv`;
  the rest are evidence and review columns.
- `data/precedent_sites_excluded.csv`: the other 47 US Epoch sites and why each was left out.
- `pipeline/precedent_sites.py`: rebuilds both files from Epoch's download
  (`python pipeline/precedent_sites.py`, about 1 minute with geocoding).

Source: Epoch AI, "AI data centers", https://epoch.ai/data/data-centers (CC BY 4.0), bundle
https://epoch.ai/data/data_centers/data_centers.zip downloaded 2026-11-15. Each row's `source`
column lists the dataset page, the timeline CSV, the site's Epoch calculation sheet and the
first source Epoch cites for that site.

## How each value is derived
| Column | Rule |
|---|---|
| `construction_start` | Date of the site's first Epoch timeline row. For all 30 kept sites that row says land clearing / construction starts; the text is in `construction_start_evidence`. |
| `operation_date` | First timeline date with Power (MW) > 0 (first building operational). Text in `operation_evidence`. |
| `mw` | Epoch **IT power** (MW) on the last timeline row on or before 2026-11-15 (`values_as_of`). Equals Epoch's "Current power (MW)". |
| `mw_facility` | Epoch facility power (IT x PUE) on the same row. Ratio to `mw`: 1.19-1.41. |
| `capex_busd` | Epoch "Total capital cost (2025 USD billions)" on the same row (buildings + power + cooling + chips). |
| `capex_construction_busd` | Epoch "Construction cost" on the same row (excludes chips). |
| `buildout_complete` | True when Epoch's timeline has no later row adding power. False means the site keeps growing after 2026-11-15 (`planned_final_mw_facility` by `planned_final_date`). |
| `epoch_water_use_mgd` | Epoch "Water use (MGD)", only where Epoch gives one (10 sites). Epoch does not say whether this is withdrawal or consumption, so `withdrawal_ml_per_yr` is left blank. |
| `lat`, `lon` | Mean of Epoch's own Google Earth links for the site where present (`epoch_link`, 7 sites), else the Epoch address geocoded with OSM Nominatim (`street`, 12) or the US Census geocoder (`street_census`, 3); else town centroid (`town`, 7); Google Kansas City East has no address in Epoch and no coordinates (`none`). |
| `a_max_acres`, `build_months`, `withdrawal_ml_per_yr`, `source_id` | Blank: filled by Phases 2 and 3. |

## Selection
1. All 77 US sites in Epoch.
2. Operational (Power > 0) by 2026-11-15: 58 left (19 dropped, first power 2026-12 to 2028-12).
3. Greenfield only, because F1 measures converted land: 8 conversions of existing buildings or
   crypto sites dropped (Colossus 1, CoreWeave Chester / Dalton / Denton / Marble / Helios,
   Stream Phoenix, xAI QTS Atlanta) plus Google Pryor (North), whose timeline starts at operation
   with no construction date. Anthropic and Core42 Lake Mariner share one address, so neither can
   get its own footprint: both dropped. 47 left.
4. Ranked buildout complete first, then earliest operation; kept 30 (29 complete + Google Storey
   County). The 17 below the cut are still expanding (for example Meta Prometheus, Colossus 2,
   Anthropic-Amazon New Carlisle, Microsoft Fairwater Wisconsin). Rerun with `--max-sites 47` to
   include them; their acres-per-MW would mix finished and unfinished buildings.

## Findings to review
1. **Epoch capex is modeled from power, not reported.** `capex_busd / mw` is 37.88 $M per IT MW
   at every site (s.d. 0.00), and construction cost is 11.77 $M/MW at every site. So k in F2 has
   no spread from these data, and F3 (MW = capex / k) would just invert Epoch's own constant.
   Superseded 2026-11-15: k now comes from announced capex (`data/precedent_capex.csv`,
   `pipeline/precedent_k.py`): 8 sites, low / median / high 4.49 / 5.73 / 11.91 $M per IT MW
   (case A). Median announcement-to-construction gap -0.6 months over 8 sites.
2. **Lag (construction start to first operation):** median 28.3 months, IQR 24.3-35.2, range
   4.9 (QTS Richmond 1, an expansion of a running campus) to 64.8 (Microsoft SAT40). Flagged
   `long_lag_*` where over 48 months: SAT40, Meta Huntsville, Google Storey County.
3. **Campus context.** 7 sites sit next to older buildings or are one phase of a larger campus
   (`outline_new_parcel_only`). Phase 2 must outline only the new parcel, or the Sentinel-1
   baseline already contains built land.
4. **Coordinates are pointers, not outlines.** 8 sites are `town` or `none`; do not use them for
   the Phase 3 utility match until Phase 2 replaces them with a PNNL/OSM campus outline.
   Note: https://im3.pnnl.gov/datacenter-atlas returned "Request Rejected" (WAF block page) from
   the cloud machine on 2026-11-15, and overpass-api.de timed out, so Phase 2 may need the
   linked computer or another OSM mirror.
5. **Sentinel-1 baseline.** Earliest construction start is 2018-12-18 (Microsoft Project Osmium),
   so every site has at least 12 months of Sentinel-1 before construction. Sentinel-1B failed in
   Dec 2021, so baselines in 2022-2024 have fewer images; the orbit fallback rule in CLAUDE.md
   applies.
6. **MW basis.** `mw` is IT power because WUE (F2, F4) is per IT kWh. Announced projects often
   quote grid or facility MW; compare with `mw_facility` when combining the two lists.

## Sites
| site_id | owner | IT MW | capex $B (Epoch model) | construction start | first operation | coords | flags |
|---|---|---|---|---|---|---|---|
| MICROSOFT-PROJECT-OSMIUM | Microsoft | 190 | 7.20 | 2018-12-18 | 2021-01-01 | town |  |
| GOOGLE-PAPILLION | Google | 237 | 8.98 | 2020-03-04 | 2023-01-23 | town |  |
| MICROSOFT-GOODYEAR | Microsoft | 202 | 7.65 | 2021-06-21 | 2023-04-24 | street |  |
| META-QTS-HILLSBORO-2 | Meta (likely) | 180 | 6.82 | 2021-04-01 | 2023-08-02 | street |  |
| GOOGLE-LANCASTER | Google | 137 | 5.19 | 2021-10-01 | 2024-01-01 | epoch_link |  |
| QTS-RICHMOND-1 |  | 238 | 9.02 | 2023-09-01 | 2024-01-29 | epoch_link |  |
| GOOGLE-NEW-ALBANY | Google | 333 | 12.62 | 2021-03-01 | 2024-04-20 | street |  |
| GOOGLE-BRISTOW | Google | 238 | 9.02 | 2021-07-01 | 2024-04-29 | street_census |  |
| MICROSOFT-SAT40 | Microsoft | 75 | 2.84 | 2018-12-28 | 2024-05-24 | epoch_link |  |
| MICROSOFT-SAT14 | Microsoft | 47 | 1.78 | 2022-02-18 | 2024-07-01 | epoch_link |  |
| GOOGLE-COUNCIL-BLUFFS-EAST | Google | 237 | 8.98 | 2022-09-06 | 2024-11-19 | street |  |
| QTS-RICHMOND-2 |  | 180 | 6.82 | 2022-04-01 | 2025-02-04 | epoch_link |  |
| GOOGLE-THE-DALLES | Google | 154 | 5.83 | 2023-03-01 | 2025-03-07 | street |  |
| GOOGLE-MESA | Google | 183 | 6.93 | 2023-08-01 | 2025-07-01 | epoch_link |  |
| STARGATE-ABILENE | Oracle | 824 | 31.21 | 2024-05-31 | 2025-09-26 | street |  |
| MICROSOFT-FAIRWATER-ATLANTA | Microsoft | 636 | 24.09 | 2023-04-09 | 2025-10-14 | street |  |
| META-EAGLE-MOUNTAIN | Meta | 133 | 5.04 | 2023-08-01 | 2025-12-07 | town |  |
| META-TEMPLE | Meta | 178 | 6.74 | 2022-04-01 | 2025-12-09 | street |  |
| META-HUNTSVILLE | Meta | 146 | 5.53 | 2021-12-13 | 2026-03-04 | town |  |
| MICROSOFT-NEBIUS-NEW-JERSEY | Nebius | 50 | 1.89 | 2024-05-31 | 2026-04-15 | street |  |
| GOOGLE-MIDLOTHIAN | Google | 103 | 3.90 | 2023-04-01 | 2026-04-19 | street |  |
| META-KUNA | Meta | 152 | 5.76 | 2022-07-01 | 2026-06-01 | street |  |
| META-JEFFERSONVILLE | Meta | 178 | 6.74 | 2024-02-01 | 2026-06-04 | street |  |
| GOOGLE-ARCOLA | Google | 77 | 2.92 | 2024-10-01 | 2026-06-16 | town |  |
| META-ROSEMOUNT | Meta | 178 | 6.74 | 2024-02-01 | 2026-06-19 | street_census |  |
| GOOGLE-KANSAS-CITY-EAST | Google | 105 | 3.98 | 2023-12-01 | 2026-08-01 | none |  |
| META-SARPY | Meta | 80 | 3.03 | 2024-08-01 | 2026-08-02 | street_census |  |
| META-AIKEN | Meta | 129 | 4.89 | 2024-05-30 | 2026-08-07 | town |  |
| META-GALLATIN | Meta | 87 | 3.30 | 2023-09-11 | 2026-08-24 | town |  |
| GOOGLE-STOREY-COUNTY | Google | 161 | 6.10 | 2019-03-18 | 2023-08-30 | epoch_link |  |
