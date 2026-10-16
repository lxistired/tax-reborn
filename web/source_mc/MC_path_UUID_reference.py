"""Source-bound normal ASCII path classifier, not an integer parser."""

class PrimaryToolAlphaIndex(ValueError):pass

def is_copy_number_candidate(component):
    if type(component)is not bytes or len(component)>4096:
        raise ValueError('Bounded explicit byte component required')
    # Normal EntityTpsContext C++ initializer sets this distinct global to32.
    if not component or len(component)>=32:return False
    first=component[0]
    if first>=128:
        raise ValueError('High-byte rune classification requires actual platform supplier')
    if 65<=first<=90 or 97<=first<=122:
        raise PrimaryToolAlphaIndex('Primary Tool alpha indices not supported')
    # The original predicate checks the first alpha bit, not all decimal digits.
    # Punctuation/NUL/nondecimal suffixes may reach a later parser and fail.
    return True

def source_uuid_path(mapping,source_uuid):
    if type(source_uuid)is not dict or source_uuid.get('source_UUID_body_verified')is not True:
        raise ValueError('Actual canonical saved FormUUID149 source fact required')
    uuid=source_uuid['source_form_uuid'].encode('ascii')
    if len(uuid)!=36 or is_copy_number_candidate(uuid):
        raise ValueError('Canonical saved child FormUUID must stay a UUID component')
    template=mapping['tps_path']
    if template.count('[uuid_1]')!=1 or not template.startswith('FDI$FSCHB:F1099I[uuid_1].'):
        raise ValueError('One exact source-derived ordinary child Mapping required')
    return dict(source_child_FormUUID149=source_uuid,
        prospective_tps_path=template.replace('[uuid_1]','['+uuid.decode('ascii')+']'),
        path_source='same actual-v5 selected child saved149 + authenticated raw5017 Mapping template',
        selected_component_kind='child FormUUID, not summary-table RecordUUID',
        source_FormUUID_is_copy_number_candidate=False,
        hypothetical_native_rewrite_of_this_component_to_RecordUUID=False,
        raw_scalar_field_has_no_array_UUID_suffix=True,
        scalar_element_zero_is_field_coordinate_not_a_created_node=True,
        normal_native_parent_form_lookup_and_MCT_rebuild_executed=False,
        native_Load_refreshUUID_preconditions_verified=False,
        source_row_to_BINT_RecordUUID_binding_verified=False,
        native_current_path_equality_or_inventory_verified=False,
        actual_v98_executed=False,comparison_only=True,writeback_allowed=False)
