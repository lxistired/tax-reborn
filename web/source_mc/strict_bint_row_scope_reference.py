"""Finite saved BINT row admission over a validated same-snapshot source view.

This pure guard has no loader, registry IO or native runtime. The caller must
first authenticate the complete current metadata and actual array payloads.
The upstream reader must validate complete hash reachability. All saved
physical nodes are checked here, including Unused retained values. This
is deliberately stricter than the unexecuted native includeUnused branches.
It neither supplies a Record UUID nor binds BINT rows to the separate INT table.
"""


def _full(value):
    if type(value) is not bytes or not 0 < len(value) <= 32:
        raise ValueError('Explicit complete field identifier bytes required')
    value = value.ljust(32, b' ')
    if not value.rstrip(b' '):
        raise ValueError('Nonempty field identifier required')
    return value


def reject_extra_bint_rows(document, bound, summary_path, first_row=1):
    """Return a source-only proof or refuse a wider/unclosed row domain.

    source/current coordinates are joined through full D2 field IDs. Checking
    the union also refuses source interval overlap whose native recovery is
    outside this one-row profile. Existing INT rows outside that union remain
    independent. Passing does not observe actual native records or Build.
    """
    if type(first_row) is not int or first_row != 1:
        raise ValueError('Only the strict ordinary first-row source scope is defined')
    if type(summary_path) not in (tuple, list) or len(summary_path) != 2 or any(
            type(i) is not int or i < 0 for i in summary_path):
        raise ValueError('Exact root summary path required')
    path = tuple(summary_path)
    if getattr(bound, 'document', None) is not document:
        raise ValueError('Document and current bindings must be the same loaded snapshot')
    try:
        formset = document.formsets[path[0]]
        summary = formset.forms[path[1]]
    except IndexError as error:
        raise ValueError('Existing summary path required') from error
    if _full(summary.header.identifier) != b'FSCHB'.ljust(32, b' ') or summary.header.parent is not None:
        raise ValueError('Exact existing root FSCHB required')
    key = (formset.header.identifier, summary.header.identifier)
    tables = [t for t in summary.tables if _full(t.identifier) == b'BINT'.ljust(32, b' ')]
    if len(tables) != 1 or tables[0].last_used_record_index != first_row:
        raise ValueError('One stored BINT table with saved last-row1 required')
    table = tables[0]
    arrays = bound.arrays.get(key)
    fields = bound.current_fields.get(key)
    if type(arrays) is not tuple or len(arrays) != 2 or any(type(x) is not tuple for x in arrays) or type(fields) is not tuple:
        raise ValueError('Complete same-snapshot current fields and both array lists required')
    bint = [a for group in arrays for a in group if _full(a.identifier) == b'BINT'.ljust(32, b' ')]
    if len(bint) != 1 or (bint[0].first_field, bint[0].last_field, bint[0].element_limit, bint[0].flags) != (4, 11, 65520, 49):
        raise ValueError('Exact externally authenticated BINT current descriptor required')
    current_by_id = {}
    current_by_ordinal = {}
    for field in fields:
        fid = _full(field.identifier)
        if fid in current_by_id or field.ordinal in current_by_ordinal:
            raise ValueError('Unique complete current metadata required')
        current_by_id[fid] = field
        current_by_ordinal[field.ordinal] = field
    if any(i not in current_by_ordinal or not current_by_ordinal[i].attributes & 0x40 for i in range(4, 12)):
        raise ValueError('Complete ordinary BINT current field range required')
    if summary.derived_tail is None:
        raise ValueError('Source D2 field map required')
    source_by_ordinal = {}
    source_by_id = {}
    for entry in summary.derived_tail.field_map.entries:
        fid = _full(entry.identifier)
        ordinal = entry.source_field_index
        if type(ordinal) is not int or not 1 <= ordinal <= 65535 or ordinal in source_by_ordinal or fid in source_by_id:
            raise ValueError('Unique nonzero source D2 coordinates required')
        source_by_ordinal[ordinal] = fid
        source_by_id[fid] = ordinal
    endpoints = tuple(source_by_id.get(_full(current_by_ordinal[i].identifier)) for i in (4, 11))
    if None in endpoints or endpoints[0] > endpoints[1] or endpoints != (table.word28, table.word2a):
        raise ValueError('Stored BINT source endpoints differ from current full-ID mapping')
    physical = {}
    for buffer in summary.hash_state.buffers:
        for node in buffer.nodes:
            coordinate = (node.field_index, node.element_index)
            if coordinate in physical:
                raise ValueError('Duplicate physical source node coordinates refused')
            physical[coordinate] = node
    bindings = bound.bindings.get(path)
    if type(bindings) is not tuple:
        raise ValueError('Complete loaded summary bindings required')
    by_coordinate = {}
    for binding in bindings:
        coordinate = (binding.source_field_index, binding.element_index)
        if coordinate in by_coordinate:
            raise ValueError('Duplicate source binding coordinates refused')
        by_coordinate[coordinate] = binding
    if set(by_coordinate) != set(physical):
        raise ValueError('Physical source nodes and current bindings differ')
    checked = []
    ignored = []
    for coordinate, node in physical.items():
        fid = source_by_ordinal.get(node.field_index)
        current = current_by_id.get(fid)
        binding = by_coordinate[coordinate]
        expected_current = current.ordinal if current is not None else None
        if (binding.field_id, binding.current_field_index, binding.source_kind, binding.source_format, binding.fv_attributes) != (
                fid, expected_current, node.kind_byte, node.flag10, node.specific_attributes):
            raise ValueError('Source D2/current binding does not match the physical saved node')
        in_source_range = endpoints[0] <= node.field_index <= endpoints[1]
        in_current_range = expected_current is not None and 4 <= expected_current <= 11
        if in_source_range or in_current_range:
            if node.element_index != first_row:
                raise ValueError('Additional or nonordinary saved BINT rows require a wider actual row-domain supplier')
            checked.append(dict(source_ordinal=node.field_index, current_ordinal=expected_current,
                                element_index=node.element_index, Used=bool(node.specific_attributes & 1)))
        else:
            ignored.append(dict(source_ordinal=node.field_index, current_ordinal=expected_current,
                                element_index=node.element_index))
    return dict(summary_path=list(path), first_row=first_row, current_BINT_range=[4, 11],
                source_BINT_endpoints=list(endpoints), checked_BINT_nodes=checked,
                unrelated_source_nodes=ignored, all_physical_summary_nodes_checked=True,
                extra_Used_zero_and_Unused_BINT_rows_refused=True,
                source_and_current_coordinate_union_checked=True,
                requires_upstream_complete_hash_validation=True,
                native_includeUnused_branch_executed=False,
                native_GetTable_Build_executed=False, native_record_inventory_verified=False,
                BINT_row_to_INT_row_binding_verified=False, native_Record_UUID_verified=False,
                comparison_only=True, writeback_allowed=False, can_commit_to_source=False)
