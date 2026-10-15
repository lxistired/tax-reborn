"""Actual owned sources; limits and raw data remain distinct from native recalc."""
from pathlib import Path
from dataclasses import replace
import json,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import binary_tax
from create_whole_number_fixture import fixture
from interop.derived_form.document_semantics_reference import document_semantic_snapshot

def fact(report):return next(f for f in report['binary_archive']['forms'][0]['fields']if f['field_id']=='OWNED_UNITS')
def edit(request,text,**change):
    report=binary_tax.inspect_request(request)
    return binary_tax.edit_request(dict(inspection=request,expected_source_sha256=report['source_sha256'],changes=[dict(path=[0,0],field_id='OWNED_UNITS',element=0,value=text)|change],confirmed=True))

class WholeNumberSourceTests(unittest.TestCase):
 def test_cross_home_full_ID_and_exact_bounds(self):
  r=fixture();f=fact(binary_tax.inspect_request(r));self.assertEqual((f['ordinal'],f['current_ordinal'],f['text']),(113,13,'7'));self.assertTrue(f['editable']);b=f['template_bounds'];self.assertEqual((b['minimum'],b['maximum']),(1,12));primary=next(t for t in r['profile']['templates']if t['form_id']=='FW2')['carrier_sha256'];self.assertNotEqual(primary,b['carrier_sha256']);self.assertEqual(b['exact_body_hex'],'010000000c00000000000300');self.assertFalse(b['complete_native_validation'])
 def test_whole_source_correction_preserves_other_facts(self):
  r=fixture();before,doc,buf,bound=binary_tax._inspect(r);out=edit(r,'12');after,new,_,_=binary_tax._inspect({**r,'base64':out['base64']});self.assertEqual(fact(after)['text'],'12');self.assertTrue(out['binary_roundtrip_verified']);self.assertFalse(out['full_return_recalculated']);form=doc.formsets[0].forms[0];updated=replace(form,hash_state=replace(form.hash_state,buffers=tuple(replace(b,nodes=tuple(replace(n,raw=12)if(n.field_index,n.element_index)==(113,0)else n for n in b.nodes))for b in form.hash_state.buffers)));self.assertEqual(document_semantic_snapshot(binary_tax.replace_form(doc,(0,0),updated)),document_semantic_snapshot(new));self.assertEqual(sum(len(f['links'])for f in before['binary_archive']['forms']),4)
  for a,b in zip(before['binary_archive']['forms'],after['binary_archive']['forms']):self.assertEqual(a['derived']['sha256'],b['derived']['sha256']);self.assertEqual(a['table_headers'],b['table_headers']);self.assertEqual(a['links'],b['links'])
 def test_outside_range_fraction_overflow_and_wrong_ID_refuse(self):
  r=fixture()
  for value in ['0','13','-1','7.0','1.25','2147483648','-2147483649','+8','1e1']:
   with self.subTest(value=value),self.assertRaises(ValueError):edit(r,value)
  with self.assertRaises(ValueError):edit(r,'8',field_id='13')
 def test_primary_empty_or_noentry_stops_fallback(self):
  for option in ['primary_empty','primary_miss']:
   r=fixture(limits=option);f=fact(binary_tax.inspect_request(r));self.assertTrue(f['editable']);self.assertFalse(f['template_bounds']['entry_present']);self.assertIsNone(f['template_bounds']['minimum']);self.assertEqual(fact(binary_tax.inspect_request({**r,'base64':edit(r,'0')['base64']}))['text'],'0')
 def test_absence_is_unknown_and_preserved_not_source_invalid(self):
  r=fixture(limits='absent');f=fact(binary_tax.inspect_request(r));self.assertEqual(f['text'],'7');self.assertFalse(f['editable']);self.assertEqual(f['status'],'whole_number_limits_unavailable')
  with self.assertRaises(ValueError):edit(r,'8')
 def test_presence_override_computed_header_exponent_and_flags_refuse(self):
  for options in [dict(attrs=0),dict(attrs=3),dict(attrs=9),dict(attrs=11),dict(header=128),dict(exponent=1),dict(flag11=204),dict(value=2147483648)]:
   r=fixture(**options)
   with self.subTest(options=options):
    self.assertFalse(fact(binary_tax.inspect_request(r))['editable'])
    with self.assertRaises(ValueError):edit(r,'8')
 def test_malformed_resource_refused_and_previous_income_profiles_unchanged(self):
  with self.assertRaises(ValueError):fixture(limits='malformed')
  r=json.loads((ROOT/'fixtures/binary-tax/typed-value-income-request.json').read_text());v=binary_tax.inspect_request(r);self.assertTrue(all(c['can_review']for c in v['candidates']));self.assertTrue(all('template_bounds'not in f for form in v['binary_archive']['forms']for f in form['fields']))
 def test_negative_whole_number_source_only(self):
  r=fixture(limits='wide');out=edit(r,'-9');v=binary_tax.inspect_request({**r,'base64':out['base64']});self.assertEqual(fact(v)['text'],'-9');self.assertFalse(v['tax_values_imported']);self.assertFalse(v['full_return_imported']);self.assertFalse(any(c['can_review']for c in v['candidates']))

if __name__=='__main__':unittest.main()
