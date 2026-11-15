# Data center growth and the water it depends on (prototype)

A starter repo for Option 2: footprint from radar, water supply chain, projection to 2030, map.

## What runs today
| Piece | Status |
|---|---|
| `pipeline/projection.py` (F2–F8) | Tested on the demo CSVs; writes `map/data.js` |
| `map/index.html` | Render logic tested; needs internet for Leaflet and map tiles |
| `pipeline/footprint.py` (F1) | Port of the GEE script on Planetary Computer `sentinel-1-rtc`; tested on Stargate Abilene (`data/footprint/`) |
| `gee/footprint_engine.js` (F1) | Logic reference only (Earth Engine is not available to this project) |
| `pipeline/water_chain.py` steps 1–3a | Written against documented file layouts and the Hydrocron API, not yet run against live data |
| `pipeline/water_chain.py` step 3b (DISP-S1) | Placeholder: inspect one real file first |

All rows in `data/*_demo.csv` are invented. `PER_CAPITA_L_PER_DAY` and `UTILIZATION` in
`projection.py` are placeholders to replace with sourced values.

## Quick start
```
pip install -r requirements.txt
python pipeline/projection.py --registry data/site_registry_demo.csv --sources data/sources_demo.csv
python -m http.server 8000        # then open http://localhost:8000/map/
```

## First real test (one site, end to end)
1. Pick one built site from Epoch (https://epoch.ai/data/data-centers). Note MW, capex, construction start.
2. Save its outline as GeoJSON in `data/footprint/` and run
   `python pipeline/footprint.py --site-id <ID> --campus data/footprint/<ID>_campus.geojson --construction-start YYYY-MM-DD`.
   It writes the area curve and `footprint_summary.csv` with `a_max_acres` and `build_months` (10%→90%).
3. Download EPA service areas into `data/raw/epa_service_areas.*` and run
   `python pipeline/water_chain.py match --registry data/site_registry.csv`.
4. Download the ECHO SDWA zip, unzip into `data/raw/`, run `... lookup --pwsid <PWSID>`.
5. Find the source name in the utility's water quality report. For a reservoir, find its lake ID
   in the SWOT Prior Lake Database, then run `... swot --lake-id <ID> --start 2023-08-01 --end 2026-11-01`.
6. Fill one row each in `data/site_registry.csv` and `data/sources.csv`, run the projection, open the map.

## Data links
- Epoch AI data centers: https://epoch.ai/data/data-centers
- PNNL data center atlas: https://im3.pnnl.gov/datacenter-atlas
- Sentinel-1 RTC (Planetary Computer): https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc
- Sentinel-1 in Earth Engine: https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD
- NISAR (ASF Vertex): https://search.asf.alaska.edu · guide: https://nisar-docs.asf.alaska.edu/availability-overview/
- EPA water system service areas: https://www.epa.gov/ground-water-and-drinking-water/public-water-system-service-areas
- ECHO SDWA download: https://echo.epa.gov/tools/data-downloads#dwdownloads
- SWOT lake product: https://podaac.jpl.nasa.gov/dataset/SWOT_L2_HR_LakeSP_D · Hydrocron: https://podaac.github.io/hydrocron/intro.html
- OPERA DISP-S1: https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-v1-1
- Google per-site water: https://sustainability.google/reports/google-2026-environmental-report/
- WRI Aqueduct: https://www.wri.org/aqueduct

## Formulas
- **F1** ΔVV, ΔVH vs 12-month baseline; converted if |Δ| > θ for ≥ 2 consecutive months; A(t) = converted area; fit logistic.
- **F2** a = acres/MW, k = $/MW, WUE = withdrawal / (MW × u × 8760 × 1000), τ = build months, lag = start→operation (percentiles per scenario).
- **F3** MW = stated MW, else capex / k.
- **F4** water (L/yr) = MW × u × 8760 × 1000 × WUE.
- **F5** share = water / (population served × per-capita use × 365).
- **F6** decline score = percentile rank of the source trend within its type.
- **F7** pressure = weighted mean of normalized share, decline score, Aqueduct stress (weights set on the map).
- **F8** build fraction B(t) logistic with τ; water ramps on the same curve centred on the operation date.
