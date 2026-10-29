const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const created=[];
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.style={};this.dataset={};this.attributes={};this.value='';this.textContent='';created.push(this)}
  append(...nodes){this.children.push(...nodes)} replaceChildren(...nodes){this.children=nodes}
  setAttribute(name,value){this.attributes[name]=String(value)} getAttribute(name){return this.attributes[name]}
}
const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element('div'));return elements.get(id)};
const context=vm.createContext({document:{createElement:tag=>new Element(tag),querySelectorAll:()=>created.filter(node=>node.dataset.inputSelectionControl!==undefined)},Intl,$:get,short:n=>String(n),preferences:{privacy:false},monday:()=> '2025-12-29'});
vm.runInContext(fs.readFileSync(path.join(__dirname,'..','engineering.js'),'utf8'),context);
const stats={status:'partial',complete:false,assessed_dates:2,eligible_dates:3,denominator_hours:24,scenarios:Object.fromEntries(['low','central','high'].map(s=>[s,{minimum:null,maximum:null,median:null,average:null,total_estimated_hours:32}]))};
context.data={engineering:{report_id:'a'.repeat(64),delivery_scope:'Independent delivery scope',repositories:[],timezone:'UTC',cutoff:'2026-01-03T15:00:00Z',assessment_cutoff:'2026-01-03T14:00:00Z',sensitivity:{8:stats},full_days:{8:{...stats,eligible_dates:2,scenarios:{central:{average:2}}}},usage:{days:{},raw_only_records:1,raw_only_tokens:35,raw_only_scope:'All reconciled sources; excluded from ledger totals until sync. Unknown counters make raw-only totals lower bounds.',limitations:[]},activity:{days:{},limitations:[]},baseline:'Conventional engineering',assumptions:[],days:[{date:'2026-01-03',status:'unknown',partial_day:true,eligible:true,hours:{low:null,central:null,high:null},unknown_items:['unestimated'],integrations:[],items:[{scope:'SECRET/customer',effort:{status:'unreviewed'},quality:[{quality_score:null,confidence:'low',final_day_scope:false,tests:[{classification:'present_only',result:'not_run',date:'2026-01-02',applies_to_delivered:true}]}]}]}],weekly:[{date:'2025-12-29',...stats}]}};
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
const html=fs.readFileSync(path.join(__dirname,'..','index.html'),'utf8');assert.match(html,/<p class="muted" id="engineeringReconciliation"><\/p>/);assert.match(html,/<script src="\/engineering.js"><\/script>/);
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
  assert.equal(get('engineeringIgnoreDays').checked,false);
  assert.equal(get('engineeringThreshold').disabled,true);
  assert.equal(get('engineeringThresholdValue').textContent,'0.10×');
  let loads=0,saved;
  context.localStorage={getItem:()=>JSON.stringify({enabled:true,threshold:.15}),setItem:(_,value)=>{saved=JSON.parse(value)}};
  vm.runInContext('bindEngineering()',context);
  assert.equal(get('engineeringThreshold').disabled,false);
  assert.equal(get('engineeringThresholdValue').textContent,'0.15×');
  context.load=async()=>{loads++;return true};
  get('engineeringThreshold').value='0.25';get('engineeringThreshold').oninput();
  assert.equal(get('engineeringThresholdValue').textContent,'0.25×');assert.equal(loads,0);
  await get('engineeringThreshold').onchange();assert.equal(loads,1);assert.deepEqual(saved,{enabled:true,threshold:.25,comparison_hours:'8',effort_scenario:'central',idle_timeout:'5',input_population:'supported'});
  context.data.engineering.day_filter={threshold:.1,comparison_hours:8,basis:'central'};
  Object.assign(stats,{excluded_dates:2,eligible_dates_before_filter:3});
  context.data.engineering.days[0].excluded_low_effort=true;
  vm.runInContext('renderEngineering()',context);
  assert.match(share(get('engineeringFilterSummary')),/2 of 3.*below 0.10× central.*0.8 h.*Unknown days remain/);
  assert.match(share(get('engineeringDays')),/excluded from effort statistics/);
  context.activeFilters={start:'2026-01-01',end:'2026-01-03'};
  let exported;
  const downloads=[];
  context.fetch=async(_,options)=>{exported=JSON.parse(options.body);return {ok:true,json:async()=>({id:'fixture',report:{},csv:''})}};
  context.engineeringDownload=(text,name,type)=>downloads.push({text,name,type});
  context.activeFilters={start:'2026-02-01',end:'2026-02-02',projects:['pending-project']};
  for(const format of ['JSON','CSV']){
    await get('engineering'+format).onclick();
    assert.deepEqual(exported,{report_id:'a'.repeat(64),privacy:true},'Export exactly the displayed snapshot, independent of pending filters or slider values');
    assert.equal(downloads.at(-1).text,format==='JSON'?'{}':'');
    assert.equal(downloads.at(-1).type,format==='JSON'?'application/json':'text/csv');
  }
  get('engineeringIgnoreDays').checked=false;await get('engineeringIgnoreDays').onchange();
  assert.equal(get('engineeringThreshold').disabled,true);
  assert.equal(vm.runInContext('engineeringSelection().effort_threshold',context),'');
  assert.match(html,/id="engineeringThreshold" min="0" max="0.50" step="0.01"/);
  assert.match(html,/<p id="engineeringFilterSummary" class="muted"><\/p>/);

  // Unequal timer denominators deliberately make the headline differ from the daily mean.
  const dates=['2026-01-01','2026-01-02'],scenarios=['low','central','high'];
  const fixed=Object.fromEntries([4,8,12].map(h=>[h,{assessed_dates:2,eligible_dates:2,denominator_hours:2*h,scenarios:Object.fromEntries(scenarios.map((name,i)=>{const factor=[.5,1,2][i];return [name,{active_date_estimated_hours:28*factor,total_estimated_hours:28*factor,minimum:10*factor/h,maximum:18*factor/h,median:14*factor/h,average:14*factor/h}]}))}]));
  const timerStats=(hours)=>({cohort_dates:dates,denominator_hours:hours,defined_daily_dates:dates,zero_timer_dates:[],scenarios:Object.fromEntries(scenarios.map((name,i)=>{const factor=[.5,1,2][i];return [name,{numerator_hours:28*factor,pooled:28*factor/hours,daily_minimum:20*factor/hours,daily_maximum:100*factor/hours,daily_median:60*factor/hours,daily_mean:60*factor/hours}]}))});
  const sensitivity={supported:{2:timerStats(4),5:timerStats(10),10:timerStats(20)},inclusive:{2:timerStats(5),5:timerStats(12),10:timerStats(22)}};
  const joint={supported:{low:.7,high:14},inclusive:{low:14/22,high:56/5}};
  const timerDay=(date,effort,duration,inC=true)=>({date,partial_day:false,in_cohort:inC,effort_status:effort===null?'unassessed':'assessed',effort_hours:{low:effort===null?null:effort/2,central:effort,high:effort===null?null:effort*2},exclusion_reason:inC?null:effort===null?'outside_token_active_scope':'no_supported_reference_timer',hours:{supported:{2:duration*.4,5:duration,10:duration*2},inclusive:{2:duration*.4,5:duration,10:duration*2}},ratios:Object.fromEntries(['supported','inclusive'].map(p=>[p,Object.fromEntries([2,5,10].map(t=>[t,{low:duration&&effort!==null?effort/2/duration:null,central:duration&&effort!==null?effort/duration:null,high:duration&&effort!==null?effort*2/duration:null}]))]))});
  const timer={method_version:'message-timer-v1',fixed_method_version:'fixed-day-v1',classifier_version:'human-inputs-v1',options:{effort_scenario:'central',idle_timeout:5,input_population:'supported'},cohort:{dates,token_active_dates:[...dates,'2026-01-03','2026-01-04'],eligible_after_filter_dates:[...dates,'2026-01-03','2026-01-04'],assessed_dates:[...dates,'2026-01-03'],unknown_dates:['2026-01-04'],no_supported_timer_dates:['2026-01-03'],low_effort_excluded_dates:[],excluded_assessed_hours:{low:8,central:16,high:32},excluded_known_item_hours:{low:1,central:2,high:4}},matched_fixed:fixed,sensitivity,joint,full_days:{dates,sensitivity,matched_fixed:fixed},weekly:[{date:'2025-12-29',dates,sensitivity,matched_fixed:fixed}],days:[timerDay(dates[0],10,1),timerDay(dates[1],18,9),timerDay('2026-01-03',16,0,false),timerDay('2026-01-04',null,1,false),timerDay('2026-01-05',null,2,false)],coverage:{retained_sources:4,current_sources:2,missing_sources:1,changed_sources:1,unsupported_sources:1,supported_human:12,ambiguous:2,excluded:3,carry_in_events:1,unmapped_events:1,outside_project_events:2,boundary_context:'retained_only'},reconciliation:{outside_cohort_dates:['2026-01-04','2026-01-05'],outside_token_active_dates:['2026-01-05'],input_only_dates:['2026-01-05'],supported_hours:{2:5.2,5:13,10:26},inclusive_hours:{2:6.2,5:15,10:28},outside_cohort_supported_hours:{2:1.2,5:3,10:6},outside_cohort_inclusive_hours:{2:1.2,5:3,10:6}},limitations:['Retained evidence can miss reading, reviews and other off-chat work.']};
  context.data.engineering.message_timer=timer;
  context.data.engineering.report_id='b'.repeat(64);
  context.data.engineering.days=[10,18,16,null].map((effort,i)=>({date:'2026-01-0'+(i+1),eligible:true,partial_day:i===3,status:effort===null?'unknown':'assessed',hours:{low:effort===null?null:effort/2,central:effort,high:effort===null?null:effort*2},items:[],integrations:[],unknown_items:effort===null?['unestimated']:[]}));
  vm.runInContext('renderEngineering()',context);
  assert.equal(get('engineeringFixedValue').textContent,'1.75×');assert.equal(get('engineeringTimerValue').textContent,'2.8×');
  assert.match(flatten(get('engineeringTimerDaily')),/Unweighted daily mean\s+6×/);
  assert.match(get('engineeringFixedCalculation').textContent,/28 conventional h.*16 assumed h/);
  assert.match(get('engineeringTimerCalculation').textContent,/28 conventional h.*10 modeled chat h/);
  assert.match(get('engineeringMatchedCohort').textContent,/2 of 4.*same dates.*stays fixed/);
  assert.match(get('engineeringFullScope').textContent,/1 unknown.*16 assessed central conventional h.*2 known item h/);
  assert.match(get('engineeringHumanCoverage').textContent,/4 retained.*1 missing.*1 changed.*1 unsupported.*complete history is not established/);
  assert.match(get('engineeringTimerReconciliation').textContent,/1 input dates.*1 have no output-assessment record.*No zero output is invented/);
  assert.match(share(get('engineeringInputOnlyDates')),/2026-01-05.*outside token-active scope.*2 modeled chat h.*Unknown output/);
  assert.match(share(get('engineeringDays')),/no supported reference time.*0 modeled chat h.*N\/A/);
  assert.match(get('engineeringJointSensitivity').textContent,/0.7×.*14×.*not confidence intervals/);
  assert.equal(get('engineeringSensitivity').children.length,9);
  assert.equal(get('engineeringStats').children[1].children[4].textContent,'Unknown','The full-D fixed summary is not overwritten by the matched estimate');
  get('engineeringPeriod').value='weekly';vm.runInContext('renderEngineering()',context);
  assert.match(share(get('engineeringDays')),/full fixed-day scope/);
  assert.match(share(get('engineeringDays')),/Matched weekly comparison.*2 dates.*fixed 1.75×.*timer pooled 2.8×.*unweighted daily mean 6×/);

  // Clamp notices and markers must survive public snapshots without changing numeric evidence.
  const beforeClampReport=context.data.engineering;
  const clampedReport=JSON.parse(JSON.stringify(beforeClampReport)),ct=clampedReport.message_timer;
  clampedReport.clamping={effort_hours_limit:10000,effort:[{date:dates[0],scenario:'central',original_hours:1e308,applied_hours:10000}]};
  clampedReport.days[0].clamped_effort={low:0,central:1,high:0};
  ct.clamping={ratio_limit:1000,applied:true,dates:[dates[0]]};
  for(const scope of [ct,ct.full_days,...ct.weekly])for(const population of Object.values(scope.sensitivity))for(const period of Object.values(population))for(const value of Object.values(period.scenarios)){
    value.pooled=1000;value.numerator_hours=1e6;value.clamping={pooled:true,daily_dates:[dates[0]]};
    value.daily_maximum=1000;value.daily_mean=value.daily_median=501;
  }
  ct.joint.supported={low:1000,high:1000};
  ct.days[0].ratios.supported[5].central=1000;
  ct.days[0].ratio_clamped={supported:{5:{central:true}}};
  context.data.engineering=clampedReport;vm.runInContext('renderEngineering()',context);
  assert.equal(get('engineeringClamping').hidden,false);
  assert.match(share(get('engineeringClamping')),/Clamping applied.*10,000.*hours per work item.*1,000×/);
  assert.match(share(get('engineeringClamping')),/Original estimates.*assessment.*Daily statistics use clamped daily ratios/);
  assert.equal(get('engineeringTimerValue').textContent,'1,000× (clamped)');
  assert.match(get('engineeringTimerCalculation').textContent,/Clamped pooled ratio.*limit/);
  assert.doesNotMatch(get('engineeringTimerCalculation').textContent,/headline is the ratio of sums/);
  assert.match(flatten(get('engineeringTimerDaily')),/501× \(clamped daily inputs\)/);
  assert.match(get('engineeringTimerFullDays').textContent,/pooled 1,000× \(clamped\)/);
  assert.match(share(get('engineeringDays')),/timer pooled 1,000× \(clamped\).*daily mean 501× \(clamped daily inputs\)/);
  assert.match(share(get('engineeringDays')),/2026-01-01.*effort clamped: central/);
  assert.match(vm.runInContext('engineeringTimerDay(data.engineering.message_timer.days[0], data.engineering.message_timer)',context),/1,000× \(clamped\)/);
  for(const row of get('engineeringSensitivity').children.slice(3))assert.equal(row.children[3].textContent,'1,000× (clamped)');
  assert.match(get('engineeringJointSensitivity').textContent,/low effort.*1,000× \(clamped\).*high effort.*1,000× \(clamped\)/);
  assert.match(html,/<p id="engineeringClamping"[^>]*role="status"[^>]*hidden><\/p>/);
  assert.doesNotMatch(html.match(/<p id="engineeringClamping"[^>]*>/)[0],/snapshot-ignore/);
  assert.equal(vm.runInContext('engineeringRatio(null,true)',context),'N/A');
  assert.equal(vm.runInContext('engineeringRatio(0,false)',context),'0×');
  assert.equal(vm.runInContext('engineeringRatio(0,true)',context),'0×');
  assert.equal(vm.runInContext('engineeringRatio(undefined,true)',context),'N/A');
  assert.equal(vm.runInContext("engineeringDailyStatistic(0,['2026-01-01'])",context),'0×');
  assert.equal(vm.runInContext("engineeringDailyStatistic(null,['2026-01-01'])",context),'N/A');
  assert.equal(vm.runInContext('engineeringRatio(1000,false)',context),'1,000×');
  clampedReport.clamping.effort=[];vm.runInContext('renderEngineering()',context);
  assert.match(get('engineeringClamping').textContent,/Clamping applied.*Timer ratios capped at 1,000×/);
  assert.doesNotMatch(get('engineeringClamping').textContent,/Original estimates|hours per work item/);
  ct.clamping.applied=false;
  for(const scope of [ct,ct.full_days,...ct.weekly])for(const population of Object.values(scope.sensitivity))for(const period of Object.values(population))for(const value of Object.values(period.scenarios))value.clamping={pooled:false,daily_dates:[]};
  ct.days[0].ratio_clamped.supported[5].central=false;clampedReport.days[0].clamped_effort.central=0;
  vm.runInContext('renderEngineering()',context);
  assert.equal(get('engineeringClamping').hidden,true);assert.equal(get('engineeringClamping').textContent,'');
  assert.equal(get('engineeringTimerValue').textContent,'1,000×');
  assert.doesNotMatch(get('engineeringJointSensitivity').textContent,/clamped/);
  assert.doesNotMatch(flatten(get('engineeringTimerDaily')),/clamped/);
  assert.doesNotMatch(share(get('engineeringDays')),/effort clamped/);
  assert.doesNotMatch(vm.runInContext('engineeringTimerDay(data.engineering.message_timer.days[0], data.engineering.message_timer)',context),/clamped/);
  clampedReport.clamping.effort=[{date:dates[0],scenario:'central',original_hours:1e308,applied_hours:10000}];
  delete clampedReport.message_timer;vm.runInContext('renderEngineering()',context);
  assert.match(get('engineeringClamping').textContent,/10,000.*Original estimates/);
  assert.doesNotMatch(get('engineeringClamping').textContent,/Timer ratios/);
  context.data.engineering=beforeClampReport;vm.runInContext('renderEngineering()',context);
  assert.equal(get('engineeringClamping').hidden,true);

  // Draft controls cannot leak into exports or change labels for the applied result.
  get('engineeringScenario').value='high';get('engineeringTimeout').value='10';get('engineeringPopulation').value='inclusive';
  await get('engineeringTimeout').onchange();
  assert.equal(saved.idle_timeout,'10');assert.equal(saved.input_population,'inclusive');assert.equal(saved.effort_scenario,'high');
  assert.equal(get('engineeringTimerValue').textContent,'2.8×');
  for(const format of ['JSON','CSV']){await get('engineering'+format).onclick();assert.deepEqual(exported,{report_id:'b'.repeat(64),privacy:true},'Pending timeout, scenario and population cannot replace the displayed snapshot')}
  context.data.engineering={...context.data.engineering,report_id:'c'.repeat(64)};
  await get('engineeringJSON').onclick();
  assert.equal(exported.report_id,'b'.repeat(64),'An incoming report is not applied until rendering succeeds');
  timer.options={effort_scenario:'high',idle_timeout:10,input_population:'inclusive'};
  context.data.engineering.full_days[8].scenarios.high={average:4};
  context.data.engineering.weekly[0].scenarios.high={total_estimated_hours:64,average_daily_equivalent:null};
  vm.runInContext('renderEngineering()',context);
  assert.equal(get('engineeringFixedValue').textContent,'3.5×');assert.equal(get('engineeringTimerValue').textContent,'2.55×');
  assert.match(get('engineeringTimerMethod').textContent,/high effort.*10-minute timeout.*All ambiguous-inclusive inputs/);
  assert.match(get('engineeringFixedMethod').textContent,/high effort.*fixed-day-v1/);
  context.preferences.privacy=false;vm.runInContext('renderEngineering()',context);
  await get('engineeringCSV').onclick();
  assert.deepEqual(exported,{report_id:'c'.repeat(64),privacy:false},'A successful render applies the new snapshot; privacy changes only the export flag');
  context.preferences.privacy=true;vm.runInContext('renderEngineering()',context);
  context.localStorage.getItem=()=>JSON.stringify(saved);vm.runInContext('bindEngineering()',context);
  assert.equal(get('engineeringScenario').value,'high');assert.equal(get('engineeringTimeout').value,'10');assert.equal(get('engineeringPopulation').value,'inclusive');

  // A sensitivity with no time keeps C fixed and renders N/A, never zero/infinity.
  timer.options={effort_scenario:'central',idle_timeout:2,input_population:'supported'};
  sensitivity.supported[2]={...timerStats(4),denominator_hours:0,defined_daily_dates:[],zero_timer_dates:dates,scenarios:Object.fromEntries(scenarios.map(name=>[name,{...timerStats(4).scenarios[name],pooled:null,daily_minimum:null,daily_maximum:null,daily_median:null,daily_mean:null}]))};
  joint.supported.high=null;vm.runInContext('renderEngineering()',context);
  assert.equal(get('engineeringTimerValue').textContent,'N/A');assert.equal(get('engineeringFixedValue').textContent,'1.75×');
  assert.match(get('engineeringTimerFullDays').textContent,/0\/2 selected daily ratios.*2 dates have zero modeled time/);
  assert.match(get('engineeringJointSensitivity').textContent,/high effort \/ 2-minute timer N\/A/);
  assert.doesNotMatch(share(get('engineeringTimerDaily')),/Infinity|NaN|Unknown/);

  // No matched evidence is distinct from the still-available original fixed-day series.
  const emptyFixed=Object.fromEntries([4,8,12].map(h=>[h,{...fixed[h],denominator_hours:0,scenarios:Object.fromEntries(scenarios.map(name=>[name,{active_date_estimated_hours:0,average:null,minimum:null,maximum:null,median:null}]))}]));
  const emptyStats={cohort_dates:[],denominator_hours:0,defined_daily_dates:[],zero_timer_dates:[],scenarios:Object.fromEntries(scenarios.map(name=>[name,{numerator_hours:0,pooled:null,daily_minimum:null,daily_maximum:null,daily_median:null,daily_mean:null}]))};
  for(const p of ['supported','inclusive'])for(const tau of [2,5,10])sensitivity[p][tau]=emptyStats;
  timer.cohort.dates=[];timer.cohort.no_supported_timer_dates=['2026-01-01','2026-01-02','2026-01-03'];timer.matched_fixed=emptyFixed;
  for(const day of timer.days.slice(0,2)){day.in_cohort=false;day.exclusion_reason='no_supported_reference_timer';for(const tau of [2,5,10]){day.hours.supported[tau]=0;day.ratios.supported[tau]={low:null,central:null,high:null}}}
  timer.full_days={dates:[],matched_fixed:emptyFixed,sensitivity};
  timer.weekly=[{date:'2026-01-05',dates:[],sensitivity,matched_fixed:emptyFixed}];
  context.monday=date=>date>='2026-01-05'?'2026-01-05':'2025-12-29';
  vm.runInContext('renderEngineering()',context);
  assert.equal(get('engineeringFixedValue').textContent,'N/A');assert.equal(get('engineeringTimerValue').textContent,'N/A');
  assert.match(get('engineeringMatchedCohort').textContent,/No matched dates.*full fixed-day results remain available/);
  assert.match(share(get('engineeringDays')),/Week 2026-01-05.*outside the output-assessment manifest.*0 dates.*timer pooled N\/A.*2026-01-05.*0.8 modeled chat h/);
  stats.eligible_dates=0;vm.runInContext('renderEngineering()',context);
  assert.equal(get('engineeringStats').children[1].children[4].textContent,'N/A','An empty full-D denominator is unavailable, not unknown output or zero');
  assert.equal(vm.runInContext("engineeringNumber(.001,' modeled chat h')",context),'0.001 modeled chat h','Positive sub-minute time must not round to a displayed zero denominator');
  assert.match(html,/Fixed-day equivalent — assumed hours\/day/);assert.match(html,/Message-timer equivalent — modeled chat hours/);
  assert.match(html,/\.engineering-comparison\{display:grid;grid-template-columns:repeat\(2,minmax\(0,1fr\)\)/);
  assert.match(html,/@media\(max-width:850px\)\{\.engineering-comparison\{grid-template-columns:1fr\}/);
  console.log('Dual-calculation dashboard checks passed: matched cards, pooled/daily distinction, scope gaps, sensitivities, independent preferences and applied exports.');

  // Individual choices use the global persisted document, independent of visible table rows.
  vm.runInContext(fs.readFileSync(path.join(__dirname,'..','engineering_table.js'),'utf8'),context);
  const clone=value=>JSON.parse(JSON.stringify(value));
  const ref={fingerprint:'a'.repeat(64),classifier_version:'human-inputs-v1'};
  let server={schema_version:1,version:7,updated_at:'2026-01-06T00:00:00Z',entries:[{id:'B',reference:ref,rationale:'PRIVATE reason'},{id:'Z',reference:ref}]};
  const input=(id,date,classification='ambiguous',inScope=true)=>({id,local_date:date,local_timestamp:date+'T09:00:00+00:00',original_timestamp:date+'T09:00:00Z',timestamp:date+'T09:00:00+00:00',timestamp_basis:'original input event',provider:'Codex',session:'PRIVATE_CHAT_'+id,classification,reason:classification==='ambiguous'?'Human origin not established':'Recorded source classification',classifier_version:'human-inputs-v1',source_statuses:['current'],in_scope:inScope});
  const inputs=[input('A',dates[0]),input('B',dates[1]),input('S',dates[0],'supported_human'),input('X',dates[0],'excluded'),input('Z',dates[1],'ambiguous',false)];
  let aliases={};const changedChoices=new Set();
  const resolution=()=>{
    const ids=server.entries.map(entry=>entry.id),resolved_ids={},missing_ids=[],changed_ids=[],invalid_ids=[];
    for(const id of ids){const target=aliases[id]||id,event=inputs.find(event=>event.id===target);if(!event)missing_ids.push(id);else if(changedChoices.has(id))changed_ids.push(id);else if(event.classification!=='ambiguous'||event.provenance_conflict)invalid_ids.push(id);else resolved_ids[id]=target}
    const valid=Object.keys(resolved_ids),inside=valid.filter(id=>inputs.find(event=>event.id===resolved_ids[id]).in_scope),outside=valid.filter(id=>!inside.includes(id));
    return {version:server.version,ids,valid_ids:valid,resolved_ids,selected_count:ids.length,valid_count:valid.length,in_scope_ids:inside,in_scope_count:inside.length,outside_scope_ids:outside,missing_ids,changed_ids,invalid_ids,headline_scope_ids:{2:inside,5:inside,10:inside},outside_cohort_ids:{2:outside,5:outside,10:outside},label:'Supported + '+inside.length+' user-included ambiguous inputs',warnings:[],limitations:[]};
  };
  timer.cohort.dates=dates;timer.matched_fixed=fixed;timer.cohort.no_supported_timer_dates=['2026-01-03'];
  for(const p of ['supported','selected','inclusive'])sensitivity[p]={2:timerStats(4),5:timerStats(10),10:timerStats(20)};
  joint.selected=joint.supported;timer.full_days={dates,sensitivity,matched_fixed:fixed};timer.weekly=[];timer.options={effort_scenario:'central',idle_timeout:5,input_population:'supported'};
  for(const day of timer.days){day.hours.selected=clone(day.hours.supported);day.ratios.selected=clone(day.ratios.supported);day.included_inputs={supported:1,selected:1,inclusive:2}}
  context.data.engineering.human_inputs={events:inputs,selection:clone(server)};
  timer.selection=resolution();stats.eligible_dates=3;
  vm.runInContext('renderEngineering()',context);
  const table=()=>vm.runInContext('engineeringTimerTableDOM',context);
  table().inputs.date_text.value=dates[0];table().inputs.date_text.oninput();
  assert.match(table().count.textContent,/1 of 5 rows/);
  const descendants=node=>[node,...node.children.flatMap(descendants)];
  const shownCheckbox=()=>descendants(table().body).find(node=>node.type==='checkbox');
  assert.equal(descendants(table().body).filter(node=>node.type==='checkbox').length,1,'Supported and known excluded events cannot be selected');
  assert.notEqual(shownCheckbox().indeterminate,true,'An unselected input is not an unresolved saved choice');
  assert.doesNotMatch(flatten(table().body),/PRIVATE_CHAT|PRIVATE reason/);
  assert.match(flatten(table().body),/Original 2026-01-01T09:00:00Z.*UTC.*Codex.*Chat/);
  assert.doesNotMatch(share(table().body),/original input event|Human origin not established|PRIVATE/);
  assert.match(get('engineeringInputSelectionSummary').textContent,/version 7.*2 saved choices globally.*1 outside/);
  assert.match(share(get('engineeringInputSelectionIds')),/B, Z/);

  const requests=[];let failPost=false,waitForGet=null,releaseGet;
  const selectionFetch=async(url,options)=>{
    assert.equal(url,'/api/engineering/input-selection');requests.push({url,options});
    if(!options){if(waitForGet)await waitForGet;return {ok:true,json:async()=>({selection:clone(server),resolution:resolution()})}}
    const body=JSON.parse(options.body);
    if(failPost)return {ok:false,json:async()=>({error:'Input selection version changed; reload'})};
    assert.equal(body.base_version,server.version);
    server={schema_version:1,version:server.version+1,updated_at:'2026-01-06T01:00:00Z',entries:body.entries.map(entry=>({...entry,reference:entry.reference||ref}))};
    return {ok:true,json:async()=>({selection:clone(server),resolution:resolution()})};
  };
  context.fetch=selectionFetch;
  const refreshSelection=async()=>{loads++;context.data.engineering.report_id=String(server.version).padStart(64,'0');context.data.engineering.human_inputs.selection=clone(server);timer.selection=resolution();timer.options.input_population=get('engineeringPopulation').value;vm.runInContext('renderEngineering()',context);return true};
  context.load=refreshSelection;
  waitForGet=new Promise(resolve=>{releaseGet=resolve});
  const checkbox=shownCheckbox();checkbox.checked=true;const saving=checkbox.onchange();
  assert.equal(checkbox.disabled,true);assert.equal(get('engineeringJSON').disabled,true);
  await vm.runInContext("engineeringToggleInput('X',true)",context);
  assert.equal(requests.length,1,'Selection writes are serialized while one is pending');
  releaseGet();await saving;waitForGet=null;
  assert.deepEqual(server.entries.map(entry=>entry.id),['B','Z','A']);
  assert.deepEqual(server.entries[0],{id:'B',reference:ref,rationale:'PRIVATE reason'},'Hidden choices and original references survive a visible checkbox update');
  assert.equal(get('engineeringPopulation').value,'selected');assert.equal(checkbox.disabled,false);
  assert.match(get('engineeringTimerMethod').textContent,/Supported \+ 2 user-included ambiguous inputs/);
  assert.equal(timer.selection.version,8);
  assert.equal(vm.runInContext('engineeringSelection().input_selection_version',context),undefined,'Live reloads request the latest selection rather than pinning the previous version');
  assert.equal(get('engineeringSensitivity').children.length,12,'All three populations retain 2/5/10-minute sensitivities');
  assert.equal(get('engineeringFixedValue').textContent,'1.75×');assert.deepEqual(timer.cohort.dates,dates);
  table().clear.onclick();
  const dayTwo=table().body.children.find(row=>row.children[0].textContent===dates[1]);
  assert.equal(descendants(dayTwo).find(node=>node.type==='checkbox').checked,true,'Showing the hidden date restores its saved checkbox state');

  let downloaded;
  context.engineeringDownload=(text,name)=>{downloaded={doc:JSON.parse(text),name}};
  await get('engineeringInputExport').onclick();assert.deepEqual(downloaded.doc,server);assert.match(downloaded.name,/private-input-selection-v8/);
  await get('engineeringInputReset').onclick();assert.deepEqual(server.entries,[]);assert.equal(get('engineeringPopulation').value,'supported');
  get('engineeringInputImport').files=[{size:100,text:async()=>JSON.stringify(downloaded.doc)}];
  await get('engineeringInputImport').onchange();
  assert.deepEqual(server.entries,downloaded.doc.entries);assert.equal(server.version,10);assert.equal(get('engineeringPopulation').value,'selected');
  assert.equal(get('engineeringInputImport').value,'');

  // A stale concurrent write fails visibly and leaves the displayed version and choices intact.
  failPost=true;const before=clone(server),beforeLoads=loads;
  await vm.runInContext("engineeringToggleInput('A',false)",context);
  assert.deepEqual(server,before);assert.equal(loads,beforeLoads);
  assert.match(get('engineeringInputLocalStatus').textContent,/not saved.*Reload and retry/);
  assert.equal(timer.selection.version,10);
  assert.equal(get('engineeringJSON').disabled,false);
  failPost=false;await vm.runInContext("engineeringToggleInput('A',false)",context);
  assert.deepEqual(server.entries.map(entry=>entry.id),['B','Z']);assert.equal(server.version,11);
  assert.match(get('engineeringTimerMethod').textContent,/Supported \+ 1 user-included ambiguous inputs/);
  assert.equal(get('engineeringFixedValue').textContent,'1.75×');assert.deepEqual(timer.cohort.dates,dates);
  context.load=async()=>{throw Error('Refresh interrupted')};
  await vm.runInContext("engineeringToggleInput('B',false)",context);
  assert.deepEqual(server.entries.map(entry=>entry.id),['Z']);assert.equal(server.version,12);
  assert.match(get('engineeringInputLocalStatus').textContent,/version 12 was saved.*displayed report has not refreshed/);
  assert.equal(timer.selection.version,11,'A saved decision followed by a failed refresh must not silently change the displayed calculation');
  context.fetch=async(url,options)=>{assert.equal(url,'/api/engineering/export');exported=JSON.parse(options.body);return {ok:true,json:async()=>({id:'fixture',report:{cutoff:'applied'},csv:'applied-csv'})}};
  context.engineeringDownload=(text,name,type)=>downloads.push({text,name,type});
  for(const format of ['JSON','CSV']){await get('engineering'+format).onclick();assert.deepEqual(exported,{report_id:String(11).padStart(64,'0'),privacy:true},'Saving a choice before a failed refresh must export the earlier displayed calculation')}
  const snapshotFetch=context.fetch;let requestsAfterFailure=0;
  context.fetch=async(...args)=>{requestsAfterFailure++;return snapshotFetch(...args)};
  const renderComparison=context.renderEngineeringComparison;
  context.data.engineering.report_id='d'.repeat(64);
  context.renderEngineeringComparison=()=>{throw Error('Render interrupted')};
  assert.throws(()=>vm.runInContext('renderEngineering()',context),/Render interrupted/);
  context.renderEngineeringComparison=renderComparison;
  for(const format of ['JSON','CSV'])await get('engineering'+format).onclick();
  assert.equal(requestsAfterFailure,0,'A partial render cannot export a mismatched snapshot');
  assert.match(get('engineeringStatus').textContent,/Refresh before exporting/);
  assert.match(get('status').textContent,/Export failed.*Refresh the report/);
  const complete=context.data.engineering;
  for(const missing of [undefined,{...complete,report_id:undefined},{...complete,report_id:''}]){
    context.data.engineering=complete;vm.runInContext('renderEngineering()',context);
    context.data.engineering=missing;vm.runInContext('renderEngineering()',context);
    for(const format of ['JSON','CSV'])await get('engineering'+format).onclick();
    assert.equal(requestsAfterFailure,0,'Missing snapshots must never fall back to recalculating filters');
  }
  context.data.engineering=complete;vm.runInContext('renderEngineering()',context);
  const beforeErrorDownloads=downloads.length;let expiredRequests=0;
  context.fetch=async()=>{expiredRequests++;return {ok:false,json:async()=>({error:'Displayed snapshot expired; refresh /PRIVATE/local/path'})}};
  for(const format of ['JSON','CSV'])await get('engineering'+format).onclick();
  assert.equal(expiredRequests,2,'Expired snapshots are not retried with recomputed controls');
  assert.equal(downloads.length,beforeErrorDownloads);
  assert.match(get('engineeringStatus').textContent,/snapshot expired.*PRIVATE/);
  assert.doesNotMatch(get('status').textContent,/PRIVATE|local\/path/);
  assert.match(get('status').textContent,/Export failed.*Refresh the report/);
  // Alias enrichment retains choices under saved IDs; UI actions operate on the resolved logical input.
  context.fetch=selectionFetch;context.load=refreshSelection;
  aliases={'A-old':'A','A-second':'A','A-late':'A','Z-old':'Z'};
  for(const order of [['A-old','A-second'],['A-second','A-old']]){
    server={...server,version:20,entries:[...order.map(id=>({id,reference:ref,rationale:'PRIVATE alias rationale '+id})),{id:'B',reference:ref},{id:'Z-old',reference:ref},{id:'U',reference:ref}]};
    await refreshSelection();
    const first=shownCheckbox();
    assert.equal(first.checked,true,'A saved alias checks the stable input row');
    assert.notEqual(first.indeterminate,true,'Valid aliases must not be presented as unresolved');
    const exceptionText=flatten(get('engineeringInputExceptions'));
    assert.match(exceptionText,/Saved choices outside this report/);
    assert.equal(descendants(get('engineeringInputExceptions')).filter(node=>node.textContent==='Remove unavailable saved choice').length,1,'Only the truly missing U entry lacks metadata; valid aliases resolve to their event');
    assert.doesNotMatch(share(get('engineeringInputExceptions')),/PRIVATE|original input event/);
    context.preferences.privacy=false;vm.runInContext('renderEngineering()',context);
    assert.match(flatten(table().body),/PRIVATE alias rationale A-old/);assert.match(flatten(table().body),/PRIVATE alias rationale A-second/);
    assert.doesNotMatch(share(table().body),/PRIVATE/);
    context.preferences.privacy=true;vm.runInContext('renderEngineering()',context);
    const originalEntries=clone(server.entries);
    await vm.runInContext("engineeringToggleInput('A',true)",context);
    assert.deepEqual(server.entries,originalEntries,'Including an already-resolved input preserves all saved IDs and original references');
    server.entries.push({id:'A-late',reference:ref});
    const checkbox=shownCheckbox();checkbox.checked=false;await checkbox.onchange();
    assert.deepEqual(server.entries.map(entry=>entry.id),['B','Z-old','U'],'Unchecking one logical input removes every resolving alias and preserves hidden/unresolved choices');
    assert.equal(inputs.find(event=>event.id==='A').classification,'ambiguous');
  }
  changedChoices.add('A');
  for(const order of [['A','A-old'],['A-old','A']]){
    server={...server,entries:order.map(id=>({id,reference:ref}))};await refreshSelection();
    assert.equal(shownCheckbox().checked,true);assert.notEqual(shownCheckbox().indeterminate,true,'One valid alias is sufficient even when another saved reference changed');
  }
  server={...server,entries:[{id:'A',reference:ref}]};await refreshSelection();
  assert.equal(shownCheckbox().indeterminate,true,'A lone changed reference is visibly unresolved');
  changedChoices.clear();
  server={...server,entries:[{id:'A-old',reference:ref},{id:'A-second',reference:ref},{id:'U',reference:ref}]};await refreshSelection();
  const beforeChange=shownCheckbox();changedChoices.add('A-old');changedChoices.add('A-second');
  beforeChange.checked=false;await beforeChange.onchange();
  assert.deepEqual(server.entries.map(entry=>entry.id),['U'],'Choices that become unresolved after display can still be deselected');changedChoices.clear();
  inputs.find(event=>event.id==='A').aliases=['A','A-old'];changedChoices.add('A-old');
  server={...server,entries:[{id:'A-old',reference:ref}]};await refreshSelection();
  assert.equal(shownCheckbox().checked,true,'A changed saved alias remains associated with its known event');
  assert.equal(shownCheckbox().indeterminate,true);const changedAlias=shownCheckbox();changedAlias.checked=false;await changedAlias.onchange();
  assert.deepEqual(server.entries,[]);changedChoices.clear();
  // A family can merge while the view is open; translate the displayed saved IDs through fresh resolution.
  server={...server,version:30,entries:[{id:'A-old',reference:ref},{id:'A-second',reference:ref},{id:'U',reference:ref}]};
  await refreshSelection();const beforeMerge=shownCheckbox();assert.equal(beforeMerge.checked,true);
  inputs.push({...inputs.find(event=>event.id==='A'),id:'M'});aliases['A-old']='M';aliases['A-second']='M';
  const removedA=inputs.splice(inputs.findIndex(event=>event.id==='A'),1)[0];
  beforeMerge.checked=false;await beforeMerge.onchange();
  assert.deepEqual(server.entries.map(entry=>entry.id),['U'],'Fresh alias resolution preserves the intent of unchecking the displayed input after a merge');
  inputs.push(removedA);aliases['A-old']='A';aliases['A-second']='A';
  const conflict={...input('F',dates[0]),aliases:['F','F-old','F-copy'],provenance_conflict:true,reason:'Conflicting authoritative original timestamps'};inputs.push(conflict);aliases['F-old']='F';aliases['F-copy']='F';
  for(const inScope of [true,false]){
    conflict.in_scope=inScope;server={...server,version:40,entries:[{id:'F-old',reference:ref},{id:'F-copy',reference:ref},{id:'U',reference:ref}]};await refreshSelection();
    const container=inScope?table().body:get('engineeringInputExceptions');
    const conflictRow=descendants(container).find(node=>node.className==='engineering-input-event'&&flatten(node).includes('Conflicting authoritative original timestamps'));
    assert.ok(conflictRow,'Conflicted aliases retain their inspectable event inside and outside the applied scope');assert.equal(descendants(conflictRow).some(node=>node.type==='checkbox'),false,'Conflicted originals cannot be newly included');
    assert.equal(descendants(get('engineeringInputExceptions')).filter(node=>node.textContent==='Remove unavailable saved choice').length,1,'Only U has unavailable metadata; invalid aliases still identify the conflicting event');
    const removeConflict=descendants(conflictRow).find(node=>node.textContent==='Remove invalid saved choice');assert.ok(removeConflict);await removeConflict.onclick();
    assert.deepEqual(server.entries.map(entry=>entry.id),['U']);
    const unselectedConflict=descendants(inScope?table().body:get('engineeringInputExceptions')).find(node=>node.className==='engineering-input-event'&&flatten(node).includes('Conflicting authoritative original timestamps'));
    assert.equal(unselectedConflict?descendants(unselectedConflict).some(node=>node.type==='checkbox'):false,false);
  }
  console.log('Immutable export and alias UI checks passed: rendered snapshot IDs, both formats, failed refresh/render isolation, missing/expired snapshots, alias-family selection/deselection, hidden choices and conflict removal.');
  console.log('Individual input dashboard checks passed: separate classifications, private aliases, hidden choice/reference preservation, serialized versioned saves, applied export pinning, reset and local JSON roundtrip.');
})().catch(error=>{console.error(error);process.exitCode=1});
