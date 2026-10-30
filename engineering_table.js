/* Table views never change the reporting cohort or input-inclusion decisions. */
const engineeringTimerColumns=[
  {key:'date',label:'Date',kind:'text'},
  {key:'inputs',label:'Included inputs',kind:'number'},
  {key:'hours2',label:'2-minute hours',kind:'number'},
  {key:'hours5',label:'5-minute hours',kind:'number'},
  {key:'hours10',label:'10-minute hours',kind:'number'},
  {key:'effort',label:'Conventional effort hours',kind:'number'},
  {key:'ratio5',label:'5-minute ratio',kind:'number'},
  {key:'evidence',label:'Evidence',kind:'text'},
];
let engineeringTimerTableState={sort:'date',direction:1,filters:{}};
let engineeringTimerTableReport=null,engineeringTimerTableDOM=null,engineeringTimerTableInputs=null;

function engineeringTimerRows(report) {
  const timer=report?.message_timer;
  if(!timer)return [];
  const {input_population:population,effort_scenario:scenario}=timer.options;
  const number=value=>typeof value==='number'&&Number.isFinite(value)?value:null;
  const effortClamps=new Map((report.days||[]).map(day=>[day.date,day.clamped_effort]));
  const reasons={outside_token_active_scope:'Outside token-active scope',low_effort_filter:'Low-effort filter',unknown_output:'Unknown output',no_supported_reference_timer:'No supported reference time'};
  return timer.days.map(day=>({
    date:day.date,
    inputs:number(day.included_inputs?.[population]),
    hours2:number(day.hours[population]['2']),
    hours5:number(day.hours[population]['5']),
    hours10:number(day.hours[population]['10']),
    effort:number(day.effort_hours[scenario]),
    ratio5:number(day.ratios[population]['5'][scenario]),
    clamped:{effort:(effortClamps.get(day.date)?.[scenario]||0)>0,ratio5:day.ratio_clamped?.[population]?.['5']?.[scenario]===true},
    evidence:[day.in_cohort?'Matched date':reasons[day.exclusion_reason]||'Outside matched dates',day.effort_status==='assessed'?'Assessed output':'Output unknown',day.partial_day?'Partial day':''].filter(Boolean).join(' · '),
  }));
}

function engineeringTimerView(rows,state) {
  const bound=value=>value===undefined||String(value).trim()===''?null:Number(value);
  return rows.map((row,index)=>({row,index})).filter(({row})=>engineeringTimerColumns.every(column=>{
    const filter=state.filters[column.key];
    if(!filter)return true;
    const value=row[column.key];
    if(column.kind==='text')return !filter.text||String(value??'').toLowerCase().includes(filter.text.toLowerCase());
    const min=bound(filter.min),max=bound(filter.max);
    if(min===null&&max===null)return true;
    return value!==null&&value!==undefined&&(min===null||value>=min)&&(max===null||value<=max);
  })).sort((a,b)=>{
    const left=a.row[state.sort],right=b.row[state.sort];
    if(left===null||left===undefined)return right===null||right===undefined?a.index-b.index:1;
    if(right===null||right===undefined)return -1;
    const difference=typeof left==='number'?left-right:String(left).toLowerCase().localeCompare(String(right).toLowerCase(),'en');
    return difference*state.direction||a.index-b.index;
  }).map(({row})=>row);
}

function engineeringTimerTableFiltersText() {
  const descriptions=[];
  for(const column of engineeringTimerColumns){
    const filter=engineeringTimerTableState.filters[column.key];
    if(!filter)continue;
    if(column.kind==='text'){
      if(filter.text)descriptions.push(`${column.label} contains ${JSON.stringify(filter.text)} (case-insensitive)`);
    }else{
      if(filter.min!==undefined&&filter.min.trim()!=='')descriptions.push(`${column.label} ≥ ${filter.min}`);
      if(filter.max!==undefined&&filter.max.trim()!=='')descriptions.push(`${column.label} ≤ ${filter.max}`);
    }
  }
  return descriptions.length?descriptions.join('; '):'none';
}

