# NASA Space Apps 2026 submission (paste-ready draft)

Each section below matches one field on the Space Apps project page, in the order the form asks for
them. Copy the text under each heading into that field. Every number comes from the live map
(https://deserto-map.onrender.com/) and the CSVs in `data/` named next to it; nothing here
is estimated beyond what the map shows.

Team: Deserto (Andrew Cho, Nicholas Middelberg, Nathnael Haile).

---

## Project Name

Deserto: radar-tracking data centers and the water they depend on

## Team / challenge (for the slide deck and your records; the form fills these from your team page)

- Challenge: Dancing with the SARs
- Team name: Deserto
- Team members: Andrew Cho, Nicholas Middelberg, Nathnael Haile

---

## High-Level Project Summary

AI data centers are announced as single numbers, a gigawatt or ten billion dollars, years before
they are built and before anyone sees what they will mean for the land and the small town water
systems they depend on. We built an interactive map that uses satellite radar to close that gap.
Sentinel-1 radar measured 8,462 acres changed at 29 finished campuses since 2017, 6,888 of them
not built on before. NASA-ISRO's new NISAR radar, which sees through cloud every 12 days, shows
602 acres getting much brighter, the signature of new buildings and steel, at 3 Stargate campuses
still under construction, months ahead of the newest aerial photos. We linked each campus to its
water utility and river, lake or aquifer, checked those sources with SWOT, OPERA DISP-S1 and NISAR,
and turned announced investments into land and water: by 2035 the 46 campuses studied would use as
much water as about 1.0 million people use in a year (range 193,000 to 1.8 million), and, if built
as announced, 5 small utilities would need to supply more water to linked campuses than to all
their customers today.

## Link to Project Demo

7-slide deck (PDF): https://github.com/acho5750/NASA_Deserto/blob/main/docs/deck/Data_Centers_and_Water_deck.pdf

## Link to Final Project

https://deserto-map.onrender.com/#land

(Code and data: https://github.com/acho5750/NASA_Deserto)

---

## Detailed Project Description

(One text box on the form: paste the whole block below.)

Deserto is a four-chapter story map of 54 US data center campuses and the 25 water sources they are
linked to. 1) Land: for 29 finished campuses, Sentinel-1 radar (ESA) shows the month each patch of
ground changed since 2017; press Play to watch campuses grow as dated aerial photos swap in. Of the
8,462 acres that changed, the pre-construction NLCD land-cover map shows 2,578 acres of farmland,
2,648 of shrubland and grassland and 828 of forest. 2) NISAR now: we read every NISAR image of the
3 campuses it covers since June 2026 and mapped ground more than 3 dB brighter: 315 acres at Vantage
Frontier (Texas), 286 at Project Jupiter (New Mexico) and 1 at Lordstown (Ohio), which is going
inside an existing factory. 3) Water: each campus is linked through EPA records to its utility and
named source. SWOT tracks river and lake levels; OPERA DISP-S1 (2016-2026) and NISAR interferograms
(2026) track ground sinking over 8 aquifers. 4) 2035: announced megawatts and dollars become land and
water, in low, middle and high scenarios, using rates measured at the built campuses: 28,598 acres
and as much water as about 1.0 million people use in a year.

How it works: radar change detection against a 12-month baseline (F1), then per-MW rates for land,
cost and water (F2-F4), the campus's share of its utility's supply (F5), and a build ramp to 2035
(F8). Every number traces to a CSV with a source link, and every judgment call is logged in
DECISIONS.md. The map says "linked to", never "caused by".

Why it matters: residents and water boards can check from space, every 12 days, whether announced
money is turning into buildings, and see which water source a campus would depend on before it is
built. Built with Python (pandas, xarray, rasterio, geopandas, earthaccess, asf_search), JavaScript
with MapLibre GL, and free NASA, ESA, EPA and USGS data.

---

## Use of Super Intelligence (SI)

(Not shown to judges; for data collection.)

