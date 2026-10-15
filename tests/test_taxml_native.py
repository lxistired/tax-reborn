"""Independent synthetic native-shape tests. Original fixtures/program runs=0."""
import json
import hashlib
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
from taxml_native import *

HEADERS=(('tpsType','formset'),('tpsSubType','OWNED'),('checksum','1'),('dataVersion','2025'),('formsetAttribute','0'),('implementationVersion','owned'))
FIELDS=tuple(FieldBinding(name,11,0) for _,name in BOX_FIELDS)
OWNED_METADATA=json.dumps([(x.name,x.metadata_kind,x.metadata_format) for x in FIELDS],sort_keys=True).encode()
OWNED_HASH=hashlib.sha256(OWNED_METADATA).hexdigest()
PROFILE=Profile('USIndividualTaxReturn',2025,'OwnedSet',HEADERS,'FW2',FIELDS,OWNED_HASH)
AMOUNTS=('1234.56','123','1234.56','76.54','1234.56','17.90')

def field_xml(name,kind=11,fmt=0,text='1234.56',attrs='',header='',child=None):
    b=FieldBinding(name,kind,fmt);h=b.expected_headers()
    return f'<{name} tpsType="{h["tpsType"]}" tpsSubType="{h["tpsSubType"]}" {header}>'+(child if child is not None else f'<td:value {attrs}>{text}</td:value>')+f'</{name}>'
def form_xml(fields=None,copy='0',filecopy='0',extra='',order='0'):
    if fields is None:fields=''.join(field_xml(x.name,text=a) for x,a in zip(FIELDS,AMOUNTS))
    return f'<FW2 tpsType="form" copyNum="{copy}" fileCopyNum="{filecopy}" porIndex="{order}" {extra}>{fields}</FW2>'
def entity_xml(forms=None,uid='00000000-0000-4000-8000-000000000001',year='2025',extra=''):
    h=' '.join(f'{k}="{v}"' for k,v in HEADERS)
    return f'<USIndividualTaxReturn xmlns="{BASE}USIndividualTaxReturn" xmlns:td="{TD}" xmlns:po="{PO}" taxYear="{year}" uuid="{uid}" tpsEngineVersion="9.15.0" {extra}><OwnedSet xmlns="{BASE}OwnedSet" {h}>{forms or form_xml()}</OwnedSet></USIndividualTaxReturn>'
def document(entity=None):return f'<TaxReturns xmlns="{BASE}TaxReturns">{entity or entity_xml()}</TaxReturns>'.encode()
def read(data=None,profile=PROFILE):return read_native_taxml(data or document(),profile)
def candidates(book):return book.w2_review_candidates(validated_registry_sha256=OWNED_HASH)

