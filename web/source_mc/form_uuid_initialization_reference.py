"""Independent finite compiled Form predicate and fresh UUID fragment.

This is an explicitly partial initialization model. It does not execute a
native Load, post events, restore a Record UUID, or certify native listeners.
"""
import re

def decimal_u16(value):
    if type(value) is not bytes or re.fullmatch(rb'(0|[1-9][0-9]{0,4})',value) is None:
        raise ValueError('Canonical finite unsigned decimal template string required')
    result=int(value)
    if result>65535:raise ValueError('Finite compiled U16 overflow refused')
    return result

def compiled_uuid_policy(form):
    primary=form.primary
    if primary is None or len(primary.strings)<19:
        raise ValueError('Actual complete selected compiled Form primary required')
    if primary.source.metadata_type!=18000 or primary.strings[0].ljust(32,b' ')!=form.identifier:
        raise ValueError('Exact original primary Form ID binding required')
    kind=decimal_u16(primary.strings[5]);limit=decimal_u16(primary.strings[10])
    multiple=kind==2 or (kind==4 and limit!=1)
    return dict(form_id_hex=form.identifier.hex(),compiled_type=kind,compiled_limit=limit,
        is_multiple_copy=multiple,source_type_string_index=5,source_limit_string_index=10,
        primary_carrier_sha256=primary.source.carrier_key.decode('ascii'),
        primary_resource_type=primary.source.metadata_type,primary_resource_id=primary.source.resource_id,
        primary_payload_sha256=__import__('hashlib').sha256(primary.source_payload).hexdigest())

def fresh_non_multiple_uuid(policy):
    if type(policy)is not dict or policy.get('is_multiple_copy')is not False:
        raise ValueError('Actual non-multiple compiled predicate required; random UUID branch is outside this fragment')
    # Base C2 starts with an empty std::string. The in-scope initializer's
    # conditional setUUID call is skipped for this source-derived predicate.
    return b''

def owned_form_address(form):
    """Original parent recursion and UUID suffix on our source projections.

    UUID absence is never converted to empty. Only a separately source-bound
    fresh non-MC fragment may explicitly supply b'' for the owned parent.
    """
    chain=[];seen=set();current=form
    while current is not None:
        if id(current)in seen or len(chain)>=16:raise ValueError('Finite parent cycle/depth refused')
        seen.add(id(current));chain.append(current);current=current.parent
    parts=[]
    for item in reversed(chain):
        token=item.form_id.rstrip(b' ')
        if not token or any(c<33 or c>126 or c in b'[]:.$' for c in token):
            raise ValueError('Finite exact printable Form ID token required')
        uuid=item.saved_form_uuid
        if type(uuid)is not bytes:raise ValueError('Owned Form UUID not supplied; absence is not empty')
        if uuid:
            if re.fullmatch(rb'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',uuid)is None:
                raise ValueError('Finite canonical existing source149 UUID required')
            token+=b'['+uuid+b']'
        parts.append(token)
    return b':'.join(parts)
