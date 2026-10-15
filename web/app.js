'use strict';
const $=(query,root=document)=>root.querySelector(query);
const BOOLEAN_ATTRIBUTES={hidden:'hidden',checked:'checked',disabled:'disabled',selected:'selected',readonly:'readOnly',required:'required',multiple:'multiple',autofocus:'autofocus',open:'open',inert:'inert',reversed:'reversed',controls:'controls',loop:'loop',muted:'muted',autoplay:'autoplay',playsinline:'playsInline',novalidate:'noValidate',formnovalidate:'formNoValidate',allowfullscreen:'allowFullscreen',ismap:'isMap',itemscope:'itemScope',defer:'defer',async:'async'};
function el(tag,attrs={},...children){const node=document.createElement(tag);for(const[key,value]of Object.entries(attrs)){if(value==null)continue;if(key==='class')node.className=value;else if(key.startsWith('on'))node.addEventListener(key.slice(2).toLowerCase(),value);else if(Object.hasOwn(BOOLEAN_ATTRIBUTES,key.toLowerCase()))node[BOOLEAN_ATTRIBUTES[key.toLowerCase()]]=!!value;else if(key==='value')node.value=String(value);else node.setAttribute(key,String(value));}for(const child of children.flat(Infinity)){if(child!=null)node.append(child instanceof Node?child:document.createTextNode(String(child)));}return node;}
const clone=value=>JSON.parse(JSON.stringify(value));
const steps=[{id:'personal',label:'Personal info',pages:['profile','dependents','eligibility']},{id:'income',label:'Wages & Income',pages:['income-overview','w2','interest','dividends','capital_gains','carryovers','businesses','retirement','other_income']},{id:'deductions',label:'Deductions',pages:['adjustments','itemized','schedule_1a','payments']},{id:'state',label:'State taxes',pages:['states']},{id:'review',label:'Review',pages:['review','trace']},{id:'forms',label:'Forms & Export',pages:['forms','schedules','payment-voucher','exports','advanced']}];
const pageNames={profile:'You & your household',dependents:'Dependents',eligibility:'Eligibility & other situations','income-overview':'Your income summary',w2:'Wages & salaries · W-2',interest:'Interest · 1099-INT',dividends:'Dividends · 1099-DIV',capital_gains:'Investment sales · 1099-B',carryovers:'Prior-year carryovers',businesses:'Self-employment · Schedule C',retirement:'Retirement & Social Security',other_income:'Other income',adjustments:'Adjustments to income',itemized:'Itemized deductions',schedule_1a:'Additional deductions · Schedule 1-A',payments:'Estimated payments',states:'State return workspace',review:'Check your return',trace:'How we calculated your tax',forms:'Form 1040 worksheet',schedules:'Schedules & workpapers','payment-voucher':'Balance due & payment voucher',exports:'Save & export',advanced:'Advanced input JSON'};
const MONEY_KEYS=new Set(['wages','federal_withholding','social_security_wages','social_security_tips','dependent_care_benefits','medicare_wages','social_security_withholding','medicare_withholding','taxable','tax_exempt','ordinary','qualified','capital_gain_distributions','unrecaptured_1250_gain','collectibles_gain','proceeds','cost_basis','adjustment','revenue','expenses','ira_gross','ira_taxable','pension_gross','pension_taxable','social_security','unemployment','other','student_loan_interest','ira_deduction','hsa_deduction','self_employed_health_insurance','medical','state_local_tax','mortgage_interest','charity','investment_interest','qualified_tips','qualified_overtime','qualified_car_loan_interest','estimated','prior_year_credit','capital_short','capital_long','qbi_loss']);
let schema=null,data=null,result=null,currentId=null,page='profile',revision=0,calculatedRevision=-1,dirty=false,hasSaved=false,synthetic=false,busySave=false,busyIncomeCommit=false,calculationSerial=0,calculateTimer=null,calculatePromise=null,toastTimer=null,dialogNode=null,installPrompt=null,documentURLs=[],calculationError='';
let metadata=window.taxRecordMetadata.empty(),savedUpdatedAt=null;
const openRecords=new Set();
let workspaceWrite=Promise.resolve(),workspaceFailureShown=false;
function workspaceSnapshot(){return data&&currentId?{id:'active',version:1,returnId:currentId,data:clone(data),metadata:clone(metadata),page,dirty,hasSaved,synthetic,savedUpdatedAt}:null;}
function checkpointWorkspace(){
 const snapshot=workspaceSnapshot();if(!snapshot)return Promise.resolve();
 workspaceWrite=workspaceWrite.catch(()=>{}).then(()=>documentOperation('readwrite',store=>store.put(snapshot),'workspace'));
 workspaceWrite.catch(()=>{if(!workspaceFailureShown){workspaceFailureShown=true;notify('The open workspace could not be retained. Save or export before leaving this screen.',true);}});
 return workspaceWrite;
}
function tellNativeWorkspaceReady(){if(currentId&&window.TaxRebornAndroid?.workspaceReady)window.TaxRebornAndroid.workspaceReady(currentId);}
async function restoreWorkspace(){
 const snapshot=await documentOperation('readonly',store=>store.get('active'),'workspace');
 if(!snapshot)return false;
 if(snapshot.version!==1||!snapshot.data||!isUUID(snapshot.returnId))throw Error('The retained workspace could not be restored. Your saved returns are still kept locally.');
 if(snapshot.hasSaved){const listing=await api('/api/returns');if(!(listing.returns||[]).some(row=>row.id===snapshot.returnId)){await documentOperation('readwrite',store=>store.delete('active'),'workspace');return false;}if(!snapshot.dirty){const saved=await api('/api/returns/'+encodeURIComponent(snapshot.returnId));snapshot.data=saved.data;snapshot.metadata=saved.metadata;snapshot.savedUpdatedAt=saved.updated_at;}}
 data=mergeDefaults(snapshot.data,schema.default_return);metadata=await window.taxRecordMetadata.normalize(data,snapshot.metadata,null,{draft:true});currentId=snapshot.returnId;savedUpdatedAt=snapshot.savedUpdatedAt??null;dirty=!!snapshot.dirty;hasSaved=!!snapshot.hasSaved;synthetic=!!snapshot.synthetic;result=null;calculationError='';revision++;calculatedRevision=-1;
 const next=Object.hasOwn(pageNames,snapshot.page)||moduleDefinitions.has(String(snapshot.page).replace(/^module:/,''))?snapshot.page:'profile';
 navigate(next);await calculate();return true;
}
function isUUID(value){return typeof value==='string'&&/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);}

