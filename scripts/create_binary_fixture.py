#!/usr/bin/env python3
"""Build independent binary examples from owned values and explicit registries.

No original saved return or vendor resource is read. The three XPRF inputs in
fixtures/taxml are independently authored field registries already in this repo.
This script constructs every document, hash node, string record and link itself.
"""
import argparse
import base64
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'web')]

import taxml_wire as wire
from interop.form_core.cx_string_wire_reference import Buffers, initialize
from interop.form_core.entity_formset_reference import EntityHeader, FormSetHeader
from interop.form_core.form_header_map_reference import Header, Parent
from interop.form_core.native_document_reference import (
    Document, FormNode, FormSetNode, LinkRecord, TableRecord, TemplateContext,
    store_document_bytes,
)
from interop.form_core.string_wire_reference import Chunk, Table
from interop.form_core.value_hash_wire_reference import Node, hash_for_nodes

FORMSET = 'S2025US1040PER'
PROFILE = 'tax-reborn-binary-entity-profile-v1'
CARRIERS = (
    ('synthetic-modern-windows-w2.xprf', 'FW2', 41),
    ('synthetic-native-interest.xprf', 'F1099I', 41),
    ('synthetic-native-dividend.xprf', 'F1099D', 42),
)
# The same income boxes as synthetic-mixed-income.xml. These are authored test
# values; the XML document is not parsed or copied to construct the binary.
VALUES = {
    'FW2': {'WAGES': '1234.56', 'FEDTAX': '123.00', 'SSWAGES': '1234.56',
            'SSTAX': '76.54', 'MEDWAGES': '1234.56', 'MEDTAX': '17.90',
            'SSTIPS': '0.00', 'DCB': '0.00'},
    'F1099I': {'L1': '100.23', 'L3': '40.27', 'EXINT': '12.34', 'L4': '20.45'},
    'F1099D': {'L1B': '1200.31', 'QDIV': '300.15', 'L1C': '1000.25',
               'L2C': '150.05', 'L1CTX': '100.05', 'L2': '200.49'},
}
TEXTS = {'NAME': 'INDEPENDENT SAMPLE', 'CA': 'SYNTHETIC EMPLOYER',
         'CA2': 'OWNED TEST DATA'}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def buffers():
    # Successful-allocation tokens for the independent codec, not pointers.
    return initialize(Buffers(), prepared_compressed_pointer=1000,
                      prepared_scratch_pointer=2000).buffers


def string_table(texts):
    """Author the finite 64-slot, one-chunk table from ASCII strings."""
    if not texts:
        return Table()
    if len(texts) > 63:
        raise ValueError('This fixture builder requires a remaining free slot.')
    records = bytearray()
    slots = bytearray(256)
    for handle, text in enumerate(texts):
        value = text.encode('ascii')
        offset = len(records)
        records.extend(struct.pack('<H', handle) + value + b'\0')
        struct.pack_into('<HH', slots, handle * 4, 1, offset + 2)
    if len(records) > 512:
        raise ValueError('Authored fixture strings exceed the finite chunk.')
    for handle in range(len(texts), 64):
        struct.pack_into('<HH', slots, handle * 4, 0,
                         handle + 1 if handle < 63 else 65535)
    return Table(free_head=len(texts), slots=bytes(slots),
                 chunks=(Chunk(bytes(records).ljust(512, b'.'), len(records)),),
                 counter=len(texts))


