"""Finite source-ordinal lookup for acknowledged base and derived documents.

This keeps the saved ordinal separate from the approved current ordinal.
It reads source bytes and a loader-created binding view; no native FixupFields,
conversion, mutation, writeback, registry allocation or field repair occurs.
"""
from interop.form_core.value_hash_wire_reference import find_value as find_base


def source_node(form, spec, path, *, profile_format, bound):
    full = spec.identifier
    if type(full) is not bytes or len(full) != 32:
        raise ValueError('Exact complete approved field ID required')
    audit = {'current_ordinal': spec.ordinal, 'full_field_id_hex': full.hex(), 'element_index': 0,
             'native_fixup_performed': False}
    if profile_format not in ('tax-reborn-binary-entity-profile-v4','tax-reborn-binary-entity-profile-v5'):
        node = find_base(form.hash_state, spec.ordinal, 0)
        audit.update(source_ordinal=spec.ordinal, source_address_kind='base_current_ordinal')
        return node, audit

    from interop.derived_form.source_bound_document_reference import BoundDocument
    from interop.derived_form.source_bound_value_document_reference import walk_forms
    from interop.derived_form.value_hash_wire_reference import find_value as find_derived
    if not isinstance(bound, BoundDocument) or bound.document is None:
        raise ValueError('Loader-created complete derived source binding required')
    if dict(walk_forms(bound.document)).get(path) is not form:
        raise ValueError('Binding view must refer to this exact decoded source form')
    fs = bound.document.formsets[path[0]]
    key = fs.header.identifier, form.header.identifier
    factory = bound.context.form_factories.get(key)
    if factory == 'base_form':
        if form.derived_tail is not None or path in bound.bindings:
            raise ValueError('Explicit base factory/source shape mismatch')
        node = find_derived(form.hash_state, spec.ordinal, 0)
        audit.update(source_ordinal=spec.ordinal, source_address_kind='explicit_v4_base_factory_current_ordinal')
        return node, audit
    if factory != 'value_form' or form.derived_tail is None or path not in bound.bindings:
        raise ValueError('Explicit ValueForm factory and actual D2 map required')
    entries = [entry for entry in form.derived_tail.field_map.entries if entry.identifier == full]
    if len(entries) > 1: raise ValueError('Ambiguous complete saved field ID')
    if not entries:
        audit.update(source_ordinal=None, source_address_kind='D2_full_field_ID_absent')
        return None, audit
    saved = entries[0].source_field_index
    node = find_derived(form.hash_state, saved, 0)
    audit.update(source_ordinal=saved, source_address_kind='D2_full_field_ID', source_current_ordinals_equal=saved == spec.ordinal)
    candidates = [value for value in bound.bindings[path] if value.field_id == full and value.element_index == 0]
    if node is None:
        if candidates: raise ValueError('Binding view disagrees with actual hash absence')
        return None, audit
    if len(candidates) != 1: raise ValueError('Actual retained scalar needs one complete source/current binding')
    value = candidates[0]
    if (value.source_field_index != saved or value.current_field_index != spec.ordinal
            or value.source_kind != node.kind_byte or value.source_format != node.flag10
            or value.source_kind != spec.kind or value.source_format != spec.format
            or value.fv_attributes != node.specific_attributes or value.native_effects_performed
            or value.native_action != 'requires_additional_scalar_codec'
            or value.array_index != 0 or value.element_limit is not None):
        raise ValueError('Additional native kind/format/shape/fixup branch outside finite current scalar source')
    audit.update(binding_native_action=value.native_action, binding_FV_attributes=value.fv_attributes,
                 source_current_kind_format_compatible=True)
    return node, audit