const get=path=>path.split('.').reduce((value,key)=>value?.[key],data);
function set(path,value){
 const w2=path.match(/^w2\.(\d+)\./),income=path.match(/^(interest|dividends)\.(\d+)\./);let before=null;
 try{if(w2)before=window.taxRecordMetadata.canonicalW2(data.w2[Number(w2[1])]);if(income)before=window.taxIncomePreparation.canonical(income[1],data[income[1]][Number(income[2])]);}catch{}
 const parts=path.split('.');let target=data;for(let index=0;index<parts.length-1;index++){const key=parts[index];if(target[key]==null)target[key]=/^\d+$/.test(parts[index+1])?[]:{};target=target[key];}target[parts.at(-1)]=value;
 if(/^(taxpayer|spouse)\.(birth_date|death_date)$/.test(path))syncPersonAge(parts[0]);
 let after=null;try{if(w2)after=window.taxRecordMetadata.canonicalW2(data.w2[Number(w2[1])]);if(income)after=window.taxIncomePreparation.canonical(income[1],data[income[1]][Number(income[2])]);}catch{}
 if(before===null||after===null||before!==after){if(w2)clearW2Review(Number(w2[1]));if(income)clearIncomeReview(income[1],Number(income[2]));}changed(path==='filing_details.paper_payment_confirmed');
}
function decimalCents(value){const text=String(value??'0').trim()||'0';if(!/^-?\d+(\.\d{1,2})?$/.test(text))throw Error('Enter a USD amount with no more than two decimal places, without commas.');const sign=text.startsWith('-')?-1n:1n;const[whole,fraction='']=text.replace(/^-/,'').split('.');return sign*(BigInt(whole)*100n+BigInt(fraction.padEnd(2,'0')));}
function dollars(value,digits=0){if(value==null)return'—';const number=Number(value);if(!Number.isFinite(number))return'—';return number.toLocaleString('en-US',{style:'currency',currency:'USD',minimumFractionDigits:digits,maximumFractionDigits:digits});}
function enteredSum(key,field){try{return dollars(Number((data[key]||[]).reduce((sum,row)=>sum+decimalCents(row[field]),0n))/100,2);}catch{return'Needs review';}}
function birthDateAge(person){
 const parse=text=>{if(!/^\d{4}-\d{2}-\d{2}$/.test(text||''))return null;const value=new Date(text+'T00:00:00Z');return Number.isFinite(value.getTime())&&value.toISOString().slice(0,10)===text?value:null;};
 const born=parse(person?.birth_date),reference=parse(person?.death_date||'2025-12-31');
 if(!born||!reference||born>reference||reference.getUTCFullYear()!==2025)return null;
 const next=new Date(reference.getTime()+86400000),age=next.getUTCFullYear()-born.getUTCFullYear()-Number(next.getUTCMonth()<born.getUTCMonth()||next.getUTCMonth()===born.getUTCMonth()&&next.getUTCDate()<born.getUTCDate());
 return age>=0&&age<=120?age:null;
}
function syncPersonAge(owner){const person=data[owner],age=birthDateAge(person),input=document.getElementById('tax-'+owner+'-age');if(age!==null)person.age=age;if(input){input.readOnly=age!==null;input.value=person.age;}}
function payload(){return normalizeInput(data);}
function normalizeInput(input){
 const output=clone(input);
 function walk(node,path=''){
  for(const[key,value]of Object.entries(node)){
   const where=path?path+'.'+key:key;
   if(value&&typeof value==='object'){walk(value,where);continue;}
   const type=inputType(where,schemaValue(where),value),meta=fieldMeta(where);
   if(type==='money'){
    try{decimalCents(value);}catch(error){throw Error(where+': '+error.message);}
    node[key]=String(value??'0').trim()||'0';
   }else if(type==='int'){
    if(!/^-?\d+$/.test(String(value)))throw Error(where+': enter a whole number.');
    const number=Number(value);if(!Number.isSafeInteger(number))throw Error(where+': the whole number is too large.');
    node[key]=number;
   }else if(type==='decimal'||type==='percent'){
    if(!/^-?\d+(\.\d+)?$/.test(String(value)))throw Error(where+': enter a decimal number without commas.');
    if(type==='percent'&&(Number(value)<0||Number(value)>100))throw Error(where+': enter a percentage from 0 to 100.');
    node[key]=String(value);
   }else if(type==='boolean'&&typeof value!=='boolean')throw Error(where+': answer this question with true or false.');
  }
 }
 walk(output);return output;
}
async function rawApi(path,options={}){const response=await(window.taxApi||window.fetch.bind(window))(path,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});if(!response.ok){let message='The local tax service could not complete this request.';try{const body=await response.json();message=body.error||body.message||message;}catch{}const error=Error(typeof message==='string'?message:JSON.stringify(message));error.status=response.status;throw error;}return response;}
async function api(path,options={}){return(await rawApi(path,options)).json();}
function notify(message,error=false){const node=$('#toast');node.textContent=message;node.className='toast'+(error?' error':'');node.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.hidden=true,6500);}
function button(label,handler,kind='secondary',attrs={}){return el('button',{type:'button',class:'button '+kind,onClick:event=>{try{const pending=handler?.(event);if(pending?.catch)pending.catch(error=>notify(error.message,true));}catch(error){notify(error.message,true);}},...attrs},label);}
function changed(preservePaperConfirmation=false){activeSourceComparison?.invalidate();if(!preservePaperConfirmation&&data.filing_details?.paper_payment_confirmed){data.filing_details.paper_payment_confirmed=false;for(const input of document.querySelectorAll('[name="filing_details.paper_payment_confirmed"]'))input.checked=false;}ensureW2Metadata();ensureIncomeMetadata();revision++;dirty=true;calculatedRevision=-1;updateHeader();scheduleCalculation();checkpointWorkspace();}
function scheduleCalculation(){clearTimeout(calculateTimer);calculateTimer=setTimeout(()=>calculate(),450);}
async function calculate(){if(!data)return;clearTimeout(calculateTimer);const serial=++calculationSerial,atRevision=revision;updateHeader('Calculating…');let input;try{input=payload();}catch(error){calculationError=error.message;result=null;updateHeader('Check your entries');renderSummary(error.message);return null;}calculatePromise=api('/api/calculate',{method:'POST',body:JSON.stringify(input)});try{const next=await calculatePromise;if(serial!==calculationSerial||revision!==atRevision)return null;result=next;calculationError='';calculatedRevision=atRevision;updateHeader();renderSummary();if(['review','trace','forms','schedules'].includes(page))renderPage(false);return next;}catch(error){if(serial!==calculationSerial)return null;calculationError=error.message;result=null;updateHeader('Calculation unavailable');renderSummary(error.message);if(['review','trace','forms','schedules'].includes(page))renderPage(false);notify(error.message,true);return null;}}
function incomeSourceIssueCount(){return Object.values(metadata.income_document_records||{}).flat().filter(item=>item.is_placeholder||item.unresolved_fields?.length).length;}
function updateHeader(calculationMessage=''){if(!data)return;$('#return-name').textContent=data.name||'Untitled federal return';$('#save-state').textContent=busySave?'Saving…':dirty?'Unsaved changes':hasSaved?'Saved on this device':'New return · not saved';$('#save-button').disabled=busySave;$('#mobile-save').disabled=busySave;const summary=result?.summary,owed=summary?.amount_owed>0;$('#refund-box').classList.toggle('owed',owed);$('#refund-label').textContent=owed?'Federal amount owed':'Federal refund estimate';$('#refund-value').textContent=summary?dollars(owed?summary.amount_owed:summary.refund):'—';$('#refund-state').textContent=calculationMessage||(calculatedRevision!==revision?'Updating estimate…':incomeSourceIssueCount()?incomeSourceIssueCount()+' income source checks remain':result?.can_prepare?'Worksheet ready · not filed':result?((result.blocking_issues||[]).length+' checks need review'):'Enter your information');}
function renderSummary(error=calculationError){const voucherBalance=$('#payment-voucher-balance');if(voucherBalance)voucherBalance.textContent='Form1040 line37 amount owed: '+dollars(result?.lines?.['37']);const target=$('#live-summary');target.replaceChildren(el('h3',{},'Your federal calculation'),el('div',{class:'calculation-status'},calculatedRevision===revision?'Calculated for tax year 2025':'Waiting for current entries'));if(error){target.append(el('div',{class:'summary-status blocked'},error));return;}for(const[label,key]of[['Adjusted gross income','agi'],['Taxable income','taxable_income'],['Total federal tax','total_tax'],['Payments & credits','payments']])target.append(el('div',{class:'summary-line'},el('span',{},label),el('strong',{},dollars(result?.summary?.[key]))));if(result){target.append(el('div',{class:'summary-line total'},el('span',{},result.summary.amount_owed>0?'Amount owed':'Refund estimate'),el('strong',{},dollars(result.summary.amount_owed>0?result.summary.amount_owed:result.summary.refund))),el('div',{class:'summary-status'+(result.can_prepare?'':' blocked')},result.can_prepare?'No blocking issues in the supported worksheet scope. This return has not been filed.':(result.blocking_issues||[]).length+' blocking issues. Review the supported scope before relying on this estimate.'),button('See calculation',()=>navigate('trace'),'secondary',{class:'button secondary small'}));}}
function currentStep(){return steps.find(step=>step.pages.includes(page))||steps[0];}
function renderNavigation(){const step=currentStep();$('#step-tabs').replaceChildren(...steps.map((item,index)=>el('button',{class:'step-tab'+(item.id===step.id?' active':''),'aria-current':item.id===step.id?'step':null,onClick:()=>navigate(item.pages[0])},el('span',{class:'step-number'},index+1),item.label)));$('#nav-items').replaceChildren(el('div',{class:'mobile-only mobile-nav-actions'},button('My returns',()=>{$('#navigator').classList.remove('open');showReturns();},'secondary',{class:'button secondary small'}),button('Documents',()=>{$('#navigator').classList.remove('open');showDocuments();},'secondary',{class:'button secondary small'})),...steps.flatMap(item=>[el('div',{class:'nav-group'},item.label),...item.pages.map(key=>el('button',{class:'nav-link'+(page===key?' active':''),'aria-current':page===key?'page':null,onClick:()=>navigate(key)},el('span',{class:'nav-dot'}),pageNames[key]))]));$('#step-location').textContent=step.label+' · '+pageNames[page];const pages=steps.flatMap(item=>item.pages),position=pages.indexOf(page);$('#back-button').disabled=position<=0;$('#next-button').textContent=position===pages.length-1?'Return to review':'Continue →';}
function navigate(next){page=next;$('#navigator').classList.remove('open');renderNavigation();renderPage();window.scrollTo({top:0,behavior:'instant'});$('#main').focus({preventScroll:true});checkpointWorkspace();}
function title(heading,description){const fragment=document.createDocumentFragment();fragment.append(el('div',{class:'eyebrow'},'2025 FEDERAL · '+currentStep().label),el('h1',{},heading),el('p',{class:'intro'},description));if(synthetic)fragment.append(el('div',{class:'synthetic-banner'},'Synthetic example · save creates a separate return. These are not your tax figures.'));return fragment;}
function card(heading,...children){return el('section',{class:'section-card'},el('h2',{},heading),children);}
const renderedPaths=new Set(),moduleDefinitions=new Map();
function normalizedPath(path){return path.split('.').map(key=>/^\d+$/.test(key)?'*':key).join('.');}
function humanLabel(value){return value.replaceAll('_',' ').replace(/\b(?:ssn|tin|ira|hsa|amt|niit|eitc|magi|qbi|flsa|ein|aotc|llc|mfs)\b/gi,text=>text.toUpperCase()).replace(/^./,text=>text.toUpperCase());}
function rowTemplate(path){
 const templates=schema?.capabilities?.row_templates||{},plain=path.split('.').filter(key=>!/^\d+$/.test(key)&&key!=='*').join('.');
 return templates[path]??templates[normalizedPath(path)]??templates[plain]??templates[plain.replaceAll('.','_')]??templates[plain.split('.').at(-1)];
}
function schemaValue(path){
 if(!schema?.default_return)return undefined;const parts=path.split('.');let value=schema.default_return;
 for(let index=0;index<parts.length;index++){
  const key=parts[index];
  if(Array.isArray(value)){
   if(!/^\d+$/.test(key)&&key!=='*')return undefined;
   value=rowTemplate(parts.slice(0,index).join('.'))??value[Number(key)]??value[0];
  }else{
   if(!value||typeof value!=='object'||!Object.hasOwn(value,key))return undefined;
   value=value[key];
  }
 }
 return value;
}
function supportsPath(path){return schemaValue(path)!==undefined;}
const localFieldMeta={
 'hsa.family_allocation_taxpayer_percent':{type:'percent',label:'Taxpayer share of the family HSA limit (%)',help:'Allocate the family contribution limit between spouses. This is a percentage, not a dollar amount.'},
 'hsa.spouse_coverage.*':{type:'enum',label:'Spouse coverage',options:[['none','No eligible HDHP coverage'],['self','Self-only HDHP'],['family','Family HDHP']]},
 'hsa.accounts.*.coverage.*':{type:'enum',label:'Coverage',options:[['none','No eligible HDHP coverage'],['self','Self-only HDHP'],['family','Family HDHP']]},
 'education.students.*.credit':{type:'enum',label:'Education credit',options:[['aotc','American Opportunity Tax Credit'],['llc','Lifetime Learning Credit']]},
 'education.students.*.aotc_prior_years':{type:'int',label:'Prior years AOTC was claimed for this student',min:0,max:4},
 'education.claimant_full_time_student':{type:'boolean',label:'The taxpayer claiming the credit was a full-time student',help:'These refundability questions refer to the taxpayer claiming the credit, not automatically to the dependent student.'},
 'education.claimant_earned_income':{type:'money',label:'Claimant earned income for the refundability test'},
 'education.claimant_support':{type:'money',label:'Total support of the taxpayer claiming the credit'},
 'marketplace.below_poverty_exception':{type:'enum',label:'Below-poverty-level eligibility exception',options:[['none','No exception'],['marketplace_estimated_at_least100','Marketplace estimated household income at least 100% FPL'],['lawful_immigrant_no_medicaid','Lawfully present immigrant ineligible for Medicaid']]},
 'marketplace.region':{type:'enum',label:'Federal poverty guideline region',options:[['contiguous','48 contiguous states and D.C.'],['alaska','Alaska'],['hawaii','Hawaii']]},
 'marketplace.months.*.month':{type:'int',label:'Month (1–12)',min:1,max:12},
 'marketplace.months.*.enrollment_premium':{type:'money',label:'Form 1095-A column A · Enrollment premium'},
 'marketplace.months.*.slcsp_premium':{type:'money',label:'Form 1095-A column B · SLCSP premium'},
 'marketplace.months.*.advance_credit':{type:'money',label:'Form 1095-A column C · Advance payment of PTC'},
 'eitc.claim':{type:'boolean',label:'Calculate the Earned Income Tax Credit',help:'Confirm the qualifying-person, residency and other eligibility questions below. Claiming the credit is separate from confirming that it does not apply.'}
};
function fieldMeta(path){
 const key=normalizedPath(path),fields=schema?.capabilities?.ui_fields||{};
 const descriptor=Array.isArray(fields)?fields.find(item=>item.path===key||item.path===path):fields[key]??fields[path];
 return {...(localFieldMeta[key]||{}),...(descriptor||{})};
}
function inputType(path,defaultValue=schemaValue(path),currentValue=get(path)){
 const type=fieldMeta(path).type;
 if(typeof defaultValue==='boolean')return'boolean';
 if(path.endsWith('_percent')||path.endsWith('_percentage'))return'percent';
 if(type)return({bool:'boolean',integer:'int',number:'decimal',select:'enum',currency:'money'})[type]||type;
 if(typeof defaultValue==='boolean')return'boolean';
 if(typeof defaultValue==='number')return'int';
 if(typeof defaultValue==='string'&&/^-?\d+(\.\d{1,2})?$/.test(defaultValue))return'money';
 if(MONEY_KEYS.has(path.split('.').at(-1)))return'money';
 if(['owner','term','credit','region'].includes(path.split('.').at(-1)))return'enum';
 return'text';
}
function legacyForeignAddress(value){return typeof value?.identity?.foreign_country==='string'&&value.identity.foreign_country.trim().length>0&&!Object.hasOwn(value?.filing_details||{},'mailing_address_type');}
function mergeDefaults(value,defaults,path=''){
 if(Array.isArray(defaults))return Array.isArray(value)?value.map((row,index)=>{const template=rowTemplate(path)??defaults[index]??defaults[0];return template&&typeof template==='object'?mergeDefaults(row,template,path+'.'+index):row;}):clone(defaults);
 if(defaults&&typeof defaults==='object'){
  const output=value&&typeof value==='object'&&!Array.isArray(value)?clone(value):{};
  for(const[key,entry]of Object.entries(defaults))output[key]=Object.hasOwn(output,key)?mergeDefaults(output[key],entry,path?path+'.'+key:key):clone(entry);
  if(path===''&&legacyForeignAddress(value))output.filing_details.mailing_address_type='foreign';
  return output;
 }
 return value===undefined?clone(defaults):value;
}
const knownInputSections=new Set(['tax_year','name','filing_status','taxpayer','spouse','dependents','w2','interest','dividends','capital_gains','carryovers','businesses','retirement','other_income','adjustments','itemized','schedule_1a','payments','eligibility','unsupported','notes']);
const moduleInfo={
 care:{label:'Dependent-care expenses & benefits',step:'deductions',description:'Enter qualifying people, care providers, expenses and employer benefits. Confirm eligibility and earned-income facts for Form2441.'},
 saver:{label:'Retirement savings credit',step:'deductions',description:'Review eligible retirement contributions, distributions and the student/dependency facts used for Form8880.'},
 elderly_credit:{label:'Credit for elderly or disabled',step:'deductions',description:'Review age or permanent-disability facts, qualifying income and nontaxable retirement benefits for ScheduleR.'},
 identity:{label:'Personal details for forms',step:'personal',description:'Optional local identity and address fields for preparing a draft form. These details are separate from tax eligibility. Use synthetic details while testing; this application does not electronically file.'},
 eitc:{label:'Earned Income Tax Credit',step:'deductions',description:'Review the household and qualifying-child facts used to calculate the 2025 Earned Income Tax Credit.'},
 niit:{label:'Net Investment Income Tax',step:'income',description:'Review the investment-income facts and eligible allocation adjustments used for Form 8960.'},
 amt:{label:'Alternative Minimum Tax',step:'deductions',description:'Enter AMT adjustments and confirm the applicable Form 6251 facts.'},
 rentals:{label:'Rental properties · Schedule E',step:'income',description:'Add each rental property. Confirm ownership, participation, at-risk and personal-use facts before using a calculated rental loss.'},
 ira:{label:'IRA contributions',step:'deductions',description:'Enter traditional and Roth IRA contributions, plan coverage and prior basis. The engine calculates the supported limits and deduction.'},
 hsa:{label:'Health Savings Accounts',step:'deductions',description:'Add each account and enter monthly eligible HDHP coverage, contributions and distributions for Form 8889.'},
 education:{label:'Education credits',step:'deductions',description:'Add each student and eligible expenses. Separately confirm the taxpayer’s eligibility and refundability facts.'},
 marketplace:{label:'Marketplace insurance · 1095-A',step:'deductions',description:'Enter all twelve months from Form 1095-A and the household eligibility facts used for Form 8962.'}
};
function configureModules(){
 moduleDefinitions.clear();for(const step of steps)step.pages=step.pages.filter(key=>!key.startsWith('module:'));
 const supplied=schema?.capabilities?.ui_modules||[];
 const configured=Array.isArray(supplied)?supplied:Object.entries(supplied).map(([id,value])=>({id,...value}));
 for(const id of Object.keys(schema.default_return)){
  if(knownInputSections.has(id)||!schema.default_return[id]||typeof schema.default_return[id]!=='object')continue;
  const definition={id,label:humanLabel(id),step:'deductions',description:'Enter the inputs supported by the local calculation engine.',...(moduleInfo[id]||{}),...(configured.find(item=>item.id===id)||{})};
  moduleDefinitions.set(id,definition);const key='module:'+id;pageNames[key]=definition.label;
  (steps.find(step=>step.id===definition.step)||steps.find(step=>step.id==='deductions')).pages.push(key);
 }
}
function field(path,label,type='money',options={}){if(!supportsPath(path))return null;renderedPaths.add(path);const id='tax-'+path.replaceAll('.','-'),value=get(path);let input;if(type==='select'){input=el('select',{id,name:path,onChange:event=>{set(path,event.target.value);if(path==='filing_status')renderPage(false);}},...(options.choices||[]).map(([key,text])=>el('option',{value:key},text)));input.value=String(value??options.choices?.[0]?.[0]??'');}else if(type==='textarea'){input=el('textarea',{id,name:path,rows:options.rows||3,onInput:event=>set(path,event.target.value)});input.value=value??'';}else{input=el('input',{id,name:path,type:['age','int'].includes(type)?'number':'text',inputmode:['money','decimal','percent'].includes(type)?'decimal':['age','int'].includes(type)?'numeric':null,class:type==='money'?'money':'',value:value??'',min:options.min??(type==='age'?0:null),max:options.max??(type==='age'?120:null),step:['age','int'].includes(type)?1:null,onInput:event=>{set(path,event.target.value);if(type==='money'){try{decimalCents(event.target.value);container.classList.remove('invalid');error.textContent='';}catch(issue){container.classList.add('invalid');error.textContent=issue.message;}}}});}const error=el('div',{class:'field-error','aria-live':'polite'}),container=el('div',{class:'field'+(options.full?' full':'')},el('label',{for:id},label),type==='money'?el('div',{class:'money-wrap'},el('span',{'aria-hidden':'true'},'$'),input):input,options.help?el('small',{},options.help):null,error);return container;}
function check(path,label,help=''){if(!supportsPath(path))return null;renderedPaths.add(path);const input=el('input',{type:'checkbox',name:path,checked:get(path)===true,onChange:event=>{set(path,event.target.checked);if(path.endsWith('.enabled'))renderPage(false);}});return el('label',{class:'check-field'},input,el('span',{},label,help?el('small',{},help):null));}
function grid(...fields){return el('div',{class:'field-grid'},fields);}
const ownerChoices=[['taxpayer','Taxpayer'],['spouse','Spouse']];
function autoField(path,label){
 if(renderedPaths.has(path)||!supportsPath(path))return null;
 const meta=fieldMeta(path),value=schemaValue(path),type=inputType(path,value),key=path.split('.').at(-1);
 const text=label||meta.label||humanLabel(key),options={help:meta.help||meta.description||'',min:meta.min,max:meta.max};
 if(type==='boolean')return check(path,text,options.help);
 if(type==='enum'){
  let choices=meta.options||meta.choices||meta.values||[];
  if(!Array.isArray(choices))choices=Object.entries(choices);
  choices=choices.map(entry=>Array.isArray(entry)?entry:typeof entry==='object'?[entry.value,entry.label||humanLabel(String(entry.value))]:[entry,humanLabel(String(entry))]);
  if(!choices.length){if(key==='owner')choices=ownerChoices;else if(key==='term')choices=[['short','Short-term'],['long','Long-term']];else choices=[[value,humanLabel(String(value))]];}
  return field(path,text,'select',{...options,choices});
 }
 return field(path,text,type==='int'?'int':type,{...options,full:type==='textarea'});
}
function autoObject(path,template=schemaValue(path)){
 if(!template||typeof template!=='object')return autoField(path);
 if(Array.isArray(template))return autoArray(path,template);
 const entries=Object.entries(template),inputs=[],questions=[],groups=[];
 for(const[key,value]of entries){const where=path?path+'.'+key:key;if(value&&typeof value==='object'){const group=autoObject(where,value);if(group)groups.push(card(fieldMeta(where).label||humanLabel(key),group));}else{const input=autoField(where);if(input)(inputType(where,value)==='boolean'?questions:inputs).push(input);}}
 if(!inputs.length&&!questions.length&&!groups.length)return null;
 return el('div',{class:'auto-section'},inputs.length?grid(...inputs):null,questions,groups);
}
function autoArray(path,template=schemaValue(path)){
 const records=get(path),holder=el('div',{class:'auto-records'}),row=rowTemplate(path)??template[0];
 if(!Array.isArray(records))return null;
 if(typeof row!=='object'||row===null){
  const months=['January','February','March','April','May','June','July','August','September','October','November','December'];
  const inputs=records.map((_,index)=>autoField(path+'.'+index,records.length===12?months[index]:humanLabel(path.split('.').at(-1))+' '+(index+1)));
  return inputs.some(Boolean)?grid(...inputs):null;
 }
 const label=fieldMeta(path).row_label||({rentals:'rental property','hsa.accounts':'HSA account','education.students':'student','marketplace.months':'coverage month','care.beneficiaries':'qualifying care recipient','care.providers':'care provider','care.deemed_income_months':'monthly earned-income record'})[path]||humanLabel(path.split('.').at(-1)).replace(/s$/,'');
 if(!records.length)holder.append(el('div',{class:'empty-state'},'No '+label+' added. Add a record to enter actual amounts and eligibility facts.'));
 records.forEach((record,index)=>{
  const recordKey=path+':'+index,isOpen=openRecords.has(recordKey)||records.length===1,content=autoObject(path+'.'+index,row),body=el('div',{class:'record-body',hidden:!isOpen},content);
  const descriptor=record.name||record.student_id||record.owner||(record.month?'Month '+record.month:'Enter details');
  const heading=el('button',{class:'record-header-button',type:'button','aria-expanded':isOpen,onClick:event=>{body.hidden=!body.hidden;event.currentTarget.setAttribute('aria-expanded',String(!body.hidden));if(body.hidden)openRecords.delete(recordKey);else openRecords.add(recordKey);}},el('span',{'aria-hidden':'true'},'⌄'),el('span',{},humanLabel(label)+' '+(index+1),el('small',{},descriptor)));
  holder.append(el('section',{class:'record'},el('div',{class:'record-header'},heading,button('Remove',()=>{records.splice(index,1);openRecords.clear();changed();renderPage(false);},'danger',{class:'delete-record','aria-label':'Remove '+label+' '+(index+1)})),body));
 });
 const actions=el('div',{class:'inline-actions'});
 if(rowTemplate(path))actions.append(button('+ Add '+label,()=>{const next=clone(rowTemplate(path));if(path==='marketplace.months'||path==='care.deemed_income_months'){const used=new Set(records.map(item=>Number(item.month)));next.month=Array.from({length:12},(_,index)=>index+1).find(month=>!used.has(month))||1;}records.push(next);openRecords.add(path+':'+(records.length-1));changed();renderPage(false);},'secondary',{class:'add-record'}));
 if(path==='marketplace.months'||path==='care.deemed_income_months')actions.append(button('Add missing months',()=>{const used=new Set(records.map(item=>Number(item.month)));for(let month=1;month<=12;month++)if(!used.has(month)){const next=clone(rowTemplate(path));next.month=month;records.push(next);}records.sort((a,b)=>a.month-b.month);changed();renderPage(false);},'secondary'));
 holder.append(actions);return holder;
}
function modulePage(id){
 const definition=moduleDefinitions.get(id),enabledPath=id+'.enabled',hasGate=supportsPath(enabledPath)&&typeof schemaValue(enabledPath)==='boolean';
 const parts=[title(definition.label,definition.description)];
 if(id==='identity')parts.push(card('Mailing address format',autoField('filing_details.mailing_address_type'),el('div',{class:'note'},'Use the US state and ZIP fields for a US mailing address, or the full country name and separate foreign province and postal fields for a foreign mailing address. Both sets stay saved when you switch. The selected format controls the printed address; it does not change tax residency or income eligibility.')));
 if(hasGate)parts.push(card('Include this section',check(enabledPath,'Report '+definition.label.toLowerCase()+' in this return','Enable only if this section applies. Stored amounts or document records in a disabled section remain blocking until you enable it or explicitly remove them.')));
 if(hasGate&&!get(enabledPath))parts.push(el('div',{class:'note warning'},'This section is currently off. Entering amounts below does not turn it on; select the question above to calculate this section.'));
 parts.push(card('Your '+definition.label.toLowerCase()+' inputs',autoObject(id)),el('div',{class:'note'},'All figures and eligibility checks are calculated by the local engine. Confirm only statements that apply to your return; unresolved rules remain visible in Review.'));
 return parts;
}
function additionalFields(path){const contents=autoObject(path);return contents?card('Additional '+humanLabel(path.split('.').at(-1))+' questions',contents):null;}
const recordDefinitions={
 dependents:{label:'dependent',name:'name',template:{name:'',age:0,qualifying_child:false,valid_ssn:false},fields:[['name','Dependent name','text'],['age','Age on December 31, 2025','age'],['qualifying_child','This person meets qualifying-child rules','check'],['valid_ssn','This dependent has an eligible SSN','check'],['valid_tin','This dependent has an eligible SSN or ITIN','check'],['eligibility_confirmed','I verified this dependent’s eligibility for the reported credit','check']]},
 w2:{label:'W-2',name:'employer',template:{employer:'',owner:'taxpayer',wages:'0',federal_withholding:'0',social_security_wages:'0',social_security_withholding:'0',medicare_wages:'0',medicare_withholding:'0'},fields:[['employer','Employer name','text'],['owner','Whose W-2 is this?','owner'],['wages','Box 1 · Wages, tips, other compensation'],['federal_withholding','Box 2 · Federal income tax withheld'],['social_security_wages','Box 3 · Social Security wages'],['social_security_withholding','Box 4 · Social Security tax withheld'],['medicare_wages','Box 5 · Medicare wages and tips'],['medicare_withholding','Box 6 · Medicare tax withheld'],['social_security_tips','Box 7 · Social Security tips'],['dependent_care_benefits','Box 10 · Dependent-care benefits']]},
 interest:{label:'1099-INT',name:'payer',template:{payer:'',taxable:'0',tax_exempt:'0',federal_withholding:'0'},fields:[['payer','Payer / bank name','text'],['taxable','Taxable interest'],['tax_exempt','Tax-exempt interest'],['federal_withholding','Federal income tax withheld']]},
 dividends:{label:'1099-DIV',name:'payer',template:{payer:'',ordinary:'0',qualified:'0',capital_gain_distributions:'0',federal_withholding:'0',unrecaptured_1250_gain:'0',collectibles_gain:'0',special_distribution_confirmed:false},fields:[['payer','Payer / brokerage name','text'],['ordinary','Box 1a · Ordinary dividends'],['qualified','Box 1b · Qualified dividends'],['capital_gain_distributions','Box 2a · Total capital gain distributions'],['unrecaptured_1250_gain','Box 2b · Unrecaptured Section 1250 gain'],['collectibles_gain','Box 2d · Collectibles (28%) gain'],['special_distribution_confirmed','I verified Box 2a includes 2b and 2d, with no QSBS, nominee or other special-gain allocation.','check'],['federal_withholding','Federal income tax withheld']]},
 capital_gains:{label:'investment sale',name:'description',template:{description:'',term:'short',proceeds:'0',cost_basis:'0',adjustment:'0'},fields:[['description','Description of property / lot','text'],['term','Holding period','term'],['proceeds','Sales proceeds'],['cost_basis','Cost or other basis'],['adjustment','Adjustment to gain or loss'],['special_rate','This sale is subject to a special rate or unsupported rule','check']]},
 businesses:{label:'business',name:'name',template:{name:'',owner:'taxpayer',revenue:'0',expenses:'0',qbi_eligible:false,active_business:false},fields:[['name','Business name','text'],['owner','Business owner','owner'],['revenue','Gross revenue'],['expenses','Allowable business expenses'],['active_business','This is an active trade or business','check'],['expenses_eligible','I verified that the entered business expenses are allowable','check'],['at_risk_confirmed','I verified the applicable at-risk business limitations','check'],['qbi_eligible','This business income qualifies for QBI treatment','check']]}
};
function ensureW2Metadata(){
 const rows=data?.w2||[];if(!Array.isArray(rows))return;
 if(!metadata||metadata.version!==1||!Array.isArray(metadata.w2_records))metadata=window.taxRecordMetadata.empty();
 while(metadata.w2_records.length<rows.length)metadata.w2_records.push(window.taxRecordMetadata.newRecord());
 if(metadata.w2_records.length>rows.length)metadata.w2_records.length=rows.length;
}
function ensureInvestmentMetadata(){
 ensureW2Metadata();const rows=data.capital_gains||[];
 if(!Array.isArray(metadata.investment_records))metadata.investment_records=[];
 while(metadata.investment_records.length<rows.length)metadata.investment_records.push(window.taxInvestmentCorrections.newRecord());
 if(metadata.investment_records.length>rows.length)metadata.investment_records.length=rows.length;
}
function ensureIncomeMetadata(){
 ensureW2Metadata();metadata.income_document_records=metadata.income_document_records||{};
 for(const key of ['interest','dividends']){
  const rows=data?.[key]||[];let entries=metadata.income_document_records[key];if(!Array.isArray(entries))entries=metadata.income_document_records[key]=[];
  while(entries.length<rows.length)entries.push(window.taxIncomePreparation.newRecord());if(entries.length>rows.length)entries.length=rows.length;
 }
 if(!Array.isArray(metadata.income_import_events))metadata.income_import_events=[];
}
function refreshIncomeReview(key,ident){
 const entry=metadata.income_document_records?.[key]?.find(item=>item.record_id===ident);if(!entry)return;
 document.querySelectorAll('[data-income-review-state="'+ident+'"]').forEach(node=>node.textContent=(entry.reviewed?'Reviewed':'Needs review')+(entry.is_placeholder?' · Prior-year placeholder':'')+(entry.unresolved_fields.length?' · '+entry.unresolved_fields.length+' unresolved facts':''));
 document.querySelectorAll('[data-income-review-control="'+ident+'"]').forEach(node=>node.checked=entry.reviewed);
}
function clearIncomeReview(key,index){ensureIncomeMetadata();const entry=metadata.income_document_records[key][index];if(!entry)return;entry.reviewed=false;entry.reviewed_at=null;entry.reviewed_fingerprint=null;refreshIncomeReview(key,entry.record_id);}
async function markIncomeReviewed(key,ident,checked){
 ensureIncomeMetadata();const returnId=currentId,atRevision=revision,index=metadata.income_document_records[key].findIndex(item=>item.record_id===ident);if(index<0)return;
 if(!checked){clearIncomeReview(key,index);metadataChanged();return;}
 if(!String(data[key][index].payer||'').trim())throw Error('Enter the payer name before reviewing this document.');
 const prepared=await window.taxIncomePreparation.markReviewed(payload(),clone(metadata),key,ident,new Date().toISOString());
 if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during review. Check the current document again.');
 metadata=prepared;refreshIncomeReview(key,ident);metadataChanged();
}
function incomeReviewPanel(key,index){
 ensureIncomeMetadata();const entry=metadata.income_document_records[key][index],ident=entry.record_id;
 const reviewed=el('input',{type:'checkbox',checked:entry.reviewed,'data-income-review-control':ident,onChange:async event=>{const input=event.currentTarget;input.disabled=true;try{await markIncomeReviewed(key,ident,input.checked);}catch(error){input.checked=false;notify(error.message,true);}finally{input.disabled=false;refreshIncomeReview(key,ident);}}});
 const placeholder=el('input',{type:'checkbox',checked:entry.is_placeholder,'aria-label':'Prior-year placeholder '+ident.slice(0,8),onChange:event=>{const current=metadata.income_document_records[key].find(item=>item.record_id===ident);if(!current)return;current.is_placeholder=event.target.checked;metadataChanged();refreshIncomeReview(key,ident);}});
 const holder=el('div',{class:'note'},el('strong',{'data-income-review-state':ident},(entry.reviewed?'Reviewed':'Needs review')+(entry.is_placeholder?' · Prior-year placeholder':'')+(entry.unresolved_fields.length?' · '+entry.unresolved_fields.length+' unresolved facts':'')),el('small',{},'Local document ID · '+ident.slice(0,8)),el('label',{class:'check-field'},reviewed,el('span',{},'I compared each entered amount with this 2025 source document.')),el('label',{class:'check-field'},placeholder,el('span',{},'This is a prior-year placeholder awaiting a current-year import.')),el('small',{},'A placeholder is still included in the estimate. Import can replace only the exact IDs you select. Reviewed and missing facts are separate states.'));
 const unresolved=el('details',{},el('summary',{},'Unresolved source facts'));
 for(const name of [...Object.keys(recordDefinitions[key].template),'current_year_confirmation']){
  const control=el('input',{type:'checkbox',checked:entry.unresolved_fields.includes(name),'aria-label':'Unresolved '+humanLabel(name)+' '+ident.slice(0,8),onChange:event=>{
   const current=metadata.income_document_records[key].find(item=>item.record_id===ident);if(!current)return;
   current.unresolved_fields=event.target.checked?[...new Set([...current.unresolved_fields,name])]:current.unresolved_fields.filter(value=>value!==name);metadataChanged();refreshIncomeReview(key,ident);
  }});
  unresolved.append(el('label',{class:'check-field'},control,el('span',{},name==='current_year_confirmation'?'Current-year source confirmation':humanLabel(name))));
 }
 holder.append(unresolved);
 if(entry.source_document){const source=entry.source_document,restored=source.return_id!==currentId;holder.append(el('p',{},restored?'Source attachment not restored · '+source.name:'Local TaxML source · '+source.name));if(!restored)holder.append(button('View source document',()=>showLocalSource(source),'secondary',{class:'button secondary small'}));}
 if(entry.taxml_dividend_boxes){const boxes=entry.taxml_dividend_boxes;holder.append(el('details',{},el('summary',{},'Reviewed 1099-DIV import snapshot'),el('dl',{},...dividendTaxMLFields.map(([name,label])=>[el('dt',{},label),el('dd',{},'$'+boxes[name])]).flat()),el('small',{},'These six imported amounts remain attached to the source. Editing the current record clears its review; it does not rewrite this snapshot. Boxes 2b and 2d are included in Box 2a.')));}
 if(entry.taxml_interest_boxes){const boxes=entry.taxml_interest_boxes;holder.append(el('details',{},el('summary',{},'Reviewed 1099-INT import snapshot'),el('dl',{},...interestTaxMLFields.map(([name,label])=>[el('dt',{},label),el('dd',{},'$'+boxes[name])]).flat()),el('small',{},'These four imported amounts remain attached to the source. Editing the current record clears its review; it does not rewrite this snapshot. Treasury interest may require a separate state exclusion review.')));}
 return holder;
}
function investmentCorrectionPanel(index){
 ensureInvestmentMetadata();const entry=metadata.investment_records[index],holder=el('div',{class:'note'},button('Correct cost basis',()=>showBasisCorrection(entry.record_id),'secondary'));
 if(entry.basis_corrections.length)holder.append(el('strong',{},'Recorded basis corrections'),el('ul',{},entry.basis_corrections.map(item=>el('li',{},'$'+item.old_cost_basis+' → $'+item.new_cost_basis+' · '+new Date(item.applied_at).toLocaleDateString(),item.reason?el('small',{},item.reason):null))));
 return holder;
}
function showBasisCorrection(recordId){
 ensureInvestmentMetadata();const id=currentId,atRevision=revision,index=metadata.investment_records.findIndex(item=>item.record_id===recordId);
 if(index<0)throw Error('The selected investment sale no longer exists');
 const original=clone(data.capital_gains[index]),source=window.taxInvestmentCorrections.canonical(original),holder=el('div');
 const basis=el('input',{type:'text',inputmode:'decimal',class:'money','aria-label':'Corrected absolute cost basis',value:window.taxInvestmentCorrections.amount(original.cost_basis??'0')});
 const note=el('input',{type:'text',maxlength:500,'aria-label':'Basis correction source or reason'}),confirmed=el('input',{type:'checkbox','aria-label':'I checked this corrected basis against my source records'});
 holder.append(el('p',{class:'intro'},'Enter the corrected absolute cost basis for this sale. This replaces the basis amount. Proceeds and separate gain or loss adjustments are retained.'),
  el('div',{class:'note'},original.description||'Selected investment sale',el('br'),'Current cost basis: $'+window.taxInvestmentCorrections.amount(original.cost_basis??'0')),
  el('div',{class:'field'},el('label',{},'Corrected absolute cost basis'),el('div',{class:'money-wrap'},el('span',{},'$'),basis)),
  el('div',{class:'field'},el('label',{},'Source or reason'),note),
  el('label',{class:'check-field'},confirmed,el('span',{},'I checked this corrected basis against my source records.')));
 let submitting=false;
 modal('Correct cost basis',holder,[['Apply basis correction',async()=>{
  if(submitting)return;submitting=true;
  try{
   if(!confirmed.checked)throw Error('Check the corrected basis against your source records first');
   ensureInvestmentMetadata();const selected=metadata.investment_records.findIndex(item=>item.record_id===recordId);
   if(currentId!==id||revision!==atRevision||selected<0||window.taxInvestmentCorrections.canonical(data.capital_gains[selected])!==source)throw Error('This sale or return changed during review; reopen the correction');
   const proposal=await window.taxInvestmentCorrections.plan(original,recordId,basis.value,note.value.trim());
   const applied=await window.taxInvestmentCorrections.apply(data,metadata,proposal);
   if(currentId!==id||revision!==atRevision)throw Error('This return changed while applying the correction; no amount was replaced');
   data=applied.data;metadata=applied.metadata;changed();closeDialog();navigate('capital_gains');notify('Cost basis replaced and correction recorded. Save to keep this return.');
  }finally{submitting=false;}
 },'primary']]);
}
function refreshW2Review(ident){
 const entry=metadata.w2_records.find(item=>item.record_id===ident);if(!entry)return;
 document.querySelectorAll('[data-w2-review-state="'+ident+'"]').forEach(node=>node.textContent=entry.reviewed?'Reviewed':'Needs review');
 document.querySelectorAll('[data-w2-review-control="'+ident+'"]').forEach(node=>node.checked=entry.reviewed);
}
function clearW2Review(index){ensureW2Metadata();const entry=metadata.w2_records[index];if(!entry)return;entry.reviewed=false;entry.reviewed_at=null;entry.reviewed_fingerprint=null;refreshW2Review(entry.record_id);}
function metadataChanged(){const current=calculatedRevision===revision;revision++;if(current)calculatedRevision=revision;dirty=true;updateHeader();renderSummary();if(!current)scheduleCalculation();checkpointWorkspace();}
async function markW2Reviewed(ident,checked){
 ensureW2Metadata();const returnId=currentId,index=metadata.w2_records.findIndex(item=>item.record_id===ident);if(index<0)return;
 if(!checked){clearW2Review(index);metadataChanged();return;}
 const row=data.w2[index];if(!String(row.employer||'').trim())throw Error('Enter the employer name before marking this W-2 reviewed.');const inspected=window.taxRecordMetadata.canonicalW2(row);
 const fingerprint=await window.taxRecordMetadata.fingerprint(row);
 const currentIndex=metadata.w2_records.findIndex(item=>item.record_id===ident);
 if(currentId!==returnId||currentIndex<0)return;
 if(inspected!==window.taxRecordMetadata.canonicalW2(data.w2[currentIndex]))throw Error('This W-2 changed during review. Check its current values again.');
 const entry=metadata.w2_records[currentIndex];entry.reviewed=true;entry.reviewed_at=new Date().toISOString();entry.reviewed_fingerprint=fingerprint;entry.row_fingerprint=fingerprint;
 refreshW2Review(ident);metadataChanged();
}
async function showLocalSource(source){
 const id=currentId;if(source.return_id!==id)throw Error('The source attachment was not restored with this backup. Attach it to this return separately.');
 const row=await documentOperation('readonly',store=>store.get(source.document_id));
 if(currentId!==id)return;
 if(!row||row.returnId!==id)throw Error('The source attachment is no longer available in this local return.');
 const url=URL.createObjectURL(row.file),holder=el('div',{},el('p',{},row.name),row.type.startsWith('image/')?el('img',{src:url,alt:'Original source document',style:'max-width:100%;height:auto'}):el('p',{},'Download this local source to compare its amounts.'));
 const actions=[['Download source',()=>downloadBlob(row.file,row.name),'secondary']];
 if(row.binding_files)actions.push(['Inspect / correct source',async()=>{
  const atRevision=revision,b=row.binding_files;
  const inspected=await window.taxMLImport.inspect(row.file,b.profile,b.carriers,b.container,true);
  if(currentId!==id||revision!==atRevision)throw Error('This return changed. Reopen the source.');
  showTaxMLCandidates(row,inspected,id,atRevision);
 },'primary']);
 modal('Your source document',holder,actions);documentURLs.push(url);
}
function w2ReviewPanel(index){
 const entry=metadata.w2_records[index],ident=entry.record_id,source=entry.source_document;
 const control=el('input',{type:'checkbox',checked:entry.reviewed,'data-w2-review-control':ident,onChange:async event=>{
  const input=event.currentTarget;input.disabled=true;
  try{await markW2Reviewed(ident,input.checked);}catch(error){input.checked=false;notify(error.message,true);}finally{input.disabled=false;refreshW2Review(ident);}
 }});
 const holder=el('div',{class:'note'},el('strong',{'data-w2-review-state':ident},entry.reviewed?'Reviewed':'Needs review'),el('label',{class:'check-field'},control,el('span',{},'I checked the owner and every entered W-2 amount against the source document.')),el('small',{},'Changing this W-2’s values or owner clears only its review. Review status does not submit or certify a tax return.'));
 if(source){const restored=source.return_id!==currentId;holder.append(el('p',{},restored?'Source attachment not restored · '+source.name:'Local '+(source.method==='taxml'?'tax data':'document')+' source · '+source.name));if(!restored)holder.append(button('View source document',()=>showLocalSource(source),'secondary',{class:'button secondary small'}));}
 return holder;
}
function repeatRecords(key){
 const definition=recordDefinitions[key],holder=el('div'),records=data[key]||(data[key]=[]);if(key==='w2')ensureW2Metadata();if(key==='capital_gains')ensureInvestmentMetadata();if(['interest','dividends'].includes(key))ensureIncomeMetadata();
 if(!records.length)holder.append(el('div',{class:'empty-state'},'No '+definition.label+' added yet.',el('br'),'Add one to enter the information from your document.'));
 for(const[rowIndex,row]of records.entries()){
  const recordKey=key+':'+(key==='w2'?metadata.w2_records[rowIndex].record_id:key==='capital_gains'?metadata.investment_records[rowIndex].record_id:['interest','dividends'].includes(key)?metadata.income_document_records[key][rowIndex].record_id:rowIndex),isOpen=openRecords.has(recordKey)||records.length===1;
  const content=grid(...definition.fields.filter(([, ,type])=>type!=='check').map(([name,label,type])=>field(key+'.'+rowIndex+'.'+name,label,type==='owner'?'select':type==='term'?'select':type||'money',type==='owner'?{choices:ownerChoices}:type==='term'?{choices:[['short','Short-term'],['long','Long-term']]}:{})));
  for(const[name,label,type]of definition.fields.filter(([, ,type])=>type==='check'))content.append(check(key+'.'+rowIndex+'.'+name,label));
  const extras=autoObject(key+'.'+rowIndex,schemaValue(key+'.'+rowIndex));if(extras)content.append(extras);if(key==='w2')content.append(w2ReviewPanel(rowIndex));if(key==='capital_gains')content.append(investmentCorrectionPanel(rowIndex));if(['interest','dividends'].includes(key))content.append(incomeReviewPanel(key,rowIndex));
  const body=el('div',{class:'record-body',hidden:!isOpen},content),caption=el('span',{},definition.label+' '+(rowIndex+1),el('small',{},row[definition.name]||'Enter details below'));
  if(key==='w2')caption.append(el('small',{'data-w2-review-state':metadata.w2_records[rowIndex].record_id},metadata.w2_records[rowIndex].reviewed?'Reviewed':'Needs review'));
  if(['interest','dividends'].includes(key)){const item=metadata.income_document_records[key][rowIndex];caption.append(el('small',{'data-income-review-state':item.record_id},(item.reviewed?'Reviewed':'Needs review')+(item.is_placeholder?' · Prior-year placeholder':'')+(item.unresolved_fields.length?' · '+item.unresolved_fields.length+' unresolved facts':'')));}
  if(key==='w2'&&metadata.w2_records[rowIndex].source_document?.return_id&&metadata.w2_records[rowIndex].source_document.return_id!==currentId)caption.append(el('small',{},'Source attachment not restored'));
  const heading=el('button',{class:'record-header-button',type:'button','aria-expanded':isOpen,onClick:event=>{body.hidden=!body.hidden;event.currentTarget.setAttribute('aria-expanded',String(!body.hidden));if(body.hidden)openRecords.delete(recordKey);else openRecords.add(recordKey);}},el('span',{'aria-hidden':'true'},isOpen?'⌄':'›'),caption);
  holder.append(el('section',{class:'record'},el('div',{class:'record-header'},heading,el('button',{class:'delete-record',type:'button','aria-label':'Remove '+definition.label+' '+(rowIndex+1),onClick:()=>{if(key==='w2')metadata.w2_records.splice(rowIndex,1);if(key==='capital_gains')metadata.investment_records.splice(rowIndex,1);if(['interest','dividends'].includes(key))metadata.income_document_records[key].splice(rowIndex,1);records.splice(rowIndex,1);openRecords.delete(recordKey);if(!['w2','capital_gains','interest','dividends'].includes(key))openRecords.clear();changed();renderPage(false);}},'Remove')),body));
 }
 holder.append(el('button',{class:'add-record',type:'button',onClick:()=>{records.push(clone(schema.capabilities?.row_templates?.[key]||definition.template));if(key==='w2'){metadata.w2_records.push(window.taxRecordMetadata.newRecord());openRecords.add(key+':'+metadata.w2_records.at(-1).record_id);}else if(key==='capital_gains'){metadata.investment_records.push(window.taxInvestmentCorrections.newRecord());openRecords.add(key+':'+metadata.investment_records.at(-1).record_id);}else if(['interest','dividends'].includes(key)){metadata.income_document_records[key].push(window.taxIncomePreparation.newRecord());openRecords.add(key+':'+metadata.income_document_records[key].at(-1).record_id);}else openRecords.add(key+':'+(records.length-1));changed();renderPage(false);}},'+ Add another '+definition.label));
 return holder;
}
function personProfile(owner){
 const person=data[owner],age=birthDateAge(person);if(age!==null)person.age=age;
 const ageField=field(owner+'.age','IRS age · calculated when birth date is entered','age',{help:'Without a birth date, enter the IRS age explicitly. Dates resolve the separate EIC and senior rules.'});if(ageField)ageField.querySelector('input').readOnly=age!==null;
 return card(owner==='taxpayer'?'Taxpayer':'Spouse',grid(field(owner+'.birth_date','Date of birth (YYYY-MM-DD)','text',{help:'Optional. Enter the complete date to calculate January1 birthday boundaries.'}),field(owner+'.death_date','Date of death in2025 (if applicable)','text',{help:'Leave empty for a living taxpayer. Final decedent filing requires separate review.'}),ageField),check(owner+'.blind','This person is blind'),check(owner+'.can_be_claimed','Someone else can claim this person as a dependent'),check(owner+'.valid_ssn','This person has an eligible SSN'),check(owner+'.valid_tin','This person has a valid SSN or ITIN','A valid ITIN does not satisfy SSN-specific credit requirements.'));
}
function profilePage(){const history=metadata.setup_import_events||[];return[title("Let's start with you.",'Tell us about your household for tax year2025. Birth dates calculate the separate EIC and senior age rules. Use synthetic identity data while testing.'),card('Return & filing status',grid(field('name','Return name','text'),field('filing_status','Filing status','select',{choices:[['single','Single'],['mfj','Married filing jointly'],['mfs','Married filing separately'],['hoh','Head of household'],['qss','Qualifying surviving spouse']]})),history.length?el('details',{},el('summary',{},'Reviewed filing-status source history'),history.map(event=>el('div',{class:'note'},el('p',{},filingStatusLabels[event.previous_filing_status]+' → '+filingStatusLabels[event.filing_status]+' · '+event.reviewed_at),el('small',{},'Source '+event.source_document.name+' · '+event.source_document.taxml_receipt.source_sha256),button('View setup source',()=>showLocalSource(event.source_document),'secondary',{class:'button secondary small'})))):null),personProfile('taxpayer'),['mfj','mfs','qss'].includes(data.filing_status)?personProfile('spouse'):null];}
function eligibilityPage(){const situations=[moduleDefinitions.has('rentals')?'Royalty income or unsupported rental situation':'Rental or royalty income','Partnership / S-corporation K-1','Foreign income or tax credit',...(moduleDefinitions.has('marketplace')?[]:['Marketplace insurance / Form 1095-A']),moduleDefinitions.has('education')?'Energy credits':'Education or energy credits',...(moduleDefinitions.has('amt')?[]:['Alternative minimum tax']),'Unsupported prior-year carryover','Other tax situation not modeled'];for(const label of data.unsupported||[])if(!situations.includes(label))situations.push(label);return[title("Let's check your tax situation.",'Confirm only statements that are true. A blocking issue remains when a required rule or unsupported situation has not been resolved.'),card('Required scope confirmations',check('eligibility.filing_status_confirmed','I verified that this filing status applies to my household.'),check('eligibility.full_year_us_resident','Taxpayer and spouse, if applicable, were full-year U.S. residents.'),check('eligibility.all_income_reported','All income for this worksheet has been entered.'),check('eligibility.no_amt_preferences','I verified that no AMT preference or adjustment requires Form 6251.'),check('eligibility.eitc_not_applicable','I reviewed Earned Income Tax Credit eligibility and EITC does not apply.','Do not check this merely to remove a warning. If EITC may apply, leave unchecked and complete the Earned Income Tax Credit interview when available.')),data.filing_status==='hoh'?card('Head of household',check('eligibility.hoh_eligible','I verified the qualifying-person and household rules for head of household.')):null,data.filing_status==='qss'?card('Qualifying surviving spouse',check('eligibility.qss_eligible','I verified qualifying-surviving-spouse eligibility.')):null,data.filing_status==='mfs'?card('Married filing separately',check('eligibility.mfs_spouse_itemizes','My spouse itemizes deductions.'),check('eligibility.mfs_lived_with_spouse','I lived with my spouse during the year.')):null,card('Situations outside the supported scope',el('p',{class:'note'},'Select any situation that applies. The engine will mark the return as blocked rather than treating unsupported tax rules as complete.'),situations.map(label=>el('label',{class:'check-field'},el('input',{type:'checkbox',name:'unsupported',value:label,checked:(data.unsupported||[]).includes(label),onChange:event=>{data.unsupported=data.unsupported||[];if(event.target.checked){if(!data.unsupported.includes(label))data.unsupported.push(label);}else data.unsupported=data.unsupported.filter(item=>item!==label);changed();}}),el('span',{},label))),field('notes','Notes for your review','textarea',{full:true}))];}
function incomeOverview(){const rows=[['w2','Wages & salaries','W-2','wages','▧'],['interest','Interest','1099-INT','taxable','◉'],['dividends','Dividends','1099-DIV','ordinary','▤'],['capital_gains','Investment sales','1099-B / brokerage lots','proceeds','↗'],['businesses','Self-employment','Schedule C / 1099-NEC revenue','revenue','▱']];return[title("Let's get your income entered.",'Choose a category to add or update your documents. Entered amounts are source-document totals; tax results come from the calculation engine.'),el('div',{class:'income-list'},rows.map(([key,label,note,total,icon])=>el('div',{class:'income-row'},el('div',{class:'card-icon','aria-hidden':'true'},icon),el('div',{class:'income-caption'},el('strong',{},label),el('small',{},note+' · '+(data[key]||[]).length+' records')),el('div',{class:'entered-amount'},enteredSum(key,total)),button((data[key]||[]).length?'Update':'Start',()=>navigate(key),'secondary',{class:'button secondary small'}))),el('div',{class:'income-row'},el('div',{class:'card-icon'},'▥'),el('div',{class:'income-caption'},el('strong',{},'Retirement & Social Security'),el('small',{},'1099-R / SSA-1099')),button('Update',()=>navigate('retirement'),'secondary',{class:'button secondary small'})),el('div',{class:'income-row'},el('div',{class:'card-icon'},'⋯'),el('div',{class:'income-caption'},el('strong',{},'Other income'),el('small',{},'Unemployment and other taxable income')),button('Update',()=>navigate('other_income'),'secondary',{class:'button secondary small'})))];}
function incomeRecordsPage(key){const titles={w2:["Let's enter your W-2.",'Use the amounts printed on your W-2. Every employer gets a separate W-2 record. Add documents as local attachments if you want to keep a copy.'],interest:["Let's add your interest income.",'Enter each payer separately. Tax-exempt interest is kept separate from taxable interest.'],dividends:["Let's add your dividends.",'Enter each 1099-DIV separately. Box 1b is part of Box 1a. Box 2a already includes the Box 2b and Box 2d special-rate components.'],capital_gains:["Let's enter your investment sales.",'Enter each short- or long-term lot, its proceeds, basis and adjustment. Unsupported carryovers or special sales must be flagged in your tax situation.'],businesses:["Let's enter your business income.",'Each business gets a separate revenue and expense record. Eligibility, losses and other business limitations are checked by the engine.']};return[title(...titles[key]),el('div',{class:'inline-actions'},button('Import CSV',()=>showCSVImport(key),'secondary'),button('Export CSV',()=>exportRecordsCSV(key),'secondary')),repeatRecords(key),key==='dividends'?card('Distribution and qualified-dividend eligibility',check('eligibility.capital_gains_eligible','I verified the capital gain distributions and supported allocation.'),check('eligibility.qualified_dividends_eligible','I verified qualified-dividend payer and holding-period eligibility.','Box 1b alone does not establish your holding period. Check related-payment and investment-interest election restrictions.')):null,key==='capital_gains'?card('Investment-sale eligibility',check('eligibility.capital_gains_eligible','I verified that these are supported ordinary brokerage sales, without unmodeled adjustments.')):null,key==='w2'?el('div',{class:'note'},typeof window.extractTaxDocument==='function'?'Manual entry and reviewed local document extraction are available. Employer-network import is not provided.':'Manual entry and CSV entry are available. Photo/PDF attachments stay locally; document extraction is not loaded in this build.'):null];}
function parseCSV(text){
 const rows=[];let row=[],cell='',quoted=false;
 const input=String(text).replace(/^\uFEFF/,'');
 for(let index=0;index<input.length;index++){
  const character=input[index];
  if(quoted){if(character==='"'){if(input[index+1]==='"'){cell+='"';index++;}else quoted=false;}else cell+=character;}
  else if(character==='"'){if(cell)throw Error('A CSV quote must begin a field.');quoted=true;}
  else if(character===','){row.push(cell);cell='';}
  else if(character==='\n'||character==='\r'){if(character==='\r'&&input[index+1]==='\n')index++;row.push(cell);if(row.some(value=>value.trim()))rows.push(row);row=[];cell='';}
  else cell+=character;
 }
 if(quoted)throw Error('The CSV contains an unclosed quoted field.');
 row.push(cell);if(row.some(value=>value.trim()))rows.push(row);
 if(rows.length<2)throw Error('Choose a CSV with a header row and at least one data row.');
 if(rows.length>5001)throw Error('Import at most 5,000 records at a time.');
 const headers=rows.shift().map(value=>value.trim());
 if(headers.some(value=>!value)||new Set(headers).size!==headers.length)throw Error('Every CSV column must have a unique, nonempty heading.');
 if(rows.some(values=>values.length!==headers.length))throw Error('Every CSV row must have the same number of fields as its header.');
 return{headers,rows};
}
function csvAmount(text){
 let value=String(text).trim();if(!value)return'0';
 if(/^\(\$?[\d,]+(?:\.\d{1,2})?\)$/.test(value))value='-'+value.slice(1,-1).replace(/^\$/,'');
 const grouped=/^-?\$?\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?$/;
 if(grouped.test(value))value=value.replaceAll(',','');
 value=value.replace(/^(-?)\$/,'$1');decimalCents(value);return value;
}
async function exportRecordsCSV(key){
 const template=rowTemplate(key);if(!template)throw Error('A CSV template is unavailable for this record type.');
 const headers=Object.keys(template).filter(name=>!template[name]||typeof template[name]!=='object');
 const escape=value=>'"'+String(value??'').replaceAll('"','""')+'"';
 const rows=[headers,...(data[key]||[]).map(record=>headers.map(name=>{
  const value=record[name]??template[name];
  return inputType(key+'.0.'+name)==='text'&&/^[=+\-@]/.test(String(value))?"'"+value:value;
 }))];
 await downloadBlob(new Blob(['\uFEFF'+rows.map(row=>row.map(escape).join(',')).join('\r\n')+'\r\n'],{type:'text/csv;charset=utf-8'}),'tax-reborn-2025-'+key+'.csv');
}
function showCSVImport(key){
 const id=currentId,openedRevision=revision,definition=recordDefinitions[key],template=rowTemplate(key),income=['interest','dividends'].includes(key),eventId=crypto.randomUUID();if(income)ensureIncomeMetadata();
 if(!template)throw Error('The local engine did not provide this record template.');
 const holder=el('div'),file=el('input',{type:'file',accept:'.csv,text/csv','aria-label':'Choose CSV file'}),mapping=el('div'),preview=el('div'),confirmed=el('input',{type:'checkbox'});let parsed=null,pendingIncomeImport=null;const selections={};
 holder.append(el('p',{class:'intro'},'Map CSV columns to '+definition.label+' fields. '+(income?'Import adds current-year records and can replace only explicitly selected prior-year placeholders. It saves the rows and replacement history together.':'Import appends new records to this return.')+' It does not establish tax eligibility.'),file,mapping,preview);
 const replacementChoices=[];
 if(income){
  const choices=el('div',{class:'note'},el('strong',{},'Optional · replace selected prior-year placeholders'));
  for(const [index,item] of metadata.income_document_records[key].entries())if(item.is_placeholder){
   const input=el('input',{type:'checkbox','aria-label':'Replace placeholder '+item.record_id.slice(0,8)});replacementChoices.push({input,id:item.record_id});
   const amount=key==='interest'?data[key][index].taxable:data[key][index].ordinary;
   choices.append(el('label',{class:'check-field'},input,el('span',{},(data[key][index].payer||'Unnamed payer')+' · '+dollars(amount)+' · ID '+item.record_id.slice(0,8))));
  }
  choices.append(el('small',{},replacementChoices.length?'Same-payer documents with other IDs are kept. No old row is removed if validation or saving fails.':'No records are marked as placeholders. Close this dialog and mark an old row if it should be replaced.'));
  holder.append(choices);
 }
 holder.append(el('label',{class:'check-field'},confirmed,el('span',{},'I reviewed the mapped fields and each source amount for tax year 2025.')));
 const dialog=modal('Import '+definition.label+' CSV',holder,[[key==='w2'?'Add W-2 records':'Add reviewed records',async()=>{
  if(currentId!==id)throw Error('The open return changed. Start the import again for that return.');
  if(revision!==openedRevision)throw Error('The return changed after opening this import. Review a fresh import.');
  if(!parsed)throw Error('Choose a CSV file first.');
  if(!confirmed.checked)throw Error('Review the source rows and confirm the mapped fields first.');
  if(!Object.values(selections).some(select=>select.value!==''))throw Error('Map at least one column to a record field.');
  const records=parsed.rows.map((values,index)=>{
   const record=clone(template);
   for(const[name,select]of Object.entries(selections)){
    if(select.value==='')continue;const raw=values[Number(select.value)].trim(),path=key+'.0.'+name,type=inputType(path);
    try{
     if(type==='money')record[name]=csvAmount(raw);
     else if(type==='boolean'){if(!/^(true|false|1|0|yes|no)$/i.test(raw))throw Error('Use true/false, yes/no or 1/0 for this question.');record[name]=/^(true|1|yes)$/i.test(raw);}
     else if(type==='int'){if(!/^\d+$/.test(raw))throw Error('Use a whole number.');record[name]=Number(raw);}
     else if(name==='term'){const term=raw.toLowerCase().replace(/[^a-z]/g,'');if(!['short','shortterm','long','longterm'].includes(term))throw Error('Use short or long for the holding period.');record[name]=term.startsWith('short')?'short':'long';}
     else if(name==='owner'){if(!['taxpayer','spouse'].includes(raw.toLowerCase()))throw Error('Use taxpayer or spouse for the owner.');record[name]=raw.toLowerCase();}
     else record[name]=raw;
    }catch(error){throw Error('CSV row '+(index+2)+', '+humanLabel(name)+': '+error.message);}
   }
   return record;
  });
  if(income){
   const targets=replacementChoices.filter(item=>item.input.checked).map(item=>item.id),prepared=await window.taxRecordMetadata.normalize(payload(),clone(metadata));
   let replacement;
   if(targets.length){const proposal=await window.taxIncomePreparation.plan(payload(),prepared,key,targets,records,eventId);replacement=await window.taxIncomePreparation.apply(payload(),prepared,proposal);}
   else{const candidate=clone(data),preparation=clone(prepared);candidate[key].push(...records);for(const row of records)preparation.income_document_records[key].push(window.taxIncomePreparation.newRecord());replacement={data:candidate,metadata:preparation};}
   for(const entry of replacement.metadata.income_document_records[key])if(!prepared.income_document_records[key].some(old=>old.record_id===entry.record_id)){entry.reviewed=true;entry.reviewed_at=new Date().toISOString();entry.reviewed_fingerprint=await window.taxIncomePreparation.fingerprint(key,replacement.data[key][replacement.metadata.income_document_records[key].indexOf(entry)]);entry.row_fingerprint=entry.reviewed_fingerprint;}
   let candidate=normalizeInput(replacement.data),preparation=await window.taxRecordMetadata.normalize(candidate,replacement.metadata);
   if(pendingIncomeImport){if(JSON.stringify(pendingIncomeImport.data)!==JSON.stringify(candidate))throw Error('This import changed after a save attempt. Close it and review a new import.');candidate=clone(pendingIncomeImport.data);preparation=clone(pendingIncomeImport.metadata);}else pendingIncomeImport={data:clone(candidate),metadata:clone(preparation)};
   await api('/api/calculate',{method:'POST',body:JSON.stringify(candidate)});
   if(currentId!==id||revision!==openedRevision||!dialog.body.isConnected)throw Error('The open return or import changed. No records were imported.');
   busySave=true;busyIncomeCommit=true;updateHeader();const controls=[...dialogNode.querySelectorAll('button,input,select,textarea')];controls.forEach(node=>node.disabled=true);dialog.error.textContent='Saving reviewed import…';
   try{
    const saved=await api('/api/returns',{method:'POST',body:JSON.stringify({id,data:candidate,metadata:preparation,expected_updated_at:hasSaved?savedUpdatedAt:null})});
    data=mergeDefaults(saved.data,schema.default_return);metadata=saved.metadata;savedUpdatedAt=saved.updated_at;result=saved.result;revision++;calculatedRevision=revision;hasSaved=true;dirty=false;synthetic=false;openRecords.clear();await checkpointWorkspace().catch(()=>notify('Import saved. Reopen the saved return if workspace recovery is unavailable.',true));tellNativeWorkspaceReady();
   }finally{busyIncomeCommit=false;busySave=false;controls.forEach(node=>node.disabled=false);updateHeader();}
   closeDialog();navigate(key);notify(targets.length?'Reviewed import saved. '+targets.length+' selected placeholder(s) replaced; unrelated records kept.':'Reviewed income records imported and saved locally.');return;
  }
  const candidate=clone(data);candidate[key].push(...records);
  await api('/api/calculate',{method:'POST',body:JSON.stringify(normalizeInput(candidate))});
  if(currentId!==id||revision!==openedRevision||!dialog.body.isConnected)throw Error('The open return changed. No records were imported.');
  data[key].push(...records);openRecords.clear();changed();closeDialog();navigate(key);notify(key==='w2'?records.length+' W-2 records added. Check each W-2 and mark its review before relying on the entries.':records.length+' reviewed records added. Save to keep them.');
 },'primary']]);
 file.addEventListener('change',async()=>{
  try{
   const selected=file.files[0];if(!selected)return;if(selected.size>5*1024*1024)throw Error('Choose a CSV smaller than 5 MB.');
   parsed=parseCSV(await selected.text());confirmed.checked=false;mapping.replaceChildren(el('h3',{style:'margin-top:22px'},'Map columns'));for(const name of Object.keys(selections))delete selections[name];const fields=grid();
   for(const[name,value]of Object.entries(template)){
    if(value&&typeof value==='object')continue;
    const select=el('select',{'aria-label':'CSV column for '+humanLabel(name)},el('option',{value:''},'Keep default / not in CSV'),...parsed.headers.map((header,index)=>el('option',{value:index},header)));
    const match=parsed.headers.findIndex(header=>header.toLowerCase().replace(/[^a-z0-9]/g,'')===name.toLowerCase().replace(/[^a-z0-9]/g,''));if(match>=0)select.value=String(match);
    selections[name]=select;fields.append(el('div',{class:'field'},el('label',{},recordDefinitions[key].fields.find(item=>item[0]===name)?.[1]||humanLabel(name)),select));
   }
   mapping.append(fields);
   preview.replaceChildren(el('div',{class:'note'},parsed.rows.length+' source rows. Dollar fields accept plain amounts or properly grouped dollar values. Unmapped eligibility questions keep their defaults and may block the worksheet.'),el('h3',{style:'margin-top:22px'},'Source preview · first '+Math.min(5,parsed.rows.length)+' rows'),el('div',{class:'table-scroll'},el('table',{class:'data-table'},el('thead',{},el('tr',{},parsed.headers.map(header=>el('th',{},header)))),el('tbody',{},parsed.rows.slice(0,5).map(values=>el('tr',{},values.map(value=>el('td',{},value))))))));dialog.error.textContent='';
  }catch(error){parsed=null;dialog.error.textContent=error.message;}
 });
}