def registry_inputs():
    blobs = [(ROOT / 'fixtures/taxml' / name).read_bytes()
             for name, _, _ in CARRIERS]
    registry = wire.Registry.from_xprf([(blob, digest(blob)) for blob in blobs])
    templates = [dict(formset_id=FORMSET, form_id=form, resource_id=ident,
                      carrier_sha256=digest(blob))
                 for blob, (_, form, ident) in zip(blobs, CARRIERS)]
    resolved = {entry['form_id']: registry.resolve(
        FORMSET, entry['form_id'], (entry['carrier_sha256'], entry['resource_id']))
        for entry in templates}
    context = TemplateContext(
        template_versions={FORMSET.encode(): 2025},
        field_ids={(FORMSET.encode(), name.encode()):
                   {field.ordinal: field.field_id.encode() for field in template.fields}
                   for name, template in resolved.items()},
        current_table_ids={}, preserve_unresolved_links=True)
    profile = dict(format=PROFILE, tax_year=2025, templates=templates,
                   template_versions={FORMSET: 2025})
    carriers = [dict(base64=base64.b64encode(blob).decode(), sha256=digest(blob))
                for blob in blobs]
    return resolved, context, profile, carriers


def form(template, name, copy_number, table_id, *, values=None, unused=()):
    values = VALUES[name] if values is None else values
    text_fields = [field for field in template.fields
                   if field.kind == 7 and field.field_id in TEXTS]
    handles = {field.field_id: index for index, field in enumerate(text_fields)}
    nodes = []
    for field in template.fields:
        if field.field_id in values:
            if field.kind != 11 or field.format != 0 or field.is_array:
                raise ValueError('Fixture amount requires explicit scalar cent metadata.')
            scaled = Decimal(values[field.field_id]) * 100
            if scaled != scaled.to_integral_value():
                raise ValueError('Fixture amount exceeds cent precision.')
            nodes.append(Node(kind_byte=11, raw=int(scaled) & ((1 << 64) - 1),
                field_index=field.ordinal, exponent_byte=7,
                specific_attributes=2 if field.field_id in unused else 3,
                flag10=0x21, flag11=0x40))
        elif field.field_id in handles:
            nodes.append(Node(kind_byte=7,
                raw=(handles[field.field_id] << 16) | table_id,
                field_index=field.ordinal, specific_attributes=1))
    return FormNode(Header(name.encode(), copy_number, word7c=11,
                           word7e=22, word80=33, word82=44),
        hash_for_nodes(tuple(nodes)),
        string_table([TEXTS[field.field_id] for field in text_fields]), table_id)


def document(templates, *, nested=False, unused=False):
    wages = form(templates['FW2'], 'FW2', 1, 1,
                 unused=('WAGES',) if unused else ())
    if unused:
        # Keep a nonzero unused payload and a distinct present zero. Neither is
        # an absent field, and Used is independent of Computed.
        zeros = {**VALUES['FW2'], 'FEDTAX': '0.00'}
        wages = form(templates['FW2'], 'FW2', 1, 1,
                     values=zeros, unused=('WAGES',))
    interest = form(templates['F1099I'], 'F1099I', 2, 2)
    dividends = form(templates['F1099D'], 'F1099D', 3, 3)
    if nested:
        wage_field = next(field.ordinal for field in templates['FW2'].fields
                          if field.field_id == 'WAGES')
        child = form(templates['F1099I'], 'F1099I', 4, 4,
                     values={key: '0.00' for key in VALUES['F1099I']})
        child = replace(child, header=replace(child.header,
            parent=Parent(b'FW2', 1, 11), parent_field_id=b'WAGES',
            parent_field_index=wage_field),
            links=(LinkRecord(b'FW2', 1, b'WAGES'),))
        # These are structural test associations, not tax-template relationships.
        wages = replace(wages, tables=(TableRecord(b'OWNED_ROWS', 5, 9),),
            children=(child,), links=(LinkRecord(b'F1099D', 3, b'QDIV'),))
        interest = replace(interest, links=(LinkRecord(b'F1099I', 4, b'L1'),))
        dividends = replace(dividends, links=(LinkRecord(b'F1099I', 2, b'L3'),))
    return Document(EntityHeader(serial=20251015,
        producer=b'Tax Reborn independently authored binary sample'),
        (FormSetNode(FormSetHeader(FORMSET.encode(), serial0=17, serial1=23,
          serial2=31, template_version=2025, field20=41),
          (wages, interest, dividends)),))


