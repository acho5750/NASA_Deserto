// Footprint engine (formula F1) for one site.
// Paste into the Earth Engine Code Editor: https://code.earthengine.google.com
// Output: monthly converted-acres curve for the campus, plus map layers to check by eye.
// For automation in Claude Code, port this to the Python earthengine-api (same calls).

// ---------- Inputs: replace for each site ----------
var siteName = 'TEST-SITE';
var campus = ee.Geometry.Polygon([[  // draw the campus outline, or paste one here
  [-97.000, 32.000], [-96.980, 32.000], [-96.980, 32.020], [-97.000, 32.020]
]]);
var constructionStart = ee.Date('2023-06-01'); // from Epoch's construction start date
var MONTHS_BEFORE = 24;   // history before construction start
var MONTHS_AFTER = 30;    // how long to follow the build
var THRESH_DB = 3;        // change threshold in dB; tune against Sentinel-2
var PASS = 'DESCENDING';  // keep one orbit direction for the whole series

// ---------- Sentinel-1 collection ----------
var aoi = campus.buffer(1000);
var start = constructionStart.advance(-MONTHS_BEFORE, 'month');
var end = constructionStart.advance(MONTHS_AFTER, 'month');

var s1All = ee.ImageCollection('COPERNICUS/S1_GRD')   // values are already in dB
  .filterBounds(aoi)
  .filterDate(start, end)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .filter(ee.Filter.eq('orbitProperties_pass', PASS));

// Keep the most frequent relative orbit so viewing geometry stays constant.
var hist = ee.Dictionary(s1All.aggregate_histogram('relativeOrbitNumber_start'));
var counts = hist.values();
var bestOrbit = ee.Number.parse(hist.keys().get(counts.indexOf(counts.reduce(ee.Reducer.max()))));
var s1 = s1All.filter(ee.Filter.eq('relativeOrbitNumber_start', bestOrbit)).select(['VV', 'VH']);
print('Images used', s1.size(), 'relative orbit', bestOrbit);

// ---------- Baseline: 12-month median before construction ----------
var baseline = s1.filterDate(constructionStart.advance(-12, 'month'), constructionStart)
  .median().clip(aoi);

// ---------- Monthly composites ----------
var nMonths = MONTHS_BEFORE + MONTHS_AFTER;
var monthly = ee.ImageCollection(ee.List.sequence(0, nMonths - 1).map(function (m) {
  var d0 = start.advance(m, 'month');
  var subset = s1.filterDate(d0, d0.advance(1, 'month'));
  return subset.median().clip(aoi)
    .set('system:time_start', d0.millis())
    .set('n_images', subset.size());
})).filter(ee.Filter.gt('n_images', 0));

// Flag pixels whose VV or VH moved more than THRESH_DB from baseline.
var flags = monthly.map(function (img) {
  return img.subtract(baseline).abs().gt(THRESH_DB)
    .reduce(ee.Reducer.max()).rename('flag')
    .copyProperties(img, ['system:time_start']);
}).sort('system:time_start');

// Persistence rule: changed this month AND last month (filters crop seasonality).
var flagList = flags.toList(flags.size());
var n = flagList.size();
var persistent = ee.List.sequence(1, n.subtract(1)).map(function (i) {
  i = ee.Number(i);
  var now = ee.Image(flagList.get(i));
  var prev = ee.Image(flagList.get(i.subtract(1)));
  return now.and(prev).copyProperties(now, ['system:time_start']);
});

// Cumulative footprint: once a pixel is converted, it stays converted.
var areaCurve = ee.FeatureCollection(ee.List.sequence(0, persistent.size().subtract(1)).map(function (i) {
  i = ee.Number(i);
  var current = ee.Image(persistent.get(i));
  var cumulative = ee.ImageCollection(persistent.slice(0, i.add(1))).max();
  var m2 = cumulative.multiply(ee.Image.pixelArea()).reduceRegion({
    reducer: ee.Reducer.sum(), geometry: aoi, scale: 10, maxPixels: 1e9
  }).values().get(0);
  return ee.Feature(null, {
    site: siteName,
    date: ee.Date(current.get('system:time_start')).format('YYYY-MM-dd'),
    t: current.get('system:time_start'),
    acres: ee.Number(m2).divide(4046.86)
  });
}));

// ---------- Outputs ----------
print(ui.Chart.feature.byFeature(areaCurve, 't', 'acres')
  .setOptions({title: siteName + ': converted acres', hAxis: {title: 'Date'}, vAxis: {title: 'Acres'}}));
// Acres before construction start are your noise floor. If that number is large, raise THRESH_DB.

Export.table.toDrive({
  collection: areaCurve, description: siteName + '_area_curve', fileFormat: 'CSV'
});

var lastCumulative = ee.ImageCollection(persistent).max();
Map.centerObject(campus, 14);
Map.addLayer(baseline.select('VV'), {min: -25, max: 0}, 'Baseline VV (dB)');
Map.addLayer(s1.filterDate(end.advance(-3, 'month'), end).median().select('VV').clip(aoi),
  {min: -25, max: 0}, 'Latest VV (dB)');
Map.addLayer(lastCumulative.selfMask(), {palette: ['ffaa00']}, 'Converted pixels');
Map.addLayer(ee.Image().paint(campus, 0, 2), {palette: ['00ffff']}, 'Campus outline');
