"""Complete caller-owned date source edits, refusing native-load assumptions."""
import base64, copy, json, struct, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'web'), str(ROOT/'scripts')]
import taxml_mac as mac
import taxml_preparation as prep
from create_mac_date_fixture import request, build, digest, resource_map, make_xml
from create_mac_taxml_fixture import request as old_request
from interop.container.raw_zip_reference import load_archive

def edit(req, index=0, value='02/29/2000', **extra):
    field = prep.inspect_request(req)['date_fields'][index]
    return prep.export_request({'inspection': req, 'expected_date_sha256': field['receipt']['field_sha256'],
                                'value': value, 'confirmed': True, **extra})

def with_resources(req, resources):
    at = 16 + 12*len(resources); directory, records = [], []
    for (kind, rid), payload in resources.items():
        record = struct.pack('<IIH',len(payload)+10,len(payload),0)+payload
        directory.append(struct.pack('<HHII',kind,rid,at,len(record)));records.append(record);at+=len(record)
    blob=b'XPRF\0\1\x10\x0c\x0a\0\0\0'+struct.pack('<I',len(resources))+b''.join(directory+records)
    req['carriers']=[{'base64':base64.b64encode(blob).decode(),'sha256':digest(blob)}]
    req['profile']['registry_order']=[digest(blob)]
    return req

