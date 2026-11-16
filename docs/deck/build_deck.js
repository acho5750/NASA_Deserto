const pptxgen = require('pptxgenjs');
const { applyTheme } = require(process.env.APPLY_THEME || './apply_theme.js');
const THEME = { name: 'Deserto', headFontFace: 'Calibri', bodyFontFace: 'Calibri',
  colors: { dk1:'1F1D1A', lt1:'FFFFFF', dk2:'5E584E', lt2:'F6F2E9', accent1:'7B2FBE', accent2:'8E2A1F', accent3:'2F6F8F', accent4:'B07A2A', accent5:'EAE3D4', accent6:'4F7A4A', hlink:'7B2FBE', folHlink:'5E2A8E' } };
const pres = new pptxgen(); pres.layout = 'LAYOUT_WIDE'; pres.theme = { headFontFace:'Calibri', bodyFontFace:'Calibri' };
pres.title = 'Deserto'; pres.author = 'NASA Space Apps 2026 team';
const C = pres.SchemeColor;
const W = 13.333, H = 7.5, M = 0.6;
const LINK = 'acho5750.github.io/NASA_Deserto';
pres.defineSlideMaster({ title:'Title', background:{ color: THEME.colors.lt2 }, objects:[] });
pres.defineSlideMaster({ title:'Content', background:{ color: THEME.colors.lt2 },
  objects:[ { placeholder:{ options:{ name:'title', type:'title', x:M, y:0.45, w:W-2*M, h:0.85, fontSize:34, bold:true, color:C.text1, valign:'top', align:'left', margin:0 }, text:'' } },
            { text:{ text:'Deserto  ·  NASA Space Apps 2026  ·  '+LINK, options:{ x:M, y:H-0.45, w:9, h:0.3, fontSize:10, color:C.text2, margin:0 } } } ],
  slideNumber:{ x:W-M-0.5, y:H-0.45, w:0.5, h:0.3, fontSize:10, color:C.text2, align:'right' } });
const tb = (s, text, o) => s.addText(text, Object.assign({ isTextBox:true, margin:0, fontSize:16, color:C.text1, valign:'top' }, o));
const card = (s, x, y, w, h, fill) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius:0.12, fill:{ color: fill || C.background1 }, line:{ color:'E2DACA', width:0.75 } });
const pill = (s, x, y, w, text, color) => { s.addShape(pres.shapes.ROUNDED_RECTANGLE,{x,y,w,h:0.32,rectRadius:0.16,fill:{color},line:{color}}); tb(s,text,{x,y,w,h:0.32,fontSize:13,bold:true,color:C.background1,align:'center',valign:'middle'}); };
const PURPLE = C.accent1, RED = C.accent2;

// 1 Title
pres.addSection({ title:'Title' });
let s = pres.addSlide({ masterName:'Title', sectionTitle:'Title' });
s.addImage({ path:'title_map2.jpg', x:6.35, y:0, w:6.983, h:7.5, altText:'Map of US data center campuses in 2035, from the project' });
tb(s, '2026 NASA Space Apps Challenge  ·  Dancing with the SARs', { x:M, y:0.75, w:5.5, h:0.3, fontSize:14, bold:true, color:PURPLE });
tb(s, 'Deserto', { x:M, y:1.2, w:5.5, h:1.0, fontSize:54, bold:true });
tb(s, 'Radar-tracking data centers and the water they depend on', { x:M, y:2.35, w:5.4, h:0.9, fontSize:22, color:C.text2 });
tb(s, 'Radar satellites show the land AI data centers have converted, and which towns’ water each campus will depend on.', { x:M, y:3.55, w:5.3, h:0.8, fontSize:16 });
card(s, M, 4.8, 5.3, 1.35);
tb(s, [ {text:'Team  ', options:{bold:true,color:C.text2}}, {text:'Deserto', options:{breakLine:true}},
        {text:'Members  ', options:{bold:true,color:C.text2}}, {text:'Andrew Cho, Nicholas Middelberg, Nathnael Haile', options:{breakLine:true}},
        {text:'Live map  ', options:{bold:true,color:C.text2}}, {text:LINK, options:{hyperlink:{url:'https://'+LINK}, color:PURPLE}} ],
   { x:M+0.2, y:4.95, w:5.0, h:1.1, fontSize:14, paraSpaceAfter:4 });
