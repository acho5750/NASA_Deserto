# Project: data center growth and the water it depends on

NASA Space Apps challenge "Dancing with the SARs". We measure how much land past data centers
converted (Sentinel-1 / NISAR radar), trace each site's water supply chain (EPA utility -> source ->
SWOT / OPERA DISP-S1 trend), and project announced investments to 2030 on an interactive map.
Formulas F1-F8 are documented in README.md; code must match them.

## Layout
- `gee/footprint_engine.js`  F1 as first written for Earth Engine. Earth Engine is NOT available
  to this project. Use it only as the logic reference for `pipeline/footprint.py`, which reads
  Sentinel-1 RTC from Microsoft Planetary Computer (collection `sentinel-1-rtc`, values are
  linear gamma0: convert with 10*log10 to dB before applying thresholds).
- `pipeline/water_chain.py`  water chain steps 1-3
- `pipeline/projection.py`   F2-F8, writes `map/data.js`
- `map/index.html`           Leaflet front end, reads `map/data.js`
- `data/`                    small curated CSVs, committed
- `data/raw/`                large downloads, never committed (gitignored)
- `DECISIONS.md`             log of every judgment call (create if missing)

## Commands
- Projection on demo data: `python pipeline/projection.py --registry data/site_registry_demo.csv --sources data/sources_demo.csv`
- Map: `python -m http.server 8000` from the repo root, then open http://localhost:8000/map/
- Water chain: `python pipeline/water_chain.py match|lookup|swot ...` (see the file's docstring)

## Where this runs and how credentials work
- Work runs in Claude Code cloud sessions (Ubuntu VM, ~30 GB disk). The VM can be reset between
  turns: commit and push finished work often. Never commit files from `data/raw/`.
- NASA Earthdata: a bearer token is attached automatically by the environment's network secret to
  requests to `*.earthdatacloud.nasa.gov`, `*.asf.alaska.edu`, and `urs.earthdata.nasa.gov`.
  Make plain HTTPS requests to those hosts; do not look for `~/.netrc` or an EARTHDATA_TOKEN variable.
  If a download returns 401/403, report it and stop: the token may have expired.
- Planetary Computer, Hydrocron, CMR search, EPA, USGS, Epoch, PNNL: public, no credentials.
- Never print, log, or commit any token or secret.

## Decision rules (act on these without asking; log each in DECISIONS.md with date and reason)
- Change threshold: start at 3 dB. If pre-construction "converted acres" exceed 5% of the final
  footprint, raise by 0.5 dB and rerun. Stop at 5 dB and flag the site.
- Orbit: use the most frequent descending relative orbit; fall back to ascending if fewer than
  12 images in the baseline year.
- Site with no utility match: mark `self_supplied_check`, keep it in the footprint model, exclude
  it from water shares.
- Purchased water (source code ends in P): follow to the seller if the CCR names it; otherwise
  mark `source_unknown` and move on.
- Hydrocron returns fewer than 4 good passes: widen the date range once, then mark `insufficient_swot`.
- Missing MW: derive from capex with F3. Missing capex and MW: drop from projection, list in DECISIONS.md.
- Prefer finishing a working end-to-end path on fewer sites over a partial path on all sites.

## Ask the human before
- Changing any formula in README.md, adding or removing sites from the registry, or making any
  claim in map copy that a data center caused a change in a water source.
- Downloading more than 20 GB in one go, or deleting anything in `data/raw/`.
- `git push`, or any change to `.claude/settings.json`.

## Conventions
- Units: acres, MW, megaliters per year (ML/yr), dates ISO `YYYY-MM-DD`, years "as of December 31".
- Every scenario value comes in low / median / high.
- Every number shown on the map must trace to a CSV in `data/` and a source link in its `source` column.
- Map copy says "linked to" or "depends on", never "drains" or "causes".
