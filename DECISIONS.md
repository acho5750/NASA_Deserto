# Decisions

Log of judgment calls. Newest first within each date. Format: date, decision, reason.

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
