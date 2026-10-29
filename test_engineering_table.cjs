const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.style={};this.attributes={};this.textContent='';this.value=''}
  append(...nodes){this.children.push(...nodes)}
  replaceChildren(...nodes){this.children=nodes}
  setAttribute(name,value){this.attributes[name]=String(value)}
  getAttribute(name){return this.attributes[name]}
}
const host=new Element('div');
const context=vm.createContext({Intl,document:{createElement:tag=>new Element(tag)},$:id=>{assert.equal(id,'engineeringTimerTable');return host},engineeringText:(tag,text,className)=>{const node=new Element(tag);node.textContent=text;node.className=className;return node},engineeringNumber:(value,suffix='')=>new Intl.NumberFormat('en',{maximumFractionDigits:2}).format(value)+suffix,fetch:()=>{throw Error('Table views must not call the API')}});
vm.runInContext(fs.readFileSync('engineering_table.js','utf8'),context);
const run=code=>vm.runInContext(code,context),read=()=>run('engineeringTimerTableDOM');
const plain=value=>JSON.parse(JSON.stringify(value));
const flatten=node=>node.textContent+' '+node.children.map(flatten).join(' ');
const snapshot=node=>node.dataset.snapshotIgnore!==undefined?'':node.textContent+' '+node.children.map(snapshot).join(' ');
const columns=plain(run('engineeringTimerColumns'));
const values=[2.004,0,100,2,2.003,10,null,2];
const numericColumns=columns.filter(column=>column.kind==='number');
const sourceRows=values.map((value,index)=>Object.fromEntries(columns.map(column=>[column.key,column.kind==='number'?values[(index+numericColumns.findIndex(c=>c.key===column.key))%values.length]:column.key==='date'?`2026-01-${String(index+1).padStart(2,'0')}`:['Zulu','bravo','charlie','Alpha','delta','echo',null,'alpha'][index]])));
context.sourceRows=sourceRows;
for(const column of columns){
  for(const direction of [1,-1]){
    context.viewState={sort:column.key,direction,filters:{}};
    const result=plain(run('engineeringTimerView(sourceRows,viewState)'));
    if(column.kind==='number'){
      assert.deepEqual(result.map(row=>row[column.key]),direction===1?[0,2,2,2.003,2.004,10,100,null]:[100,10,2.004,2.003,2,2,0,null],column.key+' numeric raw order and N/A last');
      assert.deepEqual(result.filter(row=>row[column.key]===2).map(row=>row.date),sourceRows.filter(row=>row[column.key]===2).map(row=>row.date),column.key+' stable tie order in both directions');
    }
    else if(column.key==='date')assert.deepEqual(result.map(row=>row.date),[...sourceRows].map(row=>row.date).sort().filter(Boolean)[direction===1?'slice':'reverse']());
    else assert.deepEqual(result.map(row=>row.date),direction===1?['2026-01-04','2026-01-08','2026-01-02','2026-01-03','2026-01-05','2026-01-06','2026-01-01','2026-01-07']:['2026-01-01','2026-01-06','2026-01-05','2026-01-03','2026-01-02','2026-01-04','2026-01-08','2026-01-07']);
  }
}
// Exact inclusive bounds distinguish numbers that display alike; active ranges alone exclude N/A.
for(const column of columns.filter(c=>c.kind==='number')){
  context.viewState={sort:'date',direction:1,filters:{[column.key]:{min:'2.003',max:'2.004'}}};
  assert.deepEqual(plain(run('engineeringTimerView(sourceRows,viewState)')).map(row=>row[column.key]).sort(),[2.003,2.004]);
  context.viewState.filters[column.key]={min:'0',max:'0'};
  assert.deepEqual(plain(run('engineeringTimerView(sourceRows,viewState)')).map(row=>row[column.key]),[0]);
  context.viewState.filters[column.key]={min:'',max:''};
  assert.equal(run('engineeringTimerView(sourceRows,viewState).length'),8);
}
context.sourceRows=[...sourceRows,{...sourceRows[0],date:'2026-02-01',evidence:'ALPHA'}];
context.viewState={sort:'date',direction:1,filters:{date:{text:'2026-01'},evidence:{text:'aLPHa'},inputs:{min:'2',max:'10'}}};
assert.deepEqual(plain(run('engineeringTimerView(sourceRows,viewState)')).map(row=>row.date),['2026-01-04','2026-01-08']);
assert.deepEqual(sourceRows.map(row=>row.inputs),values,'The source row order and values remain unchanged');
context.distinguishingRows=[{date:'smaller',hours5:10},{date:'larger',hours5:200}];
context.viewState={sort:'hours5',direction:1,filters:{}};
assert.equal(run("engineeringTimerView(distinguishingRows,viewState).map(row=>row.date).join(',')"),'smaller,larger','200 sorts after 10 numerically rather than lexically');