class MacDateTests(unittest.TestCase):
    def test_fixture_complete_and_reproducible(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            one,two=build(a),build(b);self.assertEqual(one,two)
            self.assertEqual((one['entities'],one['form_copies'],one['date_fields']),(2,7,9))
            self.assertFalse(one['vendor_bytes_included']);self.assertFalse(one['native_date_load_executed'])
            for name in one['files']:
                self.assertEqual((Path(a)/name).read_bytes(),(Path(b)/name).read_bytes())
                self.assertEqual((Path(a)/name).read_bytes(),(ROOT/'fixtures/mac-date-taxml'/name).read_bytes())

    def test_all_dates_separate_from_existing_income(self):
        old=prep.inspect_request(old_request())
        for mode in ('controller_filter','null_filter'):
            req=request(filter_profile=mode);result=prep.inspect_request(req)
            self.assertEqual(len(result['date_fields']),9)
            self.assertEqual([f['kind'] for f in result['date_fields']],[4,5,6]*3)
            self.assertEqual(len({f['receipt']['field_sha256'] for f in result['date_fields']}),9)
            self.assertTrue(all(f['can_edit_source'] and not f['can_review'] for f in result['date_fields']))
            self.assertTrue(all(f.amount is None for f in mac._context(req)[-1].fields if f.kind in (4,5,6)))
            self.assertEqual([c['amounts'] for c in result['candidates']],[c['amounts'] for c in old['candidates']])
            self.assertEqual(result['scalar_fields'],[])
            self.assertFalse(result['tax_values_imported']);self.assertFalse(result['unresolved_facts'])
            self.assertEqual(len(mac._context(req)[-1].fields),53)

    def test_other_profiles_do_not_silently_admit_dates(self):
        for profile in (mac.PROFILE,mac.SCALAR_PROFILE):
            req=request();req['profile']['format']=profile
            if profile==mac.PROFILE:del req['profile']['filter_profile']
            with self.assertRaises(ValueError):prep.inspect_request(req)

    def test_all_three_kinds_across_entities_and_copies_preserve_complete_document(self):
        for index,value in ((0,'02/29/2000'),(4,'12-31'),(8,'2025-12')):
            for mode in ('controller_filter','null_filter'):
                req=request(filter_profile=mode);kept=copy.deepcopy(req);original=base64.b64decode(req['base64'])
                old=load_archive(original);doc=mac._context(req)[-1];facts=prep.inspect_request(req)['date_fields']
                selected=facts[index];key=(selected['key'][0],bytes.fromhex(selected['key'][1]),bytes.fromhex(selected['key'][2]),selected['key'][3],bytes.fromhex(selected['key'][4]))
                field=next(f for f in doc.fields if f.key==key);output=edit(req,index,value);blob=base64.b64decode(output['base64']);new=load_archive(blob)
                self.assertEqual(req,kept);self.assertEqual(output['edited_date_key'],selected['key'])
                self.assertEqual(output['text_kind'],selected['text_kind']);self.assertFalse(output['tax_values_imported'])
                self.assertFalse(output['full_return_recalculated']);self.assertFalse(output['native_date_load_executed'])
                self.assertFalse(output['original_program_acceptance_verified'])
                expected=doc.source_bytes[:field.text_start]+value.encode()+doc.source_bytes[field.text_end:]
                self.assertEqual(next(m.payload for m in new.members if m.name==b'return.xml'),expected)
                self.assertEqual([m.name for m in old.members],[m.name for m in new.members])
                self.assertEqual(sum(a.local==b.local for a,b in zip(old.members,new.members)),4)
                self.assertTrue(output['container_report']['unselected_local_records_byte_identical'])
                self.assertTrue(output['container_report']['original_manifest_bytes_unchanged'])
                before=[(f.key,f.kind,value if f.key==key else f.text,f.attributes,f.value_attributes) for f in doc.fields]
                after=[(f.key,f.kind,f.text,f.attributes,f.value_attributes) for f in mac._context({**req,'base64':output['base64']})[-1].fields]
                self.assertEqual(before,after)

    def test_calendar_and_exact_text_boundaries(self):
        valid=((0,'01/01/1900'),(0,'12/31/9999'),(0,'02/29/2000'),(1,'02-29'),(2,'1900-01'),(2,'9999-12'))
        for index,value in valid:
            with self.subTest(value=value):self.assertEqual(edit(request(plaintext=True),index,value)['mime'],'application/xml')
        bad={0:['2000-02-29','2/29/2000','02/29/1900','02/30/2000','12/31/1899','01/01/10000',' 01/02/2000','01/02/2000 ',None,False],
             1:['02/29','2000-02-29','02-30','00-01','12-32','2-29'],
             2:['02/2000','2000-00','2000-13','1899-12','2000-2','0200-12']}
        for index,values in bad.items():
            for value in values:
                with self.subTest(index=index,value=value),self.assertRaises(ValueError):edit(request(),index,value)

    def test_stale_unconfirmed_unused_and_unknown_manifest_refused(self):
        req=request()
        for confirmed in (False,0,1,None,'true'):
            with self.subTest(confirmed=confirmed),self.assertRaises(ValueError):edit(req,confirmed=confirmed)
        with self.assertRaises(ValueError):edit(req,expected_date_sha256='0'*64)
        stale=prep.inspect_request(req)['date_fields'][0]['receipt']['field_sha256'];changed=request(xml=make_xml().replace(b'01/02/2000',b'01/03/2000',1))
        with self.assertRaises(ValueError):prep.export_request({'inspection':changed,'expected_date_sha256':stale,'value':'02/29/2000','confirmed':True})
        blocked=request(blocked=True);self.assertTrue(all(not f['can_edit_source'] for f in prep.inspect_request(blocked)['date_fields']))
        with self.assertRaises(ValueError):edit(blocked)
        unused=request(xml=make_xml().replace(b'<td:value>01/02/2000',b'<td:value used="false">01/02/2000',1))
        self.assertFalse(prep.inspect_request(unused)['date_fields'][0]['can_edit_source'])
        with self.assertRaises(ValueError):edit(unused)
        for flag in ('isTainted="true"','override="true"','used="true"','unknown="x"'):
            bad=request(xml=make_xml().replace(b'<td:value>01/02/2000',('<td:value '+flag+'>01/02/2000').encode(),1))
            with self.subTest(flag=flag),self.assertRaises(ValueError):prep.inspect_request(bad)

    def test_bound_metadata_format_flags_and_full_ownership(self):
        for offset,value in ((36,1),(37,1),(37,0x40)):
            resources=resource_map();payload=bytearray(resources[1900,2]);payload[offset+8*39]=value;resources[1900,2]=bytes(payload)
            with self.assertRaises(ValueError):prep.inspect_request(with_resources(request(),resources))
        plain=request(plaintext=True);xml=base64.b64decode(plain['base64'])
        for a,b in ((b'<DATE field="9"',b'<DATE field="8"'),(b'<DATE field="9" elem="0"',b'<DATE field="9" elem="1"'),(b'tpsType="date"',b'tpsType="cent"'),(b'<DATE ',b'<UNKNOWN ')):
            with self.subTest(a=a),self.assertRaises(ValueError):prep.inspect_request({**plain,'base64':base64.b64encode(xml.replace(a,b,1)).decode()})

    def test_date_at_money_box_name_never_supplies_income(self):
        resources=resource_map();payload=bytearray(resources[1900,2]);payload[35]=4;resources[1900,2]=bytes(payload)
        import re
        xml=re.sub(rb'(<WAGES [^>]*tpsType=")cent("[^>]*><td:value>)[^<]+(</td:value>)',rb'\1date\g<2>01/02/2000\3',make_xml())
        result=prep.inspect_request(with_resources(request(xml=xml),resources))
        wages=[c for c in result['candidates'] if c['record_type']=='w2']
        self.assertTrue(all(not c['can_review'] and 'wages' not in c['amounts'] for c in wages))
        self.assertTrue(any(f['field_id']=='WAGES' for f in result['date_fields']))

if __name__=='__main__':unittest.main()
