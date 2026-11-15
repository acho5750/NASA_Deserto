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
   minus 28 months (2 rows). Otherwise start = `announced_date` minus 0.6 months (18 days). That
   is the median gap over 8 built sites, from `data/precedent_k_summary.csv` in PR #6 (10 rows).
   `start_estimated` is `true`, `false`, or `missing` (Fermi has no announced date and no online date).
3. **Source rule.** MW and capex now come only from a company, government, or utility source. The
   result is in `mw_source` and `capex_source`, with `*_basis` naming the kind of source. Rows whose
   capex spans phases past 2030, or can't be tied to the 2030 capacity, have `low_confidence = true`
   with a reason.
4. **Sort.** `rank_2030` puts rows with a stated 2030 MW first, largest first. Rows with only
   capex come next, ordered by capex, then rows with neither. I don't rank capex-only rows by a
   derived MW, because the F3 conversion depends on k and on whether the capex includes compute
   (see below). Two F3 estimates are shown for reference only and are never written to `mw`:
   `mw_f3_est_k5_73` uses the median k from announced capex (PR #6), and `mw_f3_est_k37_88` uses Epoch's figure.
5. **Capex with or without compute.** `capex_includes_compute` is `no`, `no (inferred)`, or
   `unknown`. PR #6 finds that k from announced capex is $5.73M per IT MW, about a sixth of Epoch's
   $37.88M, because announced figures usually leave out chips. A figure that includes compute would
   overstate MW about 6 times through F3. Only El Paso ($14B for buildings and infrastructure, per
   Meta) and Wharton (TDLR construction cost) are stated as facility-only. The three developer
   campuses (Vantage x2, Related) are inferred as facility-only. The rest are unknown.

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
- **Project Jupiter:** $165B is a county bond ceiling covering all phases, and no company MW is
  stated. Through F3 it would give 28,796 MW at $5.73M/MW, which isn't credible. Exclude it from
  F3, or set its MW by hand from a source, before projecting (low confidence).
- **Capex-only rows** (8 projectable rows): with k = $5.73M/MW and capex of unknown scope, F3 could
  overstate their MW. For example, Laramie's $17B gives 2,967 MW.
- **Saline:** the estimated start is 2025-10-12. That is consistent with construction being underway by 2026-06-01.
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

## Share of 2030 MW that depends on F3
`pipeline/announced_f3_share.py --k 4.49 4.88 6.43` writes `data/announced_f3_share.csv`. It
applies Bubba's F3 scenario rule: facility-only rows use k, rows that include compute use $37.88M,
and rows with unstated scope use $37.88M in the low and median scenarios and k in the high one. k is
4.49 / 4.88 / 6.43 $M per IT MW (n = 6, low confidence; `data/precedent_k_summary.csv`, PR #6).
In the low scenario k is the high value, 6.43. The 7 stated-MW rows sum to 8,902 MW in every
scenario. 9 rows depend on F3.
