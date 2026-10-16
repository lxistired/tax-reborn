"""Same-registry complete actual2000/2001 array binding, without class inference."""
import hashlib


def verify_actual_array_blocks(bound,registry,*,formset_id,form_id,approved_blocks):
    if type(approved_blocks)is not list or len(approved_blocks)!=2:raise ValueError('Both externally approved complete actual array blocks required')
    key=(formset_id,form_id);encoded=(formset_id.encode(),form_id.encode())
    if bound.context.form_factories.get(encoded)!='value_form'or bound.context.table_factories.get(encoded)!='value_table':raise ValueError('Explicit caller ValueForm/ValueTable factory required; descriptor flags are not class evidence')
    blocks=getattr(registry,'array_payloads',{}).get(key)
    if blocks is None or len(blocks.blocks)!=2:raise ValueError('Complete actual arrays from this effective registry required')
    descriptors=[];receipts=[]
    for block,approved,typ in zip(blocks.blocks,approved_blocks,(2000,2001)):
        if type(approved)is not dict or set(approved)!={'attribute_type','carrier_sha256','resource_id','payload_sha256','records'}or block.attribute_type!=typ or approved['attribute_type']!=typ:raise ValueError('Exact ordered actual array block protocol required')
        source=block.source;payload=block.source_payload
        if source is None:
            if payload is not None or block.records or(approved['carrier_sha256'],approved['resource_id'],approved['payload_sha256'],approved['records'])!=(None,None,None,[]):raise ValueError('Exact actually missing array block required; missing is not a zero-count payload')
        elif type(payload)is not bytes or(source.carrier_key.decode('ascii'),source.resource_id,hashlib.sha256(payload).hexdigest())!=(approved['carrier_sha256'],approved['resource_id'],approved['payload_sha256']):raise ValueError('Actual array source identity/content differs')
        actual=[dict(identifier=a.identifier.rstrip(b' ').decode('ascii'),first_field=a.first_field,last_field=a.last_field,element_limit=a.element_limit,flags=a.flags,byte27=a.byte27)for a in block.records]
        if actual!=approved['records']:raise ValueError('Complete ordered actual array descriptors differ')
        descriptors.append(tuple((a.identifier.rstrip(b' '),a.first_field,a.last_field,a.element_limit,a.flags)for a in block.records));receipts.append(dict(approved))
    loaded=bound.arrays.get(encoded)
    if type(loaded)is not tuple or len(loaded)!=2 or tuple(tuple((a.identifier.rstrip(b' '),a.first_field,a.last_field,a.element_limit,a.flags)for a in rows)for rows in loaded)!=tuple(descriptors):raise ValueError('Bound current arrays differ from the same actual registry')
    return dict(blocks=receipts,flags_not_interpreted_as_alias=True,native_factory_executed=False,native_GetTable_Build_executed=False,native_record_inventory_verified=False)
