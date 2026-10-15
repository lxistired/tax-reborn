// Installed worker + real WebAssembly + the same reviewed-record contracts as UI.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const root=process.env.TAX_REBORN_RUNTIME_ROOT||path.resolve(__dirname,'..'),out=process.env.TAX_REBORN_QA_ROOT||path.join(root,'qa/binary-tax');
const {loadPyodide}=require(path.join(root,'web/vendor/pyodide/pyodide.js'));
const ctx={console,URL,URLSearchParams,TextEncoder,crypto:webcrypto,Response,Blob,File,Uint8Array,ArrayBuffer,setTimeout,clearTimeout,location:{href:'http://stage.local/',search:''},btoa:t=>Buffer.from(t,'binary').toString('base64'),atob:t=>Buffer.from(t,'base64').toString('binary')};ctx.window=ctx;vm.createContext(ctx);
for(const name of ['local-api.js','investment-corrections.js','income-preparation.js','taxml-import.js'])vm.runInContext(fs.readFileSync(path.join(root,'web',name),'utf8'),ctx,{filename:name});
const worker={console,URL,Uint8Array,TextDecoder,self:{location:{href:'http://stage.local/tax-worker.js'}},loadPyodide:()=>loadPyodide({indexURL:path.join(root,'web/vendor/pyodide/')}),fetch:async url=>{const name=new URL(url).pathname.slice(1),target=path.join(root,fs.existsSync(path.join(root,'web',name))?'web':'',name);return fs.existsSync(target)?new Response(fs.readFileSync(target)):new Response('missing',{status:404});}};
vm.createContext(worker);vm.runInContext(fs.readFileSync(path.join(root,'web/tax-worker-source.js'),'utf8'),worker);
let sequence=0;async function command(command,payload){return new Promise((resolve,reject)=>{const id=++sequence;worker.self.postMessage=m=>{if(m.id===id)m.error?reject(Error(m.error)):resolve(m.result);};worker.self.onmessage({data:{id,command,payload}});});}ctx.taxLocalEngine=command;
async function inspect(request){return ctx.taxMLImport.inspect(new File([Buffer.from(request.base64,'base64')],'synthetic.taxbin'),new File([JSON.stringify(request.profile)],'profile.json'),request.carriers.map((c,i)=>new File([Buffer.from(c.base64,'base64')],i+'.xprf')),'binary_entity',true);}
async function main(){
 fs.mkdirSync(out,{recursive:true});
 const request=JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/income-request.json'))),income=await inspect(request);
 assert.equal(income.candidates.length,3);assert(income.candidates.every(c=>c.can_review));
 const schema=await command('schema'),data=JSON.parse(JSON.stringify(schema.default_return)),metadata=ctx.taxRecordMetadata.empty();ctx.taxRecordMetadata.setDefaults(schema.capabilities.row_templates.w2);
 for(const candidate of income.candidates){
  const source={document_id:webcrypto.randomUUID(),return_id:webcrypto.randomUUID(),name:'synthetic.taxbin'};
  let prepared,collection;
  if(candidate.record_type==='w2'){collection='w2';prepared=await ctx.taxMLImport.reviewedRecord(candidate,{...candidate.amounts,owner:'taxpayer',employer:'Synthetic Binary Employer',social_security_tips:'0',dependent_care_benefits:'0'},source,true,schema.capabilities.row_templates.w2);metadata.w2_records.push(prepared.metadata);}
  else if(candidate.record_type==='interest'){collection='interest';prepared=await ctx.taxMLImport.reviewedInterest(candidate,{...candidate.amounts,payer:'Synthetic Binary Bank',supported_scope:true},source,true);metadata.income_document_records.interest.push(prepared.metadata);}
  else{collection='dividends';prepared=await ctx.taxMLImport.reviewedDividend(candidate,{...candidate.amounts,payer:'Synthetic Binary Fund',supported_scope:true,qualified_eligibility:true},source,true);metadata.income_document_records.dividends.push(prepared.metadata);}
  data[collection].push(prepared.row);assert.equal(prepared.metadata.reviewed,true);assert.equal(prepared.metadata.source_document.taxml_receipt.source_sha256,income.source_sha256);
 }
 const normalized=await ctx.taxRecordMetadata.normalize(data,metadata),calculated=await command('calculate',data);assert.equal(calculated.can_prepare,false);assert.equal(data.eligibility.all_income_reported,false);assert.equal(calculated.summary.refund,344);
 const nestedRequest=JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/nested-request.json'))),nested=await inspect(nestedRequest),forms=nested.binary_archive.forms;
 assert(forms.some(f=>f.tables>0));assert(forms.some(f=>f.children>0));assert(forms.some(f=>f.links.length>0));
 const form=forms.find(f=>f.fields.some(v=>v.editable)),field=form.fields.find(v=>v.editable),changes=[{path:form.path,ordinal:field.ordinal,element:field.element,value:'345.67'}];
 await assert.rejects(()=>ctx.taxMLImport.editBinary(nested,changes,false));await assert.rejects(()=>ctx.taxMLImport.editBinary({...nested},changes,true));
 const edited=await ctx.taxMLImport.editBinary(nested,changes,true);assert.equal(edited.changed_fields,1);assert.equal(edited.binary_roundtrip_verified,true);assert.equal(edited.all_other_parsed_facts_preserved,true);assert.equal(edited.full_return_recalculated,false);assert.equal(edited.original_program_acceptance_verified,false);
 fs.writeFileSync(path.join(out,'nested-corrected.taxbin'),Buffer.from(edited.base64,'base64'));
 const reopened=await inspect({...nestedRequest,base64:edited.base64}),a=JSON.parse(JSON.stringify(forms)),b=JSON.parse(JSON.stringify(reopened.binary_archive.forms));
 const original=a.find(f=>JSON.stringify(f.path)===JSON.stringify(form.path)).fields.find(f=>f.ordinal===field.ordinal&&f.element===field.element),updated=b.find(f=>JSON.stringify(f.path)===JSON.stringify(form.path)).fields.find(f=>f.ordinal===field.ordinal&&f.element===field.element);assert.equal(updated.text,'345.67');original.text=updated.text;original.raw64=updated.raw64;assert.deepEqual(a,b);
 const setupRequest=JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/filing-status-request.json'))),setup=await inspect(setupRequest),candidate=setup.setup_candidates[0];
 assert.equal(candidate.filing_status,'mfj');assert.equal(candidate.fields[4].status,'unused');assert.equal(candidate.fields[4].raw64,'1');assert(candidate.fields.every(field=>field.current_format===255));
 const source={document_id:webcrypto.randomUUID(),return_id:webcrypto.randomUUID(),name:'fictional-setup.taxbin'};
 await assert.rejects(()=>ctx.taxMLImport.reviewedFilingStatus(candidate,source,'single',false));await assert.rejects(()=>ctx.taxMLImport.reviewedFilingStatus({...candidate},source,'single',true));
 const setupEvent=await ctx.taxMLImport.reviewedFilingStatus(candidate,source,'single',true),setupData=JSON.parse(JSON.stringify(schema.default_return));
 setupData.w2.push({...schema.capabilities.row_templates.w2,employer:'Fictional',wages:'60000'});
 const beforeSetup=await command('calculate',setupData);setupData.filing_status=setupEvent.filing_status;
 const afterSetup=await command('calculate',setupData);assert(afterSetup.summary.total_tax<beforeSetup.summary.total_tax);assert.equal(afterSetup.can_prepare,false);
 const setupMetadata=await ctx.taxRecordMetadata.normalize(setupData,null);setupMetadata.setup_import_events=[setupEvent];
 const retained=await ctx.taxRecordMetadata.normalize(setupData,setupMetadata);assert.equal(retained.setup_import_events[0].source_document.taxml_receipt.source_sha256,setup.source_sha256);
 const legacy=JSON.parse(JSON.stringify(retained));delete legacy.setup_import_events;assert.equal((await ctx.taxRecordMetadata.normalize(setupData,legacy,retained)).setup_import_events.length,1);
 assert.throws(()=>ctx.taxRecordMetadata.normalizeSetupEvents([],retained.setup_import_events));assert.throws(()=>ctx.taxRecordMetadata.normalizeSetupEvents([setupEvent,{...setupEvent,event_id:webcrypto.randomUUID()}]));
 const mergedRequest=JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/merged-request.json')));
 // File pickers need not return files in metadata priority order. The explicit
 // v2 profile reorders verified inputs before they enter the actual worker.
 const merged=await inspect({...mergedRequest,carriers:[...mergedRequest.carriers].reverse()});
 assert.deepEqual(Array.from(merged.registry_binding.registry_order),mergedRequest.profile.registry_order);
 const w2Binding=merged.registry_binding.selected_templates.find(t=>t.form_id==='FW2'),fieldBindings=Object.fromEntries(w2Binding.fields.map(f=>[f.field_id,f]));
 assert.equal(fieldBindings.WAGES.source_carrier_sha256,mergedRequest.carriers[0].sha256);
 assert.equal(fieldBindings.FEDTAX.source_carrier_sha256,mergedRequest.carriers[1].sha256);
 assert.equal(fieldBindings.FEDTAX.ordinal,5);assert.equal(fieldBindings.FEDTAX.source_dictionary_ordinal,1);
 const mergedData=JSON.parse(JSON.stringify(schema.default_return)),mergedMetadata=ctx.taxRecordMetadata.empty();
 for(const candidate of merged.candidates){
  const source={document_id:webcrypto.randomUUID(),return_id:webcrypto.randomUUID(),name:'synthetic-merged.taxbin'};let prepared,collection;
  if(candidate.record_type==='w2'){collection='w2';prepared=await ctx.taxMLImport.reviewedRecord(candidate,{...candidate.amounts,owner:'taxpayer',employer:'Synthetic Two Registry Employer',social_security_tips:'0',dependent_care_benefits:'0'},source,true,schema.capabilities.row_templates.w2);mergedMetadata.w2_records.push(prepared.metadata);}
  else if(candidate.record_type==='interest'){collection='interest';prepared=await ctx.taxMLImport.reviewedInterest(candidate,{...candidate.amounts,payer:'Synthetic Two Registry Bank',supported_scope:true},source,true);mergedMetadata.income_document_records.interest.push(prepared.metadata);}
  else{collection='dividends';prepared=await ctx.taxMLImport.reviewedDividend(candidate,{...candidate.amounts,payer:'Synthetic Two Registry Fund',supported_scope:true,qualified_eligibility:true},source,true);mergedMetadata.income_document_records.dividends.push(prepared.metadata);}
  mergedData[collection].push(prepared.row);
 }
 const mergedCalculation=await command('calculate',mergedData);assert.equal(mergedCalculation.summary.refund,344);assert.equal(mergedCalculation.can_prepare,false);
 const mergedNormalized=await ctx.taxRecordMetadata.normalize(mergedData,mergedMetadata);
 assert.equal(mergedNormalized.w2_records[0].source_document.taxml_receipt.wire_profile_sha256,merged.wire_profile_sha256);
 fs.writeFileSync(path.join(out,'merged-reviewed-record.json'),JSON.stringify({data:mergedData,metadata:mergedNormalized},null,2)+'\n');
 const mergedNestedRequest=JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/merged-nested-request.json'))),mergedNested=await inspect(mergedNestedRequest);
 const wagesField=mergedNested.binary_archive.forms[0].fields.find(f=>f.field_id==='WAGES');
 const mergedEdit=await ctx.taxMLImport.editBinary(mergedNested,[{path:[0,0],ordinal:wagesField.ordinal,element:0,value:'1234.57'}],true);
 const mergedReread=await inspect({...mergedNestedRequest,base64:mergedEdit.base64});
 assert.equal(mergedReread.candidates[0].amounts.wages,'1234.57');assert.equal(mergedReread.binary_archive.forms.length,4);
 assert.equal(mergedReread.binary_archive.forms[0].tables,1);assert.equal(mergedReread.binary_archive.forms[0].children,1);
 assert.equal(mergedReread.binary_archive.forms.reduce((n,f)=>n+f.links.length,0),4);assert(mergedReread.binary_archive.forms.every(f=>f.links.every(l=>l.resolved)));
 fs.writeFileSync(path.join(out,'merged-nested-corrected.taxbin'),Buffer.from(mergedEdit.base64,'base64'));
 const valueTableRequest=JSON.parse(fs.readFileSync(path.join(root,'web/samples/binary-tax/value-table-request.json'))),valueTable=await inspect({...valueTableRequest,carriers:[...valueTableRequest.carriers].reverse()});
 const tableForm=valueTable.binary_archive.forms[0],savedTable=tableForm.table_headers[0],arrayValues=tableForm.fields.filter(f=>f.declared_array);
 assert.equal(savedTable.table_kind,'value_table');assert.equal(savedTable.saved_last_used_record_index,3);
 assert.equal(arrayValues.length,3);assert(arrayValues.every(f=>!f.editable));assert.equal(arrayValues.find(f=>f.element===3).raw64,'0');assert.equal(arrayValues.find(f=>f.element===4).specific_attributes,2);
 assert(valueTable.candidates.every(c=>!c.can_review));assert.equal(valueTable.unresolved_facts.length,2);
 await assert.rejects(()=>ctx.taxMLImport.editBinary(valueTable,[{path:[0,0],ordinal:12,element:1,value:'99.00'}],true));
 const scalarWages=tableForm.fields.find(f=>f.field_id==='WAGES'),tableEdit=await ctx.taxMLImport.editBinary(valueTable,[{path:[0,0],ordinal:scalarWages.ordinal,element:0,value:'1234.57'}],true);
 const tableReread=await inspect({...valueTableRequest,base64:tableEdit.base64});
 assert.equal(tableReread.candidates[0].amounts.wages,'1234.57');assert.equal(tableReread.binary_archive.forms[0].table_headers[0].saved_last_used_record_index,3);
 assert.deepEqual(JSON.parse(JSON.stringify(tableReread.binary_archive.forms[0].fields.filter(f=>f.declared_array))),JSON.parse(JSON.stringify(arrayValues)));
 assert.equal(tableReread.binary_archive.forms.length,4);assert.equal(tableReread.binary_archive.forms.reduce((n,f)=>n+f.links.length,0),4);
 assert.equal(tableEdit.all_other_parsed_facts_preserved,true);assert.equal(tableEdit.full_return_recalculated,false);
 fs.writeFileSync(path.join(out,'value-table-corrected.taxbin'),Buffer.from(tableEdit.base64,'base64'));
 const receipt={runtime_root:process.env.TAX_REBORN_RUNTIME_ROOT?'caller-selected packaged runtime':'source checkout',actual_packaged_assets:!!process.env.TAX_REBORN_RUNTIME_ROOT,real_pyodide:true,three_reviewed_binary_income_forms:true,actual_calculation:calculated.summary,unconfirmed_income_still_blocks_completion:true,normalized_source_records:normalized.w2_records.length+normalized.income_document_records.interest.length+normalized.income_document_records.dividends.length,nonempty_tables_children_links:true,whole_document_edit_readback:true,other_parsed_facts_preserved:true,filing_status_binary_review_and_recalculation:{before:beforeSetup.summary.total_tax,after:afterSetup.summary.total_tax,presence_and_current_format_retained:true,immutable_history_normalized:true},derived_value_table:{explicit_factory:true,source_boundary_retained:true,indexed_present_zero_and_unused_payload_retained:true,scalar_correction_full_readback:true,unknown_present_array_blocks_income_import:true,row_insertion_deletion_supported:false},ordered_effective_registry:{two_file_picker_order_reversed_and_profile_restored:true,visible_and_hidden_sources_independently_bound:true,three_reviewed_forms_actual_refund:mergedCalculation.summary.refund,source_metadata_normalized:true,nested_edit_full_readback:true},original_tax_fixture:false,original_engine_executed:false,whole_tax_compatibility:false};fs.writeFileSync(path.join(out,'binary-runtime-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt));
}main().catch(error=>{console.error(error);process.exitCode=1;});
