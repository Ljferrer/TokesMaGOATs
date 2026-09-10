const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(tag='div'){this.tag=tag;this.children=[];this.dataset={};this.style={};this.attrs={};this.value='2026';this.classList={add(){},remove(){}};}
  append(...nodes){this.children.push(...nodes)}
  replaceChildren(){this.children=[]}
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
evaluate("data={today:'2026-09-10',days:{'2026-09-08':{total:140,input:100,output:40,subagent:20}}};renderYear();renderInsights()");
let buttons=elements.get('grid').children.filter(n=>n.tag==='button');
assert.equal(buttons.at(-1).attrs['aria-label'],'2026-09-10 · 0 tokens');
assert.equal(buttons.at(-1).attrs['aria-current'],'date');
assert.equal(buttons.length,253);
assert.equal(elements.get('weeklyLedger').children[0].children[1].textContent,'140');
assert.equal(elements.get('dailyChart').children[0].tag,'svg');
buttons[buttons.length-3].onclick();assert.match(elements.get('detail').textContent,/140 total/);
elements.get('year').value='2024';evaluate('renderYear()');
buttons=elements.get('grid').children.filter(n=>n.tag==='button');
assert.equal(buttons.length,366);assert.match(buttons.at(-1).title,/2024-12-31/);
assert.equal(elements.get('weeklyChart').textContent,'No recorded usage in this year.');
assert.equal(plain("insights({},'2026-09-10')").peakDay.date,null);
console.log('Dashboard checks passed: date cutoff, leap year, weekly boundaries, missing days, future exclusion, summaries, chart rendering, day selection, empty state.');