const sectionFields={carryovers:[['capital_short','Short-term capital loss carry-in'],['capital_long','Long-term capital loss carry-in'],['qbi_loss','Qualified business loss carry-in'],['charity','Charitable contribution carry-in']],retirement:[['ira_gross','IRA gross distributions'],['ira_taxable','IRA taxable distributions'],['pension_gross','Qualified pension gross distributions'],['pension_taxable','Qualified pension taxable amount'],['social_security','Social Security benefits'],['federal_withholding','Federal income tax withheld']],other_income:[['unemployment','Unemployment compensation'],['other','Other taxable income'],['federal_withholding','Federal income tax withheld']],adjustments:[['student_loan_interest','Student loan interest paid'],['ira_deduction','Eligible IRA deduction'],['hsa_deduction','Eligible HSA deduction'],['self_employed_health_insurance','Self-employed health insurance deduction']],itemized:[['medical','Medical and dental expenses'],['state_local_tax','State and local taxes paid'],['mortgage_interest','Eligible mortgage interest'],['charity','Charitable contributions'],['investment_interest','Eligible investment interest']],schedule_1a:[['qualified_tips','Qualified tips already included in income'],['qualified_overtime','Qualified overtime premium already in income'],['qualified_car_loan_interest','Qualified car-loan interest paid']],payments:[['estimated','2025 estimated federal tax payments'],['prior_year_credit','2024 overpayment applied to 2025']]};
function sectionPage(key){const headings={carryovers:['Do you have carryovers from a prior year?','Enter amounts for a transparent record. The engine applies supported carryovers and flags any carryover rule that has not been established.'],retirement:["Let's review your retirement income.",'Enter gross distributions separately from the taxable portions. This engine does not determine taxable basis from a photographed statement.'],other_income:["Any other income to report?",'Enter taxable unemployment and other income that is within the supported scope.'],adjustments:["Let's check your income adjustments.",'Enter deductions only after checking eligibility. The engine can block amounts when deduction rules are not sufficiently established.'],itemized:["Let's find the right deduction.",'Enter your eligible expenses. The calculation engine compares the supported itemized deductions with the standard deduction.'],schedule_1a:["Let's review the additional deductions.",'For tax year 2025, enter qualified amounts and explicitly confirm their eligibility. These deduction inputs do not add tips or overtime to income.'],payments:["Let's include your tax payments.",'Withholding entered on income documents is already included. Add only estimated payments and the prior-year credit here.']};const contents=grid(...sectionFields[key].map(([name,label])=>field(key+'.'+name,label)));const parts=[title(...headings[key]),card(pageNames[key],contents)];if(key==='retirement')parts.push(card('Distribution confirmations',field('retirement.ira_distribution_kind','IRA distribution treatment','select',{choices:[['fully_taxable','Fully taxable distribution'],['qualified_rollover','Qualified rollover'],['other','Other / needs review']]}),check('retirement.taxable_amounts_confirmed','I verified the taxable IRA and pension distribution amounts.'),check('retirement.qualified_plan_confirmed','The reported pension comes from a qualified U.S. retirement plan.','Report nonqualified annuities separately when an annuity section is available. Foreign pensions and mixed qualified-plan distributions may require review.'),check('retirement.ss_lump_sum_or_repayments','Social Security includes a lump-sum payment or repayment.'),check('retirement.early_distribution_exception_confirmed','Any early taxable distribution qualifies for an applicable exception.','Confirm only when a valid exception applies. The engine does not silently ignore an early-distribution tax.')));if(key==='other_income')parts.push(card('Other-income confirmation',check('other_income.taxable_other_confirmed','I verified that the other-income amount is taxable and within the supported scope.')));if(key==='adjustments')parts.push(card('Deduction eligibility',check('eligibility.student_loan_eligible','The student loan interest meets the applicable deduction rules.'),el('div',{class:'note warning'},moduleDefinitions.has('ira')||moduleDefinitions.has('hsa')?'Use the IRA and HSA interview pages for contributions, coverage and eligibility. Entering an adjustment amount alone does not establish a deduction.':'IRA and HSA deduction computations are not implemented. Nonzero entries are retained but block a prepared worksheet.'),check('eligibility.self_employed_health_insurance_eligible','The self-employed health insurance deduction is eligible.')));if(key==='itemized')parts.push(card('Expense eligibility',check('itemized.medical_eligible','I verified that the medical expenses meet the applicable rules.'),check('itemized.mortgage_eligible','I verified the mortgage-interest deduction eligibility.'),check('itemized.charity_cash_only','The charitable amounts are eligible cash contributions only.'),check('eligibility.itemized_eligible','I verified that these itemized expenses meet the applicable rules.','The numeric amount alone does not establish medical, mortgage, charitable or investment-interest eligibility.')));if(key==='schedule_1a')parts.push(card('Schedule 1-A eligibility',check('schedule_1a.eligibility_confirmed','I verified eligibility for the entered Schedule 1-A amounts.'),check('schedule_1a.tips_occupation_eligible','The tips come from an eligible occupation.'),check('schedule_1a.tips_not_sstb','The tips are not from an excluded specified service trade or business.'),check('schedule_1a.overtime_flsa_eligible','The entered overtime is an eligible FLSA overtime premium.'),check('schedule_1a.car_loan_eligible','The car loan and vehicle satisfy the applicable deduction requirements.')));return parts;}
function resultNeeded(){return el('div',{class:'error-page'},calculationError||'A current calculation is not available. Check your input amounts or retry the local service.',el('div',{class:'inline-actions'},button('Calculate now',()=>calculate(),'primary'),button('Review eligibility',()=>navigate('eligibility'))));}
function w2ReviewSummary(){ensureW2Metadata();const count=metadata.w2_records.length;if(!count)return null;const remaining=metadata.w2_records.filter(item=>!item.reviewed).length;return card('Your W-2 document review',el('p',{class:'intro'},remaining?remaining+' of '+count+' W-2 records still need your source-document review.':'All '+count+' W-2 records are marked reviewed.'),el('small',{},'This local checklist is separate from the tax engine’s eligibility and calculation checks.'),button('Review W-2 records',()=>navigate('w2'),'secondary'));}
function incomeReviewSummary(){
 ensureIncomeMetadata();const entries=Object.values(metadata.income_document_records).flat(),total=entries.length;if(!total)return null;
 const reviewed=entries.filter(item=>item.reviewed).length,unresolved=entries.filter(item=>item.is_placeholder||item.unresolved_fields.length).length;
 const holder=card('Interest and dividend source review',el('p',{class:'intro'},reviewed+' of '+total+' documents reviewed; '+unresolved+' still have unresolved source facts or a prior-year placeholder.'),el('small',{},'Checking Reviewed does not clear missing facts. Only current document IDs are counted. Tax calculation and paper-form readiness remain separate.'),el('div',{class:'inline-actions'},button('Review interest',()=>navigate('interest'),'secondary'),button('Review dividends',()=>navigate('dividends'),'secondary')));
 if(metadata.income_import_events.length)holder.append(el('details',{},el('summary',{},'Saved placeholder replacement history'),el('ul',{},metadata.income_import_events.map(event=>el('li',{},recordDefinitions[event.receipt.collection].label+' · import '+event.event_id.slice(0,8)+' · '+event.receipt.removed_record_ids.length+' old record(s) replaced by '+event.receipt.result_record_ids.length+' current record(s).')))));
 return holder;
}
function reviewPage(){if(!result||calculatedRevision!==revision)return[title('Check your federal return.','Review blocking issues, warnings and the calculation before exporting.'),resultNeeded()];const blocked=result.blocking_issues||[],warnings=result.warnings||[];return[title('Check your federal return.','This review covers the implemented 2025 federal worksheet. Exporting a worksheet does not file a tax return.'),el('section',{class:'status-panel'+(result.can_prepare?' ready':'')},el('h2',{},result.can_prepare?'Your supported worksheet has no blocking issues.':'We found '+blocked.length+' issues that need your attention.'),blocked.length?el('ul',{class:'issue-list'},blocked.map(issue=>el('li',{},issue))):el('p',{class:'intro'},'Review all figures and scope limits before using this draft.'),el('div',{class:'inline-actions'},button('Review eligibility',()=>navigate('eligibility'),'secondary'),button('See calculation',()=>navigate('trace'),'secondary'))),formReadiness(),w2ReviewSummary(),incomeReviewSummary(),el('div',{class:'metrics'},[['Adjusted gross income','agi'],['Taxable income','taxable_income'],['Total federal tax','total_tax'],['Payments & credits','payments'],['Refund estimate','refund'],['Amount owed','amount_owed']].map(([label,key])=>el('div',{class:'metric'},el('small',{},label),el('strong',{},dollars(result.summary[key]))))),warnings.length?card('Warnings & scope notes',el('ul',{class:'issue-list'},warnings.map(issue=>el('li',{},issue)))):null,card('Deduction used',el('p',{class:'intro'},String(result.summary.deduction_type||'Engine-selected deduction')),el('div',{class:'note'},typeof window.openStateWorkspace==='function'?'State drafts are prepared separately in State taxes. No electronic filing, payment or expert representation is performed.':'State preparation is not loaded in this build. No electronic filing, payment or expert representation is performed.'))];}
function sourceNode(source){if(!source)return'';const text=typeof source==='string'?source:JSON.stringify(source);try{const url=new URL(text);if(url.protocol==='https:')return el('a',{href:url.href,target:'_blank',rel:'noopener noreferrer'},url.hostname+' · source');}catch{}return text;}
function tracePage(){return[title('Here’s how we calculated your tax.','Each row comes from the calculation engine, including the rule or source it used. Calculated IRS amounts are whole dollars.'),result&&calculatedRevision===revision?el('div',{class:'table-scroll'},el('table',{class:'data-table'},el('thead',{},el('tr',{},['Calculation step','Amount','Rule / source'].map(label=>el('th',{},label)))),el('tbody',{},(result.trace||[]).map(row=>el('tr',{},el('td',{},row.label),el('td',{class:'number'},row.amount==null?'':dollars(row.amount)),el('td',{class:'source-cell'},sourceNode(row.source))))))):resultNeeded(),result?.schedules&&calculatedRevision===revision?card('Calculated schedules',el('details',{class:'details-toggle'},el('summary',{},'Show schedule details'),el('pre',{class:'json-editor'},JSON.stringify(result.schedules,null,2)))):null];}
const formLabels={'1a':'W-2 wages','1e':'Taxable dependent-care benefits','1h':'Other earned income','1z':'Total wages and other earned income','2a':'Tax-exempt interest','2b':'Taxable interest','3a':'Qualified dividends','3b':'Ordinary dividends','4a':'IRA gross distributions','4b':'IRA taxable amount','5a':'Pensions and annuities','5b':'Pension taxable amount','6a':'Social Security benefits','6b':'Taxable Social Security','7a':'Capital gain or loss','8':'Additional income','9':'Total income','10':'Income adjustments','11a':'Adjusted gross income','11b':'Adjusted gross income carried forward','12e':'Standard or itemized deduction','13a':'Qualified business income deduction','13b':'Schedule 1-A deductions','14':'Total deductions','15':'Taxable income','16':'Income tax','17':'Schedule 2 additional tax','18':'Tax before credits','19':'Child / dependent tax credits','20':'Schedule 3 credits','21':'Total nonrefundable credits','22':'Tax after nonrefundable credits','23':'Other taxes, including self-employment','24':'Total tax','25a':'W-2 federal withholding','25b':'1099 federal withholding','25c':'Other federal withholding','25d':'Total federal withholding','26':'Estimated payments and prior-year credit','27a':'Earned income credit','28':'Additional child tax credit','29':'American opportunity credit','30':'Refundable adoption credit','31':'Schedule 3 payments','32':'Other payments and refundable credits','33':'Total payments','34':'Overpayment','35a':'Refund','36':'Amount applied to next year','37':'Amount owed','38':'Estimated tax penalty'};
function formReadiness(){
 const status=result?.form_readiness;
 if(!status||calculatedRevision!==revision)return null;
 const missing=status.missing_identity||[],parts=status.unsupported_packet_parts||[];
 const body=[el('p',{class:'intro'},'Tax calculations and paper-form facts are checked separately. Use the official paper checklist to review the actual supporting forms.'),button('Review official paper checklist',showPaperChecklist,'secondary')];
 if(missing.length)body.push(el('h3',{},'Missing identity fields'),el('ul',{class:'issue-list'},missing.map(item=>el('li',{},typeof item==='string'?humanLabel(item.replace(/^identity\./,'')):String(item.label||item.field||JSON.stringify(item))))),moduleDefinitions.has('identity')?button('Enter local form details',()=>navigate('module:identity'),'secondary'):null);
 else body.push(el('div',{class:'note'},'The identity fields required by the current draft check are present. This does not verify the person’s identity or eligibility.'));
 if(status.missing_paper_facts?.length)body.push(el('h3',{},'Missing paper-form facts'),el('ul',{class:'issue-list'},status.missing_paper_facts.map(item=>el('li',{},item))),button('Enter filing details',()=>navigate('module:filing_details'),'secondary'));
 if(parts.length)body.push(el('h3',{style:'margin-top:20px'},'Paper preparation requirements'),el('ul',{class:'issue-list'},parts.map(item=>el('li',{},typeof item==='string'?item:JSON.stringify(item)))));
 body.push(el('div',{class:'note warning'},status.electronic_filing?'Electronic-filing capability is separately reported by the local service. Review the supported scope before using it.':'Electronic filing is not provided. No IRS acceptance or payment has occurred.'));
 return card('Form packet readiness',body);
}
function formsPage(){
 const heading=title('Your Form 1040 worksheet.','This is a computed worksheet, not a signed or filed IRS return. Identity, signature and filing requirements are not established by this page.');
 if(!result||calculatedRevision!==revision)return[heading,resultNeeded()];
 const rows=Object.entries(formLabels).filter(([line])=>!['1e','1h','1z'].includes(line)||Object.hasOwn(result.additional_lines||{},line)).sort(([left],[right])=>parseInt(left,10)-parseInt(right,10)||left.localeCompare(right)).map(([line,label])=>el('tr',{},el('td',{class:'form-line'},line),el('td',{},label),el('td',{class:'number'},(result.not_computed_lines||[]).includes(line)?'Not computed':dollars(result.lines?.[line]??result.additional_lines?.[line]))));
 const form=el('section',{class:'form-document'},el('div',{class:'form-heading'},el('div',{},el('h2',{},'Form 1040'),el('small',{},'U.S. Individual Income Tax Return · worksheet')),el('span',{class:'tax-year'},'2025')),el('div',{class:'form-watermark'},result.can_prepare?'DRAFT WORKSHEET · NOT FILED':'BLOCKED DRAFT · INCOMPLETE TAX SITUATION'),el('table',{class:'data-table'},el('tbody',{},rows)));
 return[heading,formReadiness(),form,el('div',{class:'inline-actions',style:'margin-top:20px'},button('Export worksheet',()=>exportReturn('worksheet.html'),'primary'),button('Export JSON',()=>exportReturn('export.json'),'secondary'))];
}

