# Data center growth and the water it depends on (prototype)

A starter repo for Option 2: footprint from radar, water supply chain, projection to 2035, map.

## Use of AI
Code, data processing scripts and written text in this repository were produced with the help of
Claude (Anthropic) through Claude Code, an AI coding assistant. Every
judgment call is logged with its date and reason in `DECISIONS.md`. The data come from the
satellite and public sources listed under "Data links"; no data, images or map pictures are
AI-generated. Every picture on the map is satellite radar or aerial photography.

## What runs today
| Piece | Status |
|---|---|
| `pipeline/projection.py` (F2–F8) | Calibrated on real data (Phase 4); the demo CSVs still work for a quick test but are not shipped |
| `pipeline/build_map.py` (Phase 7) | Builds `map/data.js` from the real CSVs: all 54 campuses, 25 water sources, projection, radar, trends, land cover, exposure |
| `map/index.html` | Four-chapter story map over US imagery (MapLibre GL 4, Esri World Imagery): 1 Land (Sentinel-1 change, land cover before, before/after aerial photos), 2 NISAR now, 3 Water (EPA chain, SWOT, OPERA DISP-S1), 4 2035 (F2-F9). A time bar shows one lane per satellite. Deployed from `map/` to GitHub Pages by `.github/workflows/pages.yml` |
| `pipeline/nisar_overlays.py` | NISAR pictures for the map: one HH radar frame per 12-day pass over the 3 NISAR campuses (`map/nisar/`), and where the ground got > 3 dB brighter between the first 3 and last 3 passes (`data/radar/nisar_change.csv`, `map/nisar.js`). Reads GCOV windows with HTTP Range requests |
| `pipeline/gunw_aquifer.py` | NISAR L2 GUNW ground motion over one aquifer source: longest back-to-back chain of 12-day pairs, 6 km window vs. 40 km surroundings, ionosphere-corrected (`data/water/gunw/gunw_<water body>_<track>_<frame>.csv`); run on all 8 aquifer sources |
| `pipeline/gunw_story.py` | Sums those runs per aquifer: change, noise (pair s.d. x sqrt(pairs)), verdict, and the OPERA DISP-S1 rate over the same span (`data/water/gunw/gunw_summary.csv`, `map/gunw.js`) |
| `pipeline/map_story.py` | Story numbers not in `data.js`: land-cover totals, Sentinel-1 and NISAR series for the three NISAR campuses, sensor date spans (`map/story.js`) |
| `pipeline/conversion_dates.py` | Re-runs F1 per built campus and saves the month each converted pixel first changed (`data/footprint/masks/<id>_first_converted.tif`); refuses to write unless the final mask equals the committed one and monthly acres match the area curve |
| `pipeline/map_timeline.py` | Turns those months into the map's Play data: per-campus pixel polygons (`map/pixels/`) and the measured area curves (`map/timeline.js`) |
| `pipeline/map_wayback.py` | Lists the dated aerial photos of each campus in Esri World Imagery Wayback (`data/wayback_captures.csv`, `map/wayback.js`), so Play swaps in the photo taken before each date |
| `pipeline/footprint.py` (F1) | Port of the GEE script on Planetary Computer `sentinel-1-rtc`; run on 29 built sites by `pipeline/footprint_batch.py` (`data/footprint/`, radar images in `map/img/`) |
| `pipeline/campus_outline.py` | Campus outlines from OpenStreetMap (main API + Nominatim; ids in `data/footprint/campus_outlines.csv`) |
| `gee/footprint_engine.js` (F1) | Logic reference only (Earth Engine is not available to this project) |
| `pipeline/landcover.py` (Phase 6) | NLCD class before construction under each built site's F1 converted pixels (`data/footprint/masks/`); writes `data/landcover/` |
| `pipeline/proximity.py` (Phase 6) | Distance from every site and source to the nearest NWI wetland and PAD-US protected area; writes `data/proximity/` |
| `pipeline/water_chain.py` (water chain) | Run on all 54 sites: EPA match, SDWA seller chain, SWOT trend via Hydrocron (SWORD reaches), DISP-S1 reader (range reads); writes `data/sources.csv` |

All rows in `data/*_demo.csv` are invented and are used only by the demo command below; the
shipped map is built from real data only. `UTILIZATION` and per-capita use are sourced (see DECISIONS.md, Phase 4).