s.addNotes('Title. Fill in team name and member names before submitting.');

// 2 Problem
pres.addSection({ title:'Problem' });
s = pres.addSlide({ masterName:'Content', sectionTitle:'Problem' });
s.addText('AI data centers are going up fast, and most people can’t see it', { placeholder:'title' });
const stats = [['54','data center campuses tracked: 30 built, 24 announced'],['8,462','acres of land changed at 29 built campuses since 2017'],['5','town water utilities would need to supply more to linked campuses by 2035 than to all their customers today, if the announced campuses are built']];
stats.forEach((st,i)=>{ const y=1.6+i*1.35; tb(s, st[0], {x:M,y,w:2.1,h:0.8,fontSize:44,bold:true,color: i==2?RED:C.text1}); tb(s, st[1], {x:M+2.0,y:y+0.1,w:3.5,h:1.2,fontSize:15,color:C.text1}); });
s.addImage({ path:'abilene.png', x:6.55, y:1.55, w:6.18, h:2.79, altText:'Sentinel-1 radar of Stargate Abilene before and after construction' });
tb(s, 'Stargate Abilene, Texas, seen by Sentinel-1 radar: shrubland in 2023, a 1,094-acre campus about two years later.', { x:6.55, y:4.42, w:6.18, h:0.6, fontSize:12, color:C.text2 });
card(s, 6.55, 5.25, 6.18, 1.25, C.accent5);
tb(s, [{text:'Our question  ', options:{bold:true,color:PURPLE}},{text:'Where is the land going, and which rivers, lakes and aquifers does each campus depend on?'}], { x:6.8, y:5.42, w:5.7, h:0.95, fontSize:17 });
s.addNotes('Problem. Announced AI investment is turning into campuses faster than public records and aerial photos can track. Local residents and utilities rarely see the land and water commitments until they are locked in.');

// 3 NISAR
pres.addSection({ title:'NISAR' });
s = pres.addSlide({ masterName:'Content', sectionTitle:'NISAR' });
s.addText([{text:'NISAR', options:{color:PURPLE}},{text:' sees new construction every 12 days'}], { placeholder:'title' });
pill(s, M, 1.45, 2.3, 'What it is', PURPLE);
s.addText([
  {text:'A NASA–ISRO radar satellite, launched July 2025', options:{bullet:{indent:18},breakLine:true}},
  {text:'L-band (NASA) and S-band (ISRO) radar: sees through clouds, day and night', options:{bullet:{indent:18},breakLine:true}},
  {text:'Images the same ground every 12 days', options:{bullet:{indent:18}}} ], { x:M, y:1.95, w:5.6, h:1.6, fontSize:16, color:C.text1, paraSpaceAfter:6, margin:0, isTextBox:true, valign:'top' });
pill(s, M, 3.75, 2.3, 'What it added', PURPLE);
tb(s, [{text:'602 acres ', options:{fontSize:30,bold:true,color:PURPLE}},{text:'got much brighter in NISAR radar, the signature of new buildings and steel, in 5 months at 3 Stargate campuses (all 33 images read)', options:{fontSize:14}}], { x:M, y:4.2, w:5.6, h:1.2, valign:'top' });
s.addText([
  {text:'The newest aerial photo of Project Jupiter (Sept 2025) still shows bare desert; NISAR already shows the change', options:{bullet:{indent:18},breakLine:true}},
  {text:'Ground motion (GUNW) over 8 aquifers: no clear change yet, a first baseline to watch', options:{bullet:{indent:18}}} ], { x:M, y:5.5, w:5.6, h:1.3, fontSize:14, color:C.text1, paraSpaceAfter:6, margin:0, isTextBox:true, valign:'top' });