const scheduleNames={schedule_d:'Schedule D · Capital gains and losses',schedule_d_tax_worksheet:'Schedule D Tax Worksheet · 25% / 28% gains',schedule_1:'Schedule 1 · Additional income and adjustments',schedule_eic:'Schedule EIC · Earned Income Tax Credit',schedule_8812:'Schedule 8812 · Child and dependent credits',form_4952:'Form 4952 · Investment interest',ira_contributions:'IRA contribution worksheet',qualified_dividends_capital_gain_worksheet:'Qualified dividend and capital gain worksheet',schedule_c:'Schedule C · Business income',schedule_se:'Schedule SE · Self-employment tax',schedule_a:'Schedule A · Itemized deductions',schedule_1a:'Schedule 1-A · Additional deductions',schedule_e:'Schedule E · Rental properties',form_8582:'Form 8582 · Passive activity losses',form_8995:'Form 8995 · QBI deduction',form_8812:'Schedule 8812 · Child and dependent credits',form_8959:'Form 8959 · Additional Medicare tax',form_8960:'Form 8960 · Net Investment Income Tax',form_6251:'Form 6251 · Alternative Minimum Tax',form_8889:'Form 8889 · HSA',form_8863:'Form 8863 · Education credits',form_8962:'Form 8962 · Premium Tax Credit',eitc:'Earned Income Tax Credit',ira:'IRA contribution worksheet'};
function scheduleTable(value,label='Calculation details'){
 if(value===null||value===undefined)return el('span',{},'—');
 if(typeof value!=='object')return el('span',{},typeof value==='boolean'?(value?'Yes':'No'):typeof value==='number'?value.toLocaleString('en-US',{maximumFractionDigits:6}):String(value));
 const entries=Object.entries(value),body=el('tbody');
 for(const[key,item]of entries){
  const caption=Array.isArray(value)?'Record '+(Number(key)+1):label==='Form lines'?'Line '+key:humanLabel(key);
  const content=typeof item==='object'&&item!==null?el('details',{class:'details-toggle'},el('summary',{},Array.isArray(item)?item.length+' records':'Show details'),scheduleTable(item,humanLabel(key))):key==='source'?sourceNode(item):scheduleTable(item,humanLabel(key));
  body.append(el('tr',{},el('td',{},caption),el('td',{class:typeof item==='number'?'number':null},content)));
 }
 return el('div',{class:'table-scroll'},el('table',{class:'data-table schedule-table','aria-label':label},body));
}
function schedulesPage(){
 const heading=title('Your schedules and workpapers.','These are the engine’s computed workpapers. Amounts are whole U.S. dollars unless a field identifies a rate, count or percentage. They do not establish a complete signed IRS schedule packet.');
 if(!result||calculatedRevision!==revision)return[heading,resultNeeded()];
 const schedules=result.schedules||{},names=Object.keys(schedules);
 if(!names.length)return[heading,el('div',{class:'empty-state'},'No calculated schedules were returned by the engine.')];
 return[heading,...names.map(name=>card(scheduleNames[name]||humanLabel(name),scheduleTable(schedules[name],name))),el('div',{class:'inline-actions'},button('Download calculation JSON',()=>exportReturn('export.json'),'secondary'))];
}
function paymentVoucherPage(){
 const base='filing_details.',f=key=>autoField(base+key),owed=result?.lines?.['37'];
 return [title('Prepare your paper payment voucher.','For a check or money order, choose the amount you will actually send. The official2025 Form1040-V includes mailing instructions.'),
 card('Your balance due',el('p',{id:'payment-voucher-balance'},'Form1040 line37 amount owed: '+dollars(owed)),el('p',{class:'intro'},'This amount excludes any separate line38 estimated-tax penalty. Your voucher amount stays separate from tax payments already reported on this return.')),
 card('Payment method and amount',grid(f('balance_due_payment_method'),f('paper_payment_amount_source'),f('paper_payment_amount')),f('paper_payment_confirmed')),
 card('Prepare the official forms',el('div',{class:'inline-actions'},button('Review paper checklist',showPaperChecklist,'secondary'),button('Download official packet',()=>exportReturn('paper-packet.pdf'),'primary'))),
 el('p',{class:'intro'},'Review the voucher and arrange the selected payment yourself. This local preparation has not made a payment or transmitted a return.')];
}
function exportsPage(){return[title('Save your work and prepare your forms.','Saved inputs, actual calculations and official IRS2025 supporting forms stay on this device.'),
 card('Your local return',el('p',{class:'intro'},hasSaved?(dirty?'Save your changes before exporting.':'Saved return · '+data.name):'Save creates a persistent local return.'),el('div',{class:'inline-actions'},button('Save return',()=>saveReturn(),'primary'),button('Open another return',()=>showReturns()),button('Attach documents',()=>showDocuments()))),
 card('Official paper preparation',el('p',{class:'intro'},'Includes Form1040 and filled official supporting forms applicable to the entered amounts. Review missing facts, print, sign yourself and attach the original required withholding documents.'),el('div',{class:'inline-actions'},button('Review paper checklist',showPaperChecklist,'secondary'),button('Download official packet',()=>exportReturn('paper-packet.pdf'),'primary'),button('Enter filing details',()=>navigate('module:filing_details'),'secondary'))),
 card('Calculation and backup',...[['Input + calculation JSON','Portable local backup with the actual rule trace.','export.json','Download JSON'],['Printable worksheet','Print-ready HTML calculation.','worksheet.html','Download worksheet'],['Form1040 with workpapers','Official1040 plus detailed calculation workpapers.','form1040.pdf','Download PDF'],['Masked Form 1040 review copy','SSN/ITIN and refund routing/account numbers are masked. Names, addresses and financial amounts remain visible.','masked-review.pdf','Download masked review copy']].map(([name,help,path,label])=>el('div',{class:'export-card'},el('div',{},el('strong',{},name),el('small',{},help)),button(label,()=>exportReturn(path),'secondary')))),el('div',{class:'note'},'No tax return has been transmitted. The checklist separates missing facts from the signature and original documents you complete on paper.')];}
