# NASA Space Apps 2026 submission (paste-ready draft)

Each section below matches one field on the Space Apps project page, in the order the form asks for
them. Copy the text under each heading into that field. Every number comes from the live map
(https://acho5750.github.io/NASA_Deserto/) and the CSVs in `data/` named next to it; nothing here
is estimated beyond what the map shows.

Fill in before submitting (marked `[FILL IN]`): team name, team member names, the demo link
(the 7-slide deck), and your Local Event.

---

## Project Name

Data Centers & Water: what the radar sees, and what the money will build

## Team / challenge (for the slide deck and your records; the form fills these from your team page)

- Challenge: Dancing with the SARs
- Team name: [FILL IN]
- Team members: [FILL IN]

---

## High-Level Project Summary

We built an interactive map that uses satellite radar to see where data centers have already
turned land into campuses, which town water systems and rivers, lakes or aquifers those campuses
depend on, and how much water the campuses already announced could need by 2035. Sentinel-1 radar
measured 8,462 acres changed at 29 finished campuses since 2017, 6,888 of them not built on before
(farmland, shrubland, forest, wetland). NASA-ISRO NISAR, every 12 days since June 2026, shows
602 acres turning into buildings at 3 Stargate campuses still under construction, months ahead of
the newest aerial photos. We then linked each campus to its EPA water utility and source and
checked those sources with SWOT (river and lake levels), OPERA DISP-S1 and NISAR (ground sinking
over aquifers). Finally, we turned announced megawatts and dollars into land and water using what
the built campuses taught us: by 2035 the 46 campuses in the study would use the water of about
1.0 million people a year (range 193,000 to 1.8 million), and 5 small utilities would need to
supply more water to linked campuses than to all their customers today. It matters because these
decisions are announced years before the water is needed, and radar lets anyone check, from space,
whether the money is turning into buildings.

## Link to Project Demo

[FILL IN: public link to the 7-slide deck]

## Link to Final Project

- Live map: https://acho5750.github.io/NASA_Deserto/
- Code and data: https://github.com/acho5750/NASA_Deserto

---

## Detailed Project Description

### The problem

AI data centers are being announced faster than ever, often as single numbers: a gigawatt, ten
billion dollars. Those numbers are announced years before the buildings are finished and before
the water is needed, and the land and water they depend on are rarely in the same picture. Local
residents and planners usually learn what a campus means for their town's water only after it is
built. The challenge asked how SAR can show the downstream effects of infrastructure; we asked a
concrete version: how much land have data centers already converted, which water sources are they
linked to, and what does the money already announced turn into by 2035?

### What it does

The map covers 54 data center campuses (built and announced, from Epoch AI and company
announcements) and the 25 water sources they are linked to, told in four chapters.

1. **Land (Sentinel-1, 2017-2026).** For each of 29 finished campuses, radar shows the month each
   patch of ground first changed. Press Play and the campuses grow pixel by pixel while dated
   aerial photos swap in underneath. In total, 8,462 acres changed. Under those pixels, the
   pre-construction national land-cover map (NLCD) shows 2,578 acres of farmland, 2,648 of
   shrubland and grassland, 828 of forest, 576 of pasture, 79 of wetland and 1,574 already
   developed. Example: shrubland near Abilene, Texas became a 1,094-acre campus in about two years.
2. **NISAR now (2026).** NISAR launched in July 2025, after these campuses broke ground, so
   Sentinel-1 provides the "before" and NISAR the "now". We read every NISAR image of the 3
   campuses it covers (10 to 12 images each, one every 12 days) and mapped where the ground got
   more than 3 dB brighter: 315 acres at Vantage Frontier (Shackelford County, Texas), 286 acres
   at Project Jupiter (Doña Ana County, New Mexico) and 1 acre at Stargate Lordstown (Ohio), where
   the data center is going inside an existing factory and radar sees only its roof. The newest
   aerial photo of Project Jupiter (2025-09-21) still shows bare desert; NISAR shows the buildings.
3. **Water (EPA, SWOT, OPERA DISP-S1, NISAR).** Each campus is linked to the drinking-water
   utility whose EPA service area it sits in, followed to the seller when the utility buys its
   water, and then to the named river, lake or aquifer. We compare each campus's estimated water
   need with the utility's supply. Five utilities would need to supply more than their whole
   current supply to linked campuses by 2035 if the announced campuses are built, for example
   11x for Bell Milam Falls WSC (6,885 people, Lake Belton and Stillhouse Hollow Lake) and 9.2x
   for Camino Real Regional Utility Authority (21,930 people, Mesilla Bolson). SWOT gives river
   and lake level trends where it has at least 10 good passes (for example the Potomac River,
   falling 6.3 cm a year over 124 passes since 2023). Over 8 aquifers, OPERA DISP-S1 gives a
   2016-2026 ground-motion rate (for example West Memphis wells, sinking 14.1 mm a year) and NISAR
   adds June-October 2026; at the 5 aquifers where NISAR's record was clear enough to read, it
   shows no change larger than its noise yet. The map says "linked to", never "caused by": a trend
   describes the water body, not why it changed.
4. **2035.** Announced megawatts (or dollars, converted to megawatts) become land and water using
   rates measured at the built campuses, each in a low, middle and high scenario. By 2035 the 46
   campuses in the study would cover 28,598 acres (range 19,309 to 38,894), about 45 square
   miles, and use the water of about 1.0 million people a year (range 193,000 to 1.8 million). A
   separate dashed "what if the pace continues" line repeats the last two years' announcements
   (7,410 MW a year) and would add the water of 2.4 million more people; it is never added into
   the site values.

### How it works

- **F1, footprint from radar:** Sentinel-1 RTC from Microsoft Planetary Computer, converted to dB.
  A pixel counts as converted when VV or VH changes by more than a threshold (starting at 3 dB)
  against a 12-month baseline for at least 2 consecutive months; the threshold is raised in 0.5 dB
  steps when too much "change" shows up before construction began. Converted area over time is
  fitted with a logistic curve to get build speed.
- **NISAR:** L2 GCOV provisional HH images read with HTTP range requests from ASF; the first 3 and
  last 3 images of one track are averaged to calm speckle, and "much brighter" means over 3 dB.
  For aquifers, NISAR L2 GUNW 12-day interferogram pairs are chained, ionosphere-corrected, and a
  6 km window is compared with 40 km surroundings; a change only counts if it is larger than its
  noise.
- **F2-F4, from megawatts to water:** acres per MW, dollars per MW, build months and water per MW
  (Google's per-site reports) are measured at built campuses; missing MW is derived from capex.
- **F5, share:** campus water divided by the utility's supply (people served times the state's
  average use, USGS 2015), and a second share against the wholesale system for utilities that buy
  their water.
- **F6-F9:** source trend score, a pressure index, the build ramp toward the operation date, and
  the "if the pace continues" line.

Every number on the map traces to a CSV in `data/` with a source link, and every judgment call is
logged with its date and reason in `DECISIONS.md`.

### Benefits

- Anyone can check from space, every 12 days, whether announced money is turning into buildings,
  without waiting for aerial photos, permits or company reports.
- It puts land, water and investment in one picture, at the scale of the small town utility that
  actually serves the campus, rather than as national totals.
- It is open and reproducible: free satellite data, public EPA and USGS records, open code.

### What we hope to achieve

We want residents, local water boards and planners to see, before a campus is built, which water
source it would depend on and how large its need is next to the town's supply, so the questions
get asked while there is still time to plan. The same method extends to any new site as it is
announced, and to other large infrastructure such as power plants and chip factories.

### Tools, languages and software

Python (pandas, numpy, geopandas, shapely, pyproj, xarray, rasterio, h5py, stackstac,
pystac-client, planetary-computer, earthaccess, asf_search, requests, pillow, matplotlib);
JavaScript with MapLibre GL JS 4 over Esri World Imagery and Esri World Imagery Wayback; HTML/CSS;
GitHub Pages and GitHub Actions for hosting. No special hardware.

### Limits we state on the map

- Linked to is not caused by: we do not claim any data center caused a change in a water source.
- SWOT trends cover only the few years since 2023; NISAR covers only June-November 2026.
- The 2035 projection rests on few calibration sites (for example, dollars per MW from 6 sites),
  so every value is shown as low / middle / high.
- Sites with no matched utility stay in the land model but are left out of water shares.

---

## Use of Super Intelligence (SI)

(Not shown to judges; for data collection.)

Yes. We used Claude (Anthropic), through Claude Code, as a coding and writing assistant. The team
chose the question, the method and the formulas (F1-F9 in the README) and made every judgment call
logged in `DECISIONS.md`; Claude helped write and debug the Python pipeline and the map code, run
the data downloads, check numbers against the CSVs, and draft text, including this write-up and
the slide deck, which the team reviewed and edited. No SI-generated images, video or audio are
used: every picture on the map is satellite data or aerial photography. No SI was used to create
or modify NASA branding. This is also disclosed in the repository README.

---

## NASA Data

- **NISAR L2 GCOV (provisional), NASA-ISRO, via ASF DAAC:** HH radar backscatter every 12 days
  over the 3 Stargate campuses under construction (June-November 2026), used to map new buildings.
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
- [ ] Open https://acho5750.github.io/NASA_Deserto/ in a private window.
- [ ] Team name and member names are on the title slide.
- [ ] Optional: request a FortiGuard Web Filter Classification for the github.io site.
- [ ] Tick "Terms and Conditions" and "Confirm All Work is Original", then Submit for Judging
      before 11:59 p.m. local time of your Local Event (or the Team Owner's time zone for the
      Universal Event).
