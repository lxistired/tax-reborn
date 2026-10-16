"""App-facing type0 encrypted-container import bridge.

This bridge selects one decrypted TaxML document for the existing TaxML reader.
All other members remain retained source facts in the returned outer inventory.
It neither writes encrypted archives nor grants an opaque member edit permission.
"""
from __future__ import annotations
import base64
import copy

from interop.container.clear_container_reference import TYPES
from interop.container.default_encrypted_reference import (
    EncryptedContainerError, load_default_encrypted_container,
    load_local_compatibility_config, read_entities,
)


def inspect_default_taxml(source, *, compatibility_path, is_previous_year_return, profile, carriers, profile_acknowledged):
    """Inspect one selected type0 TaxML member through the existing App reader.

    ``compatibility_path`` is consumed locally and is never returned, persisted,
    or represented in the receipt. Type1 and type2 are rejected by the outer
    reader before this bridge calls TaxML parsing.
    """
    if profile_acknowledged is not True:
        raise EncryptedContainerError('Review and acknowledge the selected TaxML wire profile before inspection')
    config = load_local_compatibility_config(compatibility_path)
    container = load_default_encrypted_container(
        source, compatibility=config, is_previous_year_return=is_previous_year_return)
    taxml = tuple(document for document in container.documents if document.entity_type == TYPES[0])
    if len(taxml) != 1:
        raise EncryptedContainerError('Type0 TaxML import requires one unambiguous TaxML manifest document')

    import taxml_preparation
    request = {'base64': base64.b64encode(taxml[0].payload).decode(),
               'container': 'plaintext_xml', 'profile': copy.deepcopy(profile),
               'carriers': copy.deepcopy(carriers), 'profile_acknowledged': True}
    result = taxml_preparation.inspect_request(request)
    return {
        'format': 'tax-reborn-default-encrypted-taxml-import-v1',
        'outer_source_sha256': container.encrypted_source_sha256,
        'branch': container.branch,
        'selected_taxml_member': taxml[0].entity_key,
        'outer_inventory': container.inventory(),
        'taxml_inspection': result,
        'opaque_members_editable': False,
        'encrypted_export_supported': False,
        'full_return_imported': False,
        'native_execution': False,
        'original_archive': False,
    }


def inspect_default_taxml_mapping(source, *, compatibility, is_previous_year_return, profile, carriers):
    """Worker-safe variant: consume an already parsed local config mapping."""
    config = load_default_encrypted_container.__globals__["DefaultCryptoConfig"].from_mapping(compatibility)
    container = load_default_encrypted_container(
        source, compatibility=config, is_previous_year_return=is_previous_year_return)
    taxml = tuple(document for document in container.documents if document.entity_type == TYPES[0])
    if len(taxml) != 1:
        raise EncryptedContainerError('Type0 TaxML import requires one unambiguous TaxML manifest document')
    import taxml_preparation
    request = {'base64': base64.b64encode(taxml[0].payload).decode(),
               'container': 'plaintext_xml', 'profile': copy.deepcopy(profile),
               'carriers': copy.deepcopy(carriers), 'profile_acknowledged': True}
    result = taxml_preparation.inspect_request(request)
    return {
        'format': 'tax-reborn-default-encrypted-taxml-import-v1',
        'outer_source_sha256': container.encrypted_source_sha256,
        'branch': container.branch,
        'selected_taxml_member': taxml[0].entity_key,
        'outer_inventory': container.inventory(),
        'taxml_inspection': result,
        'opaque_members_editable': False,
        'encrypted_export_supported': False,
        'full_return_imported': False,
        'native_execution': False,
        'original_archive': False,
    }


def acknowledge_all_members(container, reader):
    """Expose the generic all-member callback for a separately bound reader."""
    return read_entities(container, reader)
