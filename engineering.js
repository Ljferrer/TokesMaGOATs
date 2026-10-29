/* Engineering estimates are independent of token/model attribution. */
function engineeringText(tag, value, className) {
  const node=document.createElement(tag);node.textContent=value;
  if(className)node.className=className;
  return node;
}
function engineeringNumber(value, suffix='') {
  return value===null||value===undefined?'Unknown':new Intl.NumberFormat('en',Math.abs(value)>0&&Math.abs(value)<.01?{maximumSignificantDigits:3}:{maximumFractionDigits:2}).format(value)+suffix;
}
function engineeringMetricLine(value) {
  if(!value)return 'Usage evidence: N/A';
  return `Fresh input ${value.fresh_input===null?'Unknown':short(value.fresh_input)} · cache reads ${short(value.cache_read)} (${value.cache_read_share==null?'N/A':(100*value.cache_read_share).toFixed(1)+'% of total'}) · cache writes ${short(value.cache_write)} · generated output ${short(value.output)} · retained total ${short(value.total)} · raw verified ${short(value.raw_verified)} (${value.raw_reconciliation_coverage===null?'N/A':(100*value.raw_reconciliation_coverage).toFixed(1)+'%'}) · mismatched ${short(value.mismatched)} · ledger only ${short(value.ledger_only)} · ${value.unknown_counter_records} records with unknown counters · ${value.aggregate_records} completed-turn aggregates`;
}
function engineeringActivityLine(a) {
  return a?`Agent evidence: ${a.roots} roots / ${a.children} children · ${a.inclusive_identities} inclusive / ${a.positive_accounting_identities} with positive accounting / ${a.zero_or_synthetic_only} zero or synthetic only · observed task-span peak ${a.task_span_peak??'N/A'} (positive view ${a.positive_task_span_peak??'N/A'}) · peak responding density 60/300/600 s: ${Object.values(a.responding_density).map(n=>n??'N/A').join(' / ')} · ${a.missing_terminal_markers} missing terminals. These are not API-call concurrency.`:'Agent evidence: N/A';
}
function engineeringSelection(applied=false) {
  const filter=applied?data?.engineering?.day_filter:null;
  const timer=applied?data?.engineering?.message_timer?.options:null;
  return {comparison_hours:String(filter?.comparison_hours||$('engineeringHours').value||8),
    effort_threshold:filter?(filter.threshold===null?'':String(filter.threshold)):($('engineeringIgnoreDays').checked?$('engineeringThreshold').value:''),
    effort_scenario:timer?.effort_scenario||$('engineeringScenario').value||'central',
    idle_timeout:String(timer?.idle_timeout||$('engineeringTimeout').value||5),
    input_population:timer?.input_population||$('engineeringPopulation').value||'supported',
    input_selection_version:applied&&data?.engineering?.message_timer?.selection?String(data.engineering.message_timer.selection.version):''};
}
function renderEngineeringThresholdControl() {
  const label=Number($('engineeringThreshold').value).toFixed(2)+'×';
  $('engineeringThresholdValue').textContent=label;
  $('engineeringThreshold').ariaValueText=label;
  $('engineeringThreshold').disabled=!$('engineeringIgnoreDays').checked;
}
function engineeringRatio(value) {
  return value===null||value===undefined?'N/A':engineeringNumber(value,'×');
}
function engineeringPopulationLabel(timer,population) {
  return population==='supported'?'Supported human inputs':population==='selected'?timer.selection.label:'All ambiguous-inclusive inputs';
}
function engineeringDailyStats(id,values) {
  $(id).replaceChildren();
  for(const [label,value] of values){const pair=document.createElement('div');pair.append(engineeringText('dt',label),engineeringText('dd',engineeringRatio(value)));$(id).append(pair)}
}
function engineeringTimerDay(day,timer) {
  const {idle_timeout,input_population,effort_scenario}=timer.options;
  const duration=day.hours[input_population][String(idle_timeout)],ratio=day.ratios[input_population][String(idle_timeout)][effort_scenario];
  const reason={outside_token_active_scope:'outside token-active scope',low_effort_filter:'low-effort filter',unknown_output:'unknown output',no_supported_reference_timer:'no supported reference time'}[day.exclusion_reason];
  return `${day.date} · ${day.in_cohort?'matched date':'outside matched dates: '+reason} · ${engineeringNumber(duration,' modeled chat h')} · ${effort_scenario} timer equivalent ${day.effort_status==='assessed'?engineeringRatio(ratio):'Unknown output'}${day.partial_day?' · partial day':''}`;
}
function engineeringMatchedWeek(week,timer,hours) {
  const {input_population,idle_timeout,effort_scenario}=timer.options;
  const selected=week.sensitivity[input_population][String(idle_timeout)],value=selected.scenarios[effort_scenario],fixed=week.matched_fixed[hours];
  return `Matched weekly comparison · ${week.dates.length} dates · ${effort_scenario} conventional effort ${engineeringNumber(value.numerator_hours,' h')} · fixed ${engineeringRatio(fixed.scenarios[effort_scenario].average)} / ${engineeringNumber(fixed.denominator_hours,' assumed h')} · timer pooled ${engineeringRatio(value.pooled)} / ${engineeringNumber(selected.denominator_hours,' modeled chat h')} · timer unweighted daily mean ${engineeringRatio(value.daily_mean)}.`;
}
function renderEngineeringComparison(e,hours) {
  const t=e.message_timer;
  for(const id of ['engineeringFixedDaily','engineeringTimerDaily','engineeringSensitivity','engineeringInputOnlyDates','engineeringTimerLimitations'])$(id).replaceChildren();
  for(const id of ['engineeringFixedCalculation','engineeringFixedMethod','engineeringTimerCalculation','engineeringTimerMethod','engineeringMatchedFixedFullDays','engineeringTimerFullDays','engineeringTimerLimits','engineeringFullScope','engineeringJointSensitivity','engineeringHumanCoverage','engineeringTimerReconciliation','engineeringInputSelectionSummary','engineeringInputSelectionIds'])$(id).textContent='';
  $('engineeringFixedValue').textContent=$('engineeringTimerValue').textContent='N/A';
  if(!t){$('engineeringMatchedCohort').textContent='Message-timer evidence is unavailable. The full fixed-day summary remains below.';return}
  const {idle_timeout,input_population,effort_scenario:scenario}=t.options;
  const timeout=String(idle_timeout),population=engineeringPopulationLabel(t,input_population);
  $('engineeringSelectedOption').textContent=t.selection?.label||'Supported + user-included ambiguous inputs';
  const cohort=t.cohort,stats=t.sensitivity[input_population][timeout],s=stats.scenarios[scenario];
  const fixed=t.matched_fixed[hours],f=fixed.scenarios[scenario];
  $('engineeringMatchedCohort').textContent=`Matched comparison C: ${cohort.dates.length} of ${cohort.token_active_dates.length} token-active dates, with assessed output and positive supported time at the reference 5-minute timeout, after the low-effort filter. Both cards use the ${scenario} effort estimate on these same dates. This cohort stays fixed across timeout and input sensitivities.${cohort.dates.length?'':' No matched dates; the full fixed-day results remain available below.'}`;
  $('engineeringFixedValue').textContent=engineeringRatio(f.average);
  $('engineeringFixedCalculation').textContent=`${engineeringNumber(f.active_date_estimated_hours,' conventional h')} ÷ ${engineeringNumber(fixed.denominator_hours,' assumed h')} (${cohort.dates.length} dates × ${hours} h). Period ratio equals the arithmetic daily mean.`;
  $('engineeringFixedMethod').textContent=`${scenario} effort · matched dates C · method ${t.fixed_method_version} · comparison day ${hours} h; not recorded human time.`;
  engineeringDailyStats('engineeringFixedDaily',[['Minimum',f.minimum],['Maximum',f.maximum],['Median',f.median],['Arithmetic mean',f.average]]);
  $('engineeringTimerValue').textContent=engineeringRatio(s.pooled);
  $('engineeringTimerCalculation').textContent=`Pooled ratio: ${engineeringNumber(s.numerator_hours,' conventional h')} ÷ ${engineeringNumber(stats.denominator_hours,' modeled chat h')}. The headline is the ratio of sums, not the unweighted daily mean.`;
  $('engineeringTimerMethod').textContent=`${scenario} effort · matched dates C · method ${t.method_version} · ${idle_timeout}-minute timeout · ${population}.`;
  engineeringDailyStats('engineeringTimerDaily',[['Daily minimum',s.daily_minimum],['Daily maximum',s.daily_maximum],['Daily median',s.daily_median],['Unweighted daily mean',s.daily_mean]]);
  const full=t.full_days.sensitivity[input_population][timeout],fullFixed=t.full_days.matched_fixed[hours];
  $('engineeringMatchedFixedFullDays').textContent=`Full days only: ${t.full_days.dates.length} matched dates; ${engineeringRatio(fullFixed.scenarios[scenario].average)} from ${engineeringNumber(fullFixed.scenarios[scenario].active_date_estimated_hours,' conventional h')} / ${engineeringNumber(fullFixed.denominator_hours,' assumed h')}.`;
  $('engineeringTimerFullDays').textContent=`Full days only: ${full.cohort_dates.length} matched dates; pooled ${engineeringRatio(full.scenarios[scenario].pooled)} from ${engineeringNumber(full.scenarios[scenario].numerator_hours,' conventional h')} / ${engineeringNumber(full.denominator_hours,' modeled chat h')}. ${stats.defined_daily_dates.length}/${cohort.dates.length} selected daily ratios are defined; ${stats.zero_timer_dates.length} dates have zero modeled time at this timeout.`;
  $('engineeringTimerLimits').textContent='Timers union overlapping input windows across all selected chats and providers before splitting by local date. Timer date/project scope matches delivery; provider/model/role filters affect usage and agent activity only. The model can include waiting and miss reading, typing, reviews, meetings and other off-chat work. No supported timer is not evidence of a day off; matched dates do not establish complete time coverage.';
  const addSensitivity=(label,numerator,denominator,ratio)=>{const row=document.createElement('tr');for(const value of [label,engineeringNumber(numerator,' h'),engineeringNumber(denominator,' h'),engineeringRatio(ratio)])row.append(engineeringText('td',value));$('engineeringSensitivity').append(row)};
  for(const h of ['4','8','12']){const value=t.matched_fixed[h];addSensitivity(`Fixed · ${h} h/day · ${scenario}`,value.scenarios[scenario].active_date_estimated_hours,value.denominator_hours,value.scenarios[scenario].average)}
  for(const p of Object.keys(t.sensitivity))for(const tau of ['2','5','10']){const value=t.sensitivity[p][tau],selected=value.scenarios[scenario];addSensitivity(`Timer · ${tau} min · ${engineeringPopulationLabel(t,p)} · ${scenario}`,selected.numerator_hours,value.denominator_hours,selected.pooled)}
  const joint=t.joint[input_population];
  $('engineeringJointSensitivity').textContent=`Joint assumption sensitivity (${population}, same C): low effort / 10-minute timer ${engineeringRatio(joint.low)}; high effort / 2-minute timer ${engineeringRatio(joint.high)}. A zero denominator is N/A. These are not confidence intervals or true bounds.`;
  $('engineeringFullScope').textContent=`Full token-active scope D: ${cohort.token_active_dates.length} dates; ${cohort.eligible_after_filter_dates.length} after the low-effort filter; ${cohort.assessed_dates.length} assessed and ${cohort.unknown_dates.length} unknown. Outside matched C: ${cohort.no_supported_timer_dates.length} dates without supported reference time, ${cohort.low_effort_excluded_dates.length} low-effort dates, and ${engineeringNumber(cohort.excluded_assessed_hours[scenario],' assessed '+scenario+' conventional h')} excluded from the paired comparison. Another ${engineeringNumber(cohort.excluded_known_item_hours[scenario],' known item h')} on unknown-output dates is incomplete evidence. Unknown output is not treated as zero.`;
  const c=t.coverage;
  $('engineeringHumanCoverage').textContent=`Human-input classifier ${t.classifier_version}. All retained sources: ${c.retained_sources??0} retained source files, ${c.current_sources??0} current, ${c.missing_sources??0} missing, ${c.changed_sources??0} changed, ${c.unsupported_sources??0} unsupported; ${c.invalid_timestamp_records??0} invalid timestamps across retained sources. Selected input metadata: ${c.supported_human??0} supported, ${c.ambiguous??0} ambiguous, ${c.excluded??0} excluded. ${c.carry_in_events??0} carry-in events considered from up to 10 minutes before the selection. Boundary context: ${c.boundary_context==='unavailable'?'unavailable':'retained records only'}; complete history is not established. Source counts do not estimate missing human hours.`;
  const r=t.reconciliation;
  $('engineeringTimerReconciliation').textContent=`At ${idle_timeout} minutes, retained inputs model ${engineeringNumber(r.supported_hours[timeout],' h supported')} / ${engineeringNumber(r.inclusive_hours[timeout],' h ambiguous-inclusive')} across all reported dates. Outside matched C: ${r.outside_cohort_dates.length} dates, ${engineeringNumber(r.outside_cohort_supported_hours[timeout],' h supported')} / ${engineeringNumber(r.outside_cohort_inclusive_hours[timeout],' h ambiguous-inclusive')}. ${r.outside_token_active_dates.length} input dates are outside token-active scope; ${r.input_only_dates.length} have no output-assessment record and require reconciliation. No zero output is invented. ${c.unmapped_events??0} inputs have no project mapping; ${c.outside_project_events??0} fall outside selected projects. Unmatched project inputs are excluded when a project is selected. Per-project unions are not additive.`;
  for(const date of r.input_only_dates){const day=t.days.find(d=>d.date===date);if(day)$('engineeringInputOnlyDates').append(engineeringText('p',engineeringTimerDay(day,t),'muted'))}
  $('engineeringTimerLimitations').replaceChildren(...t.limitations.map(value=>engineeringText('p',value,'muted')));
  const selection=t.selection;
  $('engineeringInputSelectionSummary').textContent=selection?`Applied input selection version ${selection.version}: ${selection.label}. ${selection.selected_count} saved choices globally, ${selection.valid_count} valid; ${selection.in_scope_count} in this report and ${selection.outside_scope_ids.length} outside its date/project scope. At ${idle_timeout} minutes, ${selection.headline_scope_ids[timeout].length} chosen inputs have windows on matched C and ${selection.outside_cohort_ids[timeout].length} have windows outside C; overlapping windows do not add time twice. Missing IDs: ${selection.missing_ids.length}; changed: ${selection.changed_ids.length}; invalid: ${selection.invalid_ids.length}. ${(selection.warnings||[]).join(' ')} ${(selection.limitations||[]).join(' ')}`:'No persisted individual input choices are available in this report.';
  $('engineeringInputSelectionIds').textContent=selection?`Saved ambiguous input IDs in this report’s selection metadata (version ${selection.version}): ${selection.ids.join(', ')||'none'}. JSON/CSV preserve each ID’s validity and scope; source classification remains ambiguous for valid choices.`:'';
}
let engineeringInputSaving=false,engineeringInputAliases=new Map();
function engineeringInputBusy(busy) {
  engineeringInputSaving=busy;
  for(const control of document.querySelectorAll('[data-input-selection-control]'))control.disabled=busy;
  for(const id of ['engineeringPopulation','engineeringJSON','engineeringCSV'])$(id).disabled=busy;
}
async function engineeringReadInputSelection() {
  const response=await fetch('/api/engineering/input-selection'),result=await response.json();
  if(!response.ok)throw Error(result.error||'Cannot load input selection');
  return result;
}
async function engineeringSaveInputSelection(change) {
  if(engineeringInputSaving)return;
  engineeringInputBusy(true);
  let savedVersion=null;
  try{
    const current=await engineeringReadInputSelection();
    const entries=change(current.selection.entries);
    const result=await engineeringRequest('/api/engineering/input-selection',{schema_version:1,base_version:current.selection.version,entries});
    savedVersion=result.selection.version;
    $('engineeringPopulation').value=entries.length?'selected':'supported';
    saveEngineeringPreferences();
    await load();
    $('engineeringInputLocalStatus').textContent=`Saved input selection version ${savedVersion}. Source classifications remain unchanged.`;
  }catch(error){
    $('engineeringInputLocalStatus').textContent=(savedVersion===null?'Input selection was not saved. Reload and retry.':'Selection version '+savedVersion+' was saved, but the displayed report has not refreshed. Reload to apply it.')+(preferences.privacy?'':' '+error.message);
    $('status').textContent=savedVersion===null?'Input selection change failed. Reload and retry.':'Input choices saved; reload to refresh the report. Exports remain pinned to the displayed selection version.';
    if(data?.engineering){renderEngineeringInputExceptions(data.engineering);if(typeof renderEngineeringTimerTable==='function')renderEngineeringTimerTable(data.engineering,date=>engineeringInputDay(date,data.engineering))}
  }finally{engineeringInputBusy(false)}
}
function engineeringToggleInput(id,included) {
  return engineeringSaveInputSelection(entries=>{
    const previous=entries.find(entry=>entry.id===id),next=entries.filter(entry=>entry.id!==id);
    if(included)next.push({id,...(previous?.rationale?{rationale:previous.rationale}:{})});
    return next;
  });
}
function engineeringInputEvent(event,e) {
  const row=document.createElement('div');row.className='engineering-input-event';row.dataset.snapshotIgnore='';
  const choices=e.human_inputs?.selection?.entries||[],entry=choices.find(value=>value.id===event.id),selected=Boolean(entry);
  const chat=preferences.privacy?engineeringInputAliases.get(event.provider+':'+event.session)||'Private chat':event.session;
  const time=event.original_timestamp?'Original '+event.original_timestamp:'Original timestamp unavailable; retained '+event.timestamp;
  row.append(engineeringText('p',`${time} · ${event.local_timestamp||event.timestamp} (${e.timezone}) · ${event.provider} · ${chat}`),engineeringText('p',`${event.classification} · ${event.reason} · timestamp basis: ${event.timestamp_basis} · classifier ${event.classifier_version||e.message_timer?.classifier_version}. Source status: ${(event.source_statuses||[]).join(', ')||'unavailable'}.`,'muted'));
  if(event.classification==='ambiguous'){
    const label=document.createElement('label'),checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=selected;
    checkbox.dataset.inputSelectionControl='';checkbox.disabled=engineeringInputSaving;
    checkbox.setAttribute('aria-label',`Include ${event.provider} ${chat} input at ${event.original_timestamp||event.timestamp} in timer`);
    checkbox.onchange=()=>engineeringToggleInput(event.id,checkbox.checked);
    label.append(checkbox,engineeringText('span',' Include in timer'));row.append(label);
    if(selected&&!e.message_timer?.selection?.valid_ids.includes(event.id)){checkbox.indeterminate=true;row.append(engineeringText('p','This saved choice is unresolved or changed and is not included. Review the evidence, then deselect and reselect to confirm it.','muted'))}
  }else if(selected){const button=engineeringText('button','Remove invalid saved choice');button.dataset.inputSelectionControl='';button.disabled=engineeringInputSaving;button.onclick=()=>engineeringToggleInput(event.id,false);row.append(button)}
  if(selected&&!event.in_scope)row.append(engineeringText('p','Saved choice outside the applied report scope; it does not expand the matched comparison.','muted'));
  if(selected&&entry.rationale&&!preferences.privacy)row.append(engineeringText('p','Selection rationale: '+entry.rationale,'muted'));
  return row;
}
function engineeringInputDay(date,e) {
  const events=(e.human_inputs?.events||[]).filter(event=>event.in_scope&&event.local_date===date);
  const details=document.createElement('details');details.dataset.snapshotIgnore='';
  details.append(engineeringText('summary',`Input evidence · ${events.length} events`));
  for(const event of events)details.append(engineeringInputEvent(event,e));
  if(!events.length)details.append(engineeringText('p','No original input timestamps on this date. Timer hours may include a prior date’s carry-in window.','muted'));
  return details;
}
function renderEngineeringInputExceptions(e) {
  const host=$('engineeringInputExceptions');host.replaceChildren();
  const events=e.human_inputs?.events||[],entries=e.human_inputs?.selection?.entries||[];
  engineeringInputAliases=new Map([...new Set(events.map(event=>event.provider+':'+event.session))].sort().map((key,i)=>[key,'Chat '+(i+1)]));
  const dates=new Set((e.message_timer?.days||[]).map(day=>day.date));
  const carry=events.filter(event=>event.in_scope&&!dates.has(event.local_date));
  const outside=events.filter(event=>!event.in_scope&&entries.some(entry=>entry.id===event.id));
  for(const [title,rows] of [['Carry-in inputs before the displayed dates',carry],['Saved choices outside this report',outside]])if(rows.length){host.append(engineeringText('h4',title));for(const event of rows)host.append(engineeringInputEvent(event,e))}
  for(const [i,entry] of entries.entries())if(!events.some(event=>event.id===entry.id)){
    const row=document.createElement('div');row.dataset.snapshotIgnore='';row.append(engineeringText('p',`${preferences.privacy?'Saved choice '+(i+1):entry.id} · unavailable input metadata; this choice remains recorded and is not silently promoted to human input.`));
    const button=engineeringText('button','Remove unavailable saved choice');button.dataset.inputSelectionControl='';button.disabled=engineeringInputSaving;button.onclick=()=>engineeringToggleInput(entry.id,false);row.append(button);host.append(row);
  }
}
function saveEngineeringPreferences() {
  try{const {effort_threshold,input_selection_version,...comparison}=engineeringSelection();localStorage.setItem('tokes-engineering-filter',JSON.stringify({enabled:$('engineeringIgnoreDays').checked,threshold:Number($('engineeringThreshold').value),...comparison}))}catch(_){}
}
function renderEngineering() {
  $('engineeringEditor').hidden=preferences.privacy;
  const e=data?.engineering;if(!e)return;
  const hours=String(e.day_filter?.comparison_hours||(['4','8','12'].includes($('engineeringHours').value)?$('engineeringHours').value:8));
  const stats=e.sensitivity[hours],full=e.full_days[hours];
  const scenario=e.message_timer?.options.effort_scenario||'central';
  renderEngineeringComparison(e,hours);
  renderEngineeringInputExceptions(e);
  if(typeof renderEngineeringTimerTable==='function')renderEngineeringTimerTable(e,date=>engineeringInputDay(date,e));
  const threshold=e.day_filter?.threshold;
  $('engineeringFilterSummary').textContent=threshold==null?'Low-effort filter off — all token-active dates count.':`Filtered effort statistics: ${stats.excluded_dates} of ${stats.eligible_dates_before_filter} token-active dates excluded below ${Number(threshold).toFixed(2)}× central (${engineeringNumber(threshold*Number(hours),' h')} at ${hours} h/day). Unknown days remain included. Usage and evidence below retain all dates.`;
  $('engineeringScope').textContent=e.delivery_scope+' '+e.repositories.length+' mapped repositories · timezone '+e.timezone;
  $('engineeringCoverage').textContent=`${stats.status} · ${stats.assessed_dates}/${stats.eligible_dates} eligible token-active dates assessed · denominator ${stats.eligible_dates} dates × ${hours} hours = ${stats.denominator_hours} hours. Report cutoff ${e.cutoff}; assessment cutoff ${e.assessment_cutoff||'none'}. Privacy ${preferences.privacy?'on':'off'}.`;
  $('engineeringReconciliation').textContent=`Raw-only observations: ${short(e.usage.raw_only_records)} records · ${short(e.usage.raw_only_tokens)} tokens. ${e.usage.raw_only_scope}`;
  $('engineeringStats').replaceChildren();
  for(const scenario of ['low','central','high']){
    const s=stats.scenarios[scenario],row=document.createElement('tr');
    for(const value of [scenario,...['minimum','maximum','median','average'].map(k=>stats.eligible_dates?engineeringNumber(s[k],'×'):engineeringRatio(s[k])),engineeringNumber(s.total_estimated_hours,' h')])row.append(engineeringText('td',value));
    $('engineeringStats').append(row);
  }
  $('engineeringFullDays').textContent=`Full days only: ${full.assessed_dates}/${full.eligible_dates} assessed; ${scenario} average ${full.eligible_dates?engineeringNumber(full.scenarios[scenario].average,'×'):engineeringRatio(full.scenarios[scenario].average)}; ${full.excluded_dates||0} token-active dates excluded. The current local date is partial. Incomplete period statistics remain unknown. Known estimated hours include assessed items on non-token and partly assessed dates, excluding ignored dates; daily ratios use included token-active dates.`;
  const peak=(rows,value)=>rows.reduce((best,row)=>value(row)>value(best)?row:best,rows[0]);
  const usage=Object.entries(e.usage.days).map(([date,u])=>({date,total:u.total}));
  const deliveries=e.days.filter(d=>d.status==='assessed'&&!d.excluded_low_effort);
  const usagePeak=usage.length?peak(usage,d=>d.total):null,deliveryPeak=deliveries.length?peak(deliveries,d=>d.hours.central):null;
  $('engineeringPeaks').textContent=`Usage peak: ${usagePeak?usagePeak.date+' · '+short(usagePeak.total)+' tokens':'N/A'}. Delivery peak: ${deliveryPeak?deliveryPeak.date+' · '+engineeringNumber(deliveryPeak.hours.central,' estimated hours'):'Unknown'}.`;
  const host=$('engineeringDays');host.replaceChildren();
  if($('engineeringPeriod').value==='weekly'){
    for(const week of e.weekly){
      const s=week.scenarios[scenario],details=document.createElement('details');
      const average=s.average_daily_equivalent===null||s.average_daily_equivalent===undefined?null:s.average_daily_equivalent*week.comparison_hours/Number(hours);
      details.append(engineeringText('summary',`Week ${week.date} · full fixed-day scope · ${scenario} effort · ${week.status} · ${engineeringNumber(s.total_estimated_hours/Number(hours),' assessed engineer-days')} · average daily ${week.eligible_dates?engineeringNumber(average,'×'):engineeringRatio(average)} · ${week.assessed_dates}/${week.eligible_dates} active dates assessed · ${week.excluded_dates||0} excluded`));
      const timer=e.message_timer,matched=timer?.weekly.find(w=>w.date===week.date);
      if(matched)details.append(engineeringText('p',engineeringMatchedWeek(matched,timer,hours)));
      details.append(engineeringText('p',engineeringMetricLine(week.usage),'muted'),engineeringText('p',engineeringActivityLine(week.activity),'muted'));
      details.append(engineeringText('p',`${week.integrations||0} integrations · ${week.deployments||0} independently evidenced deployments · sampled quality: ${(week.quality_scores||[]).map(s=>s??'Unknown').join(', ')||'N/A'}`));
      const dates=e.days.filter(d=>monday(d.date)===week.date);
      for(const day of dates)details.append(engineeringDay(day,e,hours));
      host.append(details);
    }
    for(const week of e.message_timer?.weekly||[])if(!e.weekly.some(w=>w.date===week.date)){
      const details=document.createElement('details');details.append(engineeringText('summary',`Week ${week.date} · human inputs outside the output-assessment manifest`),engineeringText('p',engineeringMatchedWeek(week,e.message_timer,hours)));
      for(const day of e.message_timer.days.filter(d=>monday(d.date)===week.date))details.append(engineeringText('p',engineeringTimerDay(day,e.message_timer),'muted'));
      host.append(details);
    }
  }else for(const day of e.days)host.append(engineeringDay(day,e,hours));
  if(!e.days.length)host.append(engineeringText('p','No retained positive-token or delivery evidence in this selection.'));
  $('engineeringAssumptions').replaceChildren(...[e.baseline,...e.assumptions,...e.usage.limitations,...e.activity.limitations].map(t=>engineeringText('p',t,'muted')));
}
function engineeringDay(day,e,hours) {
  const details=document.createElement('details');
  const estimates=day.status==='assessed'?['low','central','high'].map(s=>engineeringNumber(day.hours[s]/Number(hours),'×')).join(' / '):'Unknown';
  details.append(engineeringText('summary',`${day.date}${day.partial_day?' · partial day':''}${day.excluded_low_effort?' · excluded from effort statistics':''} · ${day.eligible?'token-active':'outside active-day denominator'} · ${day.status} · low / central / high ${estimates} · ${day.items.length} work items · ${day.integrations.length} integrations · ${day.deployments?.length||0} evidenced deployments · ${day.unknown_items.length} unknown items · ${day.unmapped_projects?.length||0} unmapped projects`));
  details.append(engineeringText('p',engineeringMetricLine(e.usage.days[day.date]),'muted'));
  const timerDay=e.message_timer?.days.find(d=>d.date===day.date);
  if(timerDay)details.append(engineeringText('p',engineeringTimerDay(timerDay,e.message_timer),'muted'));
  const a=e.activity.days[day.date];
  details.append(engineeringText('p',engineeringActivityLine(a),'muted'));
  for(const [i,item] of day.items.entries()){
    const label=preferences.privacy?'Work item '+(i+1):item.scope;
    // Private free text is inspectable locally, but never enters a PNG snapshot.
    const local=document.createElement('details');local.dataset.snapshotIgnore='';
    local.append(engineeringText('summary',label+' · '+item.effort.status));
    if(!preferences.privacy){
      local.append(engineeringText('pre',JSON.stringify(item,null,2)));
      local.children[1].style.cssText='white-space:pre-wrap;overflow-wrap:anywhere';
    }else local.append(engineeringText('p','Private scope and evidence hidden. Turn privacy off to inspect.'));
    details.append(local);
    for(const review of item.quality)details.append(engineeringText('p',`Sampled quality ${review.quality_score??'Unknown'}/100 · ${review.confidence} confidence · ${review.final_day_scope?'final-day revision inspected':'historical or partial revision scope; later fixes may exist'} · tests: ${review.tests.map(t=>t.classification+': '+t.result+' · '+t.date+' · '+(t.applies_to_delivered?'applies to delivered code':'does not apply to delivered code')).join(', ')||'no evidence'}`));
  }
  const refs=document.createElement('details');refs.dataset.snapshotIgnore='';refs.append(engineeringText('summary','Date review and integration evidence (local only)'));
  if(!preferences.privacy){const pre=engineeringText('pre',JSON.stringify({review:day.review,integrations:day.integrations,deployments:day.deployments,agents:a?.identities,unknown_items:day.unknown_items,unmapped_projects:day.unmapped_projects},null,2));pre.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere';refs.append(pre)}
  else refs.append(engineeringText('p','Evidence labels hidden in privacy mode.'));
  details.append(refs);return details;
}
async function engineeringRequest(path,body) {
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
  const value=await response.json();if(!response.ok)throw Error(value.error||'Engineering request failed');return value;
}
let engineeringDownloadURL=null;
function engineeringDownload(text,name,type) {
  if(engineeringDownloadURL)URL.revokeObjectURL(engineeringDownloadURL);
  engineeringDownloadURL=URL.createObjectURL(new Blob([text],{type}));
  const link=document.createElement('a');link.href=engineeringDownloadURL;link.download=name;link.textContent='Download '+name;
  $('engineeringStatus').replaceChildren(link);link.click();
}
function bindEngineering() {
  const action=fn=>async()=>{try{await fn()}catch(error){$('engineeringStatus').textContent=error.message;$('status').textContent='Engineering action failed. Private details are in the local evidence editor.'}};
  const choices=[['engineeringHours','comparison_hours',['8','4','12']],['engineeringScenario','effort_scenario',['central','low','high']],['engineeringTimeout','idle_timeout',['5','2','10']],['engineeringPopulation','input_population',['supported','selected','inclusive']]];
  for(const [id,,values] of choices)$(id).value=values[0];
  $('engineeringThreshold').value='0.10';
  $('engineeringIgnoreDays').checked=false;
  try{const saved=JSON.parse(localStorage.getItem('tokes-engineering-filter')||'{}');$('engineeringIgnoreDays').checked=saved.enabled===true;if(typeof saved.threshold==='number'&&Number.isFinite(saved.threshold)&&saved.threshold>=0&&saved.threshold<=.5)$('engineeringThreshold').value=String(saved.threshold);for(const [id,key,values] of choices)if(values.includes(String(saved[key])))$(id).value=String(saved[key])}catch(_){}
  renderEngineeringThresholdControl();
  $('engineeringThreshold').oninput=renderEngineeringThresholdControl;
  const change=action(async()=>{
    renderEngineeringThresholdControl();
    saveEngineeringPreferences();
    await load();
  });
  for(const id of [...choices.map(([id])=>id),'engineeringIgnoreDays','engineeringThreshold'])$(id).onchange=change;
  $('engineeringPeriod').onchange=renderEngineering;
  $('engineeringInputReset').onclick=()=>engineeringSaveInputSelection(()=>[]);
  $('engineeringInputExport').onclick=action(async()=>{const result=await engineeringReadInputSelection();engineeringDownload(JSON.stringify(result.selection,null,2),'private-input-selection-v'+result.selection.version+'.json','application/json');$('engineeringInputLocalStatus').textContent='Saved local input selection version '+result.selection.version+'.'});
  $('engineeringInputImport').onchange=action(async()=>{
    const file=$('engineeringInputImport').files[0];if(!file)return;
    try{if(file.size>2*1024*1024)throw Error('Input selection exceeds 2 MiB');const doc=JSON.parse(await file.text());if(doc.schema_version!==1||!Array.isArray(doc.entries))throw Error('Input selection JSON needs schema_version 1 and entries');await engineeringSaveInputSelection(()=>doc.entries)}finally{$('engineeringInputImport').value=''}
  });
  $('engineeringEdit').onclick=action(async()=>{
    const response=await fetch('/api/engineering/assessment');if(!response.ok)throw Error('Cannot load local assessments');
    const result=await response.json();$('engineeringAssessment').value=JSON.stringify(result.assessment,null,2);$('engineeringSnapshots').textContent=JSON.stringify(result.snapshots,null,2);
  });
  $('engineeringCollect').onclick=action(async()=>{const r=await engineeringRequest('/api/engineering/collect');$('engineeringStatus').textContent=r.snapshots+' repository snapshots saved. Load the assessment editor to inspect.'});
  $('engineeringFile').onchange=action(async()=>{const file=$('engineeringFile').files[0];if(file){if(file.size>2*1024*1024)throw Error('Assessment exceeds 2 MiB');$('engineeringAssessment').value=await file.text()}});
  $('engineeringImport').onclick=action(async()=>{const r=await engineeringRequest('/api/engineering/import',JSON.parse($('engineeringAssessment').value));$('engineeringStatus').textContent='Saved immutable version '+r.version;await load()});
  $('engineeringLocalExport').onclick=action(async()=>{const doc=JSON.parse($('engineeringAssessment').value);engineeringDownload(JSON.stringify(doc,null,2),'private-engineering-assessment.json','application/json')});
  for(const format of ['JSON','CSV'])$('engineering'+format).onclick=action(async()=>{
    const result=await engineeringRequest('/api/engineering/export',{filters:{...activeFilters,...engineeringSelection(true)},privacy:preferences.privacy});
    engineeringDownload(format==='JSON'?JSON.stringify(result.report,null,2):result.csv,'engineering-'+result.id.slice(0,12)+'.'+format.toLowerCase(),format==='JSON'?'application/json':'text/csv');
  });
}
