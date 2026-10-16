"""Complete explicitly cleartext containers around separately validated TaxML.

The original native constructor defaults to encryption. This selected profile
does not decrypt or establish native loading, template registration or tax parity.
Unselected documents and unreferenced members remain stored source content.
"""
import hashlib
import taxml_wire as wire

from interop.container.clear_container_reference import (
    TYPES, load_clear_container, document_by_type, replace_document_payload,
)

FORMAT = 'cleartext_persistence_container'
MANIFEST_NS = 'http://schemas.intuit.com/LocalCfpContainer.xsd'


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _manifest_edit_blockers(source):
    """Authorize only the complete manifest structure understood by this App.

    Retaining unknown metadata is not permission to change its related payload.
    Comments, processing instructions and whitespace carry no modeled fields.
    Version, CFP, relationship and arbitrary attribute contexts remain unknown.
    """
    root = wire.xml(source)
    ns = '{' + MANIFEST_NS + '}'
    blockers = []

    def block(path):
        blockers.append({'path': path, 'code': 'unmodeled_container_manifest_metadata',
                         'detail': 'This manifest metadata is outside the supported source-edit profile.'})

    def structure(node, path, allowed):
        if node.attrib or (node.text or '').strip():
            block(path)
        children = []
        for child in node:
            if (child.tail or '').strip():
                block(path)
            if not isinstance(child.tag, str):
                continue
            child_path = path + '/' + wire.qname(child.tag)[1]
            if child.tag not in {ns + name for name in allowed}:
                block(child_path)
            else:
                children.append((child, child_path))
        return children

    for node, path in structure(root, 'Manifest', {'documents', 'security', 'intuitIdentity', 'cfpIntuitIdentity'}):
        if node.tag != ns + 'documents':
            if node.attrib or any(isinstance(c.tag, str) for c in node) or (node.text or '').strip():
                block(path)
            continue
        for document, doc_path in structure(node, path, {'document'}):
            for leaf, leaf_path in structure(document, doc_path, {'entityType', 'entityKey'}):
                if leaf.attrib or any(isinstance(c.tag, str) for c in leaf):
                    block(leaf_path)
    return blockers


def inspect_source(source):
    container = load_clear_container(source, encryption_mode='cleartext')
    selected = document_by_type(container, TYPES[0])
    report = {
        'profile': FORMAT,
        'encryption_mode': 'explicit_cleartext_only',
        'source_sha256': _hash(source),
        'manifest_sha256': _hash(container.manifest_xml),
        'selected_taxml_member': selected.entity_key,
        'members': len(container.archive.members),
        'documents': [
            {'entity_key': d.entity_key, 'entity_type': d.entity_type,
             'payload_sha256': _hash(d.payload), 'bytes': len(d.payload),
             'selected_for_taxml': d.member_name == selected.member_name,
             'stored_only': d.member_name != selected.member_name}
            for d in container.documents
        ],
        'unreferenced_members': len(container.unreferenced_members),
        'native_default_encrypted_file_supported': False,
        'other_document_semantics_validated': False,
        'native_program_acceptance_verified': False,
    }
    report['blocking_metadata_facts'] = _manifest_edit_blockers(container.manifest_xml)
    report['manifest_metadata_edit_authorized'] = not report['blocking_metadata_facts']
    return selected.payload, selected.entity_key, report


def corrected_container(source, selected_key, corrected_taxml):
    _, _, source_report = inspect_source(source)
    if not source_report['manifest_metadata_edit_authorized']:
        raise ValueError('Unmodeled manifest metadata blocks source correction. The original source is retained.')
    container = load_clear_container(source, encryption_mode='cleartext')
    selected = document_by_type(container, TYPES[0])
    if selected.entity_key != selected_key:
        raise ValueError('The selected TaxML document changed. Reopen the source.')
    output = replace_document_payload(container, selected_key, corrected_taxml,
                                      expected_entity_type=TYPES[0])
    payload, key, report = inspect_source(output)
    if payload != corrected_taxml or key != selected_key:
        raise ValueError('The complete corrected container failed TaxML readback.')
    report.update({
        'complete_archive_readback_passed': True,
        'original_manifest_bytes_unchanged': True,
        'unselected_local_records_byte_identical': True,
        'source_sha256_before': _hash(source),
    })
    return output, report