const populations=['supported','selected','inclusive'];
const days=values.map((value,index)=>({date:`2026-01-${String(index+1).padStart(2,'0')}`,partial_day:index===7,in_cohort:index<6,effort_status:value===null?'unknown':'assessed',effort_hours:{low:value,central:value,high:value},included_inputs:Object.fromEntries(populations.map(p=>[p,value===null?null:Math.floor(value)])),hours:Object.fromEntries(populations.map(p=>[p,{'2':value,'5':value,'10':value}])),ratios:Object.fromEntries(populations.map(p=>[p,{'5':{low:value,central:value,high:value}}])),exclusion_reason:index===6?'unknown_output':'no_supported_reference_timer'}));
const report={selection:{start:'2026-01-01',end:'2026-01-08',projects:['PRIVATE/customer']},timezone:'America/Los_Angeles',cutoff:'2026-01-09T00:00:00Z',message_timer:{options:{input_population:'selected',effort_scenario:'central'},selection:{label:'Supported + 1 user-included ambiguous inputs',ids:['PRIVATE/input']},cohort:{dates:days.slice(0,6).map(d=>d.date)},days}};
const frozen=JSON.stringify(report);
const savedChoices=new Set(['2026-01-06']);
context.report=report;
context.renderInputs=date=>{const details=new Element('details');details.dataset.snapshotIgnore='';const checkbox=new Element('input');checkbox.type='checkbox';checkbox.checked=savedChoices.has(date);details.append(checkbox);return details};
run('renderEngineeringTimerTable(report,renderInputs)');
assert.equal(read().body.children.length,8);
assert.match(read().count.textContent,/8 of 8 rows.*Date, ascending/);
assert.match(read().scope.textContent,/2026-01-01 through 2026-01-08.*1 selected projects.*6 matched dates C.*Supported \+ 1 user-included ambiguous inputs/);
assert.doesNotMatch(snapshot(host),/PRIVATE|customer/);
assert.match(snapshot(host),/JSON\/CSV exports contain the full report.*PNG preserves this labeled table view subset/);
for(const column of columns){
  const button=read().buttons[column.key];assert.equal(button.tag,'button');assert.equal(button.type,'button');
  const before=read().headers[column.key].getAttribute('aria-sort');
  button.onclick();const first=read().headers[column.key].getAttribute('aria-sort');
  assert.equal(first,before==='ascending'?'descending':'ascending');
  assert.match(button.getAttribute('aria-label'),new RegExp('Sort '+column.label));
  assert.equal(read().indicators[column.key].textContent,first==='ascending'?' ↑':' ↓');
  button.onclick();assert.notEqual(read().headers[column.key].getAttribute('aria-sort'),first);
}
assert.equal(Object.keys(read().inputs).length,14);
for(const input of Object.values(read().inputs))assert.ok(input.getAttribute('aria-label'));
const change=(key,value)=>{const input=read().inputs[key];input.value=value;input.oninput()};
read().buttons.hours5.onclick(); // First click selects ascending numeric order.
read().buttons.hours5.onclick();
change('hours5_min','2.003');change('hours5_max','10');change('date_text','2026-01');change('evidence_text','MATCHED');
assert.match(read().count.textContent,/3 of 8 rows.*5-minute hours, descending/);
assert.deepEqual(read().body.children.map(row=>row.children[0].textContent),['2026-01-06','2026-01-01','2026-01-05']);
assert.match(snapshot(host),/Row filters \(AND\):.*Date contains "2026-01".*5-minute hours ≥ 2.003.*5-minute hours ≤ 10.*Evidence contains "MATCHED"/);
const inputControl=read().inputs.hours5_min;change('hours5_max','2.004');
assert.equal(read().inputs.hours5_min,inputControl,'Typing keeps the same focused input controls');
assert.match(read().count.textContent,/2 of 8 rows/);
assert.equal(savedChoices.has('2026-01-06'),true,'A selected input survives its row being hidden');
change('date_text','2099');assert.match(read().count.textContent,/0 of 8 rows/);assert.match(flatten(read().body),/No rows match/);
read().clear.onclick();
assert.match(read().count.textContent,/8 of 8 rows.*5-minute hours, descending.*Row filters \(AND\): none/);
assert.equal(read().headers.hours5.getAttribute('aria-sort'),'descending');
assert.ok(Object.values(read().inputs).every(input=>input.value===''));
const shown=read().body.children.find(row=>row.children[0].textContent==='2026-01-06');
assert.equal(shown.children.at(-1).children[0].children[0].checked,true,'Rebuilt hidden rows derive checkbox state from saved input decisions');
assert.equal(JSON.stringify(report),frozen,'Sorting/filtering leaves headline inputs, cohort, report and selected IDs untouched');
change('inputs_min','10');run('renderEngineeringTimerTable(report,renderInputs)');
assert.match(read().count.textContent,/2 of 8 rows.*5-minute hours, descending/);
assert.equal(read().inputs.inputs_min.value,'10','View filters persist through report rerenders');
context.report={...report,message_timer:{...report.message_timer,days:[]}};run('renderEngineeringTimerTable(report,renderInputs)');
assert.match(read().count.textContent,/0 of 0 rows/);assert.match(flatten(read().body),/No daily timer data/);
console.log('Timer table checks passed: every sort direction, raw numeric precision, stable ties, N/A/zero handling, inclusive AND filters, accessible headers, clear/rerender state, scope-labeled snapshots and unchanged input selections.');