card(s, 6.55, 1.45, 6.18, 5.25, C.background1);
s.addImage({ path:'nisar_pair.jpg', x:6.75, y:1.65, w:5.78, h:2.886, altText:'NISAR radar of Vantage Frontier, June vs October 2026, purple marks much brighter ground' });
tb(s, 'Vantage Frontier, Texas', { x:6.8, y:4.7, w:5.7, h:0.4, fontSize:18, bold:true });
tb(s, [{text:'315 acres', options:{bold:true,color:PURPLE}},{text:' got much brighter (over 3 dB) inside the 1,438-acre outline between the first NISAR image (2026-06-25) and the latest (2026-10-23). Purple = much brighter.'}], { x:6.8, y:5.15, w:5.7, h:1.0, fontSize:14 });
tb(s, 'Project Jupiter, NM: 286 acres  ·  Stargate Lordstown, OH: 1 acre (work is inside an existing building)', { x:6.8, y:6.15, w:5.7, h:0.45, fontSize:11, color:C.text2 });
s.addNotes('NISAR. It is the first NASA-ISRO joint radar mission. We read every NISAR GCOV image over the three campuses it covers and mapped ground that got more than 3 dB brighter. We also ran NISAR GUNW interferograms over 8 aquifer water sources; none shows a clear change yet beyond noise, which gives a starting baseline.');

// 4 Approach
pres.addSection({ title:'Approach' });
s = pres.addSlide({ masterName:'Content', sectionTitle:'Approach' });
s.addText('How it works: from land, to water, to 2035', { placeholder:'title' });
const steps = [
 ['1','Land','Sentinel-1 radar (ESA, via Microsoft Planetary Computer)','Month-by-month change since 2017 at 29 built campuses. NLCD shows what the land was before.', C.accent3],
 ['2','NISAR now','NASA–ISRO NISAR (ASF DAAC)','Every 12-day pass over 3 campuses under construction, plus ground motion over 8 aquifers.', PURPLE],
 ['3','Water','EPA service areas → utility → river, lake or aquifer','25 water sources. SWOT tracks water levels; OPERA DISP-S1 and NISAR track ground sinking.', C.accent3],
 ['4','2035','Announced megawatts and dollars','Turned into land and water using what the built campuses taught us. Low, median and high.', C.accent4] ];
const cw = (W-2*M-3*0.3)/4;
steps.forEach((st,i)=>{ const x=M+i*(cw+0.3), y=1.6;
  card(s, x, y, cw, 4.55);
  s.addShape(pres.shapes.OVAL,{x:x+0.3,y:y+0.3,w:0.65,h:0.65,fill:{color:st[4]},line:{color:st[4]}});
  tb(s, st[0], {x:x+0.3,y:y+0.3,w:0.65,h:0.65,fontSize:22,bold:true,color:C.background1,align:'center',valign:'middle'});
  tb(s, st[1], {x:x+0.3,y:y+1.15,w:cw-0.6,h:0.5,fontSize:22,bold:true,color: i==1?PURPLE:C.text1});
  tb(s, st[2], {x:x+0.3,y:y+1.75,w:cw-0.6,h:0.95,fontSize:14,bold:true,color:C.text2});
  tb(s, st[3], {x:x+0.3,y:y+2.75,w:cw-0.6,h:1.6,fontSize:15});
  if(i<3) s.addShape(pres.shapes.RIGHT_TRIANGLE? pres.shapes.ISOSCELES_TRIANGLE : pres.shapes.ISOSCELES_TRIANGLE,{x:x+cw+0.07,y:y+2.1,w:0.16,h:0.3,rotate:90,fill:{color:'B9AF9C'},line:{color:'B9AF9C'}});
});
tb(s, 'NASA data: NISAR (GCOV, GUNW), SWOT (via Hydrocron), OPERA DISP-S1, CMR and Earthdata.  Partner data: ESA/Copernicus Sentinel-1.  Open code: github.com/acho5750/NASA_Deserto', { x:M, y:6.3, w:W-2*M, h:0.5, fontSize:12, color:C.text2 });
s.addNotes('Approach. Every number on the map traces to a CSV in the repository with a source link.');

