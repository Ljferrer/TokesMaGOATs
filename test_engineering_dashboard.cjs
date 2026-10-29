const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.style={};this.dataset={};this.value='';this.textContent=''}
  append(...nodes){this.children.push(...nodes)} replaceChildren(...nodes){this.children=nodes}
}
const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element('div'));return elements.get(id)};
const context=vm.createContext({document:{createElement:tag=>new Element(tag)},Intl,$:get,short:n=>String(n),preferences:{privacy:false},monday:()=> '2025-12-29'});
vm.runInContext(fs.readFileSync('engineering.js','utf8'),context);
const stats={status:'partial',complete:false,assessed_dates:2,eligible_dates:3,denominator_hours:24,scenarios:Object.fromEntries(['low','central','high'].map(s=>[s,{minimum:null,maximum:null,median:null,average:null,total_estimated_hours:32}]))};
context.data={engineering:{delivery_scope:'Independent delivery scope',repositories:[],timezone:'UTC',cutoff:'2026-01-03T15:00:00Z',assessment_cutoff:'2026-01-03T14:00:00Z',sensitivity:{8:stats},full_days:{8:{...stats,eligible_dates:2,scenarios:{central:{average:2}}}},usage:{days:{},raw_only_records:1,raw_only_tokens:35,raw_only_scope:'All reconciled sources; excluded from ledger totals until sync. Unknown counters make raw-only totals lower bounds.',limitations:[]},activity:{days:{},limitations:[]},baseline:'Conventional engineering',assumptions:[],days:[{date:'2026-01-03',status:'unknown',partial_day:true,eligible:true,hours:{low:null,central:null,high:null},unknown_items:['unestimated'],integrations:[],items:[{scope:'SECRET/customer',effort:{status:'unreviewed'},quality:[{quality_score:null,confidence:'low',final_day_scope:false,tests:[{classification:'present_only',result:'not_run',date:'2026-01-02',applies_to_delivered:true}]}]}]}],weekly:[{date:'2025-12-29',...stats}]}};
get('engineeringHours').value='8';vm.runInContext('renderEngineering()',context);
assert.match(get('engineeringReconciliation').textContent,/1 records.*35 tokens/);
assert.match(get('engineeringReconciliation').textContent,/All reconciled sources.*excluded from ledger totals.*lower bounds/);
assert.match(get('engineeringCoverage').textContent,/2\/3 eligible/);assert.match(get('engineeringCoverage').textContent,/denominator 3 dates × 8 hours = 24 hours/);
assert.equal(get('engineeringStats').children[1].children[4].textContent,'Unknown');assert.match(get('engineeringFullDays').textContent,/central average 2×/);
const flatten=node=>node.textContent+' '+node.children.map(flatten).join(' ');
assert.match(flatten(get('engineeringDays')),/Unknown\/100/);assert.match(flatten(get('engineeringDays')),/SECRET\/customer/);
// Every private string in the rendered panel lives inside snapshot-excluded nodes.
const share=node=>node.dataset.snapshotIgnore!==undefined?'':node.textContent+' '+node.children.map(share).join(' ');
assert.doesNotMatch(share(get('engineeringDays')),/SECRET|customer/);
context.preferences.privacy=true;vm.runInContext('renderEngineering()',context);assert.doesNotMatch(flatten(get('engineeringDays')),/SECRET/);assert.equal(get('engineeringEditor').hidden,true);
get('engineeringPeriod').value='weekly';vm.runInContext('renderEngineering()',context);
assert.match(flatten(get('engineeringDays')),/4 assessed engineer-days/);assert.match(flatten(get('engineeringDays')),/average daily Unknown/);
assert.match(share(get('engineeringReconciliation')),/All reconciled sources.*lower bounds/);
const retainedDays=context.data.engineering.days,retainedWeeks=context.data.engineering.weekly;
context.data.engineering.days=[];context.data.engineering.weekly=[];context.data.engineering.usage.raw_only_records=0;context.data.engineering.usage.raw_only_tokens=0;vm.runInContext('renderEngineering()',context);
assert.match(get('engineeringReconciliation').textContent,/0 records.*0 tokens.*All reconciled sources/);
context.data.engineering.days=retainedDays;context.data.engineering.weekly=retainedWeeks;
const html=fs.readFileSync('index.html','utf8');assert.match(html,/<p class="muted" id="engineeringReconciliation"><\/p>/);assert.match(html,/<script src="\/engineering.js"><\/script>/);
assert.ok(html.indexOf('id="engineeringEditor"')>html.indexOf('data-snapshot-ignore id="engineeringEditor"'));
console.log('Engineering dashboard checks passed: unknowns, denominators, partial/full-day comparison, weekly labels, privacy and PNG exclusions.');

context.data.engineering.days[0].items[0].quality[0].tests=[{classification:'later_historical_snapshot_rerun',result:'passed',date:'2026-01-04',applies_to_delivered:false}];
get('engineeringPeriod').value='daily';vm.runInContext('renderEngineering()',context);
assert.match(share(get('engineeringDays')),/2026-01-04.*does not apply to delivered code/);
context.fetch=async()=>({ok:false,json:async()=>({error:'Cannot open /SECRET/customer/repository'})});
vm.runInContext('bindEngineering()',context);
(async()=>{
  await get('engineeringCollect').onclick();
  assert.match(get('engineeringStatus').textContent,/SECRET/);
  assert.doesNotMatch(get('status').textContent,/SECRET|customer|repository/);
  context.preferences.privacy=true;vm.runInContext('renderEngineering()',context);
  assert.equal(get('engineeringEditor').hidden,true);
})().catch(error=>{console.error(error);process.exitCode=1});
