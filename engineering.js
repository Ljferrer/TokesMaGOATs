/* Engineering estimates are independent of token/model attribution. */
function engineeringText(tag, value, className) {
  const node=document.createElement(tag);node.textContent=value;
  if(className)node.className=className;
  return node;
}
function engineeringNumber(value, suffix='') {
  return value===null||value===undefined?'Unknown':new Intl.NumberFormat('en',{maximumFractionDigits:2}).format(value)+suffix;
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
  return {comparison_hours:String(filter?.comparison_hours||$('engineeringHours').value||8),
    effort_threshold:filter?(filter.threshold===null?'':String(filter.threshold)):($('engineeringIgnoreDays').checked?$('engineeringThreshold').value:'')};
}
function renderEngineeringThresholdControl() {
  const label=Number($('engineeringThreshold').value).toFixed(2)+'×';
  $('engineeringThresholdValue').textContent=label;
  $('engineeringThreshold').ariaValueText=label;
  $('engineeringThreshold').disabled=!$('engineeringIgnoreDays').checked;
}
function renderEngineering() {
  $('engineeringEditor').hidden=preferences.privacy;
  const e=data?.engineering;if(!e)return;
  const hours=String(e.day_filter?.comparison_hours||(['4','8','12'].includes($('engineeringHours').value)?$('engineeringHours').value:8));
  const stats=e.sensitivity[hours],full=e.full_days[hours];
  const threshold=e.day_filter?.threshold;
  $('engineeringFilterSummary').textContent=threshold==null?'Low-effort filter off — all token-active dates count.':`Filtered effort statistics: ${stats.excluded_dates} of ${stats.eligible_dates_before_filter} token-active dates excluded below ${Number(threshold).toFixed(2)}× central (${engineeringNumber(threshold*Number(hours),' h')} at ${hours} h/day). Unknown days remain included. Usage and evidence below retain all dates.`;
  $('engineeringScope').textContent=e.delivery_scope+' '+e.repositories.length+' mapped repositories · timezone '+e.timezone;
  $('engineeringCoverage').textContent=`${stats.status} · ${stats.assessed_dates}/${stats.eligible_dates} eligible token-active dates assessed · denominator ${stats.eligible_dates} dates × ${hours} hours = ${stats.denominator_hours} hours. Report cutoff ${e.cutoff}; assessment cutoff ${e.assessment_cutoff||'none'}. Privacy ${preferences.privacy?'on':'off'}.`;
  $('engineeringReconciliation').textContent=`Raw-only observations: ${short(e.usage.raw_only_records)} records · ${short(e.usage.raw_only_tokens)} tokens. ${e.usage.raw_only_scope}`;
  $('engineeringStats').replaceChildren();
  for(const scenario of ['low','central','high']){
    const s=stats.scenarios[scenario],row=document.createElement('tr');
    for(const value of [scenario,...['minimum','maximum','median','average'].map(k=>engineeringNumber(s[k],'×')),engineeringNumber(s.total_estimated_hours,' h')])row.append(engineeringText('td',value));
    $('engineeringStats').append(row);
  }
  $('engineeringFullDays').textContent=`Full days only: ${full.assessed_dates}/${full.eligible_dates} assessed; central average ${engineeringNumber(full.scenarios.central.average,'×')}; ${full.excluded_dates||0} token-active dates excluded. The current local date is partial. Incomplete period statistics remain unknown. Known estimated hours include assessed items on non-token and partly assessed dates, excluding ignored dates; daily ratios use included token-active dates.`;
  const peak=(rows,value)=>rows.reduce((best,row)=>value(row)>value(best)?row:best,rows[0]);
  const usage=Object.entries(e.usage.days).map(([date,u])=>({date,total:u.total}));
  const deliveries=e.days.filter(d=>d.status==='assessed'&&!d.excluded_low_effort);
  const usagePeak=usage.length?peak(usage,d=>d.total):null,deliveryPeak=deliveries.length?peak(deliveries,d=>d.hours.central):null;
  $('engineeringPeaks').textContent=`Usage peak: ${usagePeak?usagePeak.date+' · '+short(usagePeak.total)+' tokens':'N/A'}. Delivery peak: ${deliveryPeak?deliveryPeak.date+' · '+engineeringNumber(deliveryPeak.hours.central,' estimated hours'):'Unknown'}.`;
  const host=$('engineeringDays');host.replaceChildren();
  if($('engineeringPeriod').value==='weekly'){
    for(const week of e.weekly){
      const s=week.scenarios.central,details=document.createElement('details');
      details.append(engineeringText('summary',`Week ${week.date} · ${week.status} · ${engineeringNumber(s.total_estimated_hours/Number(hours),' assessed engineer-days')} · average daily ${engineeringNumber(s.average_daily_equivalent===null||s.average_daily_equivalent===undefined?null:s.average_daily_equivalent*week.comparison_hours/Number(hours),'×')} · ${week.assessed_dates}/${week.eligible_dates} active dates assessed · ${week.excluded_dates||0} excluded`));
      details.append(engineeringText('p',engineeringMetricLine(week.usage),'muted'),engineeringText('p',engineeringActivityLine(week.activity),'muted'));
      details.append(engineeringText('p',`${week.integrations||0} integrations · ${week.deployments||0} independently evidenced deployments · sampled quality: ${(week.quality_scores||[]).map(s=>s??'Unknown').join(', ')||'N/A'}`));
      const dates=e.days.filter(d=>monday(d.date)===week.date);
      for(const day of dates)details.append(engineeringDay(day,e,hours));
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
  $('engineeringThreshold').value='0.10';
  $('engineeringIgnoreDays').checked=false;
  try{const saved=JSON.parse(localStorage.getItem('tokes-engineering-filter')||'{}');$('engineeringIgnoreDays').checked=saved.enabled===true;if(typeof saved.threshold==='number'&&Number.isFinite(saved.threshold)&&saved.threshold>=0&&saved.threshold<=.5)$('engineeringThreshold').value=String(saved.threshold)}catch(_){}
  renderEngineeringThresholdControl();
  $('engineeringThreshold').oninput=renderEngineeringThresholdControl;
  $('engineeringHours').onchange=$('engineeringIgnoreDays').onchange=$('engineeringThreshold').onchange=action(async()=>{
    renderEngineeringThresholdControl();
    try{localStorage.setItem('tokes-engineering-filter',JSON.stringify({enabled:$('engineeringIgnoreDays').checked,threshold:Number($('engineeringThreshold').value)}))}catch(_){}
    await load();
  });
  $('engineeringPeriod').onchange=renderEngineering;
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