// 5 Product
pres.addSection({ title:'Product' });
s = pres.addSlide({ masterName:'Content', sectionTitle:'Product' });
s.addText('The product: a story map anyone can explore', { placeholder:'title' });
s.addShape(pres.shapes.RECTANGLE,{x:M,y:1.5,w:8.3,h:4.669,fill:{color:C.background1},line:{color:'D8CFBD',width:1},shadow:{type:'outer',color:'000000',opacity:0.15,blur:8,offset:2,angle:90}});
s.addImage({ path:'product_water.jpg', x:M, y:1.5, w:8.3, h:4.669, altText:'Screenshot of the Water chapter of the live map' });
tb(s, 'Water chapter: each drop is a water source, sized by how much of the town’s supply linked campuses would need by 2035.', { x:M, y:6.27, w:8.3, h:0.5, fontSize:12, color:C.text2 });
const ux = [['Pick a chapter','Land, NISAR now, Water, 2035'],['Press Play','Watch campuses grow month by month, then into the future'],['Click a campus or source','Its own numbers, radar images and source links'],['Compare','Drag the divider between before and after photos']];
ux.forEach((u,i)=>{ const y=1.5+i*1.18, x=9.25;
  s.addShape(pres.shapes.OVAL,{x,y:y+0.03,w:0.42,h:0.42,fill:{color:C.text1},line:{color:C.text1}});
  tb(s, String(i+1), {x,y:y+0.03,w:0.42,h:0.42,fontSize:14,bold:true,color:C.background1,align:'center',valign:'middle'});
  tb(s, u[0], {x:x+0.6,y,w:2.9,h:0.4,fontSize:17,bold:true});
  tb(s, u[1], {x:x+0.6,y:y+0.42,w:2.9,h:0.7,fontSize:14,color:C.text2});
});
tb(s, [{text:'Try it: ', options:{bold:true}},{text:LINK, options:{hyperlink:{url:'https://'+LINK}, color:PURPLE}}], { x:9.25, y:6.27, w:3.5, h:0.4, fontSize:13 });
s.addNotes('Product. A four-chapter story map built with MapLibre GL. Works on phones too.');

// 6 Findings
pres.addSection({ title:'Findings' });
s = pres.addSlide({ masterName:'Content', sectionTitle:'Findings' });
s.addText('What we found', { placeholder:'title' });
card(s, M, 1.5, 6.6, 5.2);
tb(s, 'Campus water need vs. the town utility’s whole supply today, 2035 (median)', { x:M+0.3, y:1.7, w:6.0, h:0.7, fontSize:16, bold:true });
s.addChart(pres.charts.BAR, [{ name:'Times the town supply', labels:['Bell Milam Falls WSC, TX','Camino Real RUA, NM','Hawley WSC, TX','Montgomery Co PWSD 1, MO','Boling MWD, TX'], values:[10.67,9.2,6.0,3.1,2.4] }],
  { x:M+0.2, y:2.4, w:6.2, h:3.5, barDir:'bar', catAxisOrientation:'maxMin', chartColors:[THEME.colors.accent2], showValue:true, dataLabelPosition:'outEnd', dataLabelFormatCode:'0.0"×"', dataLabelFontSize:13, dataLabelColor:THEME.colors.dk1, dataLabelFontFace:'+mn-lt',
    catAxisLabelFontSize:13, catAxisLabelColor:THEME.colors.dk1, catAxisLabelFontFace:'+mn-lt', valAxisHidden:true, valGridLine:{style:'none'}, catGridLine:{style:'none'}, showLegend:false, barGapWidthPct:45, valAxisMaxVal:13, valAxisMinVal:0 });
