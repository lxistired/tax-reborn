"""Malformed complete chains cannot become income, setup or source edits."""
from pathlib import Path
from dataclasses import replace
import base64,json,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import binary_tax,create_derived_binary_fixture as derived_fixture
from interop.form_core.hash_structure_reference import validate_hash_structure,validate_document_hashes,NULL
from interop.form_core.value_hash_wire_reference import Node,Buffer,hash_for_nodes,find_value
from interop.form_core.native_document_reference import walk_forms,replace_form,store_document_bytes

def corrupt(state,mode):
    blocks=list(state.buffers);nodes=list(blocks[0].nodes);heads=list(state.heads)
    head=next(i for i,v in enumerate(heads) if v!=NULL);target=heads[head]
    if mode=='orphan':heads=[NULL]*len(heads)
    elif mode=='wrong_bucket':heads[(head+1)%len(heads)]=heads[head];heads[head]=NULL
    elif mode=='duplicate_bucket':heads[(head+1)%len(heads)]=heads[head]
    elif mode=='dangling_head':heads[head]=999999
    elif mode=='self_cycle':nodes[target]=replace(nodes[target],next_index=target)
    elif mode=='dangling_next':nodes[target]=replace(nodes[target],next_index=999999)
    elif mode=='duplicate_key':nodes[1]=replace(nodes[1],field_index=nodes[0].field_index,element_index=nodes[0].element_index)
    else:raise ValueError(mode)
    blocks[0]=replace(blocks[0],nodes=tuple(nodes));return replace(state,heads=tuple(heads),buffers=tuple(blocks))

class StrictHashTests(unittest.TestCase):
    def setUp(self):self.state=hash_for_nodes((Node(field_index=1,specific_attributes=1),Node(field_index=8,specific_attributes=1)),bucket_count=7)
    def test_all_normal_nodes_reached_once(self):
        receipt=validate_hash_structure(self.state);self.assertEqual(receipt['reachable_nodes'],2);self.assertTrue(receipt['complete_chains_checked'])
    def test_matching_value_self_cycle_is_rejected_after_find_value_returns(self):
        bad=corrupt(self.state,'self_cycle');self.assertIsNotNone(find_value(bad,1,0))
        with self.assertRaisesRegex(ValueError,'cycle'):validate_hash_structure(bad)
    def test_every_corrupt_topology_rejected_without_mutation(self):
        for mode in ('orphan','wrong_bucket','duplicate_bucket','dangling_head','dangling_next','duplicate_key'):
            bad=corrupt(self.state,mode);before=repr(bad)
            with self.subTest(mode=mode),self.assertRaises(ValueError):validate_hash_structure(bad)
            self.assertEqual(repr(bad),before)
    def test_tail_cycle_rejected(self):
        nodes=list(self.state.buffers[0].nodes);nodes[1]=replace(nodes[1],next_index=0);bad=replace(self.state,buffers=(replace(self.state.buffers[0],nodes=tuple(nodes)),))
        with self.assertRaisesRegex(ValueError,'cycle'):validate_hash_structure(bad)
    def test_unused_nonzero_reachable_storage_is_valid_not_present(self):
        state=hash_for_nodes((Node(field_index=7,raw=99999,specific_attributes=0),));self.assertEqual(validate_hash_structure(state)['reachable_nodes'],1)
    def test_runtime_spare_capacity_is_not_an_allocated_node(self):
        state=replace(self.state,buffers=(replace(self.state.buffers[0],capacity=2700),));self.assertEqual(validate_hash_structure(state)['allocated_nodes'],2)
        nodes=list(state.buffers[0].nodes);nodes[0]=replace(nodes[0],next_index=1000)
        with self.assertRaises(ValueError):validate_hash_structure(replace(state,buffers=(replace(state.buffers[0],nodes=tuple(nodes)),)))
    def test_empty_hash_is_valid(self):self.assertEqual(validate_hash_structure(hash_for_nodes(()))['allocated_nodes'],0)

class AllProfileHashGuards(unittest.TestCase):
    def malformed(self,name,mode):
        req=json.loads((ROOT/'fixtures/binary-tax'/(name+'-request.json')).read_text())
        doc,buffers,context,*_=binary_tax._context(req);form=doc.formsets[0].forms[0]
        bad=replace_form(doc,(0,0),replace(form,hash_state=corrupt(form.hash_state,mode)))
        req['base64']=base64.b64encode(store_document_bytes(bad,buffers,template_context=context)).decode();return req
    def test_v1_v2_v3_all_corruption_block_load_inspect_income_and_edit(self):
        for name in ('income','merged','value-table'):
            for mode in ('orphan','wrong_bucket','duplicate_bucket','dangling_head','self_cycle','dangling_next','duplicate_key'):
                with self.subTest(profile=name,mode=mode):
                    req=self.malformed(name,mode)
                    with self.assertRaises(ValueError):binary_tax._context(req)
                    with self.assertRaises(ValueError):binary_tax.inspect_request(req)
                    with self.assertRaises(ValueError):binary_tax.edit_request(dict(inspection=req,expected_source_sha256='x',changes=[dict(path=[0,0],ordinal=4,element=0,value='1.00')],confirmed=True))
    def test_filing_status_never_comes_from_orphan_or_cyclic_storage(self):
        for mode in ('orphan','self_cycle','wrong_bucket','dangling_next','duplicate_bucket'):
            req=self.malformed('filing-status',mode)
            with self.subTest(mode=mode),self.assertRaises(ValueError):binary_tax.inspect_request(req)
    def test_derived_context_is_guarded_before_caller_can_extract_values(self):
        for mode in ('orphan','wrong_bucket','duplicate_bucket','dangling_head','self_cycle','dangling_next','duplicate_key'):
            with self.subTest(mode=mode),self.assertRaises(ValueError):binary_tax._context(derived_fixture.fixture(hash_mutator=lambda state:corrupt(state,mode)))
    def test_normal_legacy_and_derived_contexts_return_validation_receipts(self):
        for name in ('income','merged','value-table','filing-status','derived-income'):
            req=json.loads((ROOT/'fixtures/binary-tax'/(name+'-request.json')).read_text());doc,*_=binary_tax._context(req)
            self.assertTrue(all(row['valid'] for row in doc.metadata['hash_structure_validation']))
            self.assertEqual(validate_document_hashes(doc),doc.metadata['hash_structure_validation'])

if __name__=='__main__':unittest.main()
