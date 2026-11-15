# NISAR GCOV coverage over active construction sites (Phase 5)

Checked 2026-11-15. Window: acquisitions starting 2026-06-01 through 2026-11-15.

Files
- `data/nisar_coverage_sites.csv`: the 3 sites, their coordinates and where each coordinate and
  construction claim comes from.
- `data/nisar_gcov_coverage.csv`: one row per GCOV granule (110 rows), with CMR metadata, a pixel
  check over the site, `usable`, and the CMR record (`source`) and HDF5 link (`download_url`).
- `pipeline/nisar_coverage.py`: rebuilds the CSV (`python pipeline/nisar_coverage.py`, about 10
  minutes; reads about 10-25 MB per granule with HTTP Range requests and writes nothing to disk).

## Result

All three sites have usable dual-pol (HH + HV) NISAR GCOV acquisitions every 12 days from June 2026
on, on two to four tracks each. Of the 107 distinct acquisitions, 105 pass the pixel check.

| Site | Tracks (frame) | Distinct acquisitions | Usable | First / last usable | Notes |
|---|---|---|---|---|---|
| Vantage Frontier, Shackelford Co. TX | 142 D (72), 163 A (18) | 19 | 19 | 2026-06-24 / 2026-10-23 | 9 dates on 142 D, 10 on 163 A |
| Project Jupiter, Dona Ana Co. NM | 48 A (17, 18), 99 D (72, 73), 120 A (18) | 48 (33 track-dates) | 46 | 2026-06-17 / 2026-11-08 | site sits in the overlap of two frames on tracks 48 and 99; every track-date has at least one usable frame |
| Stargate Lordstown, OH | 18 A (22), 26 D (68), 90 A (22), 127 D (68) | 40 | 40 | 2026-06-20 / 2026-11-06 | 26 D has a gap from 2026-06-28 to 2026-08-15 |

"Distinct acquisitions" counts one granule per track, frame and start time; 3 extra products of
the same acquisitions are kept in the CSV and marked in `duplicate_of`.

## What "usable" means here
Frequency A has both HH and HV, at least 90% of a 51 x 51 pixel window (510 m at 10 m posting)
centred on the site has finite positive backscatter, no pixel has an input-data anomaly bit set,
and the product is not in diagnostic mode. Failures:
- Jupiter 2026-06-17, track 48 frame 18: site at the frame edge, 10% of the window valid. Frame 17
  of the same pass is fully valid.
- Jupiter 2026-10-19, track 99 frame 72: 37% valid. Frame 73 of the same pass is fully valid.
- Lordstown 2026-09-07, track 18: the first product (`_001`) has HH only. ASF also has a
  reprocessed `_002` with HH + HV, which is fully valid and is the one counted.

## Product details that matter for Phase 2
- **Polarization.** Every counted acquisition has HH + HV on frequency A (40 MHz, 10 m posting)
  and HH + HV on frequency B (5 MHz). No acquisition here is single-pol, apart from the replaced
  Lordstown `_001`.
- **Two product versions.** June to 2026-10-21 is only in `NISAR_L2_GCOV_PROVISIONAL_V1` (product
  version 1.0.11, release P05023). From 2026-10-22 granules are in `NISAR_L2_GCOV_V1` (1.0.20,
  release P05036). V1 has not been backfilled for earlier dates. Check that the calibration of the
  two versions matches before putting them in one time series.
- **Bandwidth on Frontier track 142.** On 2026-08-11 and 2026-10-22 ASF has both a 40 MHz partial
  frame and a 20 MHz full frame. Both cover the site fully; the 40 MHz copy is counted so the
  stack stays at 10 m.
- **Missing cycles.** Cycle 027 (early August 2026; the only cycle-027 granules here are
  Frontier's on 2026-08-11 and 2026-08-12) is missing on every Jupiter and Lordstown track. Other
  gaps: Frontier 142 D misses 025-026, 163 A misses 026; Jupiter 120 A misses 026; Lordstown
  127 D misses 026, 26 D misses 025-026. So most tracks have one 24- to 36-day gap in
  July-August, and Lordstown 26 D a 48-day gap.
- **Urgent-observation flag.** 3 granules have `isUrgentObservation = True` (Jupiter 2026-11-08,
  Lordstown 2026-10-21 and 2026-11-02). Their pixels pass the check; the flag is kept in the CSV.
- **Units.** GCOV values are linear gamma0 (RTC), so the same 10*log10 step as the Sentinel-1 path
  applies before any dB threshold. The `median_*_db` columns already apply it.

## No NISAR pre-construction baseline
The earliest GCOV over any of the three sites is in `NISAR_L2_GCOV_BETA_V1`, from 2025-10-24
(Jupiter), 2025-10-26 (Lordstown) and 2025-10-27 (Frontier). Construction had already started
(Frontier 2025-08-01, Jupiter 2025-10-01, Lordstown land clearing 2025-10-12, per Epoch). So NISAR
can track construction from late 2025 on, but the F1 pre-construction baseline for these sites
must come from Sentinel-1.

## First look, not an F1 result
At Frontier the median HH in the window rises over the period on both tracks: from -9.67 dB
(2026-06-24) to -5.30 dB (2026-10-10) on 142 D, and from -10.38 dB (2026-06-25) to -7.88 dB
(2026-10-11) on 163 A. That fits Epoch's note that building shells were completed by 2026-09-04,
but the window is centred on an aggregator's campus point, not a surveyed outline, so it is not a
measured land conversion. Jupiter and Lordstown windows show no comparable trend.

## Caveats
- Coordinates. Frontier and Jupiter use Baxtel's campus points (a third-party aggregator); the
  Lordstown point is the US Census geocode of Epoch's street address. All three replace town or
  county centroids in `data/announced_sites.csv` (PR 5) for this check only; the registry is not
  changed. Phase 2 should replace them with campus outlines.
- Lordstown is mostly construction inside and next to existing industrial buildings (Epoch
  2026-02-27: "construction within preexisting facilities"), so it is a weaker test of land
  conversion than the two greenfield Texas and New Mexico sites.
- The BETA collection has no granules over these sites after 2026-06-01.

## Sources
- CMR granule search (public): https://cmr.earthdata.nasa.gov/search/granules.umm_json
  - NISAR_L2_GCOV_V1 https://cmr.earthdata.nasa.gov/search/concepts/C3622241360-ASF.html
  - NISAR_L2_GCOV_PROVISIONAL_V1 https://cmr.earthdata.nasa.gov/search/concepts/C2854338529-ASF.html
  - NISAR_L2_GCOV_BETA_V1 https://cmr.earthdata.nasa.gov/search/concepts/C3622214170-ASF.html
- Granule HDF5 files: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/ (Earthdata login), per row in
  `download_url`.
- Construction status: Epoch AI, https://epoch.ai/data/data_centers/data_center_timelines.csv (CC BY 4.0).
- Coordinates: per row in `data/nisar_coverage_sites.csv`.
