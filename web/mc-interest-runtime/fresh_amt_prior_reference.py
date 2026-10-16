"""Uniform absent current AMT prior, without recovering target row identities.

The caller first authenticates actual-v5 metadata and strict source owner/row
scope. This guard observes saved storage only. It does not run native Build,
defaults, key sorting, UUID resolution, assignment or writes.
"""
from decimal import Decimal
from interop.form_core.hash_structure_reference import validate_document_hashes


def _id(value):
    if type(value)is not bytes or not 0<len(value)<=32 or not value.rstrip(b' ')or b'\0'in value:
        raise ValueError('Exact complete source identifier bytes required')
    return value.ljust(32,b' ')


def require_all_saved_amt_priors_absent(document,bound,summary_path):
    if getattr(bound,'document',None)is not document:raise ValueError('One identical loaded document/current binding snapshot required')
    if type(summary_path)not in(list,tuple)or len(summary_path)!=2 or any(type(i)is not int or i<0 for i in summary_path):
        raise ValueError('Exact existing root summary path required')
    path=tuple(summary_path)
    try:fs=document.formsets[path[0]];form=fs.forms[path[1]]
    except IndexError as error:raise ValueError('Existing root summary required')from error
    if _id(form.header.identifier)!=b'FSCHB'.ljust(32,b' ')or form.header.parent is not None:raise ValueError('Exact root FSCHB required')
    hash_receipt=validate_document_hashes(document);key=(fs.header.identifier,form.header.identifier)
    if bound.context.form_factories.get(key)!='value_form'or bound.context.table_factories.get(key)!='value_table':
        raise ValueError('Explicit caller ValueForm/ValueTable class boundary required')
    fields=bound.current_fields.get(key);arrays=bound.arrays.get(key)
    if type(fields)is not tuple or type(arrays)is not tuple or len(arrays)!=2:raise ValueError('Complete current field/array metadata required')
    target=[f for f in fields if _id(f.identifier)==b'AMT'.ljust(32,b' ')]
    if len(target)!=1 or(target[0].ordinal,target[0].kind,target[0].format,target[0].attributes)!=(24,11,0,3652):
        raise ValueError('Exact source-reviewed FSCHB.AMT24 current metadata required')
    main=[a for group in arrays for a in group if _id(a.identifier)==b'INT'.ljust(32,b' ')]
    if len(main)!=1 or(main[0].first_field,main[0].last_field,main[0].element_limit,main[0].flags)!=(23,24,65520,49):
        raise ValueError('Distinct source-reviewed INT array23..24 flags49 required')
    if form.derived_tail is None:raise ValueError('Complete source D2 map required')
    by_id={};by_index={}
    for entry in form.derived_tail.field_map.entries:
        fid=_id(entry.identifier);index=entry.source_field_index
        if fid in by_id or index in by_index or type(index)is not int or not 1<=index<=65535:
            raise ValueError('Unique complete source D2 coordinates required')
        by_id[fid]=index;by_index[index]=fid
    source_target=by_id.get(b'AMT'.ljust(32,b' '))
    tables=[t for t in form.tables if _id(t.identifier)==b'INT'.ljust(32,b' ')]
    if len(tables)>1:raise ValueError('Ambiguous saved INT table refused')
    endpoint=None
    if tables:
        start=[f for f in fields if f.ordinal==23]
        if len(start)!=1:raise ValueError('Current INT first-field metadata required')
        endpoint=(by_id.get(_id(start[0].identifier)),source_target)
        if None in endpoint or endpoint[0]>endpoint[1]or endpoint!=(tables[0].word28,tables[0].word2a):
            raise ValueError('Existing INT source endpoints must resolve through full D2 IDs')
    physical={(n.field_index,n.element_index):n for b in form.hash_state.buffers for n in b.nodes}
    if len(physical)!=sum(len(b.nodes)for b in form.hash_state.buffers):raise ValueError('Duplicate physical node coordinates refused')
    bindings=bound.bindings.get(path)
    if type(bindings)is not tuple:raise ValueError('Complete summary current bindings required')
    matched={(b.source_field_index,b.element_index):b for b in bindings}
    if len(matched)!=len(bindings)or set(matched)!=set(physical):raise ValueError('Physical saved nodes and current bindings differ')
    examined=[]
    for coordinate,node in physical.items():
        binding=matched[coordinate];fid=by_index.get(node.field_index)
        if(binding.field_id,binding.source_kind,binding.source_format,binding.fv_attributes)!=(fid,node.kind_byte,node.flag10,node.specific_attributes):
            raise ValueError('Saved D2/hash/current binding mismatch')
        is_target=binding.current_field_index==24 or fid==b'AMT'.ljust(32,b' ')or(source_target is not None and node.field_index==source_target)
        if not is_target:continue
        if(fid,binding.current_field_index,node.kind_byte,node.flag10)!=(b'AMT'.ljust(32,b' '),24,11,0):
            raise ValueError('Unknown target conversion or source/current field collision')
        if not 1<=node.element_index<=65520:raise ValueError('Only existing ordinary INT row coordinates are supported')
        if node.specific_attributes&1:
            raise ValueError('Any existing Used AMT, including present zero, needs actual output row-key matching')
        if node.specific_attributes not in(0,2)or node.header or node.flag11:
            raise ValueError('Exterior override/itemization/error and unknown prior-header protocols are unclosed')
        examined.append(dict(source_ordinal=node.field_index,current_ordinal=24,element_index=node.element_index,
            FV_attributes=node.specific_attributes,raw_retained=str(node.raw),present=False))
    return dict(summary_path=list(path),target_field_id='AMT',target_current_ordinal=24,source_target_ordinal=source_target,
        stored_INT_table_present=bool(tables),source_INT_endpoints=list(endpoint)if endpoint else None,
        examined_AMT_nodes=examined,all_saved_AMT_priors_absent=True,Used_zero_is_refused=True,
        value_uniformity_does_not_recover_row_identity=True,hash_structure_validation=hash_receipt,
        native_post_Load_defaults_verified=False,native_record_inventory_verified=False,
        native_sort_or_UUID_mapping_executed=False,BINT_to_INT_row_binding_verified=False,
        comparison_only=True,writeback_allowed=False)


def value_only_fresh_assignment(computed_values,*,blank_prior_receipt):
    """Conditional UserEntered value identity for uniformly absent prior values.

    The complete calculated collection must already come from an authenticated
    program. This operation does not invent the other seven concatenate inputs,
    authenticate a receipt supplied by an untrusted client, assign a physical
    row, or infer any native key/UUID from the supplied symbolic map keys.
    """
    if type(blank_prior_receipt)is not dict or blank_prior_receipt.get('all_saved_AMT_priors_absent')is not True:
        raise ValueError('The same-snapshot uniformly blank prior guard is required')
    if type(computed_values)is not dict or len(computed_values)>64:
        raise ValueError('Finite explicit complete computed multicopy value collection required')
    for key,value in computed_values.items():
        if type(key)is not str or not key or len(key)>128 or '\0'in key:raise ValueError('Finite symbolic map key required')
        if value is not None and(type(value)is not Decimal or not value.is_finite()or abs(value)>Decimal('1e9')):
            raise ValueError('Finite numeric or explicit blank values required')
    return dict(computed_values)
