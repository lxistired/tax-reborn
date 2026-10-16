// Independently written, read-only UI. Original resource files are never bundled.
let fieldSequence=0;
const TKE_SHA='5e8db09dc9c4126c0cd85fe11ee7b02965a3b9e88db1075ba32efc4269e0bc2f';
const FIELD_SHA='cf30494976a27798da761cc12a145104a2ec4b57180cdd84ec88d23f4f2dcb31';
const canonical=value=>JSON.stringify(value,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
const clone=value=>JSON.parse(canonical(value));
const digest=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');
const base64=bytes=>{let s='';for(let i=0;i<bytes.length;i+=16384)s+=String.fromCharCode(...bytes.subarray(i,i+16384));return btoa(s);};
const decode=value=>{if(typeof value!=='string'||value.length>48*1024*1024)throw Error('A supported complete binary source is required.');return Uint8Array.from(atob(value),x=>x.charCodeAt(0));};
const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
const hasResourcePayload=value=>value&&typeof value==='object'&&Object.entries(value).some(([k,v])=>['base64','raw_bytes','carrier_bytes','resource_bytes','payload_bytes'].includes(k)||hasResourcePayload(v));
const stale=()=>Error('The source, selected files, field or current return changed. Read the files and confirm again.');

export function mountSourceMC(container,{execute,getSource,getInspection,saveReport=null,getContext=()=>null}={}){
 if(!container||typeof execute!=='function'||typeof getSource!=='function'||typeof getInspection!=='function'||typeof getContext!=='function'||saveReport!==null&&typeof saveReport!=='function')throw Error('Complete local source and Worker adapters are required.');
 let epoch=0,closed=false,busy=false,readingFiles=false,saving=false,resources=null,result=null,resultInputs=null,resultEpoch=null;
 const root=node('section');root.className='source-mc-diagnostics';const controlID=++fieldSequence;const title=node('h3','Read stored interest values');
 const note=node('p','Read one existing interest source value and its recorded status. This does not calculate final tax, save current values, or update the source. Unsupported sources are refused.');
 const fileField=node('div');fileField.className='field';const fileLabel=node('label','Choose both local interest resource files (.3pe)');const files=node('input');files.id='source-mc-files-'+controlID;fileLabel.htmlFor=files.id;files.type='file';files.multiple=true;files.accept='.3pe,application/octet-stream';files.setAttribute('aria-label','Choose both local interest resource files (.3pe)');fileField.append(fileLabel,files);
 const fieldContainer=node('div');fieldContainer.className='field';const fieldLabel=node('label','Stored interest field');const field=node('select');field.id='source-mc-field-'+controlID;fieldLabel.htmlFor=field.id;field.setAttribute('aria-label','Stored interest field');for(const [value,label]of[['L1','Interest amount (L1)'],['L3','Savings-bond interest (L3)'],['EXINT','Tax-exempt interest (EXINT)']]){const o=node('option',label);o.value=value;field.append(o);}fieldContainer.append(fieldLabel,field);
 const ackLabel=node('label');ackLabel.className='check-field';const ack=node('input');ack.type='checkbox';ackLabel.append(ack,node('span','I understand this reads stored source values only.'));
 const run=node('button','Read stored value');run.type='button';run.className='button primary';run.disabled=true;const download=node('button','Download source-value report');download.type='button';download.className='button secondary';download.disabled=true;
 const status=node('p','Select the two matching local resource files.');status.setAttribute('role','status');const error=node('p');error.className='dialog-error';error.setAttribute('role','alert');const content=node('div');
 note.className='note';const fields=node('div');fields.className='field-grid single';fields.append(fileField,fieldContainer);const actions=node('div');actions.className='inline-actions';actions.append(run,download);root.append(title,note,fields,ackLabel,actions,status,error,content);container.append(root);
 function clearResult(){result=null;resultInputs=null;resultEpoch=null;download.disabled=true;content.replaceChildren();}
 function update(){if(closed)return;run.disabled=busy||!resources;download.disabled=busy||saving||!result;files.disabled=busy;field.disabled=busy;ack.disabled=readingFiles;}
 function reset({dropFiles=false,message='Inputs changed. Confirm before reading again.'}={}){epoch++;clearResult();busy=false;readingFiles=false;if(dropFiles){resources=null;files.value='';}if(!closed){error.textContent='';status.textContent=message;update();}}
 function fail(e){if(closed)return;clearResult();error.textContent=e?.message||'The stored value could not be read.';status.textContent='No source or current return values were changed.';}
 function snapshot(){
  const source=getSource(),inspection=getInspection(),context=getContext();
  if(!source||source.container!=='binary_entity'||source.profile?.format!=='tax-reborn-binary-entity-profile-v5')throw Error('Inspect a supported complete saved source with its explicit automatic-table profile first.');
  const summaries=inspection?.binary_archive?.forms?.filter(f=>f.form_id==='FSCHB'&&Array.isArray(f.path)&&f.path.length===2&&f.path.every(x=>Number.isInteger(x)&&x>=0))||[];
  if(summaries.length!==1)throw Error('This reader requires one existing root interest summary in the inspected source.');
  const summary=summaries[0].path;
  const value={source,inspection,context,field:field.value,acknowledged:ack.checked};return {key:canonical(value),source:clone(source),summary:clone(summary),field:field.value,context:clone(context)};
 }
 function current(token,inputs){if(closed||token!==epoch)throw stale();if(snapshot().key!==inputs.key)throw stale();}
 const capturedFiles=()=>Array.from(files.files||[]);
 function sameFiles(selected){const now=capturedFiles();return now.length===selected.length&&now.every((f,i)=>f===selected[i]);}
 files.onchange=async()=>{
  if(closed)return;reset({dropFiles:false,message:'Reading and checking the selected local files… Confirmation is available when reading finishes.'});ack.checked=false;const token=epoch,selected=capturedFiles();resources=null;busy=true;readingFiles=true;update();
  try{
   const inputs=snapshot();if(selected.length!==2)throw Error('Select exactly the two matching .3pe resource files.');const found=new Map();
   for(const file of selected){if(file.size>128*1024*1024)throw Error('A local file exceeds the supported size.');const bytes=new Uint8Array(await file.arrayBuffer());current(token,inputs);if(!sameFiles(selected))throw stale();const sha=await digest(bytes);current(token,inputs);if(!sameFiles(selected))throw stale();if(![TKE_SHA,FIELD_SHA].includes(sha)||found.has(sha))throw Error('The selection must contain each matching local resource once, with no other files.');found.set(sha,{base64:base64(bytes),sha256:sha});}
   current(token,inputs);if(!sameFiles(selected)||found.size!==2)throw stale();resources={tke:found.get(TKE_SHA),fields:found.get(FIELD_SHA),selected};status.textContent='Both local files match. Choose a field and confirm the read-only scope.';
  }catch(e){if(!closed&&token===epoch){resources=null;fail(e);}}
  finally{if(!closed&&token===epoch){busy=false;readingFiles=false;update();}}
 };
 function checkResources(){if(!resources||!sameFiles(resources.selected))throw Error('Read both local resource files again.');}
 field.onchange=()=>{ack.checked=false;reset({message:resources?'Field changed. Confirm the read-only scope before reading.':'Select both matching local resource files.'});};ack.onchange=()=>reset({message:ack.checked?'Ready to read the selected stored value.':'Confirm the read-only scope before reading.'});
 run.onclick=async()=>{
  if(closed||busy)return;clearResult();error.textContent='';const token=epoch;busy=true;update();status.textContent='Reading the selected existing source value…';
  try{
   if(!ack.checked)throw Error('Confirm the read-only scope first.');checkResources();const inputs=snapshot();const source=clone(inputs.source);const wire=decode(source.base64),sourceSHA=await digest(wire);current(token,inputs);checkResources();
   if(!Array.isArray(source.carriers)||canonical(source.profile.registry_order)!==canonical(source.carriers.map(c=>c.sha256)))throw Error('The complete source registry order must match its selected files.');
   const found=source.carriers.map((c,i)=>c.sha256===FIELD_SHA?i:-1).filter(i=>i>=0);
   if(found.length){if(found.length!==1||found[0]!==source.carriers.length-1||source.carriers.at(-1).base64!==resources.fields.base64)throw Error('An existing field resource must be the unique matching last source registry.');}
   else{source.carriers.push(clone(resources.fields));source.profile.registry_order.push(FIELD_SHA);}
   const payload={source,expected_source_sha256:sourceSHA,summary_path:inputs.summary,source_formset_index:inputs.summary[0],row_number:1,field_id:inputs.field,need_native_row_uuid:false,local_resource:clone(resources.tke)};
   const profileSHA=await digest(new TextEncoder().encode(canonical(inputs.source.profile)));current(token,inputs);const effectiveSHA=await digest(new TextEncoder().encode(canonical(source.profile)));current(token,inputs);const contextSHA=await digest(new TextEncoder().encode(canonical(inputs.context)));current(token,inputs);checkResources();
   const report=await execute('source_mc_input_diagnose',payload);current(token,inputs);checkResources();
   const curr=report?.current_source,trace=curr?.current_field,owner=curr?.source_owner_proof,mc=report?.owned_current_MC_input?.value;
   if(hasResourcePayload(report))throw Error('The diagnostic returned resource payload bytes instead of a read-only value report.');
   if(report?.complete_owned_selected_current_input_projection!==true||report?.comparison_only!==true||report?.writeback_allowed!==false||report?.binary_context_calls!==1||curr?.source_sha256!==sourceSHA||trace?.field_id!==inputs.field||!Array.isArray(trace.document_path)||canonical(trace.document_path.slice(0,2))!==canonical(inputs.summary)||canonical(owner?.summary_path)!==canonical(inputs.summary)||mc?.type!=='MC'||!Array.isArray(mc.entries)||mc.entries.length!==1)throw Error('The diagnostic response does not match the selected source and field.');
   result={...clone(report),ui_context_binding:{ui_only_snapshot_binding:true,source_wire_sha256:sourceSHA,source_profile_sha256_before_metadata_extension:profileSHA,source_profile_sha256_used_for_projection:effectiveSHA,ordered_source_carrier_sha256_used:source.carriers.map(c=>c.sha256),complete_App_context_sha256:contextSHA,opened_return_id:inputs.context?.return_id??null,opened_revision:inputs.context?.revision??null,current_values_changed:false}};resultInputs=inputs;resultEpoch=token;
   const leaf=mc.entries[0].value;content.append(node('h4','Stored source value'),node('p',inputs.field+': '+(leaf.blank?'Blank':String(leaf.amount??'See report'))),node('p','Stored present: '+(trace.FV_attributes&1?'Yes':'No')+' · User override: '+(trace.FV_attributes&8?'Yes':'No')+' · Calculated: '+(trace.FV_attributes&2?'Yes':'No')),node('p','Source input check: '+((mc.Error===0||mc.Error===false)&&(leaf.Error===0||leaf.Error===false)?'No reported error.':'See the recorded issue in the report.')),node('p','The saved form identity below does not establish restored record relationships or permission to edit.'));
   const detail=node('details'),rawReport=node('pre',JSON.stringify({source_sha256:sourceSHA,source_field:trace,form_identity:report.owned_Form_UUID_initialization,owned_input:report.owned_current_MC_input},null,2));rawReport.style.whiteSpace='pre-wrap';rawReport.style.overflowWrap='anywhere';rawReport.style.fontSize='11px';detail.append(node('summary','Source identity and recorded input structure'),rawReport);content.append(detail);status.textContent='Stored value read. No source or current return values were saved.';
  }catch(e){if(!closed&&token===epoch)fail(e);}
  finally{if(!closed&&token===epoch){busy=false;update();}}
 };
 download.onclick=async()=>{
  if(closed||saving||!result)return;const report=result,inputs=resultInputs,token=resultEpoch;saving=true;update();let requested=false;
  try{current(token,inputs);checkResources();if(result!==report)throw stale();const blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json'}),name='Tax-Reborn-stored-interest-input.json';if(saveReport){requested=true;const saved=await saveReport(blob,name);current(token,inputs);checkResources();if(saved===false){status.textContent='Report save canceled. No source or current values were changed.';return;}}else{const url=URL.createObjectURL(blob),a=node('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);current(token,inputs);}status.textContent='Read-only report save requested. Source and current values remain unchanged.';}
  catch(e){if(!closed){clearResult();fail(requested&&e?.message===stale().message?Error('Inputs changed during the save request. Any file already saved describes the earlier source snapshot. Read and confirm again.'):e);}}
  finally{saving=false;update();}
 };
 return {invalidate(){if(!closed)reset({dropFiles:true,message:'Source or current return changed. Select the local files and confirm again.'});},destroy(){if(closed)return;closed=true;epoch++;resources=null;clearResult();root.remove();},getResult(){return result?clone(result):null;},inspect(){if(!closed)run.click();}};
}
