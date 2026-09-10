const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(tag='div'){this.tag=tag;this.children=[];this.dataset={};this.style={};this.attrs={};this.value='2026';this.classList={add(){},remove(){}};}
  append(...nodes){this.children.push(...nodes)}
  replaceChildren(...nodes){this.children=nodes}
  setAttribute(k,v){this.attrs[k]=v}
}
const elements = new Map();
const document = {
  getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id)},
  createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),querySelectorAll:()=>[]
};
const script=fs.readFileSync('index.html','utf8').split('<script>')[1].split('</script>')[0];
const context=vm.createContext({document,Intl,Date});
vm.runInContext(script.slice(0,script.indexOf("$('year').onchange=")),context);
const evaluate=code=>vm.runInContext(code,context);
const plain=code=>JSON.parse(JSON.stringify(evaluate(code)));
assert.equal(evaluate("dailySeries({},'2024-01-01','2024-12-31').length"),366);
assert.equal(evaluate("monday('2026-01-01')"),'2025-12-29');
assert.deepEqual(plain("weeks(dailySeries({'2026-09-06':{total:10},'2026-09-07':{total:20}},'2026-09-06','2026-09-08'))"),[{date:'2026-08-31',total:10},{date:'2026-09-07',total:20}]);
const results=plain("insights({'2026-09-01':{total:70},'2026-09-08':{total:140},'2026-09-11':{total:9999}},'2026-09-10')");
assert.equal(results.peakDay.date,'2026-09-08');
assert.equal(results.thisWeek,140);assert.equal(results.previousWeek,70);assert.equal(results.average,20);
assert.equal(results.peakWeek.total,140);
evaluate("data={today:'2026-09-10',days:{'2026-09-08':{total:140,input:100,output:40,subagent:20,breakdown:{main:{alpha:70,beta:50},subagent:{alpha:20}}}}};renderYear();renderInsights()");
let buttons=elements.get('grid').children.filter(n=>n.tag==='button');
assert.equal(buttons.at(-1).attrs['aria-label'],'2026-09-10 · 0 tokens');
assert.equal(buttons.at(-1).attrs['aria-current'],'date');
assert.equal(buttons.length,253);
assert.equal(elements.get('weeklyLedger').children[0].children[5].textContent,'140');
assert.equal(elements.get('dailyChart').children[0].tag,'svg');
buttons[buttons.length-3].onclick();assert.match(elements.get('detail').textContent,/140 total/);
assert.equal(elements.get('dayBreakdown').hidden,false);
assert.equal(elements.get('dayPieLegend').children.length,4);
let slices=elements.get('dayPie').children[0].children.filter(n=>n.attrs.class==='pie-slice');
assert.equal(slices.length,3);assert.match(slices[2].attrs['aria-label'],/Subagent · alpha: 20 tokens/);
assert.equal(typeof buttons.at(-1).onmouseenter,'function');assert.equal(buttons.at(-1).onfocus,undefined);
assert.equal(elements.get('dayPie').children[0].style.width,'220px');
buttons.at(-1).onmouseenter();assert.equal(elements.get('dayPie').textContent,'No recorded tokens for this day.');
assert.equal(elements.get('dayPieLegend').children.length,0);
buttons[buttons.length-3].onclick();assert.equal(elements.get('dayPieLegend').children.length,4);
assert.match(fs.readFileSync('index.html','utf8'),/<details class="panel" id="dailyLedger">/);
evaluate("data.days['2026-09-09']={total:10,subagent:0,breakdown:{main:{alpha:10},subagent:{}}};renderDay('2026-09-09')");
slices=elements.get('dayPie').children[0].children.filter(n=>n.attrs.class==='pie-slice');
assert.equal(slices.length,1);assert.equal(slices[0].tag,'circle');
assert.equal(parseFloat(elements.get('dayPie').children[0].style.width),110+110*10/140);
assert.match(elements.get('dayPieLegend').children[0].textContent,/scales linearly/);
evaluate("data.days['2025-01-01']={total:280};renderDay('2026-09-08')");
assert.equal(elements.get('dayPie').children[0].style.width,'165px');
evaluate("delete data.days['2025-01-01']");
evaluate("delete data.days['2026-09-09']");
const stacks=plain("stackedWeeks(data.days,'2026-09-07','2026-09-10')");
assert.equal(stacks[0].main,120);assert.equal(stacks[0].subagent,20);
assert.equal(stacks[0].segments.reduce((n,s)=>n+s.total,0),stacks[0].total);
assert.deepEqual(stacks[0].segments.map(s=>[s.role,s.model,s.total]),[['main','alpha',70],['main','beta',50],['subagent','alpha',20]]);
const segments=elements.get('weeklyChart').children[0].children.filter(n=>n.attrs.class==='segment');
assert.equal(segments.length,3);
assert.ok(segments[2].attrs.fill.startsWith('url(#subagent-model-'));
assert.ok(Number(segments[2].attrs.y)<Number(segments[0].attrs.y));
segments[2].onfocus();assert.match(elements.get('weeklyDetail').textContent,/Subagent · alpha · 20 tokens/);
assert.equal(elements.get('weeklyLegend').children.length,4);
evaluate("data.days['2026-09-09']={total:30,subagent:0,auditor:30,breakdown:{main:{},subagent:{},auditor:{'gpt-5.6-sol':30}}};renderYear();renderDay('2026-09-09')");
const auditWeek=plain("stackedWeeks(data.days,'2026-09-07','2026-09-10')")[0];
assert.equal(auditWeek.auditor,30);assert.equal(auditWeek.subagent,20);
assert.equal(auditWeek.segments.at(-1).role,'auditor');
assert.equal(auditWeek.segments.reduce((n,s)=>n+s.total,0),170);
assert.match(elements.get('dayPieLegend').children[1].children[1].textContent,/Auditor · gpt-5.6-sol/);
const auditRect=elements.get('weeklyChart').children[0].children.filter(n=>n.attrs.class==='segment').at(-1);
assert.match(auditRect.attrs.fill,/-auditor/);assert.match(auditRect.attrs['aria-label'],/Auditor/);
evaluate("data.days['2026-09-10']={total:5,other:5,breakdown:{other:{'codex-auto-review':5}}};renderYear();renderDay('2026-09-10')");
const otherWeek=plain("stackedWeeks(data.days,'2026-09-07','2026-09-10')")[0];
assert.equal(otherWeek.other,5);assert.equal(otherWeek.auditor,30);
assert.equal(otherWeek.segments.at(-1).role,'other');
assert.match(elements.get('dayPieLegend').children[1].children[1].textContent,/Other · codex-auto-review/);
assert.match(elements.get('weeklyChart').children[0].children.filter(n=>n.attrs.class==='segment').at(-1).attrs.fill,/-other/);
elements.get('year').value='2024';evaluate('renderYear()');
buttons=elements.get('grid').children.filter(n=>n.tag==='button');
assert.equal(buttons.length,366);assert.match(buttons.at(-1).title,/2024-12-31/);
assert.equal(elements.get('weeklyChart').textContent,'No recorded usage in this year.');
assert.equal(plain("insights({},'2026-09-10')").peakDay.date,null);
elements.get('year').value='2026';elements.get('carbonScenario').value='central';
evaluate(`data.carbon={totals:{low:{tonnes_co2:.01,kwh:10,flights:.04},central:{tonnes_co2:.1,kwh:100,flights:.4},high:{tonnes_co2:1,kwh:1000,flights:4}},days:{'2026-09-08':{low:{tonnes_co2:.01},central:{tonnes_co2:.1},high:{tonnes_co2:1}}},models:{},sources:[],grid_kg_co2_per_kwh:{low:.05,central:.445,high:.8}};renderCarbon()`);
assert.equal(elements.get('carbonTotal').textContent,'0.1 t');
assert.equal(elements.get('carbonFlights').textContent,'≈ 0.4');
assert.equal(elements.get('carbonChart').children[0].tag,'svg');
const carbonTicks=elements.get('carbonChart').children[0].children.filter(n=>n.tag==='text');
assert.ok(carbonTicks.some(n=>n.textContent==='0.100'));
elements.get('carbonScenario').value='high';evaluate('renderCarbon()');assert.equal(elements.get('carbonTotal').textContent,'1 t');
evaluate("renderDay('2026-09-08')");assert.match(elements.get('detail').textContent,/1 metric tons CO₂/);
console.log('Dashboard checks passed: date cutoff, leap year, weekly boundaries, missing days, future exclusion, summaries, chart rendering, day selection, empty state.');
