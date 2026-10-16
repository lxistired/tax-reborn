"""Bounded reader for the selected default-protected PersistenceContainer route.

The caller provides current/previous material through a private local
compatibility configuration.  This module contains no vendor material.  It
reads every ZIP member and decrypts each manifest-listed member, while leaving
payload meaning and edit permission to an explicit existing reader.

Supported route: no ``intuitIdentity`` content and no ``security`` element.
Identity and password-protected containers are rejected before member use.
Unknown members are retained as ciphertext only; successful CBC decryption is
not a semantic validation and grants no edit permission.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
import stat
import xml.etree.ElementTree as ET

from .aes_cbc_reference import CryptoInputError, decrypt_aes_cbc_pkcs7
from .clear_container_reference import MANIFEST, MAX_MANIFEST, NS, TYPES
from .raw_zip_reference import Archive, UnsupportedProfile, load_archive

MAX_ENTITY = 16 * 1024 * 1024
MAX_CONFIG_BYTES = 8192
COMPATIBILITY_FORMAT = 'tax-reborn-default-tax-crypto-v1'


class CompatibilityConfigError(ValueError):
    pass


class UnsupportedEncryptionRoute(ValueError):
    pass


class EncryptedContainerError(ValueError):
    pass


@dataclass(frozen=True)
class KeyIV:
    key: bytes = field(repr=False)
    iv: bytes = field(repr=False)

    def __post_init__(self):
        if type(self.key) is not bytes or len(self.key) not in (16, 32):
            raise CompatibilityConfigError('AES key must be 16 or 32 bytes')
        if type(self.iv) is not bytes or len(self.iv) != 16:
            raise CompatibilityConfigError('AES IV must be 16 bytes')


@dataclass(frozen=True)
class DefaultCryptoConfig:
    current_manifest: KeyIV = field(repr=False)
    current_member: KeyIV = field(repr=False)
    previous_manifest: KeyIV = field(repr=False)
    previous_member: KeyIV = field(repr=False)

    @staticmethod
    def from_mapping(value):
        if (not isinstance(value, dict) or set(value) != {'format', 'current', 'previous'}
                or value['format'] != COMPATIBILITY_FORMAT):
            raise CompatibilityConfigError('Expected explicit default-container compatibility configuration')

        def part(branch, role):
            data = value[branch]
            if (not isinstance(data, dict) or set(data) != {'manifest', 'member'}
                    or not isinstance(data[role], dict)
                    or set(data[role]) != {'key_base64', 'iv_base64'}):
                raise CompatibilityConfigError('Each branch requires explicit manifest/member key and IV values')
            try:
                key = base64.b64decode(data[role]['key_base64'], validate=True)
                iv = base64.b64decode(data[role]['iv_base64'], validate=True)
            except (ValueError, TypeError) as exc:
                raise CompatibilityConfigError('Compatibility configuration must use strict base64') from exc
            return KeyIV(key, iv)

        return DefaultCryptoConfig(part('current', 'manifest'), part('current', 'member'),
                                   part('previous', 'manifest'), part('previous', 'member'))

    def selected(self, is_previous_year_return):
        if type(is_previous_year_return) is not bool:
            raise CompatibilityConfigError('Current or previous branch must be explicit')
        return ((self.previous_manifest, self.previous_member) if is_previous_year_return
                else (self.current_manifest, self.current_member))


def compatibility_config_schema():
    """Return a no-secret description for a caller-selected private file."""
    return {
        'format': COMPATIBILITY_FORMAT,
        'branches': ('current', 'previous'),
        'roles': ('manifest', 'member'),
        'fields': ('key_base64', 'iv_base64'),
        'key_bytes': (16, 32),
        'iv_bytes': 16,
        'max_bytes': MAX_CONFIG_BYTES,
        'private_file_mode': 'owner read/write only',
    }


def load_local_compatibility_config(path):
    """Load one caller-selected owner-private config without logging its material."""
    if not isinstance(path, (str, os.PathLike)):
        raise CompatibilityConfigError('Compatibility configuration path is required')
    candidate = Path(path).expanduser()
    try:
        metadata = candidate.lstat()
    except OSError as exc:
        raise CompatibilityConfigError('Compatibility configuration is unavailable') from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise CompatibilityConfigError('Compatibility configuration must be a regular non-symlink file')
    if metadata.st_mode & 0o077 or not 0 < metadata.st_size <= MAX_CONFIG_BYTES:
        raise CompatibilityConfigError('Compatibility configuration must be bounded and owner-private')
    try:
        raw = candidate.read_bytes()
        value = json.loads(raw.decode('utf-8', 'strict'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompatibilityConfigError('Compatibility configuration is not strict UTF-8 JSON') from exc
    return DefaultCryptoConfig.from_mapping(value)


@dataclass(frozen=True)
class EncryptedDocument:
    entity_type: str
    entity_type_code: object
    entity_key: str
    member_name: bytes
    payload: bytes = field(repr=False)
    payload_semantics_validated: bool = False
    editable: bool = False


@dataclass(frozen=True)
class DefaultEncryptedContainer:
    archive: Archive
    manifest_xml: bytes = field(repr=False)
    documents: tuple
    unreferenced_members: tuple
    branch: str
    encrypted_source_sha256: str

    def inventory(self):
        docs = {d.member_name: d for d in self.documents}
        return tuple({
            'member_name': m.name.decode('utf-8', 'strict'),
            'role': ('manifest' if m.name == MANIFEST else
                     'manifest_entity' if m.name in docs else 'unreferenced_retained'),
            'decoded_bytes': (len(self.manifest_xml) if m.name == MANIFEST else
                              len(docs[m.name].payload) if m.name in docs else None),
            'ciphertext_bytes': len(m.payload),
            'ciphertext_sha256': hashlib.sha256(m.payload).hexdigest(),
            'decoded_sha256': (hashlib.sha256(self.manifest_xml if m.name == MANIFEST else docs[m.name].payload).hexdigest()
                               if m.name == MANIFEST or m.name in docs else None),
            'semantic_status': ('manifest_structure' if m.name == MANIFEST else
                                'reader_required' if m.name in docs else 'ciphertext_retained'),
        } for m in self.archive.members)


def _need(ok, text):
    if not ok:
        raise EncryptedContainerError(text)


def _children(parent, name):
    return tuple(n for n in parent if n.tag == '{' + NS + '}' + name)


def _leaf(parent, name):
    found = _children(parent, name)
    _need(len(found) == 1, 'Manifest document requires one ' + name)
    node = found[0]
    _need(not list(node) and not node.attrib, 'Manifest ' + name + ' must be a leaf')
    text = node.text or ''
    _need(bool(text) and '\0' not in text, 'Manifest ' + name + ' must be nonempty')
    return text


def _safe_member_name(raw):
    try:
        text = raw.decode('utf-8', 'strict')
    except UnicodeError as exc:
        raise EncryptedContainerError('Archive member names must be strict UTF-8') from exc
    _need(bool(text) and '\0' not in text and '\\' not in text and not text.startswith('/'),
          'Archive member path is unsupported')
    parts = text.split('/')
    _need(all(part not in ('', '.', '..') for part in parts), 'Archive member path is unsupported')
    _need(all(0x21 <= ord(ch) <= 0x7e for ch in text), 'Archive member path is outside finite profile')
    return text


def _decrypt(ciphertext, material, label):
    try:
        return decrypt_aes_cbc_pkcs7(ciphertext, material.key, material.iv)
    except CryptoInputError as exc:
        raise EncryptedContainerError('Invalid default ' + label + ' ciphertext or compatibility material') from exc


def _manifest(plain):
    _need(0 < len(plain) <= MAX_MANIFEST, 'Decrypted manifest size is unsupported')
    try:
        text = plain.decode('utf-8', 'strict')
    except UnicodeError as exc:
        raise EncryptedContainerError('Decrypted manifest must be UTF-8') from exc
    _need('\0' not in text and '<!DOCTYPE' not in text.upper() and '<!ENTITY' not in text.upper(),
          'Unsafe manifest syntax')
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise EncryptedContainerError('Decrypted manifest XML is malformed') from exc
    _need(root.tag == '{' + NS + '}Manifest', 'Manifest namespace or root is unsupported')
    identity = _children(root, 'intuitIdentity')
    _need(len(identity) <= 1, 'Ambiguous intuitIdentity')
    if identity:
        node = identity[0]
        _need(not list(node) and not node.attrib, 'Unsupported intuitIdentity shape')
        if len(node.text or ''):
            raise UnsupportedEncryptionRoute('Identity-protected containers are not supported yet')
    security = _children(root, 'security')
    _need(len(security) <= 1, 'Ambiguous security block')
    if security:
        raise UnsupportedEncryptionRoute('Password-protected containers are not supported yet')
    groups = _children(root, 'documents')
    _need(len(groups) == 1, 'Manifest requires exactly one documents collection')
    return root


def load_default_encrypted_container(source, *, compatibility, is_previous_year_return):
    """Decode only the selected type0 route after complete archive validation."""
    if isinstance(compatibility, dict):
        compatibility = DefaultCryptoConfig.from_mapping(compatibility)
    if not isinstance(compatibility, DefaultCryptoConfig):
        raise CompatibilityConfigError('Caller must supply DefaultCryptoConfig')
    manifest_material, member_material = compatibility.selected(is_previous_year_return)
    try:
        archive = load_archive(source)
    except UnsupportedProfile as exc:
        raise EncryptedContainerError(str(exc)) from exc
    for member in archive.members:
        _safe_member_name(member.name)
    members = {m.name: m for m in archive.members}
    _need(len(members) == len(archive.members) and len({m.name.lower() for m in archive.members}) == len(members),
          'Ambiguous archive member names')
    _need(MANIFEST in members, 'manifest.xml is required')
    manifest_plain = _decrypt(members[MANIFEST].payload, manifest_material, 'manifest')
    root = _manifest(manifest_plain)
    documents, referenced, seen = [], {MANIFEST}, set()
    for node in _children(_children(root, 'documents')[0], 'document'):
        kind, key = _leaf(node, 'entityType'), _leaf(node, 'entityKey')
        try:
            name = key.encode('utf-8', 'strict')
        except UnicodeError as exc:
            raise EncryptedContainerError('Manifest entityKey must be UTF-8') from exc
        _safe_member_name(name)
        _need(name != MANIFEST and name in members and name not in seen,
              'Every manifest entityKey must name one unique archive member')
        plain = _decrypt(members[name].payload, member_material, 'entity member')
        _need(len(plain) <= MAX_ENTITY, 'Decrypted entity member size is unsupported')
        documents.append(EncryptedDocument(kind, TYPES.index(kind) if kind in TYPES else None, key, name, plain))
        referenced.add(name)
        seen.add(name)
    _need(bool(documents), 'Manifest must list at least one entity member')
    return DefaultEncryptedContainer(archive, manifest_plain, tuple(documents),
                                     tuple(m.name for m in archive.members if m.name not in referenced),
                                     'previous' if is_previous_year_return else 'current',
                                     hashlib.sha256(source).hexdigest())


def read_entities(container, entity_reader):
    """Pass each complete member to an explicit reader; no edit permission is implied."""
    if not isinstance(container, DefaultEncryptedContainer) or not callable(entity_reader):
        raise EncryptedContainerError('Decoded container and explicit entity reader are required')
    results = []
    for document in container.documents:
        parsed = entity_reader(document.payload, document)
        if parsed is None:
            raise EncryptedContainerError('Entity reader must acknowledge every manifest member')
        results.append((document.entity_key, parsed))
    return tuple(results)
