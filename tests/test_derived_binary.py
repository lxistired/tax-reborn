"""Actual App calls and complete owned ValueForm files, no native execution."""
from pathlib import Path
from dataclasses import replace
from decimal import Decimal
import base64,json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import binary_tax,binary_derived,create_derived_binary_fixture as fixtures,tax_engine
from interop.derived_form.document_semantics_reference import document_semantic_snapshot
from interop.derived_form.source_bound_value_document_reference import walk_forms

def request(name='derived-income'):return json.loads((ROOT/'fixtures/binary-tax'/(name+'-request.json')).read_text())
def edit(req,value='1234567.89',**changes):
 inspected=binary_tax.inspect_request(req)
 return binary_tax.edit_request(dict(inspection=req,expected_source_sha256=inspected['source_sha256'],
     changes=[dict(path=[0,0],field_id='WAGES',element=0,value=value)|changes],confirmed=True))

class DerivedBinaryAppTests(unittest.TestCase):
 def test_owned_requests_reproduce_exactly(self):
  with tempfile.TemporaryDirectory() as directory:
   fixtures.build(directory)
   for p in Path(directory).iterdir():self.assertEqual(p.read_bytes(),(ROOT/'fixtures/binary-tax'/p.name).read_bytes())
 def test_all_sections_and_source_current_field_numbers_visible(self):
  result=binary_tax.inspect_request(request());forms=result['binary_archive']['forms']
  self.assertEqual([f['path'] for f in forms],[[0,0],[0,0,0],[0,1],[0,2]])
  self.assertEqual(sum(len(f['links']) for f in forms),4);self.assertEqual(forms[0]['children'],1)
  self.assertEqual(forms[0]['table_headers'][0]['table_kind'],'value_table')
  self.assertEqual(forms[0]['table_headers'][0]['saved_last_used_record_index'],3)
  wage=next(f for f in forms[0]['fields'] if f['field_id']=='WAGES')
  self.assertEqual((wage['ordinal'],wage['source_ordinal'],wage['current_ordinal']),(104,104,4));self.assertTrue(wage['editable'])
  self.assertTrue(all(len(f['derived']['groups'])==3 for f in forms))
  self.assertEqual([len(g['objects']) for g in forms[0]['derived']['groups']],[1,0,0])
  self.assertTrue(all(len(f['full_id_hex'])==64 for f in forms[0]['derived']['fields']))
 def test_usable_three_income_types_enter_actual_calculation(self):
  result=binary_tax.inspect_request(request());self.assertFalse(result['unresolved_facts']);self.assertTrue(all(c['can_review'] for c in result['candidates']))
  data=tax_engine.default_return();data['interest'].append(dict(tax_engine.ROW_DEFAULTS['interest'],payer='Existing owned bank',taxable='30.00'))
  for candidate in result['candidates']:
   kind=candidate['record_type'];a=candidate['amounts']
   if kind=='w2':row=dict(tax_engine.ROW_DEFAULTS[kind],**a,owner='taxpayer',employer='Owned employer')
   elif kind=='interest':row=dict(tax_engine.ROW_DEFAULTS[kind],payer='Owned bank',taxable=str(Decimal(a['interest_income'])+Decimal(a['treasury_interest'])),tax_exempt=a['tax_exempt_interest'],federal_withholding=a['federal_withholding'])
   else:row=dict(tax_engine.ROW_DEFAULTS[kind],**a,payer='Owned fund',special_distribution_confirmed=True)
   data[kind].append(row)
  calculated=tax_engine.calculate_return(data);self.assertEqual(calculated['summary']['refund'],344);self.assertFalse(calculated['can_prepare'])
 def test_full_id_correction_moves_tails_and_preserves_every_other_fact(self):
  req=request();before,doc,buffers,context=binary_tax._inspect(req);output=edit(req)
  after,newdoc,_,_=binary_tax._inspect({**req,'base64':output['base64']})
  self.assertEqual(after['candidates'][0]['amounts']['wages'],'1234567.89');self.assertTrue(output['binary_roundtrip_verified']);self.assertFalse(output['full_return_recalculated'])
  self.assertNotEqual(len(base64.b64decode(req['base64'])),len(base64.b64decode(output['base64'])))
  expected=doc;root=doc.formsets[0].forms[0]
  updated=replace(root,hash_state=replace(root.hash_state,buffers=tuple(replace(b,nodes=tuple(replace(n,raw=123456789) if n.field_index==104 and n.element_index==0 else n for n in b.nodes)) for b in root.hash_state.buffers)))
  expected=binary_derived.replace_form(expected,(0,0),updated)
  self.assertEqual(document_semantic_snapshot(expected),document_semantic_snapshot(newdoc))
  for (path,a),(_,b) in zip(walk_forms(doc),walk_forms(newdoc)):
   self.assertEqual(a.derived_tail.source_wire,b.derived_tail.source_wire);self.assertNotEqual(a.derived_tail.source_base_position,b.derived_tail.source_base_position)
   self.assertEqual(a.tables,b.tables);self.assertEqual(a.links,b.links)
   if path!=(0,0):self.assertEqual(a.hash_state,b.hash_state)
 def test_candidate_box_export_uses_full_ids(self):
  req=request();result=binary_tax.inspect_request(req);candidate=result['candidates'][0]
  amounts={k:candidate['amounts'][k] for k in binary_tax.prep.BOX_KEYS.values()};amounts['wages']='1234.57'
  out=binary_tax.export_request(dict(inspection=req,expected_candidate_sha256=candidate['receipt']['candidate_sha256'],amounts=amounts,confirmed=True))
  self.assertEqual(binary_tax.inspect_request({**req,'base64':out['base64']})['candidates'][0]['amounts']['wages'],'1234.57')
 def test_legacy_ordinal_address_rejected_for_derived(self):
  req=request();out=binary_tax.inspect_request(req)
  with self.assertRaises(ValueError):binary_tax.edit_request(dict(inspection=req,expected_source_sha256=out['source_sha256'],changes=[dict(path=[0,0],ordinal=104,element=0,value='1.00')],confirmed=True))
 def test_missing_array_context_refused(self):
  req=request();req['profile']['compiled_arrays']=[]
  with self.assertRaises(ValueError):binary_tax.inspect_request(req)
 def test_no_factory_guess_from_tail(self):
  req=request();req['profile']['form_factories'][0]['form_kind']='base_form'
  with self.assertRaises(ValueError):binary_tax.inspect_request(req)
 def test_used_array_values_block_income_but_scalar_export_preserves_rows(self):
  req=request('derived-array');before=binary_tax.inspect_request(req)
  self.assertTrue(before['unresolved_facts']);self.assertTrue(all(not c['can_review'] for c in before['candidates']))
  rows=[f for f in before['binary_archive']['forms'][0]['fields'] if f['declared_array']]
  self.assertEqual([(x['element'],x['raw64'],x['specific_attributes']) for x in rows],[(1,'2500',3),(3,'0',3),(4,'99999',2)])
  output=edit(req);after=binary_tax.inspect_request({**req,'base64':output['base64']})
  self.assertEqual(rows,[f for f in after['binary_archive']['forms'][0]['fields'] if f['declared_array']])
 def test_all_three_opaque_groups_inspectable_but_moving_export_refused(self):
  req=request('derived-opaque');result=binary_tax.inspect_request(req)
  self.assertEqual([len(g['objects']) for g in result['binary_archive']['forms'][0]['derived']['groups']],[2,1,1])
  self.assertTrue(all(not c['can_review'] for c in result['candidates']))
  self.assertIn('untyped_persistent_object',[f['code'] for f in result['unresolved_facts']])
  with self.assertRaises(ValueError):edit(req)
 def test_wrong_full_id_cannot_target_current_number(self):
  with self.assertRaises(ValueError):edit(request(),field_id='104')
 def test_orphaned_storage_is_never_current_income_or_editable(self):
  for mode in ('null','wrong_bucket','out_of_range'):
   with self.subTest(mode=mode):
    req=fixtures.fixture(hash_mode=mode)
    with self.assertRaisesRegex(ValueError,'Source hash'):binary_tax._context(req)
    with self.assertRaisesRegex(ValueError,'Source hash'):binary_tax.inspect_request(req)
    with self.assertRaises(ValueError):edit(req)
 def test_reachable_lookup_is_separate_from_allocated_nonzero_presence(self):
  result=binary_tax.inspect_request(request());row=next(f for f in result['binary_archive']['forms'][0]['fields'] if f['field_id']=='OWNED_AMOUNT' and f['element']==4)
  self.assertTrue(row['hash_reachable']);self.assertFalse(row['specific_attributes']&1);self.assertEqual(row['raw64'],'99999');self.assertFalse(row['editable'])
 def test_scalar_override_and_diagnostic_headers_refused(self):
  req=request();_,doc,buffers,bound=binary_tax._inspect(req)
  for changes in ({'specific_attributes':11},{'header':128}):
   form=doc.formsets[0].forms[0];state=replace(form.hash_state,buffers=tuple(replace(b,nodes=tuple(replace(n,**changes) if n.field_index==104 else n for n in b.nodes)) for b in form.hash_state.buffers))
   # Source-preservation scope rejects this mutation before any output exists.
   mutated=binary_derived.replace_form(doc,(0,0),replace(form,hash_state=state))
   with self.assertRaises(ValueError):binary_derived.store_and_read(mutated,buffers,bound)
 def test_raw_kind13_optional_exponent_uses_actual_node_field(self):
  from interop.derived_form.source_bound_document_reference import load_source_bound_document_bytes,correct_bound_scalar,store_source_bound_document_bytes
  from interop.derived_form.source_field_binding_reference import CurrentField
  from interop.derived_form.value_hash_wire_reference import hash_for_nodes,Node
  template=type('OwnedTemplate',(),{'fields':(type('OwnedField',(),{'field_id':'AMOUNT','ordinal':1})(),)})()
  tail=fixtures.tail(template,1)
  context=fixtures.TemplateContext(template_versions={b'OWNED':37},field_ids={(b'OWNED',b'FORM'):{101:b'AMOUNT'}},form_factories={(b'OWNED',b'FORM'):'value_form'},table_factories={(b'OWNED',b'FORM'):'value_table'})
  form=fixtures.FormNode(fixtures.Header(b'FORM',1),hash_for_nodes((Node(kind_byte=13,raw=0,field_index=101,specific_attributes=1),)),fixtures.Table(),1,derived_tail=tail)
  doc=fixtures.Document(fixtures.EntityHeader(),(fixtures.FormSetNode(fixtures.FormSetHeader(b'OWNED',template_version=37),(form,)),))
  buffers=binary_tax._buffers();wire=fixtures.store_document_bytes(doc,buffers,template_context=context)
  current={(b'OWNED',b'FORM'):(CurrentField(b'AMOUNT',1,13,0),)};arrays={(b'OWNED',b'FORM'):((),())}
  bound=load_source_bound_document_bytes(wire,buffers,template_context=context,current_fields=current,arrays=arrays)
  updated=correct_bound_scalar(bound,(0,0),b'AMOUNT',0,7,exponent=3)
  after=load_source_bound_document_bytes(store_source_bound_document_bytes(updated,buffers),buffers,template_context=context,current_fields=current,arrays=arrays)
  self.assertEqual(after.document.formsets[0].forms[0].hash_state.buffers[0].nodes[0].exponent_byte,3)

if __name__=='__main__':unittest.main()