async function showPaperChecklist(){
 try{if(dirty||!hasSaved)await saveReturn();const status=await api('/api/returns/'+encodeURIComponent(currentId)+'/paper-checklist.json');
 const holder=el('div',{},el('h3',{},status.paper_preparation_complete?'Your supported paper preparation is ready for review.':'Complete these facts before signing.'),status.missing_facts.length?el('ul',{class:'issue-list'},status.missing_facts.map(item=>el('li',{},item))):el('p',{class:'intro'},'No missing facts identified for these entered amounts within the supported scope.'),el('h3',{},'Included official supporting forms'),el('ul',{class:'issue-list'},status.supporting_forms.length?status.supporting_forms.map(form=>el('li',{},form.id+' · '+form.owner+' · '+form.pages+' page(s)')):el('li',{},'No supporting schedule required by these entered amounts.')),el('div',{class:'note'},'Print and review the packet. Sign Form1040 yourself and attach the required original withholding documents. This application has not transmitted your return.'),status.penalty_applicability_review_required?el('div',{class:'note warning'},'Estimated-tax penalty applicability has not been reviewed. Enter the actual dates and amounts in Estimated-tax penalty if needed.'):null);
 modal('Your official paper packet',holder,[['Enter filing details',()=>{closeDialog();navigate('module:filing_details');},'secondary'],['Download official packet',()=>exportReturn('paper-packet.pdf'),'primary']]);
 }catch(error){notify(error.message,true);}
}
function statePage(){
 const ready=typeof window.openStateWorkspace==='function';
 return[title('Prepare a state return.','State calculations use a separate local rule engine and their own coverage checks. Federal figures supply starting values; review every state-specific adjustment.'),
  card('Your state workspace',el('p',{class:'intro'},ready?'Choose a state and enter residency, income adjustments and state-specific facts. Results remain drafts with visible notes and assumptions.':'The state calculation module is not loaded in this build. Your federal return remains editable and saved locally.'),
   button('Open state workspace',async()=>{await saveReturn();if(typeof window.openStateWorkspace!=='function')throw Error('The state calculation module is unavailable in this build.');await window.openStateWorkspace({returnId:currentId,federalData:payload(),federalResult:result});},'primary',{disabled:!ready})),
  el('div',{class:'note warning'},'State coverage is evaluated by the state module. A state calculation does not electronically file a return, and unsupported residency or state-specific facts must be resolved before relying on it.')];
}
function advancedPage(){const editor=el('textarea',{class:'json-editor','aria-label':'Advanced return input JSON',spellcheck:false});editor.value=JSON.stringify(data,null,2);return[title('Advanced input JSON.','Use this view for every engine field, including new eligibility fields. Applying valid JSON updates the same return and triggers an actual recalculation.'),editor,el('div',{class:'inline-actions',style:'margin-top:15px'},button('Apply JSON',async()=>{try{const next=JSON.parse(editor.value);if(!next||Array.isArray(next)||typeof next!=='object')throw Error('Return input must be a JSON object.');const id=currentId,atRevision=revision;const prior=await window.taxRecordMetadata.normalize(data,clone(metadata),null,{draft:true});const preparation=await window.taxRecordMetadata.normalize(next,null,prior,{draft:true});if(currentId!==id||revision!==atRevision)throw Error('The return changed while applying JSON. Refresh this editor and try again.');data=next;metadata=preparation;changed();renderPage(false);notify('JSON applied. Review the engine validation.');}catch(error){notify(error.message,true);}},'primary'),button('Reset editor from current return',()=>editor.value=JSON.stringify(data,null,2),'secondary'))];}
function renderPage(focus=true){if(!data)return;const main=$('#main');renderedPaths.clear();let nodes;if(page==='profile')nodes=profilePage();else if(page==='dependents')nodes=[title('Who can you claim as a dependent?','Enter each dependent and confirm only the qualifying-child and SSN statements that apply.'),repeatRecords('dependents')];else if(page==='eligibility')nodes=eligibilityPage();else if(page==='income-overview')nodes=incomeOverview();else if(recordDefinitions[page])nodes=incomeRecordsPage(page);else if(sectionFields[page])nodes=sectionPage(page);else if(page.startsWith('module:'))nodes=modulePage(page.slice(7));else if(page==='states')nodes=statePage();else if(page==='review')nodes=reviewPage();else if(page==='trace')nodes=tracePage();else if(page==='forms')nodes=formsPage();else if(page==='schedules')nodes=schedulesPage();else if(page==='payment-voucher')nodes=paymentVoucherPage();else if(page==='exports')nodes=exportsPage();else nodes=advancedPage();if(sectionFields[page])nodes.push(additionalFields(page));if(page==='profile')nodes.push(additionalFields('taxpayer'),['mfj','mfs','qss'].includes(data.filing_status)?additionalFields('spouse'):null);if(page==='eligibility')nodes.push(additionalFields('eligibility'));main.replaceChildren(...nodes.filter(Boolean));if(focus)main.focus({preventScroll:true});updateHeader();renderSummary();}
let dialogCleanup=null,activeSourceComparison=null;
function closeDialog(){if(busyIncomeCommit)return;const cleanup=dialogCleanup;dialogCleanup=null;if(cleanup)cleanup();dialogNode=null;$('#dialog-root').replaceChildren();for(const url of documentURLs)URL.revokeObjectURL(url);documentURLs=[];}
function modal(title,content,actions=[]){closeDialog();const error=el('div',{class:'dialog-error','aria-live':'polite'}),body=el('div',{class:'dialog-body'},content),footer=el('div',{class:'dialog-footer'},button('Close',closeDialog,'secondary'),actions.map(([label,callback,kind,attrs])=>button(label,async event=>{const target=event.currentTarget;target.disabled=true;error.textContent='';try{await callback();}catch(issue){error.textContent=issue.message;}finally{target.disabled=false;}},kind||'primary',attrs||{})));const box=el('section',{class:'dialog',role:'dialog','aria-modal':'true','aria-label':title},el('header',{class:'dialog-header'},el('h2',{},title),el('button',{class:'icon-button','aria-label':'Close dialog',onClick:closeDialog},'×')),body,error,footer);dialogNode=el('div',{class:'overlay'},box);$('#dialog-root').append(dialogNode);box.addEventListener('keydown',event=>{if(event.key!=='Tab')return;const controls=[...box.querySelectorAll('button,input:not([type=hidden]),select,textarea,a[href]')].filter(node=>!node.disabled&&!node.hidden&&node.getClientRects().length);if(!controls.length)return;const first=controls[0],last=controls.at(-1);if(event.shiftKey&&(document.activeElement===first||!box.contains(document.activeElement))){event.preventDefault();last.focus();}else if(!event.shiftKey&&(document.activeElement===last||!box.contains(document.activeElement))){event.preventDefault();first.focus();}});requestAnimationFrame(()=>{if(box.isConnected&&!box.contains(document.activeElement))(box.querySelector('input:not([type=file]),select,textarea')||footer.querySelector('button')).focus();});return{body,error,footer};}
async function saveReturn(){if(busySave)return false;let input;try{input=payload();}catch(error){notify(error.message,true);throw error;}if(!currentId)currentId=crypto.randomUUID();const id=currentId,atRevision=revision;busySave=true;updateHeader();try{const preparation=await window.taxRecordMetadata.normalize(input,clone(metadata));const saved=await api('/api/returns',{method:'POST',body:JSON.stringify({id,data:input,metadata:preparation})});if(currentId!==id){notify('The previous return was saved.');return true;}currentId=saved.id;savedUpdatedAt=saved.updated_at;hasSaved=true;if(revision===atRevision){metadata=saved.metadata||preparation;dirty=false;if(saved.result){result=saved.result;calculatedRevision=revision;}}await checkpointWorkspace();tellNativeWorkspaceReady();notify('Return saved locally.');updateHeader();renderSummary();return true;}catch(error){notify(error.message,true);throw error;}finally{busySave=false;updateHeader();}}
async function discardOrSave(callback){if(!dirty){await callback();return;}modal('Keep your current changes?',el('p',{class:'intro'},'Save the current return before switching, or discard its unsaved changes.'),[['Discard changes',async()=>{closeDialog();await callback();},'secondary'],['Save & continue',async()=>{await saveReturn();closeDialog();await callback();},'primary']]);}
async function loadReturn(id){const saved=await api('/api/returns/'+encodeURIComponent(id));data=mergeDefaults(saved.data,schema.default_return);metadata=await window.taxRecordMetadata.normalize(data,saved.metadata,null,{draft:true});currentId=saved.id;savedUpdatedAt=saved.updated_at;result=legacyForeignAddress(saved.data)?null:(saved.result||null);calculationError='';revision++;calculatedRevision=result?revision:-1;dirty=false;hasSaved=true;synthetic=false;openRecords.clear();closeDialog();navigate('profile');if(!result)await calculate();await checkpointWorkspace();tellNativeWorkspaceReady();}
function newReturn(example=null){data=mergeDefaults(example||schema.default_return,schema.default_return);metadata=window.taxRecordMetadata.empty();ensureW2Metadata();ensureIncomeMetadata();savedUpdatedAt=null;currentId=crypto.randomUUID();result=null;calculationError='';revision++;calculatedRevision=-1;dirty=false;hasSaved=false;synthetic=!!example;openRecords.clear();closeDialog();navigate('profile');calculate();checkpointWorkspace().then(tellNativeWorkspaceReady).catch(()=>{});}
function normalizedDemos(){const raw=schema.demos||[];if(Array.isArray(raw))return raw.map((item,index)=>({name:item.name||'Synthetic example '+(index+1),data:item.data||item.input||item.return||item}));return Object.entries(raw).map(([name,item])=>({name,data:item.data||item.input||item}));}
async function showReturns(){try{const listing=await api('/api/returns'),holder=el('div');holder.append(el('div',{class:'inline-actions'},button('+ New return',()=>discardOrSave(()=>newReturn()),'primary'),button('Synthetic examples',()=>showDemos(),'secondary'),button('Restore JSON backup',()=>showRestoreBackup(),'secondary')));const returns=listing.returns||[];if(!returns.length)holder.append(el('div',{class:'empty-state',style:'margin-top:20px'},'No saved returns yet. Start a return, enter your information and choose Save.'));for(const item of returns){holder.append(el('div',{class:'return-card'},el('div',{},el('strong',{},item.name||'Untitled return'),el('small',{},'Updated '+new Date(item.updated_at).toLocaleString()),item.summary?el('small',{},'Federal '+(item.summary.amount_owed>0?'owed '+dollars(item.summary.amount_owed):'refund estimate '+dollars(item.summary.refund))):null),el('div',{class:'inline-actions'},button('Open',()=>discardOrSave(()=>loadReturn(item.id)),'secondary',{class:'button secondary small'}),button('Delete',()=>confirmDelete(item),'danger',{class:'button danger small'}))));}modal('My local returns',holder);}catch(error){notify(error.message,true);}}
const BACKUP_STATES=new Set('il va ca ny pa nj oh nc ga md mo wi mn sc al or ok ct ks ar nm ne id wv me hi ri mt de nd vt'.split(' '));
function parseReturnBackup(text){
 let backup;try{backup=JSON.parse(text);}catch{throw Error('This file is not valid JSON. Choose a Tax Reborn JSON return backup.');}
 if(!backup||Array.isArray(backup)||typeof backup!=='object'||backup.format!=='tax-reborn-return-v1')throw Error('Choose a tax-reborn-return-v1 JSON backup exported by Tax Reborn.');
 if(!backup.data||Array.isArray(backup.data)||typeof backup.data!=='object')throw Error('The backup must contain a federal return data object.');
 if(backup.data.tax_year!==2025)throw Error('This build restores only tax-year2025 return backups.');
 return backup;
}
function backupStateValidator(){
 let worker=null,sequence=0;const pending=new Map();
 function close(){if(worker)worker.terminate();worker=null;for(const request of pending.values()){clearTimeout(request.timeout);request.reject(Error('Local state validation stopped.'));}pending.clear();}
 function validate(input){
  if(!worker){worker=new Worker('state-worker.js');worker.onmessage=event=>{const request=pending.get(event.data.id);if(!request)return;pending.delete(event.data.id);clearTimeout(request.timeout);event.data.error?request.reject(Error(event.data.error)):request.resolve(event.data.result);};worker.onerror=()=>close();}
  return new Promise((resolve,reject)=>{const id=++sequence,timeout=setTimeout(()=>{pending.delete(id);reject(Error('Local state validation timed out. This state was not restored.'));close();},45000);pending.set(id,{resolve,reject,timeout});worker.postMessage({id,command:'calculate',input});});
 }
 return{validate,close};
}
async function restoreReturnBackup(backup,id,onProgress=()=>{},providedValidator=null){
 const input=backup.data;
 onProgress('Validating the federal return with the local engine…');
 const calculated=await api('/api/calculate',{method:'POST',body:JSON.stringify(input)});
 onProgress('Saving a new federal draft…');
 const saved=await api('/api/returns',{method:'POST',body:JSON.stringify({id,data:mergeDefaults(input,schema.default_return),metadata:backup.metadata})});
 const report={id:saved.id,federal_saved:true,blocking_issue_count:(saved.result?.blocking_issues||calculated.blocking_issues||[]).length,restored_states:[],failed_states:[],state_notes:[],attachments_restored:false};
 const states=Object.hasOwn(backup,'states')?backup.states:{};
 if(!states||Array.isArray(states)||typeof states!=='object'){
  report.failed_states.push({jurisdiction:'State backup section',error:'The state backup must be an object keyed by state code. No state data was restored.'});return report;
 }
 const validator=providedValidator||backupStateValidator();
 try{
  for(const[jurisdiction,state]of Object.entries(states)){
   onProgress('Validating and restoring '+jurisdiction.toUpperCase()+' state input…');
   try{
    if(!BACKUP_STATES.has(jurisdiction))throw Error('This build restores only the 31 supported full-year-resident state drafts.');
    if(!state||Array.isArray(state)||typeof state!=='object'||state.jurisdiction!==jurisdiction)throw Error('State input must be an object with a matching jurisdiction.');
    const checked=await validator.validate(state);
    await api('/api/returns/'+encodeURIComponent(saved.id)+'/states',{method:'POST',body:JSON.stringify({jurisdiction,input:state})});
    report.restored_states.push(jurisdiction);
    if((checked.incomplete||[]).length)report.state_notes.push({jurisdiction,message:'The state engine reports incomplete facts. Review the restored draft in State taxes.'});
   }catch(error){report.failed_states.push({jurisdiction,error:String(error.message||error).slice(0,1200)});}
  }
 }finally{validator.close();}
 return report;
}
function restoreReportDialog(report){
 const partial=report.failed_states.length>0,holder=el('div');
 holder.append(el('p',{class:'intro'},partial?'A new federal draft was saved, but some state inputs could not be restored. Your original saved returns and current draft were kept.':'The backup was restored as a new local draft. Your original saved returns and current draft were kept.'),el('div',{class:'note'},'A separate local draft was created.'),el('p',{},report.restored_states.length+' state drafts restored'+(report.restored_states.length?': '+report.restored_states.map(code=>code.toUpperCase()).join(', '):'.')));
 if(report.blocking_issue_count)holder.append(el('div',{class:'note warning'},'The current federal engine reports '+report.blocking_issue_count+' blocking issues. Open the restored draft and review them before relying on the calculation.'));
 if(partial)holder.append(el('h3',{},'State inputs not restored'),el('ul',{class:'issue-list'},report.failed_states.map(item=>el('li',{},item.jurisdiction.toUpperCase()+': '+item.error))));
 for(const item of report.state_notes)holder.append(el('div',{class:'note warning'},item.jurisdiction.toUpperCase()+': '+item.message));
 holder.append(el('div',{class:'note warning'},'Source photos and PDF attachments are not included in the JSON return backup. Add those local documents separately. No return was filed.'));
 modal(partial?'Backup partially restored':'Backup restored as a new draft',holder,[['Open restored return',()=>discardOrSave(()=>loadReturn(report.id)),'primary'],['My returns',()=>showReturns(),'secondary']]);
}
function showRestoreBackup(){
 const holder=el('div'),file=el('input',{type:'file',accept:'.json,application/json','aria-label':'Choose Tax Reborn JSON backup'}),preview=el('div'),progress=el('div',{class:'note','aria-live':'polite',hidden:true});let backup=null,newId=null;
 holder.append(el('p',{class:'intro'},'Restore a tax-year2025 Tax Reborn JSON backup into a new return. Federal data and each supported state draft are validated locally before saving. This does not overwrite the backup’s old ID or any existing return.'),file,preview,progress,el('div',{class:'note warning'},'JSON backups do not include the original photo/PDF attachments. Current unsaved work remains open while restoration runs.'));
 const dialog=modal('Restore JSON backup',holder,[['Restore as a new return',async()=>{
  if(!backup)throw Error('Choose a valid JSON return backup first.');
  if(!newId)newId=crypto.randomUUID();progress.hidden=false;
  try{const report=await restoreReturnBackup(backup,newId,text=>progress.textContent=text);restoreReportDialog(report);}catch(error){progress.textContent='The federal restore could not be confirmed. Original returns and the current draft were kept. Retry uses the same new-copy ID.';throw error;}
 },'primary']]);
 file.addEventListener('change',async()=>{
  try{const selected=file.files[0];if(!selected)return;if(selected.size>10*1024*1024)throw Error('Choose a JSON backup smaller than 10 MB.');
   backup=parseReturnBackup(await selected.text());newId=null;progress.hidden=true;dialog.error.textContent='';
   const stateCount=backup.states&&typeof backup.states==='object'&&!Array.isArray(backup.states)?Object.keys(backup.states).length:0;
   preview.replaceChildren(el('div',{class:'section-card'},el('strong',{},typeof backup.data.name==='string'?backup.data.name:'Federal return backup'),el('p',{},'Tax year2025 · '+stateCount+' state input copies in this backup.'),el('small',{},'Saved calculation results are ignored. Current rules recalculate the restored input.')));
  }catch(error){backup=null;newId=null;preview.replaceChildren();dialog.error.textContent=error.message;}
 });
}
function showDemos(){const list=el('div',{},el('div',{class:'note warning'},'Every example is synthetic. It loads into a separate unsaved return and never overwrites your existing return.'));for(const demo of normalizedDemos())list.append(el('div',{class:'return-card'},el('div',{},el('strong',{},demo.name),el('small',{},'Synthetic 2025 federal example')),button(demo.name==='Synthetic EIC birthday boundary'?'Open birthday example':demo.name==='Synthetic parent and child income'?'Open child income example':demo.name==='Synthetic 1099-DIV special AMT'?'Open AMT example':demo.name==='Synthetic 1099-DIV special distributions'?'Open distribution example':'Open example',()=>discardOrSave(()=>newReturn(demo.data)),'secondary',{class:'button secondary small'})));modal('Synthetic examples',list);}
function confirmDelete(item){modal('Delete this local return?',el('p',{class:'intro'},'Delete “'+(item.name||'Untitled return')+'” and its attachments stored in this browser. Export a backup first if you want to keep it.'),[['Delete return',async()=>{await api('/api/returns/'+encodeURIComponent(item.id),{method:'DELETE'});await deleteDocumentsForReturn(item.id).catch(()=>{});if(currentId===item.id)newReturn();await showReturns();notify('Return deleted.');},'danger']]);}
function bytesToBase64(bytes){let binary='';const size=16384;for(let start=0;start<bytes.length;start+=size)binary+=String.fromCharCode(...bytes.subarray(start,start+size));return btoa(binary);}
async function downloadBlob(blob,name){
 if(new URLSearchParams(location.search).get('desktop')==='1'||window.TaxRebornIOS?.saveFile||window.TaxRebornAndroid?.saveFile){const saved=await window.taxNativeSaveFile(blob,name);if(saved.cancelled){notify('Save canceled. Your local draft is kept.');return false;}notify(saved.saved?'Local file saved.':'Choose where to save this local file.');return true;}
 const url=URL.createObjectURL(blob),link=el('a',{href:url,download:name});document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);return true;
}
async function exportReturn(kind){try{if(dirty||!hasSaved)await saveReturn();const response=await rawApi('/api/returns/'+encodeURIComponent(currentId)+'/'+kind),blob=await response.blob(),name='tax-reborn-2025-'+currentId.slice(0,8)+'-'+kind.replaceAll('/','-');await downloadBlob(blob,name);if(new URLSearchParams(location.search).get('desktop')!=='1'&&!window.TaxRebornAndroid?.saveFile&&!window.TaxRebornIOS?.saveFile)notify('Draft export downloaded. No tax return was filed.');}catch(error){notify(error.message,true);}}

