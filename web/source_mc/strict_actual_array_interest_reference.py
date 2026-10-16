"""Additional strict saved-row scope over the immutable actual-v5 projection.

The original reader/projector remains unchanged. This adapter executes no
native initializer, factory, UUID generator, scheduler or source writes.
"""
import hashlib
from .interest_snapshot_reference import project
from .summary_child_current_reference import read_request
from .strict_bint_row_scope_reference import reject_extra_bint_rows


def _raw_header_ids(form):
    wire = form.metadata.get('source_header_wire')
    if type(wire) is not bytes or not wire or wire[0] != 0xc4:
        raise ValueError('Validated original C4/CB header bytes required')
    def ident(pos):
        if pos + 2 > len(wire):
            raise ValueError('Complete source ID length required')
        size = int.from_bytes(wire[pos:pos + 2], 'big')
        value = wire[pos + 2:pos + 2 + size]
        if not 0 < size <= 32 or len(value) != size or b'\0' in value:
            raise ValueError('Finite complete source ID bytes required')
        return value, pos + 2 + size
    source_id, pos = ident(1)
    pos += 12
    if pos + 2 > len(wire) or wire[pos] != 0xcb or wire[pos + 1] not in (0, 1):
        raise ValueError('Validated source CB marker and parent-presence byte required')
    parent_id = ident(pos + 2)[0] if wire[pos + 1] else None
    if source_id != form.header.identifier or (
            parent_id is None) != (form.header.parent is None) or (
            parent_id is not None and parent_id != form.header.parent.identifier):
        raise ValueError('Original source ID bytes differ from this typed owner')
    return source_id, parent_id


def exact_source_owner_ids(document, proof):
    summary_path = proof['summary_path']
    summary = document.formsets[summary_path[0]].forms[summary_path[1]]
    child_path = proof['child_path']
    if child_path[:-1] != summary_path or len(child_path) != 3:
        raise ValueError('Exact direct same-owner child path required')
    child = summary.children[child_path[-1]]
    summary_id, summary_parent = _raw_header_ids(summary)
    child_id, child_parent = _raw_header_ids(child)
    if (summary_id.ljust(32, b' '), child_id.ljust(32, b' '), child_parent.ljust(32, b' ') if child_parent is not None else None) != (
            b'FSCHB'.ljust(32, b' '), b'F1099I'.ljust(32, b' '), b'FSCHB'.ljust(32, b' ')) or summary_parent is not None:
        raise ValueError('Source owner IDs must match complete32 bytes; case folding is not native MatchID')
    tables = [t for t in summary.tables if t.identifier.ljust(32, b' ') == b'BINT'.ljust(32, b' ')]
    if len(tables) != 1:
        raise ValueError('One exact32 source BINT table ID required')
    wire = tables[0].metadata.get('source_wire')
    if type(wire) is not bytes or len(wire) < 3 or wire[0] != 0xe1:
        raise ValueError('Validated original E1 table bytes required')
    size = int.from_bytes(wire[1:3], 'big')
    raw_id = wire[3:3 + size]
    if not 0 < size <= 32 or len(raw_id) != size or raw_id != tables[0].identifier or raw_id.ljust(32, b' ') != b'BINT'.ljust(32, b' '):
        raise ValueError('Original source BINT ID bytes must match complete32 bytes')
    return dict(summary_ID32_hex=summary_id.ljust(32, b' ').hex(),
                child_ID32_hex=child_id.ljust(32, b' ').hex(),
                parent_ID32_hex=child_parent.ljust(32, b' ').hex(),
                BINT_ID32_hex=raw_id.ljust(32, b' ').hex(),
                no_case_folding=True, source_typed_raw_IDs_equal=True,
                complete32_identity_is_not_native_inventory=True)


def strict_project(request, *, binary_loader, approved_profile, program, expected_program_sha256):
    fields = {p['field_id']: tuple(p[k] for k in ('ordinal', 'kind', 'format', 'template_attributes'))
              for p in approved_profile['input_fields']}
    proof = read_request(request, binary_loader=binary_loader, approved_metadata=dict(
        summary_identity=approved_profile['summary_identity'], child_identity=approved_profile['child_identity'],
        fields=fields, array_blocks=approved_profile['array_blocks']))
    doc, buffers, bound, registry, selected, source = binary_loader(request['source'])
    if hashlib.sha256(source).hexdigest() != proof['source_sha256']:
        raise ValueError('Source changed before strict saved-row scope check')
    ids = exact_source_owner_ids(doc, proof)
    scope = reject_extra_bint_rows(doc, bound, proof['summary_path'], first_row=1)
    result = project(request, binary_loader=binary_loader, approved_profile=approved_profile,
                     program=program, expected_program_sha256=expected_program_sha256)
    if result['source_sha256'] != proof['source_sha256']:
        raise ValueError('Source changed between strict row check and calculation')
    return dict(result, strict_saved_BINT_row_scope=scope, exact_source_owner_IDs=ids,
                native_full_CopyNumber_supplier_verified=False,
                native_Record_UUID=None, native_record_state_observed=False)