function refreshEngineeringTimerTable() {
  const dom=engineeringTimerTableDOM,report=engineeringTimerTableReport,timer=report?.message_timer;
  const rows=engineeringTimerRows(report),visible=engineeringTimerView(rows,engineeringTimerTableState);
  for(const column of engineeringTimerColumns){
    const selected=engineeringTimerTableState.sort===column.key;
    const direction=selected?(engineeringTimerTableState.direction===1?'ascending':'descending'):'none';
    dom.headers[column.key].setAttribute('aria-sort',direction);
    dom.indicators[column.key].textContent=selected?(direction==='ascending'?' ↑':' ↓'):'';
    const next=selected&&direction==='ascending'?'descending':'ascending';
    dom.buttons[column.key].setAttribute('aria-label',`Sort ${column.label} ${next}`);
    dom.buttons[column.key].title=`Sort ${column.label} ${next}`;
  }
  dom.body.replaceChildren();
  for(const row of visible){
    const tr=document.createElement('tr');
    for(const column of engineeringTimerColumns){
      const value=row[column.key];
      const label=value===null||value===undefined?'N/A':column.kind==='number'?engineeringNumber(value,column.key==='ratio5'?'×':''):value;
      const cell=engineeringText('td',label+(value>0&&row.clamped?.[column.key]?' (clamped)':''));
      if(column.key==='evidence'&&engineeringTimerTableInputs){const inputs=engineeringTimerTableInputs(row.date);if(inputs)cell.append(inputs)}
      tr.append(cell);
    }
    dom.body.append(tr);
  }
  if(!visible.length){
    const row=document.createElement('tr'),cell=engineeringText('td',rows.length?'No rows match these table filters.':'No daily timer data in this reporting scope.');
    cell.colSpan=engineeringTimerColumns.length;row.append(cell);dom.body.append(row);
  }
  const filters=engineeringTimerTableFiltersText(),sort=engineeringTimerColumns.find(c=>c.key===engineeringTimerTableState.sort);
  dom.count.textContent=`Table view subset: ${visible.length} of ${rows.length} rows visible. Sort: ${sort.label}, ${engineeringTimerTableState.direction===1?'ascending':'descending'}; N/A last. Row filters (AND): ${filters}.`;
  const selection=report?.selection||{},projectCount=selection.projects?.length||selection.project_count||0;
  const population=timer?.options.input_population==='selected'?(timer.selection?.label||'Supported + user-included ambiguous inputs'):timer?.options.input_population==='inclusive'?'All ambiguous-inclusive inputs':'Supported human inputs';
  dom.scope.textContent=timer?`Full report scope remains ${selection.start||timer.window?.start||'unknown start'} through ${selection.end||timer.window?.end||'unknown end'} · ${report.timezone} · ${projectCount?projectCount+' selected projects':'all projects'} · cutoff ${report.cutoff} · ${timer.cohort.dates.length} matched dates C · ${timer.options.effort_scenario} conventional effort · ${population}. This table always shows 2/5/10-minute hours and the 5-minute daily ratio. Included inputs count original timestamps on each date; carry-in time can have zero inputs on that date.`:'Message-timer evidence is unavailable.';
}

function renderEngineeringTimerTable(report,renderInputs=null) {
  engineeringTimerTableReport=report;
  engineeringTimerTableInputs=renderInputs;
  const host=$('engineeringTimerTable');
  if(!engineeringTimerTableDOM||engineeringTimerTableDOM.host!==host){
    host.replaceChildren();
    host.append(engineeringText('p','These filters affect table rows only. They do not recalculate cards, change input selections or redefine the matched cohort C. Use the global date/project controls to change the report. JSON/CSV exports contain the full report; a PNG preserves this labeled table view subset.','muted'));
    const count=engineeringText('p','','muted'),scope=engineeringText('p','','muted');count.setAttribute('aria-live','polite');
    const clear=engineeringText('button','Clear filters');clear.type='button';clear.dataset.snapshotIgnore='';
    const wrap=document.createElement('div');wrap.className='chart-scroll engineering-timer-scroll';
    wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Scrollable daily timer detail');
    const table=document.createElement('table'),head=document.createElement('thead'),headRow=document.createElement('tr'),filterRow=document.createElement('tr'),body=document.createElement('tbody');
    table.style.minWidth='1100px';table.setAttribute('aria-label','Daily message-timer detail');filterRow.dataset.snapshotIgnore='';
    const headers={},indicators={},buttons={},inputs={};
    for(const column of engineeringTimerColumns){
      const header=document.createElement('th');header.scope='col';
      const indicator=engineeringText('span',''),button=engineeringText('button','↕');button.type='button';button.dataset.snapshotIgnore='';button.style.cssText='padding:4px 7px;margin-left:6px;font-size:12px;min-height:30px';
      header.append(engineeringText('span',column.label),indicator,button);headRow.append(header);
      headers[column.key]=header;indicators[column.key]=indicator;buttons[column.key]=button;
      button.onclick=()=>{engineeringTimerTableState.direction=engineeringTimerTableState.sort===column.key?-engineeringTimerTableState.direction:1;engineeringTimerTableState.sort=column.key;refreshEngineeringTimerTable()};
      const cell=document.createElement('td');
      for(const part of column.kind==='number'?['min','max']:['text']){
        const label=document.createElement('label'),input=document.createElement('input');
        label.style.cssText='display:inline-grid;gap:4px;margin:0 4px 4px 0;font-size:11px;color:var(--muted)';
        input.type=column.kind==='number'?'number':'search';input.step='any';input.style.cssText=`width:${column.kind==='number'?'78':'150'}px;padding:6px`;
        input.setAttribute('aria-label',column.kind==='number'?`${part==='min'?'Minimum':'Maximum'} ${column.label}`:`Filter ${column.label}`);
        input.value=engineeringTimerTableState.filters[column.key]?.[part]||'';
        label.append(engineeringText('span',column.kind==='number'?part==='min'?'Min':'Max':'Contains'),input);cell.append(label);
        inputs[column.key+'_'+part]=input;
        input.oninput=()=>{(engineeringTimerTableState.filters[column.key]||={})[part]=input.value;refreshEngineeringTimerTable()};
      }
      filterRow.append(cell);
    }
    clear.onclick=()=>{engineeringTimerTableState.filters={};for(const input of Object.values(inputs))input.value='';refreshEngineeringTimerTable()};
    head.append(headRow,filterRow);table.append(head,body);wrap.append(table);host.append(count,scope,clear,wrap);
    engineeringTimerTableDOM={host,body,count,scope,headers,indicators,buttons,inputs,clear};
  }
  refreshEngineeringTimerTable();
}
