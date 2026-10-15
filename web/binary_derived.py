"""Explicit derived-ValueForm profile; source ordinals and opaque bytes stay local."""
from dataclasses import replace
import hashlib
from interop.derived_form.source_bound_value_document_reference import (
    TemplateContext, Document, walk_forms, replace_form)
from interop.derived_form.source_bound_document_reference import (
    BoundDocument, load_source_bound_document_bytes, store_source_bound_document_bytes)
from interop.derived_form.source_field_binding_reference import (
    CompiledArray, current_fields_from_template)
from interop.derived_form.string_wire_reference import read as read_string
from interop.derived_form.value_hash_wire_reference import find_value
from interop.derived_form.persistent_uuid_body_reference import NAME,load_form_uuid_body

PROFILE='tax-reborn-binary-entity-profile-v4'
AUTO_ARRAY_PROFILE='tax-reborn-binary-entity-profile-v5'
PROFILES=(PROFILE,AUTO_ARRAY_PROFILE)

def _key(entry):
    if type(entry.get('formset_id')) is not str or type(entry.get('form_id')) is not str:
        raise ValueError('Explicit formset/form IDs required.')
    return entry['formset_id'],entry['form_id']

def load_context(profile,registry,selected,source,buffers,table_ids):
    factories={};tables={}
    if type(profile['form_factories']) is not list:
        raise ValueError('Declare every selected form factory.')
    for entry in profile['form_factories']:
        if type(entry) is not dict or set(entry)!={'formset_id','form_id','form_kind','table_kind'}:
            raise ValueError('Invalid derived form factory declaration.')
        key=_key(entry)
        if key not in selected or key in factories or (entry['form_kind'],entry['table_kind']) not in (
                ('base_form','base_e1'),('base_form','value_table'),('value_form','value_table')):
            raise ValueError('Choose one explicit supported factory per selected form.')
        factories[key]=entry['form_kind'];tables[key]=entry['table_kind']
    if set(factories)!=set(selected) or 'value_form' not in factories.values():
        raise ValueError('Bind all selected factories and at least one ValueForm.')
    if profile['format']==AUTO_ARRAY_PROFILE:
        supplied=getattr(registry,'array_payloads',None)
        if type(supplied) is not dict or set(supplied)!=set(selected):
            raise ValueError('Bind actual arrays from the same complete effective registry.')
        arrays={key:supplied[key].construct(CompiledArray) for key,kind in factories.items() if kind=='value_form'}
    else:
        arrays={}
        if type(profile['compiled_arrays']) is not list:
            raise ValueError('Supply complete prepared array lists for every ValueForm.')
        for entry in profile['compiled_arrays']:
            if type(entry) is not dict or set(entry)!={'formset_id','form_id','visible','hidden'}:
                raise ValueError('Invalid complete compiled array declaration.')
            key=_key(entry)
            if factories.get(key)!='value_form' or key in arrays:
                raise ValueError('Array lists must uniquely bind a selected ValueForm.')
            lists=[]
            for name in ('visible','hidden'):
                if type(entry[name]) is not list or len(entry[name])>65535:
                    raise ValueError('Explicit ordered array lists required.')
                values=[]
                for value in entry[name]:
                    if type(value) is not dict or set(value)!={'identifier','first_field','last_field','element_limit','flags'}:
                        raise ValueError('Invalid prepared array descriptor.')
                    ident=value['identifier']
                    if type(ident) is not str or not ident or len(ident)>32 or any(ord(c)<33 or ord(c)>126 for c in ident):
                        raise ValueError('Explicit ASCII array ID required.')
                    for item in ('first_field','last_field','element_limit'):
                        if type(value[item]) is not int or not 0<=value[item]<=65535:
                            raise ValueError('Array ranges and limits require explicit U16 values.')
                    if type(value['flags']) is not int or not 0<=value['flags']<=255:
                        raise ValueError('Explicit array flag byte required.')
                    values.append(CompiledArray(ident.encode(),value['first_field'],value['last_field'],value['element_limit'],value['flags']))
                lists.append(tuple(values))
            arrays[key]=tuple(lists)
        if set(arrays)!={key for key,kind in factories.items() if kind=='value_form'}:
            raise ValueError('Do not infer missing current array lists from the source file.')
    encoded=lambda mapping:{(fs.encode(),form.encode()):value for (fs,form),value in mapping.items()}
    current={key:current_fields_from_template(registry.resolve(*key,identity))
             for key,identity in selected.items() if factories[key]=='value_form'}
    ids={(fs.encode(),form.encode()):{f.ordinal:f.field_id.encode() for f in registry.resolve(fs,form,identity).fields}
         for (fs,form),identity in selected.items()}
    context=TemplateContext(template_versions={key.encode():v for key,v in profile['template_versions'].items()},
        field_ids=ids,current_table_ids=table_ids,preserve_unresolved_links=True,
        form_factories=encoded(factories),table_factories=encoded(tables))
    bound=load_source_bound_document_bytes(source,buffers,template_context=context,
        current_fields=encoded(current),arrays=encoded(arrays))
    if profile['format']==AUTO_ARRAY_PROFILE and any(value.native_action=='requires_array_shape_recovery'
            for values in bound.bindings.values() for value in values):
        raise ValueError('Source array shape requires unsupported native recovery against actual definitions.')
    return bound

