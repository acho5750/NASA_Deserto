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

One row per resource on the form: copy the Link Text box, then the Link Url box. Each row is the
parent page for something we used (for example, the NISAR row covers both NISAR products). Every
URL was checked and opens without a login.

1. Link Text:

   ```
   NASA-ISRO NISAR mission
   ```

   Link Url:

   ```
   https://science.nasa.gov/mission/nisar/
   ```

2. Link Text:

   ```
   NISAR data at NASA's Alaska Satellite Facility DAAC
   ```

   Link Url:

   ```
   https://nisar-docs.asf.alaska.edu/
   ```

3. Link Text:

   ```
   OPERA DISP-S1 ground displacement (NASA JPL OPERA)
   ```

   Link Url:

   ```
   https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-v1-1
   ```

4. Link Text:

   ```
   SWOT water levels at NASA PO.DAAC
   ```

   Link Url:

   ```
   https://podaac.jpl.nasa.gov/SWOT
   ```

5. Link Text:

   ```
   NASA Earthdata
   ```

   Link Url:

   ```
   https://www.earthdata.nasa.gov/
   ```

## Space Agency Partner & Other Data

Includes partner agency data, other data, code, tools, and the AI tool used.

1. Link Text:

   ```
   ESA Copernicus Sentinel-1
   ```

   Link Url:

   ```
   https://sentinels.copernicus.eu/copernicus/sentinel-1
   ```

2. Link Text:

   ```
   Sentinel-1 RTC on Microsoft Planetary Computer
   ```

   Link Url:

   ```
   https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc
   ```

3. Link Text:

   ```
   Epoch AI Frontier Data Centers database
   ```

   Link Url:

   ```
   https://epoch.ai/data/data-centers
   ```

4. Link Text:

   ```
   US EPA drinking water data (water system service areas, SDWA records)
   ```

   Link Url:

   ```
   https://www.epa.gov/ground-water-and-drinking-water
   ```

5. Link Text:

   ```
   USGS Estimated Use of Water in the United States, 2015
   ```

   Link Url:

   ```
   https://doi.org/10.5066/F7TB15V5
   ```

6. Link Text:

   ```
   USGS National Land Cover Database (NLCD)
   ```

   Link Url:

   ```
   https://www.mrlc.gov/data
   ```

7. Link Text:

   ```
   USGS PAD-US 4.1 protected areas
   ```

   Link Url:

   ```
   https://edits.nationalmap.gov/arcgis/rest/services/PAD-US/PAD_US_4_1/MapServer
   ```

8. Link Text:

   ```
   USFWS National Wetlands Inventory
   ```

   Link Url:

   ```
   https://www.fws.gov/program/national-wetlands-inventory
   ```

9. Link Text:

   ```
   WRI Aqueduct 4.0 water stress
   ```

   Link Url:

   ```
   https://www.wri.org/data/aqueduct-global-maps-40-data
   ```

10. Link Text:

   ```
   Google 2026 Environmental Report (data center water use)
   ```

   Link Url:

   ```
   https://sustainability.google/reports/google-2026-environmental-report/
   ```

11. Link Text:

   ```
   OpenStreetMap (campus outlines)
   ```

   Link Url:

   ```
   https://www.openstreetmap.org/copyright
   ```

12. Link Text:

   ```
   Esri World Imagery and Wayback aerial photos
   ```

   Link Url:

   ```
   https://livingatlas.arcgis.com/wayback/
   ```

13. Link Text:

   ```
   MapLibre GL JS
   ```

   Link Url:

   ```
   https://maplibre.org/
   ```

14. Link Text:

   ```
   Python open-source libraries (list in requirements.txt)
   ```

   Link Url:

   ```
   https://github.com/acho5750/NASA_Deserto/blob/main/requirements.txt
   ```

15. Link Text:

   ```
   Claude Code (AI coding assistant, Anthropic)
   ```

   Link Url:

   ```
   https://claude.com/product/claude-code
   ```

16. Link Text:

   ```
   Render (website hosting)
   ```

   Link Url:

   ```
   https://render.com/
   ```

17. Link Text:

   ```
   Deserto source code and data (GitHub)
   ```

   Link Url:

   ```
   https://github.com/acho5750/NASA_Deserto
   ```

---

## Before you press "Submit for Judging"

- [ ] Paste the demo link and check it opens in a private browser window with no login.
- [ ] Open https://deserto-map.onrender.com/#land in a private window.
- [ ] Team name and member names are on the title slide.
- [ ] Optional: request a FortiGuard Web Filter Classification for the onrender.com site.
- [ ] Tick "Terms and Conditions" and "Confirm All Work is Original", then Submit for Judging
      before 11:59 p.m. local time of your Local Event (or the Team Owner's time zone for the
      Universal Event).
