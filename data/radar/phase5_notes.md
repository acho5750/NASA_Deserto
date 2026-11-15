# Phase 5: NISAR L-band next to Sentinel-1 C-band at three construction sites

Run 2026-11-15. All numbers below come from the CSVs in this folder, `data/footprint/` and
`data/water/gunw/`; every row there carries its source link.

## In plain words

Radar satellites send microwaves down and measure how much bounces back. Flat bare ground sends
most of the signal away, so it looks dark. Buildings, steel frames and piles of material bounce it
straight back, so they look bright. When a field turns into a data center, the spot gets brighter.

- **Vantage Frontier (Texas)** and **Project Jupiter (New Mexico)** got much brighter as they were
  built. Sentinel-1 shows it from the start (it has been flying since 2014). NISAR started taking
  pictures here in 2025, and from June 2026 it shows the same buildings rising, in sharper and
  steadier pictures.
- **Stargate Lordstown (Ohio)** barely changes, because most of the work is inside an old factory
  building. Radar sees roofs, not what happens under them.
- Under **Project Jupiter's water source**, the Mesilla Bolson aquifer, NISAR measured how much the
  ground moved from June to October 2026. Any movement was smaller than the measurement can detect
  (about 1 cm). That fits the Sentinel-1 record, which shows only about 2 mm per year.

## Sites, outlines and dates

