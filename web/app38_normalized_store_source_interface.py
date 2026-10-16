"""Source-only front end for the private document normalized-store lane.

The adapter intentionally accepts one complete caller-local ``binary_entity``
source bundle.  It derives the document, registries, current field inventory,
arrays, and D2 bindings only by calling the frozen App codec's ``_context``.
It accepts no decoded document, prepared registry, native-ready state, mapping,
or result injection.

This is an independent wire-normalization route.  It is not native Load,
FixupFields, Resolve, SetLinkedForm, or an original-program compatibility claim.
"""
from __future__ import annotations

import base64
import hashlib
import re
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP_WEB = Path(os.environ.get('TAX_REBORN_BINARY_TAX_ROOT', str(HERE)))
# The browser/packaged runtime contains the independently authored codec and
# interop closure beside this adapter. Caller-owned source and registry bytes
# are supplied per request; no private filesystem default is permitted.
import sys
for path in (APP_WEB, HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
import binary_tax
from interop.derived_form.source_bound_document_reference import load_source_bound_document_bytes
from interop.derived_form.source_bound_value_document_reference import walk_forms
from interop.form_core.hash_structure_reference import validate_document_hashes
from reference_document_normalized_store_reference import normalize_document_store_bytes

_SHA256 = re.compile(r'^[0-9a-f]{64}$')
_TOP = frozenset({'source'})
_SOURCE = frozenset({'base64', 'sha256', 'container', 'profile', 'carriers', 'profile_acknowledged'})


class SourceOnlyNormalizationRejected(ValueError):
    """Raised before an output exists when the source-only contract is unmet."""


def _reject(message):
    raise SourceOnlyNormalizationRejected(message)


def _bytes(encoded):
    if not isinstance(encoded, str):
        _reject('Source base64 must be a string.')
    try:
        return base64.b64decode(encoded.encode('ascii'), validate=True)
    except (UnicodeEncodeError, ValueError) as error:
        raise SourceOnlyNormalizationRejected('Source base64 is invalid.') from error


def _source_request(request):
    """Validate public shape and produce the exact existing App request shape."""
    if type(request) is not dict or set(request) != _TOP:
        _reject('Only one complete source bundle is accepted.')
    source = request['source']
    if type(source) is not dict or set(source) != _SOURCE:
        _reject('Source must contain only binary_entity bytes, hash, profile, and ordered local carriers.')
    if source['container'] != 'binary_entity':
        _reject('Only the existing binary_entity container is supported.')
    decoded = _bytes(source['base64'])
    expected = source['sha256']
    if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
        _reject('Source SHA-256 must be lowercase hexadecimal.')
    actual = hashlib.sha256(decoded).hexdigest()
    if actual != expected:
        _reject('Source SHA-256 does not match source base64.')
    # Deliberately omit only the public integrity field: binary_tax._context
    # itself accepts this exact five-key request and derives all mutable context.
    app_request = {key: source[key] for key in ('base64', 'container', 'profile', 'carriers', 'profile_acknowledged')}
    return decoded, expected, app_request


def _summary(bound, result, independent):
    forms = tuple(walk_forms(independent.document))
    return {
        'whole_document_readback': True,
        'source_form_count': len(tuple(walk_forms(result.original.document))),
        'output_form_count': len(forms),
        'current_registry_form_count': len(bound.current_fields),
        'array_owner_count': len(bound.arrays),
        'D2_rekeyed_nodes': len(result.node_remaps),
        'parent_U16_remaps': len(result.parent_remaps),
        'E1_endpoint_remaps': len(result.e1_range_remaps),
        'D7_exact_preserved': result.preserved_D7,
        'stored_kind7_exactly_preserved': result.preserved_stored_strings,
        'stored_kind7_array_elements_exactly_preserved': result.preserved_stored_kind7_array_elements,
        'stored_kind3_group_scalars_exactly_preserved': result.preserved_stored_kind3_group_scalars,
        'kind22_preserved_under_D7_proof': result.preserved_kind22,
        'ordinary_array_elements_exactly_preserved': result.preserved_array_elements,
        'output_readback_sha256': hashlib.sha256(independent.document.source_bytes).hexdigest(),
    }


def normalize_binary_entity_source(request):
    """Normalize one complete local binary_entity source and fully reload it.

    ``request`` has exactly ``{'source': {...}}``.  ``source`` contains a
    complete existing App binary_entity request plus the source SHA-256.  The
    caller supplies no field maps, arrays, D2 map, decoded document, native
    state, or injected result.  The current registry and binding context come
    solely from ``binary_tax._context`` using the caller's ordered carriers.
    """
    source_bytes, source_sha256, app_request = _source_request(request)
    document, buffers, bound, _registry, _selected, loaded_source = binary_tax._context(app_request)
    if loaded_source != source_bytes or bound.document is not document:
        _reject('App codec did not retain the exact submitted source bytes.')
    result = normalize_document_store_bytes(
        source_bytes, buffers, template_context=bound.context,
        current_fields=bound.current_fields, arrays=bound.arrays,
    )
    # This is intentionally a second full-source parse, independent from the
    # normalizer's own readback object.
    independent = load_source_bound_document_bytes(
        result.wire, buffers, template_context=result.readback.context,
        current_fields=bound.current_fields, arrays=bound.arrays,
    )
    if independent.document.source_bytes != result.wire:
        _reject('Independent complete output readback did not retain output bytes.')
    output_sha256 = hashlib.sha256(result.wire).hexdigest()
    if output_sha256 != result.output_sha256 or result.source_sha256 != source_sha256:
        _reject('Normalization receipt source or output identity mismatch.')
    return {
        'format': 'tax-reborn-normalized-binary-entity-source-v2',
        'mode': result.mode,
        'source': {'container': 'binary_entity', 'sha256': source_sha256, 'bytes': len(source_bytes)},
        'normalized_source': {'base64': base64.b64encode(result.wire).decode('ascii'),
                              'sha256': output_sha256, 'bytes': len(result.wire)},
        'readback': _summary(bound, result, independent),
        'proven_changed_wire_categories': {
            'D2_and_physical_hash_keys_chains': len(result.node_remaps),
            'parent_header_U16': len(result.parent_remaps),
            'E1_two_big_endian_endpoints_only': len(result.e1_range_remaps),
            'D7_descriptor_bytes_exactly_preserved_after_target_identity_validation': result.preserved_D7,
            'ordinary_stored_kind7_and_StringTable_exactly_preserved': result.preserved_stored_strings,
            'existing_ordinary_kind7_array_hash_entries_rekeyed_without_row_or_string_lifecycle': result.preserved_stored_kind7_array_elements,
            'existing_ordinary_kind3_group_scalars_rekeyed_with_current_registry_anchor_only': result.preserved_stored_kind3_group_scalars,
            'existing_ordinary_array_hash_entries_rekeyed_without_row_lifecycle': result.preserved_array_elements,
        },
        'constraints': [
            'No external field map, prepared document, arrays, D2 map, native-ready state, or result object is accepted.',
            'E1 may move only with complete owning D2 identities and a strictly increasing contiguous current ordinal range.',
            'D7 is retained only after same-document form_id/file_copy/full-field target validation and exact wire comparison.',
            'To combine a field correction, use an existing source-bound whole-document correction first, then submit its complete output as a fresh source bundle; this interface accepts no amount JSON.',
        ],
        'native_Load_executed': False,
        'native_FixupFields_executed': False,
        'original_execution_count': 0,
    }


def inspect_normalized_binary_entity_source(request):
    """Freshly inspect a complete normalized source without normalizing it.

    The App download flow calls this after it has received the complete
    normalized ``.taxbin`` bytes.  It intentionally uses a new codec context
    and a second source-bound loader.  The result is a read-only structural
    receipt; it does not run native Load/Fixup/Resolve or accept a prepared
    document/result side channel.
    """
    source_bytes, source_sha256, app_request = _source_request(request)
    document, buffers, bound, _registry, _selected, loaded_source = binary_tax._context(app_request)
    if loaded_source != source_bytes or bound.document is not document:
        _reject('App codec did not retain the exact submitted source bytes.')
    fresh = load_source_bound_document_bytes(
        source_bytes, buffers, template_context=bound.context,
        current_fields=bound.current_fields, arrays=bound.arrays,
    )
    validate_document_hashes(fresh.document)
    forms = tuple(walk_forms(fresh.document))
    return {
        'format': 'tax-reborn-normalized-binary-entity-fresh-read-v1',
        'source': {'container': 'binary_entity', 'sha256': source_sha256,
                   'bytes': len(source_bytes)},
        'readback': {
            'whole_document_readback': fresh.document.source_bytes == source_bytes,
            'form_count': len(forms),
            'form_paths': [list(path) for path, _form in forms],
            'document_sha256': hashlib.sha256(fresh.document.source_bytes).hexdigest(),
            'current_registry_form_count': len(bound.current_fields),
            'array_owner_count': len(bound.arrays),
            'hash_structure_valid': True,
        },
        'native_Load_executed': False,
        'native_FixupFields_executed': False,
        'native_Resolve_executed': False,
        'native_SetLinkedForm_executed': False,
        'original_execution_count': 0,
    }
