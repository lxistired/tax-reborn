"""Clean effective-registry -> existing owned Field/Template constructor bridge.

The caller validates full carrier bytes, directory/frame bounds and hashes,
then supplies matching immutable registry maps and identities. Carrier SHA
syntax/order checks here do not independently verify original file identity.
No checksum is inferred, no imported wire is read, and no App is imported.
"""
from collections.abc import Mapping
import hashlib,re
from .effective_registry_fields_reference import Registry,field_template,UnsupportedProfile


def _token(identifier):
    token=identifier.rstrip(b' ')
    if not token or any(c<33 or c>126 for c in token):raise UnsupportedProfile('printable token ID required')
    return token.decode('ascii')


def effective_wire_templates(registry,*,carrier_sha256_by_key,registry_order,
                             selected_targets,field_factory,template_factory):
    """Return (tuple[owned Template], JSON-safe source report).

    selected_targets is an explicit ordered iterable of
    (formsetID:str, formID:str, primarySHA:str, primaryRID:int).
    A selected target needs a real full ID-primary. Minimal-only templates
    remain retained in the registry and cannot masquerade as full primaries.
    """
    if not isinstance(registry,Registry) or not isinstance(carrier_sha256_by_key,Mapping):
        raise UnsupportedProfile('prepared registry and explicit SHA mapping required')
    if not callable(field_factory) or not callable(template_factory):raise UnsupportedProfile('owned constructors required')
    identities=dict(carrier_sha256_by_key)
    if set(identities)!={c.key for c in registry.carriers}:raise UnsupportedProfile('exact complete carrier identity mapping required')
    if any(type(v) is not str or not re.fullmatch('[0-9a-f]{64}',v) for v in identities.values()):raise UnsupportedProfile('lowercase SHA256 identities required')
    order=tuple(identities[c.key] for c in registry.carriers)
    if len(set(order))!=len(order):raise UnsupportedProfile('duplicate SHA carrier instances are outside this profile')
    if tuple(registry_order)!=order:raise UnsupportedProfile('registry_order must equal request carrier order')
    def home(record):
        s=record.source
        return dict(carrier_sha256=identities[s.carrier_key],resource_id=s.resource_id,
                    metadata_type=s.metadata_type,metadata_payload_sha256=hashlib.sha256(record.source_payload).hexdigest())
    forms={};membership=[]
    for fs in registry.formsets:
        fsid=_token(fs.identifier);frows=[]
        for form in fs.forms:
            fid=_token(form.identifier);forms[fsid,fid]=(fs,form)
            frows.append(dict(form_id=fid,selection_version=form.version,
                primary=home(form.primary) if form.primary else None,
                homes=[home(r) for r in form.homes]))
        membership.append(dict(formset_id=fsid,selection_version=fs.version,
                primary=home(fs.primary) if fs.primary else None,
                homes=[home(r) for r in fs.homes],forms=frows))
    targets=tuple(selected_targets);seen=set();templates=[];reported=[]
    for target in targets:
        if type(target) is not tuple or len(target)!=4:raise UnsupportedProfile('explicit selected target tuple required')
        fsid,fid,primary_sha,rid=target
        if type(fsid) is not str or type(fid) is not str or type(rid) is not int or not 0<rid<=65535:
            raise UnsupportedProfile('selected token IDs and RID1..65535 required')
        key=(fsid,fid)
        if key in seen:raise UnsupportedProfile('duplicate selected template')
        seen.add(key)
        if key not in forms:raise UnsupportedProfile('selected effective template absent')
        fs,form=forms[key]
        if form.primary is None:raise UnsupportedProfile('selected template has no full ID-primary')
        primary=home(form.primary)
        if (primary_sha,rid)!=(primary['carrier_sha256'],primary['resource_id']):
            raise UnsupportedProfile('selected primary SHA/RID differs from effective registry')
        parsed,sources=field_template(registry,form,template_swap=False)
        ids=parsed.context_field_ids();fields=[];bindings=[]
        visible_count=len(parsed.visible.fields) if parsed.visible else 0
        for value in parsed.fields:
            field_id=ids[value.ordinal].decode('ascii')
            fields.append(field_factory(field_id=field_id,ordinal=value.ordinal,kind=value.kind,
                          format=value.format,attributes=value.attributes,hidden=value.hidden))
            source=sources[1 if value.hidden else 0]
            if source is None:raise UnsupportedProfile('field without selected source')
            dictionary_ordinal=value.ordinal-visible_count if value.hidden else value.ordinal
            bindings.append(dict(field_id=field_id,ordinal=value.ordinal,kind=value.kind,format=value.format,
                declared_attributes_u32=value.attributes,hidden=value.hidden,
                source_carrier_sha256=identities[source.carrier_key],source_resource_id=source.resource_id,
                source_resource_type=1901 if value.hidden else 1900,
                source_metadata_type=source.metadata_type,source_dictionary_ordinal=dictionary_ordinal,
                source_row_sha256=hashlib.sha256(value.source_encoded_id+value.source_metadata).hexdigest()))
        templates.append(template_factory(formset_id=fsid,form_id=fid,carrier_sha256=primary_sha,
                         resource_id=rid,fields=tuple(fields)))
        reported.append(dict(formset_id=fsid,form_id=fid,selection_version=form.version,
            primary=primary,fields=bindings))
    return tuple(templates),dict(registry_order=list(order),membership=membership,selected_templates=reported,
             source='explicit prepared effective registry; carrier identity verification belongs to caller',
             original_execution_count=0,native_current_registry_verified=False,checksum_inferred_from_wire=False)


def build_effective_templates(ordered_complete_resource_maps,selected,*,field_factory,template_factory):
    """Adapter for an owned Registry.from_effective_xprf classmethod.

    Inputs are ordered (independently_verified_carrier_SHA, complete_decoded_map)
    pairs. Caller must already compare this order to the profile's registry_order.
    selected maps (FormSetID:str, FormID:str) -> (primarySHA:str, primaryRID:int).
    This function has no web imports, XPRF reader, profile/hash inference or IO.
    """
    from .effective_registry_fields_reference import Carrier,register_records
    pairs=tuple(ordered_complete_resource_maps)
    if not isinstance(selected,Mapping):raise UnsupportedProfile('explicit selected target mapping required')
    carriers=[];identities={};order=[]
    for item in pairs:
        if type(item) is not tuple or len(item)!=2:raise UnsupportedProfile('ordered SHA/resource-map tuples required')
        digest,resources=item
        if type(digest) is not str or not re.fullmatch('[0-9a-f]{64}',digest):raise UnsupportedProfile('explicit SHA256 required')
        key=digest.encode('ascii')
        if key in identities:raise UnsupportedProfile('duplicate SHA carrier instances are outside this profile')
        carriers.append(Carrier(key,resources));identities[key]=digest;order.append(digest)
    targets=[]
    for key,value in selected.items():
        if type(key) is not tuple or len(key)!=2 or type(value) is not tuple or len(value)!=2:
            raise UnsupportedProfile('selected (fs,form):(SHA,RID) mapping required')
        targets.append((*key,*value))
    registry=register_records(carriers)
    return effective_wire_templates(registry,carrier_sha256_by_key=identities,registry_order=order,
             selected_targets=tuple(targets),field_factory=field_factory,template_factory=template_factory)
