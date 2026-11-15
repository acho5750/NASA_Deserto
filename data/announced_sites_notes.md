# Announced US data center projects: notes for review

`data/announced_sites.csv` lists 24 announced US projects, researched 2026-11-15 and revised the same day under the review rules below. **Every row is
`unverified`** and waits for review before anything goes into `data/site_registry.csv`.

## What's included
- Only US projects that have been publicly announced, are not yet fully operating, and have a named
  location of at least county level. Each one has a planned or likely first operation date between
  2026 and 2030, or no date at all.
- Expansions of campuses that already operate are left out, because their land was already converted
  before the build started (see the table below).
- Numbers are recorded only when the developer, a regulator, or a filing states them. Third-party
  estimates, such as Epoch's projected GW, go in `notes` or `*_basis` and are not used as values.

## Review rules applied (Bubba, 2026-11-15)
1. **2030 window.** `mw` is the capacity expected by the end of 2030, not the full build.
   `mw_full_build` keeps the full figure. Hyperion: `mw` = 2000, `mw_full_build` = 5000. Every
   other stated MW completes by 2030 or gives no completion year, so for those the full figure is used.
2. **Missing construction start.** If there is an expected online date, start = `operation_date`
   minus 28 months. Otherwise start = `announced_date` plus the median gap from announcement to
   groundbreaking across the built sites. That median comes from the built-sites thread (PR 6) and
   **has not arrived yet**, so those rows show `start_estimated = pending`. `start_estimated` is
   `true`, `false`, or `pending`.
3. **Source rule.** MW and capex now come only from a company, government, or utility source. The
   result is in `mw_source` and `capex_source`, with `*_basis` naming the kind of source. Rows whose
   capex spans phases past 2030, or can't be tied to the 2030 capacity, have `low_confidence = true`
   with a reason.
4. **Sort.** Rows are sorted by `mw_2030_for_sort`, largest first, and `rank_2030_mw` gives the
   order. That is the stated `mw` when there is one. Otherwise it is capex / $37.88M per MW (Epoch's
   median), used **for sorting only**. Each figure sits next to its source column.

## Changes from the first version
- **Saline capex:** $7B (one secondary source) became **$16B** (Related Digital financing release, 2026-04-24).
- **El Paso:** capex became **$14B** (Meta, total development cost; Meta's own share is more than $10B).
  Operation is now 2028 (Meta).
- **Port Washington:** 902 MW is now sourced to Vantage itself (blog, 2026-03-30).
- **West Memphis:** re-checked against primary sources. Google's blog says $4B in Arkansas through
  2027, covering the data center plus cloud/AI infrastructure and local programs. The Arkansas EDC
  release says only "multi-billion", so the row is marked low confidence.
- **Montgomery MO:** $10B is from the Missouri governor's office. Amazon's own release says "several billion".
- **King George VA:** $6B is from the county's notice.
- **Wharton TX:** start 2026-08-01 and first completion Jan 2027, both from the TDLR registrations.
- **Hyperion:** capex is blank because the share of the $50B tied to 2 GW isn't stated. The MW is
  stated, so F3 doesn't need capex.

## Columns
- The registry columns (`site_id` … `source_id`) are all present. Copy them by name, not by position.
- `mw_type` is `IT`, `facility (utility contract load)` or `unspecified`. The built list (PR 6) uses
  IT MW, so Saline's 1.4 GW (DTE contract load) is not like-for-like with it.
- `projection_eligible` is `no` when a row has neither MW nor capex.

- **Dates.** When only a month, quarter, or year is known, a start date is set to the first day of
  that period and an operation date to the last day. The `*_basis` column gives the precision.
- **Coordinates.** All coordinates are OSM Nominatim centroids of the town or county, not the campus
  (`location_basis` says which). Campus outlines come from OSM in Phase 2.

## Still open for your review
- **Project Jupiter ranks #1 only because of the sort estimate.** $165B is a county bond ceiling
  covering all phases, and no company MW is stated (low confidence).
- **Saline:** construction was underway by 2026-06-01, so any estimated start must fall before that date.
- **xAI Southaven:** rule 2 gives a start of 2024-08-31, from Dec 2026 operation minus 28 months.
  These sites were announced in Nov 2026 inside existing buildings, so that date is implausible.
  The row isn't projectable anyway (no MW and no capex).
- **Low-confidence rows:** Lordstown and Fermi Matador are kept and flagged.

## Not included
| Project | Why it's left out |
|---|---|
| Stargate Abilene, Microsoft Fairwater 1 (Mount Pleasant) | Built precedent sites (Phase 1a) |
| Microsoft Fairwater 2, Atlanta | Operating since Oct 2025 |
| AWS New Carlisle, IN ($13.8B) | Expansion of an operating campus (about 18 of 30 buildings running) |
| Google Jackson County, AL ($1.5B) | Expansion of a campus operating since 2019 |
| AWS Madison County, MS ($11B, Apr 2026) | Expansion of existing campuses |
| Google Ellis County, TX | Expansion, and no site-level capex in the $40B Texas total |
| Anthropic / Fluidstack, TX and NY ($50B) | No location disclosed |
| Crusoe / Tallgrass Project Jade, Cheyenne | Paused Jun 2026; the site is now Google Laramie County (included) |
