window.RADAR_PANELS = [
 {
  "id": "FRONTIER-SHACKELFORD",
  "kind": "site",
  "name": "Vantage Frontier (Stargate Shackelford County)",
  "lat": 32.54331,
  "lon": -99.54679,
  "caption": "Sentinel-1 radar brightness inside the campus outline rose: -13.2 dB in the 12 months before construction began (Aug 2025), -4.0 dB on the latest dates (to 03 Nov 2026). NISAR L-band brightness changed by +1.5 dB between 25 Jun and 23 Oct 2026. Bright means a strong echo, from buildings, steel and equipment. Sentinel-1 counts about 1,030 acres of changed land inside the outline plus 200 m.",
  "source": "data/radar/s1_series.csv ; data/radar/nisar_series.csv ; data/footprint/footprint_summary.csv ; https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc ; https://cmr.earthdata.nasa.gov/search/concepts/C2854338529-ASF.html ; https://cmr.earthdata.nasa.gov/search/concepts/C3622241360-ASF.html ; https://epoch.ai/data/data_centers/data_center_timelines.csv",
  "images": [
   "img/FRONTIER-SHACKELFORD_radar.png",
   "img/FRONTIER-SHACKELFORD_nisar.png",
   "img/FRONTIER-SHACKELFORD_timeseries.png"
  ]
 },
 {
  "id": "JUPITER-DONAANA",
  "kind": "site",
  "name": "Project Jupiter (Stargate Dona Ana County)",
  "lat": 31.8184,
  "lon": -106.66557,
  "caption": "Sentinel-1 radar brightness inside the campus outline rose: -13.7 dB in the 12 months before construction began (Oct 2025), -5.3 dB on the latest dates (to 06 Nov 2026). NISAR L-band brightness changed by +3.5 dB between 17 Jun and 08 Nov 2026. Bright means a strong echo, from buildings, steel and equipment. Sentinel-1 counts about 450 acres of changed land inside the outline plus 200 m. The outline covers only part of the campus, so the acres are a lower bound.",
  "source": "data/radar/s1_series.csv ; data/radar/nisar_series.csv ; data/footprint/footprint_summary.csv ; https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc ; https://cmr.earthdata.nasa.gov/search/concepts/C2854338529-ASF.html ; https://cmr.earthdata.nasa.gov/search/concepts/C3622241360-ASF.html ; https://epoch.ai/data/data_centers/data_center_timelines.csv",
  "images": [
   "img/JUPITER-DONAANA_radar.png",
   "img/JUPITER-DONAANA_nisar.png",
   "img/JUPITER-DONAANA_timeseries.png"
  ]
 },
 {
  "id": "LORDSTOWN",
  "kind": "site",
  "name": "Stargate Lordstown",
  "lat": 41.14639,
  "lon": -80.87771,
  "caption": "Sentinel-1 radar brightness inside the campus outline changed little: 10.2 dB in the 12 months before construction began (Oct 2025), 10.8 dB on the latest dates (to 07 Nov 2026). NISAR L-band brightness changed by +0.2 dB between 20 Jun and 30 Oct 2026. Bright means a strong echo, from buildings, steel and equipment. Sentinel-1 counts about 20 acres of changed land inside the outline plus 200 m. Most of the work here is inside an existing plant building; radar sees the roof, not the inside.",
  "source": "data/radar/s1_series.csv ; data/radar/nisar_series.csv ; data/footprint/footprint_summary.csv ; https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc ; https://cmr.earthdata.nasa.gov/search/concepts/C2854338529-ASF.html ; https://cmr.earthdata.nasa.gov/search/concepts/C3622241360-ASF.html ; https://epoch.ai/data/data_centers/data_center_timelines.csv",
  "images": [
   "img/LORDSTOWN_radar.png",
   "img/LORDSTOWN_nisar.png",
   "img/LORDSTOWN_timeseries.png"
  ]
 },
 {
  "id": "WB-MESILLA",
  "kind": "aquifer",
  "name": "Mesilla Bolson (Santa Teresa)",
  "lat": 31.8536,
  "lon": -106.67598,
  "caption": "Ground motion over a 6 km x 6 km area of the Mesilla Bolson (Santa Teresa) aquifer. NISAR L-band, 17 Jun to 15 Oct 2026: no motion above about 1 cm detected (measured +2.1 mm, uncertainty about 9 mm). Sentinel-1 (OPERA DISP-S1), 2016 to 2026: -2.4 mm per year along the satellite's line of sight.",
  "source": "data/water/gunw/gunw_WB-MESILLA_48_17.csv ; data/sources.csv ; https://cmr.earthdata.nasa.gov/search/concepts/C2854335566-ASF.html ; https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-v1-1",
  "images": [
   "img/WB-MESILLA_ground_motion.png"
  ]
 }
];