def binding(bound,path,node):
    return next((value for value in bound.bindings.get(path,())
        if value.source_field_index==node.field_index and value.element_index==node.element_index),None)

def decorate_fact(fact,form,node,value):
    fact.update(source_ordinal=node.field_index,current_ordinal=value.current_field_index if value else None,
        address_kind='field_id',binding_action=value.native_action if value else 'missing_source_binding')
    # Existing source-proven amount codec admits11/12. Frozen83's generic raw
    # helper intentionally admits13 only; this App extension is explicit here.
    compatible=value and value.native_action=='requires_additional_scalar_codec' and node.kind_byte in (11,12)
    fact['editable']=bool(fact['editable'] and compatible and not node.specific_attributes&8)
    reached=find_value(form.hash_state,node.field_index,node.element_index)
    fact['hash_reachable']=reached is node
    if reached is not node:
        fact.update(status='unreachable_hash_node',editable=False,text=None)
    return fact

def tail_report(form):
    tail=form.derived_tail
    if tail is None:return None
    text=lambda v:v.rstrip(b' ').decode('ascii',errors='backslashreplace') if isinstance(v,bytes) else None
    groups=[]
    for index,objects in enumerate(tail.groups):
        rows=[]
        for obj in objects:
            typed=False;uuid=None
            if obj.class_name==NAME and obj.group==0:
                try:uuid=load_form_uuid_body(obj).decode();typed=True
                except ValueError:pass
            rows.append(dict(class_name=text(obj.class_name),first_index=obj.first_index,
                second_index=obj.second_index,attachment_id=text(obj.attachment_id),
                body_bytes=len(obj.opaque_payload),body_sha256=hashlib.sha256(obj.opaque_payload).hexdigest(),
                typed_form_uuid=typed,uuid=uuid))
        groups.append(dict(group=index,kind=('form','record','value')[index],objects=rows))
    return dict(source_position=tail.source_base_position,bytes=len(tail.source_wire),
        sha256=hashlib.sha256(tail.source_wire).hexdigest(),
        fields=[dict(field_id=text(e.identifier),full_id_hex=e.identifier.hex(),source_ordinal=e.source_field_index)
                for e in tail.field_map.entries],groups=groups,
        native_fixup_performed=False,source_ordinals_preserved=True)

def store_and_read(document,buffers,bound):
    output=store_source_bound_document_bytes(replace(bound,document=document),buffers)
    reread=load_source_bound_document_bytes(output,buffers,template_context=bound.context,
        current_fields=bound.current_fields,arrays=bound.arrays)
    return output,reread.document