function openDocumentDB(){return new Promise((resolve,reject)=>{if(!window.indexedDB){reject(Error('Local document storage is unavailable in this browser.'));return;}const request=indexedDB.open('tax-reborn-local-documents',2);request.onupgradeneeded=()=>{if(!request.result.objectStoreNames.contains('documents'))request.result.createObjectStore('documents',{keyPath:'id'}).createIndex('returnId','returnId');if(!request.result.objectStoreNames.contains('workspace'))request.result.createObjectStore('workspace',{keyPath:'id'});};request.onerror=()=>reject(request.error);request.onsuccess=()=>resolve(request.result);});}
async function documentOperation(mode,operation,storeName='documents'){const database=await openDocumentDB();return new Promise((resolve,reject)=>{const transaction=database.transaction(storeName,mode),store=transaction.objectStore(storeName);let value;try{const request=operation(store);if(request){request.onsuccess=()=>value=request.result;request.onerror=()=>reject(request.error);}}catch(error){database.close();reject(error);return;}transaction.oncomplete=()=>{database.close();resolve(value);};transaction.onerror=transaction.onabort=()=>{database.close();reject(transaction.error||Error('The local storage transaction was interrupted.'));};});}
const documentsForReturn=id=>documentOperation('readonly',store=>store.index('returnId').getAll(id));
async function deleteDocumentsForReturn(id){const rows=await documentsForReturn(id);await documentOperation('readwrite',store=>{for(const row of rows)store.delete(row.id);});}
async function reviewExtractedW2(row,returnId){
 if(typeof window.extractTaxDocument!=='function')throw Error('Local document extraction is not available in this build. You can enter the W-2 manually.');
 const atRevision=revision,source={document_id:row.id,return_id:returnId,name:String(row.name||'W-2 document').replace(/[\u0000-\u001f\u007f]/g,'').slice(0,256),method:'ocr'};
 window.taxRecordMetadata.assertNewSource(metadata.w2_records,source,'W-2');
 notify('Reading this document locally…');
 const extracted=await window.extractTaxDocument(row.file);
 if(currentId!==returnId||revision!==atRevision)throw Error('This return changed while extracting. Reopen its document before importing.');
 const candidates=extracted.candidates||{},draft=clone(rowTemplate('w2')||recordDefinitions.w2.template),inputs={},holder=el('div');
 holder.append(el('p',{class:'intro'},'Review each candidate against the original W-2. Extraction can misread boxes or digits. Adding this record will not overwrite an existing W-2.'),
  el('div',{class:'note warning'},extracted.form_type==='w2'?'W-2 candidate · verify tax year 2025 and every amount.':'The document was not confidently identified as a W-2. Only add it if you have verified that it is a 2025 W-2.'),
  ...(extracted.warnings||[]).map(warning=>el('div',{class:'note warning'},warning)));
 const inputGrid=grid();
 for(const[name,label,type]of recordDefinitions.w2.fields){
  if(!Object.hasOwn(draft,name))continue;
  const candidate=candidates[name],value=candidate&&typeof candidate==='object'?(candidate.value??candidate.amount??''):(candidate??(type==='owner'?'taxpayer':type==='text'?'':'0'));
  let input;
  if(type==='owner'){input=el('select',{'aria-label':label},...ownerChoices.map(([key,text])=>el('option',{value:key},text)));input.value=String(value);}
  else input=el('input',{type:'text',inputmode:type==='text'?null:'decimal',class:type==='text'?'':'money',value:String(value),'aria-label':label});
  inputs[name]=input;
  const source=candidate&&typeof candidate==='object'?(candidate.source_excerpt??candidate.source??''):(extracted.sources?.[name]||'');
  inputGrid.append(el('div',{class:'field'},el('label',{},label),type==='text'||type==='owner'?input:el('div',{class:'money-wrap'},el('span',{'aria-hidden':'true'},'$'),input),source?el('small',{},String(source)):null));
 }
 holder.append(inputGrid);
 if(extracted.text)holder.append(el('details',{class:'details-toggle'},el('summary',{},'Show extracted source text'),el('pre',{class:'document-source'},String(extracted.text).slice(0,6000))));
 const reviewed=el('input',{type:'checkbox'});
 holder.append(el('label',{class:'check-field'},reviewed,el('span',{},'I verified this is a 2025 W-2 and checked each imported amount against the document.')));
 let committing=false;
 modal('Review W-2 candidates',holder,[['Add reviewed W-2',async()=>{
  if(committing)return;committing=true;
  try{
  if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during review. Reopen its document before importing.');
  if(!reviewed.checked)throw Error('Review the document and confirm the imported amounts first.');
  for(const[name,input]of Object.entries(inputs)){
   if(MONEY_KEYS.has(name)){decimalCents(input.value);draft[name]=String(input.value).trim()||'0';}else draft[name]=input.value;
  }
  if(!draft.employer.trim())throw Error('Enter the employer name from the W-2.');
  const preparation=window.taxRecordMetadata.newRecord(source);
  const fingerprint=await window.taxRecordMetadata.fingerprint(draft);
  if(currentId!==returnId||revision!==atRevision||!holder.isConnected)throw Error('This return or review window changed. No income record was added.');
  preparation.reviewed=true;preparation.reviewed_at=new Date().toISOString();preparation.reviewed_fingerprint=fingerprint;preparation.row_fingerprint=fingerprint;
  ensureW2Metadata();window.taxRecordMetadata.assertNewSource(metadata.w2_records,source,'W-2');data.eligibility.all_income_reported=false;data.w2.push(draft);metadata.w2_records.push(preparation);openRecords.add('w2:'+preparation.record_id);changed();closeDialog();navigate('w2');notify('Reviewed W-2 added. Review income completeness and save to keep this return.');
  }finally{committing=false;}
 },'primary']]);
}
async function showTaxMLImport(){
 if(!hasSaved)await saveReturn();
 const id=currentId,openedRevision=revision,holder=el('div');
 const source=el('input',{type:'file',accept:'.xml,.tax,.tax2025,.taxbin,.bin,.zip,application/xml,text/xml,application/zip,application/octet-stream','aria-label':'Choose plaintext TaxML or .tax container'});
 const profile=el('input',{type:'file',accept:'.json,application/json','aria-label':'Choose explicit TaxML wire profile'});
 const carriers=el('input',{type:'file',multiple:true,accept:'.xprf,application/octet-stream','aria-label':'Choose caller-owned XPRF registries'});
 const container=el('select',{'aria-label':'TaxML container declaration'},el('option',{value:''},'Choose the known file format'),el('option',{value:'plaintext_xml'},'Plaintext TaxML XML'),el('option',{value:'declared_plaintext_zip'},'Plaintext ZIP — extract corrected XML'),el('option',{value:'cleartext_persistence_container'},'Cleartext container — preserve complete archive'),el('option',{value:'binary_entity'},'Binary tax data — supported profile'));
 const acknowledged=el('input',{type:'checkbox','aria-label':'Acknowledge the selected unverified wire profile'});
 holder.append(el('p',{class:'intro'},'Open local TaxML or supported binary tax data with your own registry files and an explicit profile. Review W-2, 1099-INT and 1099-DIV amounts before adding them. Binary corrections retain supported child forms, table records, links and unedited fields. Protected and unsupported files are refused.'),
  el('div',{class:'note warning'},'The selected wire profile is supplied by you. Original TurboTax loading and calculation are unverified. Unknown fields and source facts block adding a candidate.'),
  el('div',{class:'field'},el('label',{},'Source TaxML / binary tax data'),source),
  el('div',{class:'field'},el('label',{},'Known file format'),container),
  el('div',{class:'field'},el('label',{},'Explicit root / namespace / template profile'),profile),
  el('div',{class:'field'},el('label',{},'Your XPRF registry files'),carriers),
  el('label',{class:'check-field'},acknowledged,el('span',{},'I selected this wire profile and understand that compatibility with the original program is unverified.')),
  el('details',{},el('summary',{},'Try independently generated binary samples'),el('p',{},'Fictional source data for testing this complete local workflow. These are not original TurboTax files.'),el('div',{class:'inline-actions'},button('Load binary income sample',()=>loadBinarySample('income',id,openedRevision),'secondary'),button('Load nested binary sample',()=>loadBinarySample('nested',id,openedRevision),'secondary'),button('Load filing-status sample',()=>loadBinarySample('filing-status',id,openedRevision),'secondary'),button('Load income sample with two registries',()=>loadBinarySample('merged',id,openedRevision),'secondary'),button('Load nested sample with two registries',()=>loadBinarySample('merged-nested',id,openedRevision),'secondary'),button('Load source with indexed table values',()=>loadBinarySample('value-table',id,openedRevision),'secondary'),button('Load complete saved-form sample',()=>loadBinarySample('derived-income',id,openedRevision),'secondary'),button('Load saved-form array sample',()=>loadBinarySample('derived-array',id,openedRevision),'secondary'),button('Load preserved-object sample',()=>loadBinarySample('derived-opaque',id,openedRevision),'secondary'),button('Load automatic table sample',()=>loadBinarySample('auto-array-income',id,openedRevision),'secondary'),button('Load saved value-note sample',()=>loadBinarySample('typed-value-income',id,openedRevision),'secondary'),button('Load whole-number sample',()=>loadBinarySample('whole-number-income',id,openedRevision),'secondary'),button('Load saved document objects',()=>loadBinarySample('persistent-document-income',id,openedRevision),'secondary'),button('Load plaintext container sample',()=>loadClearContainerSample(id,openedRevision),'secondary'),button('Load Mac monetary container sample',()=>loadClearContainerSample(id,openedRevision,true),'secondary'),button('Load Mac decimal source sample',()=>loadClearContainerSample(id,openedRevision,true,true),'secondary'))));
 const dialog=modal('Inspect local TaxML',holder,[['Inspect locally',async()=>{
  if(currentId!==id||revision!==openedRevision)throw Error('This return changed. Reopen the import before inspecting.');
  if(!container.value)throw Error('Declare the known file format explicitly. Unknown or encrypted files cannot be imported.');
  const file=source.files[0],profileFile=profile.files[0],registryFiles=[...carriers.files];
  const inspected=await window.taxMLImport.inspect(file,profileFile,registryFiles,container.value,acknowledged.checked);
  if(currentId!==id||revision!==openedRevision||!dialog.body.isConnected)throw Error('This return or import window changed. No income record was added.');
  const row={id:crypto.randomUUID(),returnId:id,file,name:file.name,type:file.type||'application/octet-stream',size:file.size,created:new Date().toISOString(),binding_files:{profile:profileFile,carriers:registryFiles,container:container.value}};
  await documentOperation('readwrite',store=>store.put(row));
  if(currentId!==id||revision!==openedRevision)throw Error('This return changed. The original source remains attached, but no income record was added.');
  showTaxMLCandidates(row,inspected,id,openedRevision);
 },'primary']]);
}
async function loadBinarySample(name,id,atRevision){
 if(currentId!==id||revision!==atRevision)throw Error('This return changed. Reopen the import.');
 const response=await fetch('samples/binary-tax/'+name+'-request.json');if(!response.ok)throw Error('This binary sample is missing from the installed package.');
 const request=await response.json(),decode=value=>Uint8Array.from(atob(value),c=>c.charCodeAt(0));
 const file=new File([decode(request.base64)],'synthetic-'+name+'.taxbin',{type:'application/octet-stream'}),profile=new File([JSON.stringify(request.profile)],'synthetic-'+name+'-profile.json',{type:'application/json'}),carriers=request.carriers.map((item,i)=>new File([decode(item.base64)],'synthetic-registry-'+i+'.xprf'));
 const inspected=await window.taxMLImport.inspect(file,profile,carriers,'binary_entity',true);
 if(currentId!==id||revision!==atRevision)throw Error('This return changed while opening the sample.');
 const row={id:crypto.randomUUID(),returnId:id,file,name:file.name,type:file.type,size:file.size,created:new Date().toISOString(),binding_files:{profile,carriers,container:'binary_entity'}};
 await documentOperation('readwrite',store=>store.put(row));
 if(currentId!==id||revision!==atRevision)throw Error('This return changed. The sample is attached; no income was added.');
 showTaxMLCandidates(row,inspected,id,atRevision);
}
async function loadClearContainerSample(id,atRevision,mac=false,scalar=false){
 if(currentId!==id||revision!==atRevision)throw Error('This return changed. Reopen the import.');
 const response=await fetch(scalar?'samples/mac-scalar-request.json':mac?'samples/mac-taxml-request.json':'samples/plaintext-container-request.json');if(!response.ok)throw Error('The cleartext sample is missing from the installed package.');
 const request=await response.json(),decode=value=>Uint8Array.from(atob(value),c=>c.charCodeAt(0));
 const file=new File([decode(request.base64)],scalar?'synthetic-Mac-decimal-container.zip':mac?'synthetic-Mac-monetary-container.zip':'synthetic-cleartext-container.zip',{type:'application/zip'}),profile=new File([JSON.stringify(request.profile)],'synthetic-container-profile.json',{type:'application/json'}),carriers=request.carriers.map((item,i)=>new File([decode(item.base64)],'synthetic-container-registry-'+i+'.xprf'));
 const inspected=await window.taxMLImport.inspect(file,profile,carriers,'cleartext_persistence_container',true);
 if(currentId!==id||revision!==atRevision)throw Error('This return changed while opening the source.');
 const row={id:crypto.randomUUID(),returnId:id,file,name:file.name,type:file.type,size:file.size,created:new Date().toISOString(),binding_files:{profile,carriers,container:'cleartext_persistence_container'}};
 await documentOperation('readwrite',store=>store.put(row));
 if(currentId!==id||revision!==atRevision)throw Error('This return changed. The source remains attached; no income was added.');
 showTaxMLCandidates(row,inspected,id,atRevision);
}
function showTaxMLCandidates(row,inspected,returnId,atRevision,completed=new Set()){
 const holder=el('div',{},el('p',{class:'intro'},'Review each supported income form or filing-status setup separately. The original source stays attached; every change needs your confirmation.'),
  ...(inspected.warnings||[]).map(warning=>el('div',{class:'note warning'},warning)),
  el('small',{},'Source SHA-256 · '+inspected.source_sha256));
 if(inspected.container_report){
  const report=inspected.container_report;
  holder.append(el('div',{class:'note'},el('strong',{},'Complete cleartext container'),el('p',{},report.members+' ZIP members · '+report.documents.length+' stored documents · '+report.unreferenced_members+' extra members. Corrections preserve the original manifest and every unselected local record.'),el('p',{},'Selected TaxML: '+report.selected_taxml_member),el('p',{},'Encrypted original files are unsupported. Other stored documents are preserved without treating them as active tax data.')));
 }
 if(inspected.registry_binding){
  const binding=inspected.registry_binding;
  holder.append(el('p',{},'The profile fixes the order of '+binding.registry_order.length+' registry files. Visible and hidden field definitions are selected separately.'),
   el('details',{},el('summary',{},'Selected registry sources'),
    ...binding.selected_templates.map(template=>{
     const origins=new Map(template.fields.map(field=>{
      const description=(field.hidden?'Hidden':'Visible')+' fields · '+field.source_carrier_sha256.slice(0,12)+' · resource '+field.source_resource_id;
      return [description,description];
     }));
     return el('div',{class:'note'},el('strong',{},template.form_id+' · metadata selection version '+template.selection_version),el('ul',{},[...origins.values()].map(text=>el('li',{},text))));
    })));
 }
 if(inspected.registry_binding?.selected_array_templates){
  const templates=inspected.registry_binding.selected_array_templates;
  const total=templates.reduce((n,t)=>n+t.blocks.reduce((m,b)=>m+b.records.length,0),0);
  holder.append(el('details',{},el('summary',{},'Automatic table definitions · '+total),
   el('p',{},'These definitions came from the same attached files as the fields. Each part keeps its own source. No table rows were created.'),
   ...templates.map(template=>el('div',{class:'note'},el('strong',{},template.form_id),
    ...template.blocks.map(block=>el('div',{},el('p',{},(block.attribute_type===2000?'Visible':'Hidden')+' definitions · '+block.records.length+(block.present?' · '+block.carrier_sha256.slice(0,12)+' · resource '+block.resource_id:' · absent in complete source files')),
     el('ul',{},block.records.map(record=>el('li',{},'Current fields '+record.first_field+'–'+record.last_field+' · element limit '+record.element_limit+' · saved flags '+record.flags+'/'+record.byte27,
      el('code',{class:'binary-raw-id'},record.identifier_hex))))))))));
 }
 if(inspected.unresolved_facts?.length)holder.append(el('div',{class:'note warning'},'Income additions are blocked by '+inspected.unresolved_facts.length+' unresolved source facts. Filing-status setup is checked separately.'),el('details',{},el('summary',{},'Show unresolved source facts'),el('ul',{},inspected.unresolved_facts.map(item=>el('li',{},item.path+' · '+item.code+(item.detail?' · '+item.detail:''))))));
 if(!inspected.candidates?.length)holder.append(el('div',{class:'empty-state'},'No supported W-2, 1099-INT or 1099-DIV candidates were found. The source was not imported as a return.'));
 for(const candidate of inspected.candidates||[]){
  const interest=candidate.record_type==='interest',dividend=candidate.record_type==='dividends',label=dividend?'1099-DIV':interest?'1099-INT':'W-2',caption=interest||dividend?(candidate.payer||'Payer name requires review'):(candidate.employer||'Employer name requires review');
  const added=completed.has(candidate.receipt.candidate_sha256),onAdded=(inspected.candidates.length>1)?()=>{completed.add(candidate.receipt.candidate_sha256);showTaxMLCandidates(row,inspected,returnId,revision,completed);}:null;
  holder.append(el('div',{class:'return-card'},el('div',{},el('strong',{},caption),el('small',{},label+' source form '+candidate.receipt.form_path+' · '+(added?'Added in this review':candidate.can_review?'Candidate needs explicit review':'Adding blocked; source correction may be available')),...(candidate.source_owner?[el('small',{},'Stored entity '+candidate.source_owner.entity_uuid+' · copy '+candidate.source_owner.copyNum+' · file copy '+candidate.source_owner.fileCopyNum)]:[])),button('Review '+label+' candidate',()=>dividend?reviewTaxMLDividend(row,candidate,returnId,atRevision,onAdded):interest?reviewTaxMLInterest(row,candidate,returnId,atRevision,onAdded):reviewTaxMLW2(row,candidate,returnId,atRevision,onAdded),'secondary',{class:'button secondary small',disabled:added||!(candidate.can_review||candidate.can_edit_source)})));
 }
 for(const candidate of inspected.setup_candidates||[]){
  holder.append(el('div',{class:'return-card'},el('div',{},el('strong',{},'Filing-status source setup'),el('small',{},'Form '+candidate.receipt.form_path+' · '+(candidate.can_review?'Review the five source checkboxes':'Source selection is unresolved'))),button('Review filing-status setup',()=>reviewBinaryFilingStatus(row,candidate,returnId,atRevision),'secondary',{class:'button secondary small'})));
 }
 if(inspected.scalar_fields?.length)holder.append(button('Inspect / edit decimal fields',()=>showMacDecimalFields(row,inspected,returnId,atRevision),'secondary'));
 if(inspected.binary_archive)holder.append(button('Inspect / edit binary fields',()=>showBinaryFields(row,inspected,returnId,atRevision),'secondary'),button('Compare local source calculation',()=>showSourceCalculation(inspected,returnId),'secondary'),button('Compare source interest L4 / L8A',()=>showRawInterestCalculation(inspected,returnId),'secondary'));
 modal('TaxML inspection results',holder,[['Download original source',()=>downloadBlob(row.file,row.name),'secondary']]);
}
function showMacDecimalFields(source,inspected,returnId,atRevision){
 const fields=inspected.scalar_fields,holder=el('div'),detail=el('div');
 const select=el('select',{'aria-label':'Decimal source field'},...fields.map((field,index)=>el('option',{value:String(index)},field.field_id+' · '+field.form_id+' #'+field.file_copy+' · entity '+field.entity_uuid.slice(0,8))));
 const input=el('input',{type:'text',inputmode:'decimal','aria-label':'Decimal source value'});
 const confirmed=el('input',{type:'checkbox','aria-label':'Confirm decimal source correction'});
 function render(){const field=fields[Number(select.value)];input.value=field.text;input.disabled=!field.can_edit_source;confirmed.checked=false;
  detail.replaceChildren(el('p',{},'Stored value '+field.text+' · decimal coefficient '+field.coefficient+' · one fractional digit'),el('small',{},'Entity '+field.entity_uuid+' · file copy '+field.file_copy+' · field '+field.field_id),el('p',{},field.can_edit_source?'One existing field can be corrected in a separate source copy.':'Read only. The source profile or stored flags do not authorize editing.'));}
 select.addEventListener('change',render);input.addEventListener('input',()=>{confirmed.checked=false;});render();
 holder.append(el('p',{class:'intro'},'These source fields store decimal coefficients with one fractional digit. They are not money and are not added to your income or tax calculation.'),select,detail,el('div',{class:'field'},el('label',{},'Decimal source value'),input),el('label',{class:'check-field'},confirmed,el('span',{},'I checked this source correction. The original program and derived values have not been recalculated.')));
 modal('Decimal source fields',holder,[['Download corrected container',async()=>{
  if(currentId!==returnId||revision!==atRevision)throw Error('This return changed. Reopen the source.');
  const field=fields[Number(select.value)];if(input.value===field.text)throw Error('Change the selected decimal value first.');
  const output=await window.taxMLImport.correctedScalar(field,input.value,confirmed.checked);
  if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during export. Reopen the source.');
  const suffix=output.export_container==='cleartext_persistence_container'?'.zip':'.xml';
  if(!await downloadBlob(new Blob([Uint8Array.from(atob(output.base64),c=>c.charCodeAt(0))],{type:output.mime}),String(source.name).replace(/\.[^.]*$/,'')+'-corrected'+suffix))return;
  notify('Corrected source checked and saved. Other fields retained; income and current return unchanged.');
 },'primary']]);
}
async function showSourceCalculation(inspected,returnId=currentId,demo=null){
 const request=demo?.source||window.taxMLImport.sourceRequest(inspected);
 if(currentId!==returnId)throw Error('Reopen the source from the intended return.');
 const container=el('div');const dialog=modal('Local source comparison',container);
 let closed=false,transport=null,widget=null;
 const cleanup=()=>{closed=true;if(activeSourceComparison===widget)activeSourceComparison=null;widget?.destroy();transport?.close();};dialogCleanup=cleanup;
 try{
  const module=await import('./source-calculation.js');if(closed)return;
  transport=module.createSourceCalculationWorker();
  widget=await module.mountSourceCalculation(container,{execute:transport.run,saveAudit:downloadBlob,
   getCurrentSource:()=>clone(request),getCurrentAppReturn:()=>{if(currentId!==returnId)throw Error('The current return changed. Reopen the comparison.');return normalizeInput(clone(data));}});
  if(closed){widget.destroy();transport.close();return;}
  activeSourceComparison=widget;
  widget.setSource(request,demo?{profileId:demo.source_profile_id,calculationCarriers:demo.calculation_carriers,reviewDefaults:demo.reviewed_context}:{});
 }catch(error){cleanup();if(container.isConnected)dialog.error.textContent=error.message;}
}
async function showRawInterestCalculation(inspected,returnId=currentId){
 const request=window.taxMLImport.sourceRequest(inspected);
 if(currentId!==returnId)throw Error('Reopen the source from the intended return.');
 const container=el('div'),dialog=modal('Source interest L4 / L8A comparison',container);
 let closed=false,transport=null,widget=null;
 const cleanup=()=>{closed=true;if(activeSourceComparison===widget)activeSourceComparison=null;widget?.destroy();transport?.close();};dialogCleanup=cleanup;
 try{
  const module=await import('./raw-interest-flow.js');if(closed)return;
  transport=module.createRawInterestWorker();
  widget=await module.mountRawInterest(container,{execute:transport.run,saveAudit:downloadBlob,getCurrentSource:()=>{if(currentId!==returnId)throw Error('The current return changed. Reopen the source comparison.');return clone(request);}});
  if(closed){widget.destroy();transport.close();return;}
  activeSourceComparison=widget;widget.setSource();
 }catch(error){cleanup();if(container.isConnected)dialog.error.textContent=error.message;}
}
function showLocalComparisonOptions(){
 modal('Choose a local calculation comparison',el('div',{},
  el('p',{class:'intro'},'Open and inspect your own binary source to compare its bounded interest L4 / L8A path. Select your complete local original calculation resources in the next step. No original resources or source examples are included.'),
  button('Open binary source for L4 / L8A comparison',showTaxMLImport,'primary'),
  el('p',{},'The existing independent wage example remains available separately.'),
  button('Try the independent wage comparison example',showSourceCalculationExample,'secondary')));
}
async function showSourceCalculationExample(){
 const returnId=currentId;
 const response=await fetch('samples/source-calculation-demo-request.json');
 if(!response.ok)throw Error('The independent comparison example is unavailable.');
 await showSourceCalculation(null,returnId,await response.json());
}
const filingStatusLabels={single:'Single',mfj:'Married filing jointly',mfs:'Married filing separately',hoh:'Head of household',qss:'Qualifying surviving spouse'};
function reviewBinaryFilingStatus(source,candidate,returnId,atRevision){
 const confirmed=el('input',{type:'checkbox','aria-label':'Confirm filing-status source and replacement'}),holder=el('div',{},el('p',{class:'intro'},'This changes only the filing status in this App and recalculates its existing tax worksheet. Check the original source and your filing eligibility. Other source forms remain separate.'),el('p',{},'Current: '+filingStatusLabels[data.filing_status]+' · Source: '+(filingStatusLabels[candidate.filing_status]||'Unresolved')),el('ul',{},candidate.fields.map(fact=>el('li',{},fact.field_id+' · '+filingStatusLabels[fact.filing_status]+' · '+fact.status))),...(candidate.problems||[]).map(text=>el('div',{class:'note warning'},text)),el('div',{class:'note warning'},'A source checkbox does not verify filing eligibility. Review ages, dependents, spouse details and all other situations. Filing-status eligibility, income completeness and paper-payment confirmations will be cleared.'),el('label',{class:'check-field'},confirmed,el('span',{},'I checked the source filing status and confirm replacing the current status.')));
 let committing=false;
 modal('Review filing-status setup',holder,[['Apply reviewed filing status',async()=>{
  if(committing)return;committing=true;
  try{
   if(currentId!==returnId||revision!==atRevision)throw Error('This return changed. Reopen the source before applying setup.');
   const event=await window.taxMLImport.reviewedFilingStatus(candidate,{document_id:source.id,return_id:returnId,name:source.name},data.filing_status,confirmed.checked);
   const next=clone(data),nextMetadata=clone(metadata);next.filing_status=event.filing_status;next.eligibility.all_income_reported=false;next.eligibility.filing_status_confirmed=false;next.eligibility.hoh_eligible=false;next.eligibility.qss_eligible=false;
   if(next.filing_details)next.filing_details.paper_payment_confirmed=false;
   nextMetadata.setup_import_events=window.taxRecordMetadata.normalizeSetupEvents([...(nextMetadata.setup_import_events||[]),event],nextMetadata.setup_import_events||[]);
   const checked=await window.taxRecordMetadata.normalize(next,nextMetadata),calculated=await api('/api/calculate',{method:'POST',body:JSON.stringify(normalizeInput(next))});
   if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during review. No setup was applied.');
   data=next;metadata=checked;changed();result=calculated;calculatedRevision=revision;closeDialog();navigate('profile');updateHeader();renderSummary();
   notify('Reviewed filing status applied and recalculated. Save to keep its source history.');
  }finally{committing=false;}
 },'primary',{disabled:!candidate.can_review}]]);
}
function savedObjectGroup(group,label){
 if(!group)return null;
 return el('details',{},el('summary',{},'Saved '+label+' objects · '+group.objects.length),
  el('p',{},'Read only. These stored objects are preserved and checked after export. They do not supply active metadata or run the original program.'),
  el('ul',{},group.objects.map(obj=>el('li',{},el('strong',{},obj.class_name),
   el('p',{},obj.kind==='stored_metadata'?'Stored metadata · '+obj.rows.length+' ordered rows, including repeated paths':obj.kind==='stored_identifier'?'Stored identifier · original bytes retained':'Uninterpreted saved body · movement blocked'),
   el('small',{},obj.body_bytes+' saved bytes · SHA-256'),el('code',{class:'binary-raw-id'},obj.body_sha256)))));
}
function showBinaryFields(source,inspected,returnId,atRevision){
 const forms=inspected.binary_archive.forms,changes=new Map(),holder=el('div'),details=el('div');
 const selected=el('select',{'aria-label':'Binary form'},...forms.map((form,i)=>el('option',{value:String(i)},form.path.join('/')+' · '+form.form_id+' #'+form.file_copy)));
 const confirmed=el('input',{type:'checkbox','aria-label':'Confirm binary source corrections'});
 function render(){
  const form=forms[Number(selected.value)];details.replaceChildren();if(!form)return;
  details.append(el('p',{},form.fields.length+' stored fields · '+form.tables+' table records · '+form.children+' child forms · '+form.links.length+' links'));
  for(const table of form.table_headers||[]){
   const boundary=table.table_kind==='value_table'?' · saved last-used record '+table.saved_last_used_record_index:'';
   details.append(el('div',{class:'note'},el('strong',{},'Preserved table '+table.identifier),el('p',{},table.table_kind+' · fields '+table.first_field_ordinal+'–'+table.last_field_ordinal+boundary),el('small',{},'Read only. Existing indexed values and the saved record boundary are retained. Adding, removing or reordering rows is not supported.')));
  }
  const saved=inspected.binary_archive.persistent_objects;
  if(saved){const entity=savedObjectGroup(saved.entity,'Entity');if(entity)details.append(entity);const fs=saved.formsets.find(fs=>fs.index===form.path[0]);const attrs=fs&&savedObjectGroup(fs.persistent_attributes,'FormSet '+fs.formset_id);if(attrs)details.append(attrs);}
  if(form.derived){
   details.append(el('details',{},el('summary',{},'Saved field identities · '+form.derived.fields.length),el('ul',{},form.derived.fields.map(field=>el('li',{},el('strong',{},field.field_id),el('small',{},' · saved number '+field.source_ordinal),el('code',{class:'binary-raw-id'},field.full_id_hex))))));
   for(const group of form.derived.groups)details.append(el('details',{},el('summary',{},'Preserved '+group.kind+' objects · '+group.objects.length),group.objects.length?el('ul',{},group.objects.map(obj=>el('li',{},el('strong',{},obj.class_name),el('p',{},obj.typed_form_uuid?'Saved UUID '+obj.uuid:obj.typed_value_body?.kind==='value_note'?(obj.typed_value_body.text_bytes?'Saved value note · '+obj.typed_value_body.text_bytes+' bytes':'Empty saved value note · original bytes retained'):obj.typed_value_body?.kind==='destination_reference'?'Saved destination reference · '+obj.typed_value_body.destination_formset+' · index '+obj.typed_value_body.destination_index+' · element '+obj.typed_value_body.destination_element:'Uninterpreted body retained · '+obj.body_bytes+' bytes'),el('small',{},'Body SHA-256'),el('code',{class:'binary-raw-id'},obj.body_sha256)))):el('p',{},'Empty saved group.')));
   details.append(el('small',{},'Saved field numbers and object bytes stay unchanged. Current field definitions are shown separately; the original loader and calculation engine have not run.'));
  }
  if(form.links.length)details.append(el('details',{},el('summary',{},'Preserved links'),el('ul',{},form.links.map(link=>el('li',{},link.form_id+' #'+link.file_copy+' → '+link.field_id+'['+link.element+'] · '+(link.resolved?'resolved':'descriptor retained'))))));
  for(const fact of form.fields){
   const key=JSON.stringify([form.path,fact.ordinal,fact.element]),label=(fact.field_id||'Field '+fact.ordinal)+' ['+fact.element+']';
   if(fact.editable){
    const input=el('input',{type:'text',inputmode:'decimal',value:changes.get(key)?.value??fact.text,'aria-label':'Binary '+label,onInput:event=>{confirmed.checked=false;const value=event.currentTarget.value;if(value===fact.text)changes.delete(key);else changes.set(key,{path:form.path,...(fact.address_kind==='field_id'?{field_id:fact.field_id}:{ordinal:fact.ordinal}),element:fact.element,value});}});
    details.append(el('div',{class:'field'},el('label',{},label),input,el('small',{},(fact.number_kind==='whole_number'?'Whole number · saved template range '+(fact.template_bounds.minimum??'unbounded')+' to '+(fact.template_bounds.maximum??'unbounded'):'Stored kind '+fact.kind+' · attributes '+fact.specific_attributes)+(fact.current_ordinal===undefined?'':' · saved/current field numbers '+fact.ordinal+'/'+fact.current_ordinal))));
   }else details.append(el('div',{class:'field'},el('strong',{},label),el('span',{},fact.text??fact.status),el('small',{},'Read only · stored kind '+fact.kind+' · attributes '+fact.specific_attributes+' · raw '+fact.raw64)));
  }
 }
 selected.addEventListener('change',render);render();
 holder.append(el('p',{class:'intro'},'Edit supported numeric source fields. Child forms, table records, links and all unedited parsed values are checked after the complete file is written and read again.'),el('div',{class:'note warning'},'This creates a separate corrected binary copy. It does not run the original calculation engine or update derived values. Unsupported structures stop export.'),selected,details,el('label',{class:'check-field'},confirmed,el('span',{},'I checked all source corrections and understand that derived values have not been recalculated.')));
 modal('Binary source fields',holder,[['Download corrected binary',async()=>{
  if(currentId!==returnId||revision!==atRevision)throw Error('This return changed. Reopen the source.');
  if(!changes.size)throw Error('Change at least one supported numeric value.');
  const output=await window.taxMLImport.editBinary(inspected,[...changes.values()],confirmed.checked);
  if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during export. Reopen the source.');
  if(!await downloadBlob(new Blob([Uint8Array.from(atob(output.base64),c=>c.charCodeAt(0))],{type:output.mime}),String(source.name).replace(/\.[^.]*$/,'')+'-corrected.taxbin'))return;
  notify('Corrected binary checked. Complete structure readback passed; original source retained.');
 },'primary']]);
}
function reviewTaxMLW2(source,candidate,returnId,atRevision,onAdded=null){
 const binary=candidate.source_format==='binary_entity',archive=candidate.source_format==='cleartext_persistence_container',copyLabel=binary?'Download corrected binary':archive?'Download corrected container':'Download corrected XML',copyExtension=binary?'.taxbin':archive?'.zip':'.xml';
 const holder=el('div'),inputs={};
 holder.append(el('p',{class:'intro'},'Check each amount against the original 2025 W-2. This adds a separate record and keeps existing W-2s. Source flags do not establish who owns this W-2.'),
  el('div',{class:'note warning'},'Select taxpayer or spouse. For Boxes 7 and 10, a missing source value remains blank. Enter zero only after verifying that the original W-2 is blank or zero.'));
 const fields=grid();
 for(const[name,label,type]of recordDefinitions.w2.fields){
  const value=name==='employer'?(candidate.employer||''):candidate.amounts[name]??'';let input;
  if(type==='owner')input=el('select',{'aria-label':label},el('option',{value:''},'Select the W-2 owner'),...ownerChoices.map(([key,text])=>el('option',{value:key},text)));
  else input=el('input',{type:'text',inputmode:type==='text'?null:'decimal',class:type==='text'?'':'money',value,'aria-label':label});
  inputs[name]=input;const wire=candidate.sources[name];
  fields.append(el('div',{class:'field'},el('label',{},label),type==='text'||type==='owner'?input:el('div',{class:'money-wrap'},el('span',{},'$'),input),wire?el('small',{},'Wire '+wire.field_id+' · '+wire.wire_text):name==='social_security_tips'||name==='dependent_care_benefits'?el('small',{},'Not established by this source · enter explicitly'):null));
 }
 const confirmed=el('input',{type:'checkbox','aria-label':'Confirm all TaxML W-2 amounts and ownership'});
 holder.append(fields,el('label',{class:'check-field'},confirmed,el('span',{},'I checked tax year 2025, the owner, employer and every amount against the original W-2.')),
  el('p',{class:'note'},(binary?'Download corrected binary writes supported source amounts to a separate copy, checks every parsed field and structure by reading it again, and retains the original. Derived source values are not recalculated. ':archive?'Download corrected container saves the complete cleartext ZIP, checks every member and preserves all other stored documents. Source tax totals are not recalculated. ':'Download corrected XML writes only Boxes 1–6 to a separate plaintext XML copy. Other source bytes are retained. Owner, employer, Boxes 7 and 10 are added to this App only. The original return is not recalculated.')));
 let committing=false;
 modal('Review TaxML W-2 candidate',holder,[['Add reviewed W-2',async()=>{
  if(committing)return;committing=true;
  try{
   if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during review. Reopen the import.');
   const values=Object.fromEntries(Object.entries(inputs).map(([name,input])=>[name,input.value]));
   const prepared=await window.taxMLImport.reviewedRecord(candidate,values,{document_id:source.id,return_id:returnId,name:String(source.name).replace(/[\u0000-\u001f\u007f]/g,'').slice(0,256)},confirmed.checked,rowTemplate('w2'));
   if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during review. No income record was added.');
   ensureW2Metadata();window.taxRecordMetadata.assertNewSource(metadata.w2_records,prepared.metadata.source_document,'W-2');data.eligibility.all_income_reported=false;data.w2.push(prepared.row);metadata.w2_records.push(prepared.metadata);openRecords.add('w2:'+prepared.metadata.record_id);changed();closeDialog();navigate('w2');notify('Reviewed TaxML W-2 added. Income completeness was not confirmed. Save to keep this draft.');onAdded?.();
  }finally{committing=false;}
 },'primary',{disabled:!candidate.can_review}],[copyLabel,async()=>{
  if(committing)return;committing=true;
  try{
   if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during review. Reopen the import.');
   const values=Object.fromEntries(Object.entries(inputs).map(([name,input])=>[name,input.value]));
   const corrected=await window.taxMLImport.correctedSource(candidate,values,confirmed.checked);
   if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during export. Reopen the import.');
   const bytes=Uint8Array.from(atob(corrected.base64),c=>c.charCodeAt(0));
   if(!await downloadBlob(new Blob([bytes],{type:corrected.mime}),String(source.name).replace(/\.[^.]*$/,'')+'-corrected'+copyExtension))return;
   notify(binary?'Corrected binary copy checked. Complete structure readback passed; derived source values were not recalculated.':archive?'Complete corrected container checked and saved. Other source members retained; current return unchanged.':'Corrected XML copy downloaded. Original source retained; no full-return recalculation.');
  }finally{committing=false;}
 },'secondary']]);
}
const interestTaxMLFields=[['interest_income','Box 1 · Interest income'],['treasury_interest','Box 3 · U.S. savings bonds and Treasury interest'],['tax_exempt_interest','Box 8 · Tax-exempt interest'],['federal_withholding','Box 4 · Federal income tax withheld']];
function reviewTaxMLInterest(source,candidate,returnId,atRevision,onAdded=null){
 const binary=candidate.source_format==='binary_entity',archive=candidate.source_format==='cleartext_persistence_container',copyLabel=binary?'Download corrected binary':archive?'Download corrected container':'Download corrected XML',copyExtension=binary?'.taxbin':archive?'.zip':'.xml';
 const holder=el('div'),inputs={},payer=el('input',{type:'text',value:candidate.payer||'','aria-label':'1099-INT payer name'}),fields=grid(el('div',{class:'field'},el('label',{},'Payer / bank name'),payer));
 holder.append(el('p',{class:'intro'},'Check the four amounts against your original 2025 1099-INT. Boxes 1 and 3 are added together before federal rounding; Box 8 remains tax-exempt and Box 4 is federal withholding. Existing income records are kept.'));
 for(const[name,label]of interestTaxMLFields){const input=inputs[name]=el('input',{type:'text',inputmode:'decimal',class:'money',value:candidate.amounts[name]??'','aria-label':label});fields.append(el('div',{class:'field'},el('label',{},label),el('div',{class:'money-wrap'},el('span',{},'$'),input),el('small',{},'Source '+candidate.sources[name].field_id+' · '+candidate.sources[name].wire_text)));}
 const scope=el('input',{type:'checkbox','aria-label':'Confirm supported 1099-INT situation'}),confirmed=el('input',{type:'checkbox','aria-label':'Confirm all TaxML 1099-INT amounts and household'});
 holder.append(fields,el('label',{class:'check-field'},scope,el('span',{},'I verified there is no early-withdrawal penalty, investment expense, foreign tax, private-activity bond interest, market discount, bond-premium adjustment, nominee allocation or education-related savings-bond exclusion to import.')),
  el('label',{class:'check-field'},confirmed,el('span',{},'I checked tax year 2025, this household, the payer and every amount against the original 1099-INT.')),
  el('p',{class:'note'},(binary?'Download corrected binary writes supported source amounts to a separate copy, checks every parsed field and structure by reading it again, and retains the original. Derived source values are not recalculated. ':archive?'Download corrected container saves the complete cleartext ZIP, checks every member and preserves all other stored documents. Source tax totals are not recalculated. ':'Download corrected XML writes these four amounts to a separate plaintext XML copy. The payer is entered in this App only. The original return is not recalculated. State exclusions need a separate state-workspace review.')));
 const values=()=>({...Object.fromEntries(Object.entries(inputs).map(([name,input])=>[name,input.value])),payer:payer.value,supported_scope:scope.checked});let committing=false;
 modal('Review TaxML 1099-INT candidate',holder,[['Add reviewed 1099-INT',async()=>{
  if(committing)return;committing=true;
  try{
   if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during review. Reopen the import.');
   const prepared=await window.taxMLImport.reviewedInterest(candidate,values(),{document_id:source.id,return_id:returnId,name:String(source.name).replace(/[\u0000-\u001f\u007f]/g,'').slice(0,256)},confirmed.checked);
   if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during review. No income record was added.');
   ensureIncomeMetadata();window.taxRecordMetadata.assertNewSource(metadata.income_document_records.interest,prepared.metadata.source_document,'1099-INT');data.eligibility.all_income_reported=false;data.interest.push(prepared.row);metadata.income_document_records.interest.push(prepared.metadata);openRecords.add('interest:'+prepared.metadata.record_id);changed();closeDialog();navigate('interest');notify('Reviewed TaxML 1099-INT added. Save to keep the draft and original source snapshot.');onAdded?.();
  }finally{committing=false;}
 },'primary',{disabled:!candidate.can_review}],[copyLabel,async()=>{
  if(committing)return;committing=true;
  try{
   if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during export. Reopen the import.');
   const corrected=await window.taxMLImport.correctedSource(candidate,values(),confirmed.checked);
   if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during export. Reopen the import.');
   if(!await downloadBlob(new Blob([Uint8Array.from(atob(corrected.base64),c=>c.charCodeAt(0))],{type:corrected.mime}),String(source.name).replace(/\.[^.]*$/,'')+'-corrected'+copyExtension))return;notify(binary?'Corrected 1099-INT binary checked. Structure readback passed.':archive?'Complete corrected 1099-INT container checked and saved. Other source members retained.':'Corrected 1099-INT XML downloaded. Original source retained.');
  }finally{committing=false;}
 },'secondary']]);
}
const dividendTaxMLFields=[['ordinary','Box 1a · Total ordinary dividends'],['qualified','Box 1b · Qualified dividends'],['capital_gain_distributions','Box 2a · Total capital gain distributions'],['unrecaptured_1250_gain','Box 2b · Unrecaptured section 1250 gain'],['collectibles_gain','Box 2d · Collectibles (28%) gain'],['federal_withholding','Box 4 · Federal income tax withheld']];
function reviewTaxMLDividend(source,candidate,returnId,atRevision,onAdded=null){
 const binary=candidate.source_format==='binary_entity',archive=candidate.source_format==='cleartext_persistence_container',copyLabel=binary?'Download corrected binary':archive?'Download corrected container':'Download corrected XML',copyExtension=binary?'.taxbin':archive?'.zip':'.xml';
 const holder=el('div'),inputs={},payer=el('input',{type:'text',value:candidate.payer||'','aria-label':'1099-DIV payer name'}),fields=grid(el('div',{class:'field'},el('label',{},'Payer / bank name'),payer));
 holder.append(el('p',{class:'intro'},'Check the six amounts against your original 2025 1099-DIV. Box 1b is part of Box 1a. Boxes 2b and 2d are part of Box 2a and are not added again to income. Box 4 is federal withholding. Existing income records are kept.'));
 for(const[name,label]of dividendTaxMLFields){const input=inputs[name]=el('input',{type:'text',inputmode:'decimal',class:'money',value:candidate.amounts[name]??'','aria-label':label});fields.append(el('div',{class:'field'},el('label',{},label),el('div',{class:'money-wrap'},el('span',{},'$'),input),el('small',{},'Source '+candidate.sources[name].field_id+' · '+candidate.sources[name].wire_text)));}
 const qualified=el('input',{type:'checkbox','aria-label':'Confirm qualified dividend eligibility'}),scope=el('input',{type:'checkbox','aria-label':'Confirm supported 1099-DIV situation'}),confirmed=el('input',{type:'checkbox','aria-label':'Confirm all TaxML 1099-DIV amounts and household'});
 holder.append(fields,el('label',{class:'check-field'},qualified,el('span',{},'I verified the Box 1b qualified dividends meet the holding-period and other qualified-dividend requirements, or entered an explicit zero.')),el('label',{class:'check-field'},scope,el('span',{},'I verified these six boxes cover this record: there are no QSBS exclusions, FIRPTA distributions, nondividend distributions, section 199A dividends, investment expenses, foreign taxes, liquidation distributions, exempt-interest or private-activity bond dividends, or nominee allocations to import. Boxes 2b and 2d match the original form.')),
  el('label',{class:'check-field'},confirmed,el('span',{},'I checked tax year 2025, this household, the payer and every amount against the original 1099-DIV.')),
  el('p',{class:'note'},(binary?'Download corrected binary writes supported source amounts to a separate copy, checks every parsed field and structure by reading it again, and retains the original. Derived source values are not recalculated. ':archive?'Download corrected container saves the complete cleartext ZIP, checks every member and preserves all other stored documents. Source tax totals are not recalculated. ':'Download corrected XML writes these six amounts to a separate plaintext XML copy. The payer is entered in this App only. The original return is not recalculated. Other distribution types need a separate supported workflow; this import does not establish them.')));
 const values=()=>({...Object.fromEntries(Object.entries(inputs).map(([name,input])=>[name,input.value])),payer:payer.value,supported_scope:scope.checked,qualified_eligibility:qualified.checked});let committing=false;
 modal('Review TaxML 1099-DIV candidate',holder,[['Add reviewed 1099-DIV',async()=>{
  if(committing)return;committing=true;
  try{
   if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during review. Reopen the import.');
   const prepared=await window.taxMLImport.reviewedDividend(candidate,values(),{document_id:source.id,return_id:returnId,name:String(source.name).replace(/[\u0000-\u001f\u007f]/g,'').slice(0,256)},confirmed.checked);
   if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during review. No income record was added.');
   ensureIncomeMetadata();window.taxRecordMetadata.assertNewSource(metadata.income_document_records.dividends,prepared.metadata.source_document,'1099-DIV');data.eligibility.all_income_reported=false;data.dividends.push(prepared.row);metadata.income_document_records.dividends.push(prepared.metadata);openRecords.add('dividends:'+prepared.metadata.record_id);changed();closeDialog();navigate('dividends');notify('Reviewed TaxML 1099-DIV added. Save to keep the draft and original source snapshot.');onAdded?.();
  }finally{committing=false;}
 },'primary',{disabled:!candidate.can_review}],[copyLabel,async()=>{
  if(committing)return;committing=true;
  try{
   if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during export. Reopen the import.');
   const corrected=await window.taxMLImport.correctedSource(candidate,values(),confirmed.checked);
   if(currentId!==returnId||revision!==atRevision)throw Error('This return changed during export. Reopen the import.');
   if(!await downloadBlob(new Blob([Uint8Array.from(atob(corrected.base64),c=>c.charCodeAt(0))],{type:corrected.mime}),String(source.name).replace(/\.[^.]*$/,'')+'-corrected'+copyExtension))return;notify(binary?'Corrected 1099-DIV binary checked. Structure readback passed.':archive?'Complete corrected 1099-DIV container checked and saved. Other source members retained.':'Corrected 1099-DIV XML downloaded. Original source retained.');
  }finally{committing=false;}
 },'secondary']]);
}
async function showDocuments(){
 try{if(!hasSaved)await saveReturn();}catch{return;}
 const id=currentId,holder=el('div'),files=el('input',{type:'file',accept:'image/*,application/pdf',multiple:true,'aria-label':'Attach local documents'}),camera=el('input',{type:'file',accept:'image/*',capture:'environment','aria-label':'Capture a document photo'}),list=el('div',{class:'doc-list'}),extractReady=typeof window.extractTaxDocument==='function';
 holder.append(el('p',{class:'intro'},'Photo, PDF and inspected TaxML copies stay in this browser/device. Attachments are separate from your return JSON backup.'),el('div',{class:'capture-controls'},el('label',{},'Choose files',files),el('label',{},'Camera photo',camera)),el('div',{class:'inline-actions'},button('Open TaxML / binary .tax',showTaxMLImport,'secondary',{disabled:!window.taxMLImport}),button('Try local calculation comparison',showLocalComparisonOptions,'secondary')),el('div',{class:'note'},extractReady?'Local extraction offers editable W-2 candidates. Compare the amounts with the document and confirm them before adding a record. No cloud upload is performed.':'Enter document amounts manually. Local extraction is not available in this build; no cloud upload is performed.'),list);
 modal('Your local documents',holder);
 async function refresh(){
  for(const url of documentURLs)URL.revokeObjectURL(url);documentURLs=[];
  const rows=await documentsForReturn(id);list.replaceChildren();
  if(!rows.length){list.append(el('div',{class:'empty-state'},'No local documents attached.'));return;}
  for(const row of rows){const url=URL.createObjectURL(row.file);documentURLs.push(url);
   list.append(el('div',{class:'document-card'},el('div',{class:'document-thumb'},row.type.startsWith('image/')?el('img',{src:url,alt:row.name}):row.type==='application/pdf'?'PDF':'TaxML'),el('div',{class:'document-info'},el('strong',{},row.name),el('small',{},(row.size/1024).toFixed(0)+' KB · local copy'),el('div',{class:'inline-actions'},button('Extract W-2 fields',async event=>{const target=event.currentTarget;target.disabled=true;try{await reviewExtractedW2(row,id);}finally{target.disabled=false;}},'secondary',{class:'button secondary small',disabled:!extractReady||!(/^(image\/|application\/pdf$)/.test(row.type))}),button('Download',()=>downloadBlob(row.file,row.name),'secondary',{class:'button secondary small'}),button('Remove',async()=>{await documentOperation('readwrite',store=>store.delete(row.id));await refresh();},'danger',{class:'button danger small'})))));
  }
 }
 async function attach(input){
  try{for(const file of input.files){
   if(!/^(image\/|application\/pdf$)/.test(file.type))throw Error('Choose an image or PDF document.');
   if(file.size>15*1024*1024)throw Error('Each document must be smaller than 15 MB.');
   await documentOperation('readwrite',store=>store.put({id:crypto.randomUUID(),returnId:id,file,name:file.name,type:file.type,size:file.size,created:new Date().toISOString()}));
  }input.value='';await refresh();notify('Documents saved on this device. Review extraction or enter amounts manually.');}catch(error){notify(error.message,true);}
 }
 files.addEventListener('change',()=>attach(files));camera.addEventListener('change',()=>attach(camera));try{await refresh();}catch(error){list.replaceChildren(el('div',{class:'error-page'},error.message));}
}
function showAbout(){
 modal('About Tax Reborn',el('div',{class:'about'},
  el('div',{class:'brand'},el('img',{src:'icon.svg',alt:''}),el('span',{},'Tax Reborn',el('small',{},'Project #000002 · tax year 2025'))),
  el('p',{},'Independent local tax-preparation worksheets with real calculations and persistent returns. No Intuit account is required.'),
  el('p',{},'The packaged application includes local state-tax worksheets, W-2 image OCR and readable-PDF text extraction. Review extracted candidates before adding them. State coverage and unsupported facts remain visible in the state workspace.'),
  el('p',{},'State calculations use the third-party OpenTax core, corpus and composition rules. This is an open-source integration; it is separate from the original-product workflow research.'),
  el('p',{},'The combined Tax Reborn application is licensed under GNU AGPL-3.0-only. Original independent-code MIT notices, upstream licenses and corresponding OpenTax source are retained in the source distribution. Ledger Reborn, Project #000001, remains a separate MIT project.'),
  el('p',{},'Workflow research uses official TurboTax Desktop help, public mobile demos and store references. Original runtime parity and pixel parity remain unverified. No vendor artwork is shipped.'),
  el('p',{},'The mobile web interface can be installed as a PWA where supported. Android builds use a packaged local WebView and offline engine; native iOS support has not been established.'),
  el('p',{},'This application does not electronically file, pay taxes or provide expert representation. Tax calculations and filing-packet readiness are separate checks.'),
  el('div',{class:'inline-actions'},button('Offline availability',()=>window.showOfflineReadiness(),'secondary',{disabled:typeof window.showOfflineReadiness!=='function'})),
  el('p',{},'Maintained by ',el('a',{href:'https://github.com/lxistired',target:'_blank',rel:'noopener noreferrer'},'@lxistired')),
  el('p',{},'Rule evidence: ',el('a',{href:'https://www.irs.gov/pub/irs-prior/f1040--2025.pdf',target:'_blank',rel:'noopener noreferrer'},'IRS 2025 Form 1040'))
 ));
}
$('#brand').addEventListener('click',showAbout);$('#save-button').addEventListener('click',()=>saveReturn().catch(()=>{}));$('#mobile-save').addEventListener('click',()=>saveReturn().catch(()=>{}));$('#returns-button').addEventListener('click',showReturns);$('#documents-button').addEventListener('click',showDocuments);$('#menu-toggle').addEventListener('click',()=>$('#navigator').classList.add('open'));$('#nav-close').addEventListener('click',()=>$('#navigator').classList.remove('open'));$('#back-button').addEventListener('click',()=>{const pages=steps.flatMap(item=>item.pages),index=pages.indexOf(page);if(index>0)navigate(pages[index-1]);});$('#next-button').addEventListener('click',()=>{const pages=steps.flatMap(item=>item.pages),index=pages.indexOf(page);navigate(pages[index+1]||'review');});document.addEventListener('keydown',event=>{if(event.key==='Escape'){closeDialog();$('#navigator').classList.remove('open');}if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='s'){event.preventDefault();saveReturn().catch(()=>{});}});document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')checkpointWorkspace();});window.addEventListener('beforeunload',event=>{checkpointWorkspace();if(dirty){event.preventDefault();event.returnValue='';}});window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installPrompt=event;$('#install-button').hidden=false;});$('#install-button').addEventListener('click',async()=>{if(installPrompt){await installPrompt.prompt();installPrompt=null;$('#install-button').hidden=true;}});
async function boot(){schema=await api('/api/schema');if(!schema.default_return)throw Error('The local service did not provide the input contract.');window.taxRecordMetadata.setDefaults(schema.capabilities?.row_templates?.w2||recordDefinitions.w2.template);window.taxInvestmentCorrections.setDefaults(schema.capabilities?.row_templates?.capital_gains||recordDefinitions.capital_gains.template);configureModules();if(!await restoreWorkspace())newReturn();await checkpointWorkspace();tellNativeWorkspaceReady();renderNavigation();document.querySelectorAll('[data-boot-control]').forEach(node=>{node.disabled=false;});if('serviceWorker'in navigator&&location.protocol.startsWith('http'))navigator.serviceWorker.register('service-worker.js').catch(()=>{});}
boot().catch(error=>{$('#main').replaceChildren(el('div',{class:'error-page'},el('h2',{},'The local tax service is unavailable.'),error.message,el('div',{class:'inline-actions'},button('Retry',()=>location.reload(),'primary'))));notify(error.message,true);});

