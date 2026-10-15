"""Public negative coverage uses owned bytes; no original resource fixture."""
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'web'))
import binary_tax,source_stored_cell

class SourceStoredCellBoundaryTests(unittest.TestCase):
    def request(self):return json.loads((ROOT/'fixtures/binary-tax/auto-array-used-request.json').read_text())
    def command(self):return dict(inspection=self.request(),expected_source_sha256='0'*64,expected_cell_sha256='0'*64,path=[0,0],field_id='AMT',element=1,value='12.34',confirmed=True)
    def test_owned_array_is_not_original_resource_authority(self):
        req=self.request();kept=copy.deepcopy(req);view=binary_tax.inspect_request(req);self.assertNotIn('source_stored_amount_cells',view);self.assertEqual(req,kept)
        with self.assertRaises(ValueError):source_stored_cell.correct_request(self.command())
    def test_request_cannot_self_assert_native_or_profile_permission(self):
        for key in('trusted','approved_profile','native_permission','prepared_amount'):
            with self.assertRaises(ValueError):source_stored_cell.correct_request({**self.command(),key:True})
    def test_explicit_confirmation_and_receipts_required(self):
        cmd=self.command()
        with self.assertRaises(ValueError):source_stored_cell.correct_request({**cmd,'confirmed':False})
        del cmd['expected_cell_sha256']
        with self.assertRaises(ValueError):source_stored_cell.correct_request(cmd)

class IndependentSyntheticStoredCellTests(unittest.TestCase):
    def request(self):return json.loads((ROOT/'fixtures/source-cell/request.json').read_text())
    def command(self,element=1,value='1234.57'):
        r=self.request();c=next(x for x in binary_tax.inspect_request(r)['source_stored_amount_cells']if x['element']==element)
        return dict(inspection=r,expected_source_sha256=c['receipt']['source_sha256'],expected_cell_sha256=c['receipt']['cell_sha256'],path=c['path'],field_id=c['field_id'],element=element,value=value,confirmed=True)
    def test_public_fixture_rebuilds_without_original_bytes(self):
        sys.path.insert(0,str(ROOT/'scripts'));import create_source_cell_fixture
        self.assertEqual(create_source_cell_fixture.fixture(),self.request())
    def test_complete_correction_has_separate_synthetic_authority(self):
        import base64
        from dataclasses import replace
        for element,value in((1,'1234.57'),(3,'12.34')):
            command=self.command(element,value);original=copy.deepcopy(command);out=source_stored_cell.correct_request(command)
            self.assertEqual(command,original);self.assertEqual(out['policy_kind'],'independent_synthetic');self.assertTrue(out['independent_synthetic_example']);self.assertFalse(out['native_propagation']);self.assertFalse(out['tax_recalculated'])
            doc,buffers,bound,*_=binary_tax._context(command['inspection']);node=next(n for b in doc.formsets[0].forms[0].hash_state.buffers for n in b.nodes if(n.field_index,n.element_index)==(112,element))
            changed=binary_tax.replace_form(doc,(0,0),replace(doc.formsets[0].forms[0],hash_state=replace(doc.formsets[0].forms[0].hash_state,buffers=tuple(replace(b,nodes=tuple(replace(n,raw=int(__import__('decimal').Decimal(value)*100))if n is node else n for n in b.nodes))for b in doc.formsets[0].forms[0].hash_state.buffers))))
            expected,_=binary_tax.derived.store_and_read(changed,buffers,bound);self.assertEqual(base64.b64decode(out['base64']),expected)
            self.assertEqual(len(list(binary_tax.walk_forms(doc))),8);self.assertEqual(sum(len(f.links)for _,f in binary_tax.walk_forms(doc)),8)
    def test_unused_is_not_default_zero(self):
        cells=binary_tax.inspect_request(self.request())['source_stored_amount_cells'];self.assertEqual([c['element']for c in cells],[1,3]);self.assertEqual(cells[1]['text'],'0.00')
        c=self.command();c['element']=4
        with self.assertRaises(ValueError):source_stored_cell.correct_request(c)
    def test_self_claim_or_other_policy_cannot_grant_permission(self):
        for key in('trusted','policy','policy_kind','approved_profile','prepared_amount'):
            with self.assertRaises(ValueError):source_stored_cell.correct_request({**self.command(),key:True})
        c=self.command();c['field_id']='AMT'
        with self.assertRaises(ValueError):source_stored_cell.correct_request(c)
    def test_profile_and_order_are_bound_by_receipt(self):
        for mutate in(lambda r:r['carriers'].reverse(),lambda r:r['profile'].update(note='changed')):
            c=self.command();mutate(c['inspection'])
            with self.assertRaises(ValueError):source_stored_cell.correct_request(c)
    def test_reject_extra_precision_and_unchanged(self):
        for value in('1.234','25.00','NaN','1e3',''):
            with self.assertRaises(ValueError):source_stored_cell.correct_request(self.command(value=value))



class SyntheticIdentityRefusals(unittest.TestCase):
    request=IndependentSyntheticStoredCellTests.request
    command=IndependentSyntheticStoredCellTests.command
    def changed(self,fn):
        import base64
        from dataclasses import replace
        from interop.derived_form.source_bound_value_document_reference import store_document_bytes
        r=self.request();doc,buffers,bound,*_=binary_tax._context(r);doc=fn(doc)
        def clean(f):return replace(f,metadata={k:v for k,v in f.metadata.items()if k!='source_value_form_scope'},children=tuple(clean(c)for c in f.children))
        doc=replace(doc,metadata={},source_bytes=None,formsets=tuple(replace(fs,forms=tuple(clean(f)for f in fs.forms))for fs in doc.formsets))
        r['base64']=base64.b64encode(store_document_bytes(doc,buffers,template_context=bound.context)).decode();return r
    def test_stored_owner_table_and_used_override_not_permission(self):
        from dataclasses import replace
        def form_change(doc,fn):return binary_tax.replace_form(doc,(0,0),fn(doc.formsets[0].forms[0]))
        mutations=[lambda d:form_change(d,lambda f:replace(f,header=replace(f.header,file_copy=f.header.file_copy+1))),lambda d:form_change(d,lambda f:replace(f,tables=tuple(replace(t,identifier=b'OTHER_ROWS')for t in f.tables))),lambda d:form_change(d,lambda f:replace(f,tables=tuple(replace(t,last_used_record_index=0)for t in f.tables)))]
        for attrs in(0,9):
            mutations.append(lambda d,attrs=attrs:form_change(d,lambda f:replace(f,hash_state=replace(f.hash_state,buffers=tuple(replace(b,nodes=tuple(replace(n,specific_attributes=attrs)if(n.field_index,n.element_index)==(112,1)else n for n in b.nodes))for b in f.hash_state.buffers)))))
        for mutate in mutations:
            cmd=self.command()
            with self.assertRaises(ValueError):
                cmd['inspection']=self.changed(mutate)
                source_stored_cell.correct_request(cmd)
    def test_other_form_path_cannot_use_same_cell_receipt(self):
        for path in([1,0],[0,1],[0,0,0]):
            cmd=self.command();cmd['path']=path
            with self.assertRaises(ValueError):source_stored_cell.correct_request(cmd)

if __name__=='__main__':unittest.main()
