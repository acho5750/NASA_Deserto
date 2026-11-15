# Announced US data center projects: notes for review

`data/announced_sites.csv` lists 24 announced US projects, researched 2026-11-15. **Every row is
`unverified`** and waits for review before anything goes into `data/site_registry.csv`.

## What's included
- Only US projects that have been publicly announced, are not yet fully operating, and have a named
  location of at least county level. Each one has a planned or likely first operation date between
  2026 and 2030, or no date at all.
- Expansions of campuses that already operate are left out, because their land was already converted
  before the build started (see the table below).
- Numbers are recorded only when the developer, a regulator, or a filing states them. Third-party
  estimates, such as Epoch's projected GW, go in `notes` or `*_basis` and are not used as values.

## Columns
The first 13 columns match `data/site_registry_demo.csv`, so rows can be copied over directly. After them:
- `*_basis` says where each value came from, how precise it is, and any caveats.
- `projection_eligible` is `no` when a row has neither MW nor capex (CLAUDE.md rule: drop it from the projection).
- `source`: the primary link. `source_2`: a corroborating or secondary link.
- `mw_by_2030` is filled only where the developer gave a figure for 2030 (Hyperion: 2 GW of its 5 GW).

## Conventions (logged in DECISIONS.md)
- **Dates.** When only a month, quarter, or year is known, `construction_start` is set to the first
  day of that period and `operation_date` / `full_buildout_date` to the last day. The basis column
  gives the precision.
- **Coordinates.** All coordinates are OSM Nominatim centroids of the town or county, not the campus.
  `location_basis` says which one. Campus outlines are a Phase 2 job (PNNL atlas or OSM).
- **MW.** `mw` is the developer's stated full-build figure. When the only power number is a utility
  contract or on-site generation, it is used only if it is the sole stated figure (Saline: DTE
  1.4 GW contract). Otherwise it is left blank (Homer City 4.5 GW and Fermi 11 GW are generation).

## Needs your call
1. **Missing construction start.** 8 of the 16 projection-eligible rows have no stated
   construction start: Saline, Fairwater WI-2, Google Laramie, Google West Memphis, AWS Richmond,
   Montgomery, King George, and Wharton. `projection.py` needs that date. Options: use
   `announced_date` as a proxy, or leave these out of the 2030 curve.
2. **Capex that isn't campus capex.** Project Jupiter's $165B is the amount of the county bond.
   West Memphis's $4B includes some non-data-center spending. Saline's $7B comes from one secondary
   source only.
3. **Hyperion** is recorded at its full 5 GW and $50B, but Meta expects only 2 GW by 2030.
4. **Low-confidence rows:** Lordstown (operation disputed, may become manufacturing) and Fermi
   Matador (stalled, no tenant). Both are kept and flagged.

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
