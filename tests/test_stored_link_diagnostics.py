"""Whole independently owned source diagnostics; no original resource input."""
from pathlib import Path
from dataclasses import replace
import base64,copy,json,sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web')]
import binary_tax,source_link_diagnostics
from interop.derived_form.source_bound_value_document_reference import store_document_bytes

def request():return json.loads((ROOT/'fixtures/binary-tax/owned-existing-link-request.json').read_text())
def authored_variant(*,attrs=None,raw=None,kind=None,fmt=None,duplicate=False,orphan=False):
 # Author a new negative test document. Source-scope guards are deliberately
 # removed only in this own-fixture authoring code, never in a public API.
 q=request();doc,buffers,bound,_,_,_=binary_tax._context(q);forms=list(doc.formsets[0].forms);receiver=forms[0];blocks=[]
 for block in receiver.hash_state.buffers:
  nodes=[]
  for node in block.nodes:
   changes={}
   for key,value in(('specific_attributes',attrs),('raw',raw),('kind_byte',kind),('flag10',fmt)):
    if value is not None:changes[key]=value
   nodes.append(replace(node,**changes))
  blocks.append(replace(block,nodes=tuple(nodes)))
 state=replace(receiver.hash_state,buffers=tuple(blocks))
 if orphan:state=replace(state,heads=tuple(0xffffffff for _ in state.heads))
 forms[0]=replace(receiver,hash_state=state,metadata={});forms[1]=replace(forms[1],metadata={},links=forms[1].links*2 if duplicate else forms[1].links)
 doc=replace(doc,formsets=(replace(doc.formsets[0],forms=tuple(forms),metadata={}),),metadata={},source_bytes=None)
 q['base64']=base64.b64encode(store_document_bytes(doc,buffers,template_context=bound.context)).decode();return q

class StoredLinkDiagnostics(unittest.TestCase):
 def test_complete_713_source_full_result_and_no_write_capability(self):
  q=request();kept=copy.deepcopy(q);r=source_link_diagnostics.inspect_request(q);self.assertEqual(r,json.loads((ROOT/'fixtures/binary-tax/owned-existing-link-expected.json').read_text()));self.assertEqual(q,kept)
  self.assertFalse(r['writeback_allowed']);self.assertFalse(r['native_inventory_verified']);self.assertTrue(r['not_editability_or_tax_completeness_proof'])
 def test_fixed_context_runs_exactly_once(self):
  with patch.object(binary_tax,'_context',wraps=binary_tax._context)as actual:source_link_diagnostics.inspect_request(request());self.assertEqual(actual.call_count,1)
 def test_unused_nonzero_cannot_supply_a_link(self):
  r=source_link_diagnostics.inspect_request(authored_variant(attrs=0));self.assertEqual(r['stored_consistent_links'],0);self.assertEqual(r['links'][0]['status'],'saved_FV_Used0_not_a_GetLinkedForm_value')
 def test_override_read_fact_does_not_grant_permission(self):
  r=source_link_diagnostics.inspect_request(authored_variant(attrs=9));self.assertEqual(r['stored_consistent_links'],1);self.assertTrue(r['links'][0]['source_FV_Override']);self.assertFalse(r['native_Override_Used_sideeffects'])
 def test_fileCopy_not_word7c_and_kind_format_mismatch(self):
  for variant in({'raw':202},{'kind':11},{'fmt':1}):self.assertEqual(source_link_diagnostics.inspect_request(authored_variant(**variant))['stored_consistent_links'],0)
 def test_duplicate_links_and_orphan_storage_refuse_success(self):
  self.assertEqual(source_link_diagnostics.inspect_request(authored_variant(duplicate=True))['stored_consistent_links'],0)
  with self.assertRaises(ValueError):source_link_diagnostics.inspect_request(authored_variant(orphan=True))
 def test_callback_claims_carrier_tamper_and_manual_arrays_refused(self):
  for key in('native_inventory_verified','trusted_profile','prepared_descriptor','owner_present'):
   q=request();q[key]=True
   with self.assertRaises(ValueError):source_link_diagnostics.inspect_request(q)
  q=request();q['carriers'][0]['base64']=base64.b64encode(b'other resource bytes').decode()
  with self.assertRaises(ValueError):source_link_diagnostics.inspect_request(q)
  q=request();q['profile']['format']='tax-reborn-binary-entity-profile-v4';q['profile']['compiled_arrays']=[dict(formset_id=x['formset_id'],form_id=x['form_id'],visible=[],hidden=[])for x in q['profile']['templates']]
  with self.assertRaisesRegex(ValueError,'same-registry automatic'):source_link_diagnostics.inspect_request(q)

if __name__=='__main__':unittest.main()
