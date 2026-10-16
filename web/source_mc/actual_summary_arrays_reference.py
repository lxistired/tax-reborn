"""Bind current array definitions to the same validated v5 effective registry.

Flags are copied bytes, not a runtime alias discriminator. Containing form and
table classes remain the caller's explicit profile declaration. This module
does not run native GetTable/Build, create rows, or supply native RecordUUIDs.
"""
import hashlib


def verify_summary_arrays(bound, registry, *, formset_id, approved_blocks):
    if type(approved_blocks) is not list or len(approved_blocks)!=2:
        raise ValueError('Both externally approved complete array blocks required')
    key=(formset_id,'FSCHB');encoded=(formset_id.encode(),b'FSCHB')
    payloads=getattr(registry,'array_payloads',None)
    if type(payloads)is not dict or key not in payloads:
        raise ValueError('Actual arrays must come from this effective registry snapshot')
    if bound.context.form_factories.get(encoded)!='value_form' or bound.context.table_factories.get(encoded)!='value_table':
        raise ValueError('Explicit ValueForm/ValueTable caller factory required; flags do not select a class')
    blocks=payloads[key].blocks;result=[];descriptors=[]
    if len(blocks)!=2:raise ValueError('Complete visible and hidden array blocks required')
    for block,approved,typ in zip(blocks,approved_blocks,(2000,2001)):
        required={'attribute_type','carrier_sha256','resource_id','payload_sha256','records'}
        if type(approved)is not dict or set(approved)!=required or block.attribute_type!=typ or approved['attribute_type']!=typ:
            raise ValueError('Exact source-reviewed array block profile required')
        source=block.source;payload=block.source_payload
        if source is None or type(payload)is not bytes:
            raise ValueError('Selected original array block must be present, including a zero-count payload')
        digest=hashlib.sha256(payload).hexdigest()
        if (source.carrier_key.decode('ascii'),source.resource_id,digest)!=(approved['carrier_sha256'],approved['resource_id'],approved['payload_sha256']):
            raise ValueError('Actual array block identity/content differs from approved local resources')
        actual=[];local=[]
        for item in block.records:
            identifier=item.identifier.rstrip(b' ').decode('ascii')
            row=dict(identifier=identifier,first_field=item.first_field,last_field=item.last_field,
                element_limit=item.element_limit,flags=item.flags,byte27=item.byte27)
            actual.append(row);local.append((item.identifier.rstrip(b' '),item.first_field,item.last_field,item.element_limit,item.flags))
        if actual!=approved['records']:
            raise ValueError('Complete ordered actual array descriptors differ from approved definitions')
        descriptors.append(tuple(local))
        result.append(dict(attribute_type=typ,carrier_sha256=approved['carrier_sha256'],resource_id=source.resource_id,
            payload_sha256=digest,records=actual))
    loaded=bound.arrays.get(encoded)
    if type(loaded)is not tuple or len(loaded)!=2:
        raise ValueError('Complete bound current array lists required')
    actual_bound=tuple(tuple((r.identifier.rstrip(b' '),r.first_field,r.last_field,r.element_limit,r.flags)for r in rows)for rows in loaded)
    if actual_bound!=tuple(descriptors):raise ValueError('Bound current arrays differ from this same registry')
    bint=[r for rows in result for r in rows['records']if r['identifier']=='BINT']
    if len(bint)!=1 or bint[0] != dict(identifier='BINT',first_field=4,last_field=11,element_limit=65520,flags=49,byte27=0):
        raise ValueError('This finite actual-array bridge selects exact BINT descriptor 0x31')
    main=[r for rows in result for r in rows['records']if r['identifier']=='INT']
    if len(main)!=1 or main[0] != dict(identifier='INT',first_field=23,last_field=24,element_limit=65520,flags=49,byte27=0):
        raise ValueError('Distinct exact INT output table required; it is not BINT')
    return dict(array_blocks=result,BINT_descriptor=bint[0],INT_descriptor=main[0],
        byte26_flags_are_not_interpreted_as_alias=True,
        factory_origin='explicit_caller_ValueForm_ValueTable_profile',native_factory_executed=False,
        native_GetTable_Build_executed=False,native_record_inventory_verified=False,
        BINT_row_to_INT_row_binding_verified=False,can_commit_to_source=False)
