"""Independently reopen the complete public owned source and verify its audit.

This verifier never calls the diagnostic API. It checks actual D2/FV/D7/header
facts and the exact public source bytes. It is not an original-runtime oracle.
"""
from pathlib import Path
import argparse,base64,hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[1];sys.dont_write_bytecode=True;sys.path[:0]=[str(ROOT),str(ROOT/'web')]
import binary_tax
from interop.derived_form.value_hash_wire_reference import find_value
sha=lambda b:hashlib.sha256(b).hexdigest()

def verify(file):
 request=json.loads((ROOT/'fixtures/binary-tax/owned-existing-link-request.json').read_text());wire=base64.b64decode(request['base64']);assert len(wire)==713 and sha(wire)=='7cf7e9d0ea0a8be8500cd7466497e5d8d26998c1981e81db0a7af6f9b874c679'
 doc,_,bound,_,_,loaded=binary_tax._context(request);assert loaded==wire;forms=dict(binary_tax.walk_forms(doc));receiver=forms[0,0];containing=forms[0,1]
 assert receiver.header.identifier==b'OWNEDRECEIVER'and receiver.header.file_copy==101 and receiver.header.word7c==3
 assert containing.header.identifier==b'OWNEDLINKED'and containing.header.file_copy==202 and containing.header.word7c==9
 entries=[e for e in receiver.derived_tail.field_map.entries if e.identifier==b'OWNED_LINK'.ljust(32,b' ')];assert len(entries)==1 and entries[0].source_field_index==101
 binding=[b for b in bound.bindings[0,0]if b.source_field_index==101 and b.element_index==0];assert len(binding)==1 and binding[0].current_field_index==1 and binding[0].source_kind==22
 node=find_value(receiver.hash_state,101,0);assert node is not None and(node.kind_byte,node.raw,node.specific_attributes,node.flag10)==(22,9,1,0)
 assert len(containing.links)==1;link=containing.links[0];assert(link.form_id,link.file_copy,link.field_id,link.element_index)==(b'OWNEDRECEIVER',101,b'OWNED_LINK',0)
 audit=json.loads(Path(file).read_text());assert audit['source_sha256']==sha(wire)and audit['source_bytes']==713 and audit['existing_saved_links']==audit['stored_consistent_links']==1
 profile_sha=sha(json.dumps(request['profile'],sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode());assert audit['profile_sha256']==profile_sha
 assert len(request['carriers'])==1 and request['carriers'][0]['sha256']=='3257eb44b1eb0a7dde5859d9215098d880e3d841537808a83d91855a39f7bc66'
 assert audit['ordered_carrier_sha256']==[request['carriers'][0]['sha256']]
 raw=base64.b64decode(request['carriers'][0]['base64']);assert sha(raw)==request['carriers'][0]['sha256'];body=binary_tax.wire.read_xprf_resources(raw,sha(raw))[2150,1]
 assert len(body)==70 and body[:5]==b'\x01\0\x01\0\xff'and body[37]==255 and body[5:37]==b'OWNEDLINKED'.ljust(32,b' ')
 for key in('writeback_allowed','native_inventory_verified','native_FindForm_executed','native_Load_or_current_FV_verified','native_current_copyNum_verified','native_link_container_edits','native_Override_Used_sideeffects'):assert audit[key]is False,key
 assert audit['not_editability_or_tax_completeness_proof']is True;item=audit['links'][0]
 assert item['status']=='consistent_saved_kind22_link'and item['stored_consistent']is True and item['writeback_allowed']is False
 assert(item['source_field_index'],item['current_field_index'],item['stored_link_copy_number_U16'],item['source_FV_raw64'],item['source_FV_attrs'])==(101,1,9,'9',1)
 assert(item['containing_path'],item['receiving_path'],item['containing_file_copy_U32'],item['descriptor_receiving_file_copy_U32'],item['containing_stored_word7c_U16'])==('0/1','0/0',202,101,9)
 assert item['original_D7_record_sha256']==sha(link.metadata['source_wire']);context=audit.get('App_read_only_context')
 descriptor=item['descriptor2150'];assert descriptor['body_sha256']==sha(body)and descriptor['record_hex']==body[2:].hex()and descriptor['first_form_id_hex']==body[5:37].hex()and descriptor['second_id_hex_uninterpreted']==body[38:70].hex()
 assert(descriptor['current_ordinal'],descriptor['kind'],descriptor['compiled_format'],descriptor['compiled_attributes'],descriptor['RID'])==(1,22,0,132,1)
 assert(item['source_FV_header'],item['source_FV_format'],item['source_FV_flag11'])==(0,0,0)
 if context is not None:
  assert set(context)=={'opened_return_id','opened_revision','current_input_metadata_snapshot_sha256','diagnostic_writes_current_return'}
  assert re.fullmatch(r'[0-9a-f-]{36}',context['opened_return_id'])and type(context['opened_revision'])is int and context['diagnostic_writes_current_return']is False
  assert re.fullmatch(r'[0-9a-f]{64}',context['current_input_metadata_snapshot_sha256'])
 return dict(all_passed=True,independently_reopened_complete_source=True,source_bytes=713,source_sha256=sha(wire),actual_D2_FV_D7_header_facts=True,diagnostic_API_used_as_oracle=False,native_inventory_verified=False,writeback_allowed=False,audit_bytes=Path(file).stat().st_size,audit_sha256=sha(Path(file).read_bytes()))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('file',type=Path);p.add_argument('--output',type=Path);args=p.parse_args();result=verify(args.file)
 if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