| Site | Outline | Construction start (Epoch) | Sentinel-1 orbit | NISAR chart stack |
|---|---|---|---|---|
| Vantage Frontier, Shackelford Co. TX | hand-drawn on Sentinel-2 2026-10-08, 1,440 ac (no OSM object within 8 km) | 2025-08-01 | ascending 5 | track 163 A, frame 18 |
| Project Jupiter, Dona Ana Co. NM | OSM way/1476734418 "Project Jupiter", 613 ac (graded land west of it is outside OSM's outline) | 2025-10-01 | descending 56 | track 48 A, frame 17 |
| Stargate Lordstown, OH | OSM way/473431363 "Stargate Project", 43 ac (the existing plant building) | 2025-10-12 | ascending 77 | track 90 A, frame 22 |

Outlines are recorded in `data/footprint/campus_outlines.csv`. Another thread is fixing the
announced-site coordinates in `data/announced_sites.csv` in parallel; this phase uses its own
outlines and does not change the registry.

## Results

**Brightness inside the campus outline** (`data/radar/s1_series.csv`, `data/radar/nisar_series.csv`;
mean of linear gamma0 inside the outline, in dB).

| Site | Sentinel-1 VV / VH: 12 months before start -> last 3 dates | Sentinel-1 VV / VH, same span as NISAR | NISAR HH / HV, first -> last date (Jun to Oct/Nov 2026) |
|---|---|---|---|
| Frontier | -13.2 -> -4.0 (+9.2) / -19.7 -> -13.7 (+6.0) | +1.4 / +1.7 | +1.5 / +1.6 |
| Jupiter | -13.7 -> -5.3 (+8.4) / -19.2 -> -14.2 (+5.0) | +2.8 / +2.8 | +3.5 / +2.9 |
| Lordstown | +10.3 -> +10.8 (+0.5) / -4.4 -> -4.2 (+0.2) | +0.4 / 0.0 | +0.2 / -0.6 |

The NISAR columns compare the first two and last two dates of the chart stack with the
Sentinel-1 dates within 14 days of them.

**Converted land (F1, Sentinel-1)** (`data/footprint/footprint_summary.csv`, outline + 200 m):

| Site | Converted acres by Nov 2026 | Threshold | Flags |
|---|---|---|---|
| Frontier | 1,033 | 4.5 dB | curve_not_saturated (still growing) |
| Jupiter | 453 | 5.0 dB | noise_floor_above_5pct_at_max_threshold; curve_not_saturated |
| Lordstown | 24 | 5.0 dB | noise_floor_above_5pct_at_max_threshold; curve_not_saturated |

Vantage reports a 1,200-acre campus at Frontier; the 1,033 acres are within that. At Jupiter, OSM's
outline covers only part of the reported ~1,400-acre campus, so 453 acres is a lower bound. None of
these curves has levelled off yet, so no `a_max_acres` is written to any registry.

**Images for the map** (`map/img/`):
- `<site>_radar.png`: Sentinel-1 VV, median of the 12 months before construction vs the last months.
  This is the pre-construction baseline. NISAR has no data from before construction at any of the
  three sites (its first GCOV here is from late October 2025).
- `<site>_nisar.png`: NISAR HH (top) and HV (bottom), first vs latest date of the chart stack.
- `<site>_timeseries.png`: campus brightness over time, Sentinel-1 panel above NISAR panel.
- `WB-MESILLA_ground_motion.png`: ground motion over Project Jupiter's aquifer, DISP-S1 and NISAR.

The images are not yet placed in `map/index.html`. Their captions are map copy, and map copy goes to
the person for review.

## Calibration: provisional vs final NISAR products

NISAR GCOV from June to 2026-10-21 exists only as the provisional product (version 1.0.11). From
2026-10-22 on, only the final product (1.0.20) exists. No date has both, so the check compares the
reference ring (500 m to 1.5 km outside each outline, mostly untouched land) just before and just
after the switch, on every NISAR stack (`data/radar/nisar_calibration.csv`):

- Median step across the 10 stacks: **-0.28 dB (HH)** and **-0.19 dB (HV)**. The tolerance was set
  at 0.5 dB before looking, so the two versions are mixed in the charts.
- On 9 of 10 stacks the step is smaller than the normal change from one date to the next. The
  exception is Lordstown track 18 HH (-0.88 dB, twice its normal change). All four Lordstown stacks
  step down, which fits autumn leaf fall in Ohio as much as a calibration change. A date that exists
  in both versions would settle it; ASF has not reprocessed the older dates yet.

## Ground motion over the aquifer (NISAR GUNW)

Source: `data/sources.csv` row SRC-NM3502507, Mesilla Bolson (Santa Teresa), which supplies the
utility matched to Project Jupiter. Same 6 km window centre as its DISP-S1 trend.

- NISAR L2 GUNW (provisional), track 48 frame 17: 9 back-to-back 12- to 24-day pairs, 2026-06-17 to
  2026-10-15 (`data/water/gunw/gunw_WB-MESILLA_48_17.csv`). Ionosphere phase screen subtracted;
  each pair referenced to the median of a 40 km box around the window.
- Total line-of-sight change: **+2.1 mm in 120 days**. Without the ionosphere correction it is
  -3.1 mm. The pair-to-pair spread is 3.0 mm, so summing 9 pairs has an uncertainty of about 9 mm
  (3.0 x sqrt 9). **No motion is detected.**
- The DISP-S1 trend for the same window is -2.36 mm/yr (2016-07 to 2026-04), so about -0.8 mm would
  be expected over these four months. That is far below what 12-day L-band pairs can resolve.
  DISP-S1 has no data after 2026-04-16, so the two do not overlap in time.
- The NISAR line looks much smoother than DISP-S1 in the chart. Part of that is the reference:
  NISAR is measured against a 40 km box nearby, DISP-S1 against the frame's single reference point
  much farther away. Do not read the difference as L-band alone.

None of this says the data center changed the aquifer. It shows what the radar measured over the
water source the campus depends on.

## What L-band shows that C-band doesn't

Sentinel-1's C-band waves are 5.6 cm long. They bounce off anything about that size or bigger:
leaves, gravel, loose dirt, rough wet soil. So C-band lights up as soon as the ground is disturbed,
and it also flickers when rain falls or crops grow. NISAR's L-band waves are about 24 cm long. They
pass through leaves and slip over small stones and loose dirt. They bounce back mostly from big,
solid things: steel frames, walls, tree trunks, the ground under vegetation. That makes L-band better
at telling "a building is going up here" from "the soil was scraped". It also keeps its interference
pattern (coherence) over grass and disturbed ground for longer, which is what lets it measure
millimetre ground motion where C-band loses the signal.

In these data, both bands saw the Texas and New Mexico campuses brighten by similar amounts from
June to November 2026. NISAR's HH brightness jumped around less from one date to the next than
Sentinel-1's VV: 0.3 to 0.5 dB, against about 1.1 dB. The cross-polarised channels (HV and VH) were
about equally steady in both. Both missed Lordstown, where the work is under a
roof. One caution: L-band is more disturbed by the ionosphere, which is why the GUNW products carry
a correction layer. At Mesilla that correction changed the four-month total by 5 mm.

## Also worth noting
- At Jupiter, Sentinel-1 brightens in July to October 2025, before Epoch's construction start
  (2025-10-01) and around the groundbreaking reported in the registry (September 2025). This looks
  like early ground work. It is an observation, not a change to any date.

## Reproduce
```
python pipeline/campus_outline.py build --site-id JUPITER-DONAANA --osm way/1476734418
python pipeline/campus_outline.py build --site-id LORDSTOWN --osm way/473431363
python pipeline/footprint.py --site-id FRONTIER-SHACKELFORD --campus data/footprint/FRONTIER-SHACKELFORD_campus.geojson \
    --construction-start 2025-08-01 --months-after 16 --radar-png map/img/FRONTIER-SHACKELFORD_radar.png   # same for the others
python pipeline/radar_showcase.py        # NISAR + Sentinel-1 series, calibration, images (~20 min)
python pipeline/gunw_aquifer.py          # NISAR GUNW over the Mesilla Bolson (~5 min)
```