Yes. We used Claude (Anthropic), through Claude Code, as a coding and writing assistant. The team
chose the question, the method and the formulas (F1-F9 in the README) and made every judgment call
logged in `DECISIONS.md`; Claude helped write and debug the Python pipeline and the map code, run
the data downloads, check numbers against the CSVs, and draft text, including this write-up and
the slide deck, which the team reviewed and edited. No SI-generated images, video or audio are
used: every picture on the map is satellite data or aerial photography. No SI was used to create
or modify NASA branding. This is also disclosed in the "Use of AI" section of the repository README.

---

## NASA Data

- **NISAR L2 GCOV (provisional), NASA-ISRO, via ASF DAAC:** HH radar backscatter every 12 days
  over the 3 Stargate campuses under construction (June-November 2026), used to map where the ground got much brighter (new buildings and steel).
  https://search.asf.alaska.edu · https://nisar-docs.asf.alaska.edu/availability-overview/
- **NISAR L2 GUNW (interferograms), via ASF DAAC:** chained 12-day pairs over 8 aquifer water
  sources, to check for ground sinking (`data/water/gunw/gunw_summary.csv`).
  https://cmr.earthdata.nasa.gov/search/concepts/C3622247503-ASF.html
- **OPERA L3 DISP-S1 (JPL OPERA, from Sentinel-1), via ASF DAAC:** 2016-2026 ground motion over
  aquifer sources. https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-v1-1
- **SWOT L2 HR river and lake products, via PO.DAAC Hydrocron:** water level trends for the
  rivers and lakes campuses are linked to. https://podaac.github.io/hydrocron/intro.html ·
  https://podaac.jpl.nasa.gov/dataset/SWOT_L2_HR_LakeSP_D
- **NASA Earthdata (CMR search, Earthdata Login)** to find and access all of the above.

## Space Agency Partner Data and Other References

Space Agency Partner data:
- **ESA / Copernicus Sentinel-1** radar (RTC product hosted by Microsoft Planetary Computer):
  the 2017-2026 land-change measurement at every campus, and the "before" for the NISAR campuses.
  https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc
- **ISRO**, as NASA's partner on NISAR (S-band and L-band mission; we used the L-band products).

Other data:
- Epoch AI Frontier Data Centers database (sites, MW, capex, dates): https://epoch.ai/data/data-centers
- PNNL IM3 data center atlas: https://im3.pnnl.gov/datacenter-atlas
- Company and government announcements for each announced campus (links per row in
  `data/announced_sites.csv` and `data/precedent_capex.csv`)
- US EPA Public Water System Service Areas:
  https://www.epa.gov/ground-water-and-drinking-water/public-water-system-service-areas
- US EPA ECHO Safe Drinking Water Act data: https://echo.epa.gov/tools/data-downloads#dwdownloads
- Utility water quality reports (CCRs) naming each source (links in `data/water/source_assignments.csv`)
- USGS 2015 water use estimates (per-person public supply): https://www.usgs.gov/mission-areas/water-resources/science/water-use-united-states
- Google 2026 Environmental Report (per-site data center water use):
  https://sustainability.google/reports/google-2026-environmental-report/
- WRI Aqueduct water stress: https://www.wri.org/aqueduct
- USGS/MRLC NLCD land cover: https://www.mrlc.gov/data
- USFWS National Wetlands Inventory: https://www.fws.gov/program/national-wetlands-inventory
- USGS PAD-US 4.1 protected areas: https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview
- OpenStreetMap campus outlines (© OpenStreetMap contributors, ODbL)
- Esri World Imagery and World Imagery Wayback (dated aerial photos, map background)

Tools and code: MapLibre GL JS (BSD-3), Python open-source libraries listed above, GitHub Pages.
All of our own code is in https://github.com/acho5750/NASA_Deserto. No copyrighted material is
used beyond the attributed basemap imagery under its terms of use.

---

## Before you press "Submit for Judging"

- [ ] Paste the demo link and check it opens in a private browser window with no login.
- [ ] Open https://deserto-map.onrender.com/#land in a private window.
- [ ] Team name and member names are on the title slide.
- [ ] Optional: request a FortiGuard Web Filter Classification for the onrender.com site.
- [ ] Tick "Terms and Conditions" and "Confirm All Work is Original", then Submit for Judging
      before 11:59 p.m. local time of your Local Event (or the Team Owner's time zone for the
      Universal Event).