tb(s, 'If the announced campuses are built. Ranges are wide (Bell Milam: 2.0× to 19×). Two of these towns buy water from a larger wholesale system.', { x:M+0.3, y:5.9, w:6.0, h:0.7, fontSize:12, color:C.text2 });
const f = [['6,888','acres','of the land changed at built campuses was not built on before: farmland, pasture, shrubland, forest, wetland', C.text1],
           ['1.0 million','people’s worth of water','a year by 2035 for 46 campuses, built and announced (range 193,000 to 1.8 million)', C.accent3],
           ['28,598','acres','of campus land by 2035, about 45 square miles (range 19,309 to 38,894)', C.text1]];
f.forEach((r,i)=>{ const y=1.5+i*1.75, x=7.55;
  tb(s, [{text:r[0]+' ', options:{fontSize:34,bold:true,color:r[3]}},{text:r[1], options:{fontSize:16,bold:true,color:C.text2}}], { x, y, w:5.2, h:0.7, valign:'bottom' });
  tb(s, r[2], { x, y:y+0.75, w:5.15, h:0.85, fontSize:14 });
});
s.addNotes('Findings. Numbers are from the live map and the CSVs in data/. These campuses are linked to the water sources; the map does not claim that data centers caused any change in a water source.');

// 7 Impact
pres.addSection({ title:'Impact' });
s = pres.addSlide({ masterName:'Content', sectionTitle:'Impact' });
s.addText('Why it matters, and what comes next', { placeholder:'title' });
const cols = [['Who it helps', C.text1, ['Town councils and water utilities weighing a new campus','Residents and reporters asking where the water will come from','Planners comparing announced plans with what radar shows is built']],
              ['What NISAR makes possible', PURPLE, ['Check every 12 days for new construction at announced campuses','Watch the ground over the aquifers towns depend on','Free, open data anyone can re-run']],
              ['Next steps', C.text1, ['Follow every campus as NISAR coverage grows','Grow the aquifer baseline into trends','Add utilities’ own water reports for each source']]];
const cw2 = (W-2*M-2*0.3)/3;
cols.forEach((c,i)=>{ const x=M+i*(cw2+0.3), y=1.5;
  card(s, x, y, cw2, 3.6, i==1?'F1EAF8':C.background1);
  tb(s, c[0], {x:x+0.3,y:y+0.3,w:cw2-0.6,h:0.5,fontSize:20,bold:true,color:c[1]});
  s.addText(c[2].map((t,j)=>({text:t,options:{bullet:{indent:18},breakLine:j<c[2].length-1}})), {x:x+0.3,y:y+0.95,w:cw2-0.6,h:2.9,fontSize:15,color:C.text1,paraSpaceAfter:10,margin:0,isTextBox:true,valign:'top'});
});
tb(s, [{text:'See the land and water stakes of a data center before they are locked in.  ', options:{bold:true}},{text:'Explore: '},{text:LINK, options:{hyperlink:{url:'https://'+LINK}, color:PURPLE}}], { x:M, y:5.5, w:W-2*M, h:0.45, fontSize:18 });
tb(s, 'AI use: code, data processing and these slides were made with help from Claude (an AI assistant). Map screenshots are of our own product. All numbers trace to public data in the repository.', { x:M, y:6.15, w:W-2*M, h:0.45, fontSize:11, color:C.text2 });
s.addNotes('Impact and next steps. Map copy says linked to or depends on, never causes.');

(async()=>{ await pres.writeFile({ fileName:'Data_Centers_and_Water_deck.pptx' }); await applyTheme('Data_Centers_and_Water_deck.pptx', THEME); console.log('ok'); })();