def build_fixtures(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    templates, context, profile, carriers = registry_inputs()
    entries = {}
    for name, options in [('income', {}), ('nested', {'nested': True}),
                          ('unused-zero', {'unused': True})]:
        payload = store_document_bytes(document(templates, **options), buffers(),
                                       template_context=context)
        request = dict(base64=base64.b64encode(payload).decode(),
                       container='binary_entity', profile=profile,
                       carriers=carriers, profile_acknowledged=True)
        request_bytes = (json.dumps(request, indent=2, sort_keys=True) + '\n').encode()
        (destination / f'{name}.taxbin').write_bytes(payload)
        (destination / f'{name}-request.json').write_bytes(request_bytes)
        entries[name] = dict(binary=f'{name}.taxbin', binary_sha256=digest(payload),
            request=f'{name}-request.json', request_sha256=digest(request_bytes),
            bytes=len(payload), forms=4 if options.get('nested') else 3)
    manifest = dict(format='tax-reborn-independent-binary-fixtures-v1',
        provenance='Independently constructed values, packed nodes, strings and graph; caller-owned synthetic registries only.',
        vendor_resources_included=False, original_saved_return=False,
        original_runtime_executions=0, original_program_acceptance_verified=False,
        expected_income_app_refund=344, entries=entries)
    # The fixture contract compares bytes across Windows and Unix. Avoid the
    # platform text newline translation, as for the request JSON above.
    (destination / 'manifest.json').write_bytes(
        (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    build_setup_fixture(destination)
    build_merged_fixture(destination)
    build_value_table_fixture(destination)
    return manifest


def build_setup_fixture(destination):
    """Author a small registry and box values; no original file is an input."""
    destination = Path(destination)
    formset, name, resource = 'OWNED2025SETUP', 'FINFOWKS', 73
    names = [f'FS{i}' for i in range(1, 6)]
    strings = [name.encode(), formset.encode()]
    body = struct.pack('<H', len(strings)) + b''.join(bytes([len(s)]) + s for s in strings)
    fields = struct.pack('<H', 5) + b''.join(b'\xff'+field.encode().ljust(32,b' ')+struct.pack('<BBI',3,0,0) for field in names)
    records = [(18000, body), (1900, fields)]
    header = b'XPRF\0\1\x10\x0c\x0a\0\0\0'+struct.pack('<I',len(records))
    offset = 16 + 12*len(records)
    entries, payloads = [], []
    for kind, data in records:
        payload = struct.pack('<IIH',len(data)+10,len(data),0)+data
        entries.append(struct.pack('<HHII',kind,resource,offset,len(payload)))
        payloads.append(payload); offset += len(payload)
    carrier = header + b''.join(entries) + b''.join(payloads)
    context = TemplateContext(template_versions={formset.encode():2025},
        field_ids={(formset.encode(),name.encode()):{i:field.encode() for i,field in enumerate(names,1)}},
        current_table_ids={},preserve_unresolved_links=True)
    # Used0 with a retained nonzero payload remains unused. Current format255
    # on a box is independent of template format0 and is ignored by this path.
    nodes = tuple(Node(kind_byte=3,raw=1 if i in (2,5) else 0,field_index=i,
        specific_attributes=2 if i==5 else 3,flag10=255,flag11=64) for i in range(1,6))
    form_node = FormNode(Header(name.encode(),7),hash_for_nodes(nodes),Table(),11)
    doc = Document(EntityHeader(serial=20251015,producer=b'Independently authored filing-status review'),
        (FormSetNode(FormSetHeader(formset.encode(),template_version=2025),(form_node,)),))
    blob = store_document_bytes(doc,buffers(),template_context=context)
    profile = dict(format=PROFILE,tax_year=2025,templates=[dict(formset_id=formset,form_id=name,
        carrier_sha256=digest(carrier),resource_id=resource)],template_versions={formset:2025})
    request = dict(base64=base64.b64encode(blob).decode(),container='binary_entity',
        profile=profile,carriers=[dict(base64=base64.b64encode(carrier).decode(),sha256=digest(carrier))],
        profile_acknowledged=True)
    for filename, data in [('filing-status.xprf',carrier),('filing-status.taxbin',blob),
            ('filing-status-profile.json',(json.dumps(profile,indent=2,sort_keys=True)+'\n').encode()),
            ('filing-status-request.json',(json.dumps(request,indent=2,sort_keys=True)+'\n').encode())]:
        (destination/filename).write_bytes(data)


def owned_xprf(resources):
    """Wrap independently authored decoded resource payloads, without a tool."""
    header=b'XPRF\0\1\x10\x0c\x0a\0\0\0'+struct.pack('<I',len(resources))
    position=16+12*len(resources);directory=[];records=[]
    for (typ,rid),data in resources.items():
        record=struct.pack('<IIH',len(data)+10,len(data),0)+data
        directory.append(struct.pack('<HHII',typ,rid,position,len(record)))
        records.append(record);position+=len(record)
    return header+b''.join(directory)+b''.join(records)


def merged_registry_inputs(*, value_table=False):
    """Two owned carriers select visible/hidden blocks from different homes."""
    old, *_ = registry_inputs()
    fsid='OWNED2025MERGED'
    def metadata(name,version='1',full=True):
        values=[name.encode(),fsid.encode(),version.encode(),b'1']
        if full:
            values += [b'0']*15
            values[16]=b'5'
        return struct.pack('<H',len(values))+b''.join(bytes([len(s)])+s for s in values)
    def fields(values):
        return struct.pack('<H',len(values))+b''.join(b'\xff'+f.field_id.encode().ljust(32,b' ')+struct.pack('<BBI',f.kind,f.format,f.attributes) for f in values)
    alpha={(18000,1):metadata('FW2',full=False),
        (1900,1):fields(old['FW2'].fields[:4]),
        (18000,2):metadata('F1099I'),(1900,2):fields(old['F1099I'].fields),
        (18000,3):metadata('F1099D'),(1900,3):fields(old['F1099D'].fields),
        (18000,4):metadata('OWNED_UNUSED'),}
    beta={(18000,1):metadata('FW2'),(18001,1):metadata('FW2',full=False),
        (1901,1):fields(old['FW2'].fields[4:]),
        (18000,2):metadata('OWNED_UNUSED',version='2')}
    if value_table:
        # One independently authored indexed amount. The current record's
        # presence is independent of both its numeric payload and row index.
        array=wire.Field(field_id='OWNED_AMOUNT',ordinal=12,kind=11,format=0,attributes=0x40)
        beta[1901,1]=fields((*old['FW2'].fields[4:],array))
    blobs=[owned_xprf(alpha),owned_xprf(beta)]
    shas=[digest(blob) for blob in blobs]
    selected={(fsid,'FW2'):(shas[1],1),(fsid,'F1099I'):(shas[0],2),(fsid,'F1099D'):(shas[0],3)}
    registry=wire.Registry.from_effective_xprf(list(zip(blobs,shas)),selected)
    templates={name:registry.resolve(fs,name,identity) for (fs,name),identity in selected.items()}
    context=TemplateContext(template_versions={fsid.encode():2025},
        field_ids={(fsid.encode(),name.encode()):{f.ordinal:f.field_id.encode() for f in template.fields} for name,template in templates.items()},
        current_table_ids={},preserve_unresolved_links=True)
    profile=dict(format='tax-reborn-binary-entity-profile-v2',tax_year=2025,
        template_versions={fsid:2025},registry_order=shas,
        templates=[dict(formset_id=fs,form_id=name,carrier_sha256=identity[0],resource_id=identity[1]) for (fs,name),identity in selected.items()])
    carriers=[dict(base64=base64.b64encode(blob).decode(),sha256=sha) for blob,sha in zip(blobs,shas)]
    return fsid,templates,context,profile,carriers,registry.binding_report


def value_table_inputs():
    fsid,templates,context,profile,carriers,report=merged_registry_inputs(value_table=True)
    context=replace(context,table_factories={(fsid.encode(),b'FW2'):'value_table'},
                    default_table_factory=None)
    profile={**profile,'format':'tax-reborn-binary-entity-profile-v3',
        'table_factories':[dict(formset_id=fsid,form_id='FW2',table_kind='value_table')]}
    return fsid,templates,context,profile,carriers,report


def value_table_document(templates,fsid):
    doc=document(templates,nested=True)
    forms=list(doc.formsets[0].forms);wages=forms[0]
    ordinal=next(f.ordinal for f in templates['FW2'].fields if f.field_id=='OWNED_AMOUNT')
    # Preserve explicit source metadata. This does not simulate the original
    # runtime's Build/UUID callbacks or recompute a last-used record index.
    rows=(Node(kind_byte=11,raw=2500,field_index=ordinal,element_index=1,
               exponent_byte=7,specific_attributes=3),
          Node(kind_byte=11,raw=0,field_index=ordinal,element_index=3,
               exponent_byte=7,specific_attributes=3),
          Node(kind_byte=11,raw=99999,field_index=ordinal,element_index=4,
               exponent_byte=7,specific_attributes=2))
    nodes=tuple(node for buffer in wages.hash_state.buffers for node in buffer.nodes)+rows
    forms[0]=replace(wages,hash_state=hash_for_nodes(nodes),
        tables=(TableRecord(b'OWNED_ROWS',ordinal,ordinal,table_kind='value_table',
                            last_used_record_index=3),))
    return replace(doc,formsets=(replace(doc.formsets[0],
        header=replace(doc.formsets[0].header,identifier=fsid.encode()),forms=tuple(forms)),))


def build_value_table_fixture(destination):
    fsid,templates,context,profile,carriers,report=value_table_inputs()
    doc=value_table_document(templates,fsid)
    blob=store_document_bytes(doc,buffers(),template_context=context)
    request=dict(base64=base64.b64encode(blob).decode(),container='binary_entity',
        profile=profile,carriers=carriers,profile_acknowledged=True)
    for name,data in [('value-table.taxbin',blob),
            ('value-table-request.json',(json.dumps(request,indent=2,sort_keys=True)+'\n').encode()),
            ('value-table-profile.json',(json.dumps(profile,indent=2,sort_keys=True)+'\n').encode()),
            *[(f'value-table-{name}.xprf',base64.b64decode(value['base64'])) for name,value in zip(('alpha','beta'),carriers)]]:
        (Path(destination)/name).write_bytes(data)


def build_merged_fixture(destination):
    fsid,templates,context,profile,carriers,report=merged_registry_inputs()
    destination=Path(destination)
    for name,nested in [('merged',False),('merged-nested',True)]:
        doc=document(templates,nested=nested)
        doc=replace(doc,formsets=tuple(replace(fs,header=replace(fs.header,identifier=fsid.encode())) for fs in doc.formsets))
        blob=store_document_bytes(doc,buffers(),template_context=context)
        request=dict(base64=base64.b64encode(blob).decode(),container='binary_entity',
            profile=profile,carriers=carriers,profile_acknowledged=True)
        (destination/(name+'.taxbin')).write_bytes(blob)
        (destination/(name+'-request.json')).write_bytes((json.dumps(request,indent=2,sort_keys=True)+'\n').encode())
    for name,data in [('merged-profile.json',(json.dumps(profile,indent=2,sort_keys=True)+'\n').encode()),
            ('merged-registry-report.json',(json.dumps(report,indent=2,sort_keys=True)+'\n').encode()),
            *[(f'merged-{name}.xprf',base64.b64decode(value['base64'])) for name,value in zip(('alpha','beta'),carriers)]]:
        (destination/name).write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path,
                        default=ROOT / 'fixtures/binary-tax')
    args = parser.parse_args()
    manifest = build_fixtures(args.output_dir)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