class NativeShapeTests(unittest.TestCase):
    def test_actual_source_root_entity_form_scalar_structure(self):
        book=read();self.assertFalse(book.unresolved);self.assertEqual(len(candidates(book)),1)
        self.assertEqual(candidates(book)[0]['boxes'][0]['wire_text'],'1234.56')
        self.assertTrue(candidates(book)[0]['requires_review']);self.assertFalse(candidates(book)[0]['automatic_tax_overwrite'])
    def test_original_source_retained_no_writer(self):
        blob=document();book=read(blob);self.assertEqual(book.original_bytes(),blob)
        with self.assertRaises(NativeWireError):replace(book,source=blob+b'x').original_bytes()
    def test_no_registry_context_is_not_review_ready(self):
        with self.assertRaises(NativeWireError):read().w2_review_candidates(validated_registry_sha256='0'*64)
        with self.assertRaises(NativeWireError):read(profile=replace(PROFILE,owned_registry_sha256=''))
    def test_cent_wire_is_dollars_no_division_by100(self):
        fact=read().forms[0].fields[0]
        self.assertEqual(fact.metadata_kind,11);self.assertEqual(fact.parsed_decimal,Decimal('1234.56'))
        self.assertNotEqual(fact.parsed_decimal,Decimal('12.3456'))
    def test_dollar_kind_remains_distinct_and_text_retained(self):
        p=replace(PROFILE,fields=(FieldBinding('OWNEDWHOLE',12),))
        book=read(document(entity_xml(form_xml(field_xml('OWNEDWHOLE',12,text='1000')))),p)
        fact=book.forms[0].fields[0];self.assertEqual(fact.wire_text,'1000');self.assertEqual(fact.parsed_decimal,Decimal('1000'))
        self.assertEqual(candidates(book),())
    def test_fractional_dollar_kind_is_unresolved(self):
        p=replace(PROFILE,fields=(FieldBinding('OWNEDWHOLE',12),))
        fact=read(document(entity_xml(form_xml(field_xml('OWNEDWHOLE',12,text='1000.25')))),p).forms[0].fields[0]
        self.assertIn('fractional_dollar_kind_requires_review',fact.unresolved);self.assertEqual(fact.wire_text,'1000.25')
    def test_ordinary_native_whole_dollar_dot_is_kind_specific(self):
        for text in ('1000.', '-1000.', '0.', '-0.'):
            profile=replace(PROFILE,fields=(FieldBinding('OWNEDWHOLE',12),))
            book=read(document(entity_xml(form_xml(field_xml('OWNEDWHOLE',12,text=text)))),profile)
            fact=book.forms[0].fields[0]
            self.assertEqual(fact.wire_text,text)
            self.assertEqual(fact.parsed_decimal,Decimal(text))
            self.assertFalse(fact.unresolved)
            self.assertEqual(candidates(book),())
        cent=read(document(entity_xml(form_xml(field_xml('WAGES',11,text='1000.'))))).forms[0].fields[0]
        self.assertIsNone(cent.parsed_decimal)
        self.assertTrue(cent.unresolved)
    def test_native_iso_date_and_dob_subtype(self):
        p=replace(PROFILE,form_name='FINFOWKS',fields=(FieldBinding('TDOB',4,14),))
        form=form_xml(field_xml('TDOB',4,14,text='1960-02-29')).replace('FW2','FINFOWKS')
        fact=read(document(entity_xml(form)),p).forms[0].fields[0]
        self.assertEqual(fact.parsed_iso_date,'1960-02-29');self.assertFalse(fact.unresolved)
    def test_invalid_date_leap_and_noniso_preserved_unresolved(self):
        p=replace(PROFILE,fields=(FieldBinding('DATE',4),))
        for text in ('1900-02-29','2025-13-01','02/29/1960','1799-12-31'):
            fact=read(document(entity_xml(form_xml(field_xml('DATE',4,text=text)))),p).forms[0].fields[0]
            self.assertIn('unsupported_date_wire',fact.unresolved);self.assertEqual(fact.wire_text,text)
    def test_foreign_root_namespace_refuses_all(self):
        self.assertEqual(candidates(read(document().replace((BASE+'TaxReturns').encode(),b'urn:foreign'))),())
    def test_unbound_entity_type_and_namespace(self):
        for blob in (document().replace(b'USIndividualTaxReturn',b'OtherEntity'),document().replace((BASE+'USIndividualTaxReturn').encode(),b'urn:foreign')):self.assertEqual(candidates(read(blob)),())
    def test_wrong_year_version_and_entity_header_refuse(self):
        for blob in (document(entity_xml(year='2024')),document().replace(b'9.15.0',b'9.15.1'),document(entity_xml(extra='future="1"'))):self.assertEqual(candidates(read(blob)),())
    def test_duplicate_entity_uuid_globally_refuses(self):self.assertEqual(candidates(read(document(entity_xml()+entity_xml()))),())
    def test_invalid_uuid_refuses(self):self.assertEqual(candidates(read(document(entity_xml(uid='unknown')))),())
    def test_formset_namespace_header_template_context(self):
        for blob in (document().replace((BASE+'OwnedSet').encode(),b'urn:foreign'),document().replace(b'checksum="1"',b'checksum="2"'),document().replace(b'tpsSubType="OWNED"',b'tpsSubType="other"')):self.assertEqual(candidates(read(blob)),())
    def test_unknown_form_header_preserves_and_refuses(self):
        book=read(document(entity_xml(form_xml(extra='future="1"'))));self.assertEqual(candidates(book),());self.assertEqual(dict(book.forms[0].raw_form_attrs)['future'],'1')
    def test_duplicate_copy_identity_refuses(self):self.assertEqual(candidates(read(document(entity_xml(form_xml()+form_xml())))),())
    def test_same_copy_other_filecopy_still_ambiguous(self):self.assertEqual(candidates(read(document(entity_xml(form_xml()+form_xml(filecopy='1'))))),())
    def test_distinct_logical_copies_retained_separately(self):
        book=read(document(entity_xml(form_xml()+form_xml(copy='1',filecopy='1'))));self.assertEqual(len(candidates(book)),2)
    def test_oversized_and_nonnumeric_copy_fail_closed(self):
        for number in ('9'*5000,'65536','-1','1.0'):
            book=read(document(entity_xml(form_xml(copy=number))));self.assertEqual(candidates(book),())
    def test_copy_widths_differ_from_filecopy(self):
        self.assertEqual(len(candidates(read(document(entity_xml(form_xml(filecopy='4294967295')))))),1)
        self.assertEqual(candidates(read(document(entity_xml(form_xml(filecopy='4294967296'))))),())
    def test_foreign_form_namespace(self):self.assertEqual(candidates(read(document().replace(b'<FW2 ',b'<FW2 xmlns="urn:foreign" '))),())
    def test_foreign_field_namespace(self):self.assertEqual(candidates(read(document().replace(b'<WAGES ',b'<WAGES xmlns="urn:foreign" '))),())
    def test_foreign_td_value_namespace(self):self.assertEqual(candidates(read(document().replace(TD.encode(),b'urn:foreign'))),())
    def test_unbound_tps_kind_and_subtype(self):
        for blob in (document().replace(b'tpsType="cent"',b'tpsType="dollar"',1),document().replace(b'tpsSubType="default"',b'tpsSubType="noComma"',1)):
            self.assertEqual(candidates(read(blob)),())
    def test_unknown_field_header_preserved_unresolved(self):
        blob=document().replace(b'<WAGES ',b'<WAGES future="semantic" ')
        fact=read(blob).forms[0].fields[0];self.assertEqual(dict(fact.raw_field_attrs)['future'],'semantic');self.assertEqual(candidates(read(blob)),())
    def test_primitive_flat_text_does_not_fake_native_scalar(self):
        blob=document().replace(b'<td:value >1234.56</td:value>',b'1234.56',1);self.assertEqual(candidates(read(blob)),())
    def test_nested_scalar_unknown_alias_is_not_flattened(self):
        for child in ('<td:raw>1234.56</td:raw>','<td:value><td:any>1234.56</td:any></td:value>','<td:value>1234.56</td:value><po:blob>unknown</po:blob>'):
            self.assertEqual(candidates(read(document(entity_xml(form_xml(field_xml('WAGES',child=child)))))),())
    def test_duplicate_missing_or_unmapped_fields_refuse(self):
        for fields in ('',field_xml('WAGES')*2, ''.join(field_xml(x.name) for x in FIELDS[1:]), ''.join(field_xml(x.name) for x in FIELDS)+'<UNKNOWN><td:value>1</td:value></UNKNOWN>'):
            # Empty explicit field list must not use the helper's default fields.
            blob=document(entity_xml(form_xml(fields=fields)));self.assertEqual(candidates(read(blob)),())
    def test_record_subtree_refused_preserved(self):
        blob=document().replace(b'</FW2>',b'<record index="1"><WAGES>1</WAGES></record></FW2>')
        book=read(blob);self.assertEqual(candidates(book),());self.assertEqual(book.original_bytes(),blob)
    def test_raw_attrs_preserved_error_used_computed_override(self):
        for key,val in [('error','true'),('used','false'),('computed','true'),('override','true'),('generalImport','true'),('autoBlanked','true'),('approx','true')]:
            blob=document().replace(b'<td:value >',f'<td:value {key}="{val}">'.encode(),1)
            fact=read(blob).forms[0].fields[0];self.assertEqual(dict(fact.raw_value_attrs)[key],val);self.assertEqual(candidates(read(blob)),())
    def test_explicit_used_true_zero_keeps_presence(self):
        fields=''.join(field_xml(x.name,text='0.00',attrs='used="true"') for x in FIELDS)
        book=read(document(entity_xml(form_xml(fields))));self.assertEqual(len(candidates(book)),1);self.assertEqual(candidates(book)[0]['boxes'][0]['amount_dollars'],'0.00')
    def test_unknown_attrs_or_boolean_lexical_refuse(self):
        for attrs in ('future="1"','computed="1"','error="FALSE"','error="maybe"'):
            blob=document().replace(b'<td:value >',f'<td:value {attrs}>'.encode(),1);self.assertEqual(candidates(read(blob)),())
    def test_comma_exponent_large_nan_amounts_stay_unresolved(self):
        for text in ('1,234.56','1e3','NaN','100000000000000','1.234',' 123.00'):
            blob=document().replace(b'1234.56',text.encode(),1);self.assertEqual(candidates(read(blob)),())
    def test_mixed_scope_text_refuses(self):
        for marker in (b'<FW2 ',b'<WAGES ',b'<OwnedSet '):
            blob=document().replace(marker,b'unknown'+marker,1);self.assertEqual(candidates(read(blob)),())
    def test_processing_instruction_is_opaque_unresolved(self):
        blob=document().replace(b'</FW2>',b'<?unknown semantic?></FW2>');self.assertEqual(candidates(read(blob)),())
    def test_internal_dtd_utf16_utf32_nonUTF8_refused(self):
        for raw in (document().decode().encode('utf-16-le'),document().decode().encode('utf-32-be'),b'<?xml version="1.0" encoding="iso-8859-1"?>'+document(),b'<!DOCTYPE TaxReturns [<!ENTITY x "123">]>'+document()):
            with self.assertRaises(NativeWireError):read(raw)
    def test_utf8_bom_and_declaration_exact_source_retention(self):
        raw=b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?>'+document();book=read(raw);self.assertEqual(len(candidates(book)),1);self.assertEqual(book.original_bytes(),raw)
    def test_deep_opaque_subtree_refused(self):
        blob=document().replace(b'</FW2>',b'<opaque>'*130+b'</opaque>'*130+b'</FW2>')
        with self.assertRaises(NativeWireError):read(blob)
    def test_other_known_field_problem_blocks_complete_owner(self):
        p=replace(PROFILE,fields=FIELDS+(FieldBinding('NAME',7),))
        blob=document().replace(b'</FW2>',field_xml('NAME',7,header='future="1"',text='Synthetic').encode()+b'</FW2>')
        self.assertEqual(candidates(read(blob,p)),())

if __name__=='__main__':unittest.main(verbosity=2)
