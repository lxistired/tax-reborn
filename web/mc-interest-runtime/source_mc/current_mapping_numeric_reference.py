"""Pure exact Mapping declaration; no private request driver."""
import re

PATHS={'L1':'InterestIncomeAmtPP','L3':'InterestOnBondsAndTreasuryAmtPP','EXINT':'TaxExemptInterestAmtPP'}


CARRIER='5e8db09dc9c4126c0cd85fe11ee7b02965a3b9e88db1075ba32efc4269e0bc2f'


PAYLOAD='01584dd4774d85f0dab04c48eebde541fdffd6e68b6809d165e80e512442b2fa'


XML='8c7ac4b6e57dfe021ac47a9b81a49f32bfe4c8c1ed017fdfd7367a06d71effaa'


def configuration(root,field):
    if field not in PATHS:raise ValueError('Only exact three source-reviewed numeric input fields supported')
    tag=lambda e:e.tag.rsplit('}',1)[-1]
    path='/Return/ReturnData/PP1099Int[uuid_1]/'+PATHS[field]
    mappings=[e for e in root.iter()if tag(e)=='Mapping'and e.get('mef')==path]
    if len(mappings)!=1:raise ValueError('One exact ordinary Mapping required')
    m=mappings[0];expected={'mef':path,'tps':'FDI$FSCHB:F1099I[uuid_1].'+field}
    if m.attrib!=expected or len(m):raise ValueError('Selected mapping has extra attrs/transforms or changed source address')
    definitions=[e for e in root.iter()if tag(e)=='ConstraintDefinition']
    matches=[e for e in definitions if e.get('mef','')==path]
    if matches:raise ValueError('Attached read/write constraint requires unexecuted predicate evaluation')
    return dict(mef_path=path,tps_path=expected['tps'],mapping_attributes=dict(m.attrib),
        Mapping_class='ordinary Mapping',transform_name='',value_transform_count=0,
        complete_constraint_definition_count=len(definitions),exact_constraint_key_count=0,
        read_constraint_count=0,write_constraint_count=0,
        registered_runtime_Mapping_object_verified=False)


def kind11_default_stage(instance):
    # Only the exact canonical text produced internally by the fixed current
    # source reader is admitted; this is not a public prepared-text endpoint.
    text=instance['text']if instance['has_value']else''
    if type(text)is not str or re.fullmatch(r'-?(?:0|[1-9][0-9]{0,9})\.[0-9]{2}',text)is None and text!='':
        raise ValueError('Finite canonical current cents text required')
    if type(instance['has_value'])is not bool or type(instance['flags'])is not int or instance['error68']is not False:
        raise ValueError('Successful direct source Instance protocol required')
    # Native kind11 uses original default-copy target3397. Normal entry resets
    # suppression102b62cd8=0, so presence or nonempty text writes output. Empty
    # fresh absent output remains absent. Direction0 CP1252->UTF8 succeeds for
    # these ASCII digits/minus/point and preserves them.
    present=instance['has_value']or bool(text)
    encoded=text.encode('ascii').decode('cp1252').encode('utf8').decode('utf8')if present else''
    assert encoded==text
    return dict(text=encoded,has_value=present,marker99=False,flags=instance['flags'],
        has_flags=instance['has_flags'],Error68=False,field_kind=11,transform_direction=0,
        native_kind11_dispatch_target='0x1015b3397',whole_dollar_cast_performed=False,
        original_mapping_restores_input_flags=True,
        native_path_resolution_and_optional_refetch_executed=False)