## Quick start
```
pip install -r requirements.txt
python pipeline/build_map.py      # real data -> map/data.js
python pipeline/conversion_dates.py --skip-done   # month each radar pixel changed (re-runs F1, ~80 s per campus)
python pipeline/map_timeline.py                   # -> map/pixels/, map/timeline.js
python pipeline/map_wayback.py                    # dated aerial photos per campus -> map/wayback.js
python pipeline/map_story.py                      # chapter numbers -> map/story.js (after build_map.py)
python pipeline/nisar_overlays.py                 # NISAR frames + brightening map -> map/nisar/, map/nisar.js (Earthdata token)
python -m http.server 8000        # then open http://localhost:8000/map/
# demo only (overwrites map/data.js with invented data; do not commit):
# python pipeline/projection.py --registry data/site_registry_demo.csv --sources data/sources_demo.csv
```

## First real test (one site, end to end)
1. Pick one built site from Epoch (https://epoch.ai/data/data-centers). Note MW, capex, construction start.
2. Save its outline as GeoJSON in `data/footprint/` and run
   `python pipeline/footprint.py --site-id <ID> --campus data/footprint/<ID>_campus.geojson --construction-start YYYY-MM-DD`.
   It writes the area curve and `footprint_summary.csv` with `a_max_acres` and `build_months` (10%→90%).
3. Run `python pipeline/water_chain.py points` then `... match` (queries EPA's service area
   ArcGIS service by point; no download needed).
4. Download the ECHO SDWA zip, unzip into `data/raw/sdwa/`, run `... lookup` (all matched
   utilities, following purchased water to sellers) or `... lookup --pwsid <PWSID>`.
5. Name the water body per utility in `data/water/source_assignments.csv` (SDWA plus the utility's
   water quality report), then run `... sources` (SWOT via Hydrocron, DISP-S1 for aquifers).
6. Fill one row each in `data/site_registry.csv` and `data/sources.csv`, run the projection, open the map.

## Data links
- Epoch AI data centers: https://epoch.ai/data/data-centers
- PNNL data center atlas: https://im3.pnnl.gov/datacenter-atlas
- Sentinel-1 RTC (Planetary Computer): https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc
- Sentinel-1 in Earth Engine: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD
- NISAR (ASF Vertex): https://search.asf.alaska.edu · guide: https://nisar-docs.asf.alaska.edu/availability-overview/
- EPA water system service areas: https://www.epa.gov/ground-water-and-drinking-water/public-water-system-service-areas
  · ArcGIS service used by the pipeline: https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/Water_System_Boundaries/FeatureServer/0
- ECHO SDWA download: https://echo.epa.gov/tools/data-downloads#dwdownloads
- SWOT lake product: https://podaac.jpl.nasa.gov/dataset/SWOT_L2_HR_LakeSP_D · Hydrocron: https://podaac.github.io/hydrocron/intro.html
- OPERA DISP-S1: https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-v1-1
- Google per-site water: https://sustainability.google/reports/google-2026-environmental-report/
- WRI Aqueduct: https://www.wri.org/aqueduct
- NLCD (MRLC WCS): https://www.mrlc.gov/data · NWI: https://www.fws.gov/program/national-wetlands-inventory · PAD-US 4.1: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview

## Formulas
- **F1** ΔVV, ΔVH vs 12-month baseline; converted if |Δ| > θ for ≥ 2 consecutive months; A(t) = converted area; fit logistic.
- **F2** a = acres/MW, k = $/MW, WUE = withdrawal / (MW × u × 8760 × 1000), τ = build months, lag = start→operation (percentiles per scenario).
- **F3** MW = stated MW, else capex / k.
- **F4** water (L/yr) = MW × u × 8760 × 1000 × WUE.
- **F5** share = water / (population served × per-capita use × 365).
  For a utility that buys its water, a second share uses the wholesale system instead: water / (population served by the sellers and their direct buyers × per-capita use × 365). The map shows both (decided by the person, 2026-11-15).
- **F6** decline score = percentile rank of the source trend within its type.
- **F7** pressure = weighted mean of normalized share, decline score, Aqueduct stress (weights set on the map).
- **F8** build fraction B(t) logistic with τ; water ramps on the same curve centred on the operation date.
- **F9** (past the announced list, national only) pace = MW of projected announced campuses announced in the 24 months before the data date ÷ 2 years. One cohort of that many MW is announced (and starts) on July 1 of each year from 2027; each cohort follows F2, F4 and F8. Shown as a separate dashed "if the pace continues" line, never added into site values (decided by the person, 2026-11-15).