window.addEventListener('tax-reborn-native-document',async event=>{
 try{
  const detail=event.detail||{},file=window.taxDecodeNativeFile(detail);if(!file)return;if(!data)throw Error('Wait for the tax workspace to finish opening.');
  if(!/^(image\/|application\/pdf$)/.test(file.type))throw Error('Choose a document photo or PDF.');if(file.size>15*1024*1024)throw Error('The local document is too large.');
  const returnId=detail.returnId||currentId;if(!isUUID(returnId))throw Error('The document did not identify its local return.');
  if(returnId===currentId&&!hasSaved)await saveReturn();else await api('/api/returns/'+encodeURIComponent(returnId));
  const documentId=isUUID(detail.documentId)?detail.documentId:crypto.randomUUID(),existing=await documentOperation('readonly',store=>store.get(documentId));
  if(existing&&existing.returnId!==returnId)throw Error('The document identifier belongs to a different local return.');
  if(!existing)await documentOperation('readwrite',store=>store.put({id:documentId,returnId,file,name:file.name,type:file.type,size:file.size,created:new Date().toISOString()}));
  if(isUUID(detail.documentId)&&window.TaxRebornAndroid?.acknowledgeDocument)window.TaxRebornAndroid.acknowledgeDocument(detail.documentId);
  if(currentId===returnId)await showDocuments();notify(currentId===returnId?'Document saved locally. Review its extracted amounts before adding them.':'Document saved to the return that opened the camera. Open that return to review it.');
 }catch(error){notify(error.message,true);}
});
