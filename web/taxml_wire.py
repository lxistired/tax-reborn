"""Independent, bounded TaxML/ZIP interoperability research adapter.

This parses real XML and archive bytes, not an invented intermediate record.
It reads caller-owned XPRF metadata; no original resources, keys or code ship.
Unsupported values remain explicit unresolved records. Original-program
acceptance, engine recalculation and .tax compatibility are not established.
"""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from copy import copy
import datetime as dt
import hashlib
import re
import struct
import xml.etree.ElementTree as ET
import xml.parsers.expat as Expat
import zipfile

TD = "http://www.intuit.com/Ctg/Pta/TurboTax/TaxDataType"
PO = "http://www.intuit.com/Ctg/Pta/TurboTax/PersistentObjects"
MANIFEST_NS = "http://schemas.intuit.com/LocalCfpContainer.xsd"
TAXML_TYPE = "/tax/income/individual/taxreturn/taxml"
VALUE_BITS = {"roundedUp": 1, "ccToken": 8, "approx": 16,
              "valueAlias": 32, "valueAliasChgOK": 64, "error": 128}
SPECIFIC_BITS = {"used": 1, "computed": 2, "converted": 4, "override": 8,
                 "itemized": 16, "dropAssigned": 32, "generalImport": 64,
                 "computedExternally": 128, "convFromState": 256,
                 "autoBlanked": 512, "fixedAssetImport": 1024,
                 "fieldNote": 2048, "calcDefault": 4096,
                 "spouseAmount": 8192, "jointAmount": 16384,
                 "clientEntered": 32768}
SCALES = {10: 0, 11: 2, 12: 0}
BOX_FIELDS = ((1, "WAGES"), (2, "FEDTAX"), (3, "SSWAGES"),
              (4, "SSTAX"), (5, "MEDWAGES"), (6, "MEDTAX"))


class WireError(ValueError):
    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(code + (": " + str(detail) if detail else ""))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def qname(tag):
    if not isinstance(tag, str):
        return "", ""
    if tag.startswith("{"):
        return tuple(tag[1:].split("}", 1))
    return "", tag


def xml(data):
    if not isinstance(data, bytes) or len(data) > 64 * 1024 * 1024:
        raise WireError("xml_size_or_type")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise WireError("xml_declaration_unsupported")
    try:
        # The studied native path explicitly obtains UTF-8 text.
        data.decode("utf-8", errors="strict")
        root = ET.fromstring(data, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True)))
    except (ET.ParseError, UnicodeError) as error:
        raise WireError("invalid_utf8_xml") from error
    stack, count = [(root, 1)], 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if depth > 256 or count > 100000:
            raise WireError("independent_xml_structure_limit")
        stack.extend((child, depth + 1) for child in node)
    return root


def bounded_int(text, maximum):
    if not isinstance(text, str) or not re.fullmatch(r"[0-9]+", text):
        raise WireError("integer_attribute_grammar")
    if len(text) > 10:
        raise WireError("integer_attribute_bound")
    value = int(text)
    if not 0 <= value <= maximum:
        raise WireError("integer_attribute_bound")
    return value


@dataclass(frozen=True)
class Field:
    field_id: str
    ordinal: int
    kind: int
    format: int
    attributes: int
    hidden: bool = False

    @property
    def is_array(self):
        return bool(self.attributes & 0x40)


@dataclass(frozen=True)
class Template:
    formset_id: str
    form_id: str
    carrier_sha256: str
    resource_id: int
    fields: tuple


class Registry:
    def __init__(self, templates=()):
        self.entries = {}
        for template in templates:
            if len({f.field_id for f in template.fields}) != len(template.fields):
                raise WireError("ambiguous_field_dictionary", template.form_id)
            self.entries.setdefault((template.formset_id, template.form_id), []).append(template)

    def resolve(self, formset_id, form_id, selected_profile=None):
        choices = self.entries.get((formset_id, form_id), ())
        if selected_profile is not None:
            sha, rid = selected_profile
            choices = [t for t in choices if (t.carrier_sha256, t.resource_id) == (sha, rid)]
        if len(choices) != 1:
            raise WireError("unknown_or_ambiguous_template", (formset_id, form_id))
        return choices[0]

    @classmethod
    def from_xprf(cls, carriers):
        """carriers is [(owned_file_bytes, independently_expected_sha256), ...].

        All directory entries and record headers are checked, even if their
        type is not interpreted. Current metadata has ID33 + u8 kind + u8
        format + u32 attributes. Array capacities are separate and refused.
        """
        templates = []
        for data, expected_sha in carriers:
            if not isinstance(data, bytes) or len(data) < 16 or len(data) > 128 * 1024 * 1024:
                raise WireError("xprf_size_or_type")
            if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
                raise WireError("carrier_identity_required")
            if digest(data) != expected_sha:
                raise WireError("carrier_identity_mismatch")
            if data[:10] != b"XPRF\0\1\x10\x0c\x0a\0":
                raise WireError("unsupported_xprf_profile")
            count = struct.unpack_from("<I", data, 12)[0]
            end = 16 + 12 * count
            if count > 100000 or end > len(data):
                raise WireError("xprf_directory_bound")
            records = {}
            for i in range(count):
                typ, rid, offset, size = struct.unpack_from("<HHII", data, 16 + 12 * i)
                if (typ, rid) in records or size < 10 or offset < end or offset + size > len(data):
                    raise WireError("xprf_record_bound_or_duplicate")
                record = data[offset:offset + size]
                if struct.unpack_from("<IIH", record) != (size, size - 10, 0):
                    raise WireError("xprf_record_header")
                records[typ, rid] = record[10:]
            for (typ, rid), body in records.items():
                if typ != 18000:
                    continue
                if len(body) < 2:
                    raise WireError("form_metadata_bound")
                n = struct.unpack_from("<H", body)[0]
                at, strings = 2, []
                for _ in range(n):
                    if at >= len(body):
                        raise WireError("form_metadata_bound")
                    size = body[at]
                    at += 1
                    if at + size > len(body):
                        raise WireError("form_metadata_bound")
                    try:
                        strings.append(body[at:at + size].decode("ascii"))
                    except UnicodeError as error:
                        raise WireError("form_metadata_encoding") from error
                    at += size
                if at != len(body) or len(strings) < 2 or not strings[0] or not strings[1]:
                    raise WireError("form_metadata_shape")
                fields = []
                for field_type, hidden in ((1900, False), (1901, True)):
                    values = records.get((field_type, rid))
                    if values is None:
                        continue
                    if len(values) < 2:
                        raise WireError("field_dictionary_bound")
                    num = struct.unpack_from("<H", values)[0]
                    if len(values) != 2 + 39 * num:
                        raise WireError("field_dictionary_shape")
                    for j in range(num):
                        row = values[2 + 39 * j:2 + 39 * (j + 1)]
                        try:
                            name = row[1:33].decode("ascii").rstrip(" ")
                        except UnicodeError as error:
                            raise WireError("field_id_encoding") from error
                        if row[0] != 255 or not name or any(ord(c) < 33 or ord(c) > 126 for c in name):
                            raise WireError("field_id_shape")
                        kind, fmt, attrs = struct.unpack_from("<BBI", row, 33)
                        fields.append(Field(name, len(fields) + 1, kind, fmt, attrs, hidden))
                templates.append(Template(strings[1], strings[0], expected_sha, rid, tuple(fields)))
        return cls(templates)


def decode_flags(attributes):
    unknown = set(attributes) - (VALUE_BITS.keys() | SPECIFIC_BITS.keys() | {"time", "author", "idValue"})
    if unknown:
        raise WireError("unsupported_value_attributes", sorted(unknown))
    value = specific = 0
    for name, bit in {**VALUE_BITS, **SPECIFIC_BITS}.items():
        text = attributes.get(name)
        if text is not None and text not in ("", "true", "false", "0", "1"):
            raise WireError("attribute_grammar", name)
        enabled = (name == "used" and text in (None, "")) or (text is not None and "true" in text)
        if enabled:
            if name in VALUE_BITS:
                value |= bit
            else:
                specific |= bit
    return value, specific


def decode_scalar(spec, text, *, tax_year=2025):
    """Selected ASCII, finite scalar subset; original source text is retained.

    For dates this accepts the observed writer's ISO spellings. The broader
    native legacy grammar, two-digit-year pivot, fallback text, string handles
    and native Julian-day storage are recorded in research, not guessed here.
    """
    if not isinstance(text, str) or "\x00" in text or not text.isascii():
        raise WireError("unsupported_scalar_encoding")
    if spec.is_array:
        raise WireError("array_capacity_unresolved")
    if any(ord(c) < 32 and c not in "\t\n\r" for c in text):
        raise WireError("unsupported_scalar_controls")
    if spec.kind in SCALES:
        if text == "" or not re.fullmatch(r"-?[0-9]{1,9}(?:\.[0-9]{1,9})?", text):
            # Empty native values must not silently become a present zero.
            raise WireError("numeric_grammar_or_empty_presence")
        scale = SCALES[spec.kind]
        amount = Decimal(text)
        if abs(amount) > Decimal("1000000000"):
            raise WireError("independent_numeric_limit")
        mantissa = int(amount.scaleb(scale).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        return {"mantissa": mantissa, "scale": scale, "decimal": str(Decimal(mantissa).scaleb(-scale)),
                "storage": "selected_numeric_mantissa", "native_presence_verified": False}
    if spec.kind == 3:
        if text not in ("0", "1", "false", "true", "X", "x"):
            raise WireError("box_grammar_or_empty_presence")
        return {"checked": text in ("1", "true", "X", "x"), "native_presence_verified": False}
    if spec.kind == 7:
        normalized = text.replace("\n", "\r") if spec.format == 8 else text
        return {"text": normalized, "storage": "logical_string", "native_handle_recovered": False,
                "native_presence_verified": False}
    try:
        if spec.kind == 4 and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
            date = dt.date.fromisoformat(text)
            if date.year < 1800:
                raise WireError("independent_date_year_scope")
            stored = f"{date.month:02d}/{date.day:02d}/{date.year:04d}"
        elif spec.kind == 6 and re.fullmatch(r"[0-9]{4}-[0-9]{2}", text):
            date = dt.date.fromisoformat(text + "-01")
            if date.year < 1800:
                raise WireError("independent_date_year_scope")
            stored = f"{date.month:02d}/{date.year:04d}"
        elif spec.kind == 5 and re.fullmatch(r"[0-9]{2}-[0-9]{2}", text):
            # Original IsDate explicitly uses 1984 for month/day validation.
            date = dt.date.fromisoformat("1984-" + text)
            stored = f"{date.month:02d}/{date.day:02d}"
        else:
            raise WireError("unsupported_scalar_or_date_grammar", spec.kind)
    except ValueError as error:
        if isinstance(error, WireError):
            raise
        raise WireError("invalid_calendar_date") from error
    return {"iso_text": text, "observed_default_storage_text": stored,
            "native_julian_storage_recovered": False, "native_presence_verified": False}


@dataclass
class TaxML:
    original: bytes
    root: object
    registry: Registry
    values: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)
    elements: dict = field(default_factory=dict, repr=False)
    modified: bool = False
    root_qname_bound: bool = False
    namespace_context_writable: bool = False
    outside_document_context_writable: bool = False

    @property
    def source_sha256(self):
        return digest(self.original)

    def patch_value(self, key, new_text):
        """Edit one decoded wire value; always requires explicit original key.

        This does not run the original engine or promise a loadable .tax return.
        Unknown subtrees are retained, never converted into blank/zero values.
        """
        if key not in self.elements:
            raise WireError("unresolved_or_unknown_edit_target")
        element, spec = self.elements[key]
        scalar = decode_scalar(spec, new_text)
        element.text = new_text
        self.modified = True
        for value in self.values:
            if value["key"] == key:
                value.update(edited_text=new_text, scalar=scalar, locally_edited=True)

    def serialize(self):
        if not self.modified:
            return self.original
        if not self.namespace_context_writable:
            raise WireError("unpreserved_namespace_context")
        if not self.outside_document_context_writable:
            raise WireError("unpreserved_outside_document_context")
        ET.register_namespace("td", TD)
        ET.register_namespace("po", PO)
        return ET.tostring(self.root, encoding="utf-8", xml_declaration=True)


def read_taxml(data, registry, *, profiles=None, namespace_profile=None, root_qname=None):
    """Deserialize the studied entity→formset→form→field→td:value hierarchy.

    The native formset ID is tpsPrefix + local element name. The adapter checks
    required header integers but cannot validate their original runtime meaning.
    Every unfamiliar field, row, link, scalar or persistent object is unresolved.
    No partial list is ever labeled an imported tax return.
    """
    root = xml(data)
    document = TaxML(data, root, registry)
    # ElementTree can discard prefixes used only inside opaque QName-valued
    # strings. Preserve originals unchanged; refuse edited output unless every
    # lexical binding can be retained with the fixed serializer prefixes.
    retained_bindings = {"td": TD, "po": PO, "xml": "http://www.w3.org/XML/1998/namespace"}
    namespace_writable = [True]
    outside_writable, depth = [True], [0]
    namespace_parser = Expat.ParserCreate(namespace_separator="}")
    def namespace_binding(prefix, uri):
        if retained_bindings.get(prefix) != uri:
            namespace_writable[0] = False
    namespace_parser.StartNamespaceDeclHandler = namespace_binding
    namespace_parser.StartElementHandler = lambda name, attrs: depth.__setitem__(0, depth[0] + 1)
    namespace_parser.EndElementHandler = lambda name: depth.__setitem__(0, depth[0] - 1)
    def outside_context(*_):
        if depth[0] == 0:
            outside_writable[0] = False
    namespace_parser.ProcessingInstructionHandler = outside_context
    namespace_parser.CommentHandler = outside_context
    namespace_parser.Parse(data, True)
    document.namespace_context_writable = namespace_writable[0]
    document.outside_document_context_writable = outside_writable[0]
    profiles = {} if profiles is None else profiles
    # This binding comes from the caller's verified wire profile, never from
    # whichever arbitrary xmlns declaration happens to occur in the input.
    namespace_profile = {"formset": ("",), "form": ("",), "field": ("",)} if namespace_profile is None else namespace_profile
    if set(namespace_profile) != {"formset", "form", "field"} or any(
            not isinstance(v, tuple) or not v or any(not isinstance(n, str) for n in v)
            for v in namespace_profile.values()):
        raise WireError("namespace_profile_shape")

    def pending(path, code, detail=""):
        document.unresolved.append({"path": path, "code": code, "detail": str(detail)})

    if root_qname is None:
        pending("", "root_identity_unbound")
    elif not isinstance(root_qname, str) or root.tag != root_qname:
        pending("", "root_identity_mismatch")
        return document
    else:
        document.root_qname_bound = True

    identities = {}
    for formset in root:
        ns, local = qname(formset.tag)
        if not local or ns not in namespace_profile["formset"]:
            continue
        fs_id = formset.get("tpsPrefix", "") + local
        for form in formset:
            ns, local_form = qname(form.tag)
            if not local_form or ns not in namespace_profile["form"]:
                continue
            try:
                copy_number = bounded_int(form.get("copyNum", "0"), 0x7ffe)
            except WireError:
                continue
            identity = fs_id, local_form, copy_number
            identities[identity] = identities.get(identity, 0) + 1

    for si, formset in enumerate(root):
        ns, local = qname(formset.tag)
        if not local:
            continue
        spath = f"{si}"
        if ns == PO:
            pending(spath, "persistent_object_unresolved")
            continue
        if ns not in namespace_profile["formset"]:
            pending(spath, "unbound_formset_namespace", ns)
            continue
        formset_attributes = {"tpsPrefix", "checksum", "dataVersion", "formsetAttribute", "uuid",
                              "showSmartWorksheets", "sharedForAllDataVersion", "sharedForFSDataVersion",
                              "implementationVersion"}
        if set(formset.attrib) - formset_attributes:
            pending(spath, "unresolved_formset_attributes", sorted(set(formset.attrib) - formset_attributes))
            continue
        formset_id = formset.get("tpsPrefix", "") + local
        try:
            for name, maximum in (("checksum", 0xfffffffe), ("dataVersion", 0xfffffffe),
                                  ("formsetAttribute", 0x7ffe)):
                bounded_int(formset.attrib.get(name), maximum)
        except WireError as error:
            pending(spath, error.code, "formset header")
            continue
        for fi, form in enumerate(formset):
            ns, form_id = qname(form.tag)
            if not form_id:
                continue
            fpath = f"{si}/{fi}"
            if ns == PO:
                pending(fpath, "persistent_object_unresolved")
                continue
            if ns not in namespace_profile["form"]:
                pending(fpath, "unbound_form_namespace", ns)
                continue
            allowed_form_attributes = {"copyNum", "fileCopyNum", "porIndex", "uuid"}
            if set(form.attrib) - allowed_form_attributes:
                pending(fpath, "unresolved_form_attributes", sorted(set(form.attrib) - allowed_form_attributes))
                continue
            incompatible_children = False
            for hi, child in enumerate(form):
                child_ns, child_name = qname(child.tag)
                if not child_name or child_ns == PO:
                    continue
                if child_ns not in namespace_profile["field"]:
                    pending(f"{si}/{fi}/{hi}", "unbound_field_namespace", child_ns)
                    incompatible_children = True
                extra_attributes = set(child.attrib) - {"element", "row", "fileCopyNum", "orphaned"}
                if extra_attributes:
                    pending(f"{si}/{fi}/{hi}", "unresolved_field_attributes", sorted(extra_attributes))
                    incompatible_children = True
            if incompatible_children:
                continue
            try:
                template = registry.resolve(formset_id, form_id, profiles.get((formset_id, form_id)))
                copy_number = bounded_int(form.get("copyNum", "0"), 0x7ffe)
                file_copy_number = bounded_int(form.attrib.get("fileCopyNum"), 0xfffffffe)
                if "porIndex" in form.attrib:
                    bounded_int(form.attrib["porIndex"], 0x7ffe)
                if identities.get((formset_id, form_id, copy_number), 0) > 1:
                    raise WireError("duplicate_form_copy_identity")
            except WireError as error:
                pending(fpath, error.code, form_id)
                continue
            field_map = {field.field_id: field for field in template.fields}
            field_counts = {}
            for child in form:
                ns, name = qname(child.tag)
                if name and ns != PO and "row" not in child.attrib:
                    field_counts[name] = field_counts.get(name, 0) + 1
            observed_ids = set()
            for hi, wire_field in enumerate(form):
                ns, field_id = qname(wire_field.tag)
                if not field_id:
                    continue
                hpath = f"{si}/{fi}/{hi}"
                if ns == PO or "row" in wire_field.attrib:
                    pending(hpath, "persistent_or_row_unresolved")
                    continue
                spec = field_map.get(field_id)
                if spec is None or field_id in observed_ids or field_counts.get(field_id, 0) > 1:
                    pending(hpath, "unknown_or_duplicate_field", field_id)
                    continue
                observed_ids.add(field_id)
                if spec.is_array or wire_field.get("element", "0") != "0":
                    pending(hpath, "array_capacity_unresolved", field_id)
                    continue
                children = [e for e in wire_field if qname(e.tag)[1]]
                if len(children) != 1 or children[0].tag != "{" + TD + "}value" or len(children[0]):
                    pending(hpath, "value_link_or_nested_structure_unresolved", field_id)
                    continue
                value = children[0]
                text = value.text or ""
                try:
                    value_flags, specific_flags = decode_flags(value.attrib)
                    if specific_flags & 2:
                        raise WireError("computed_loader_context_unresolved")
                    scalar = decode_scalar(spec, text)
                except WireError as error:
                    pending(hpath, error.code, field_id)
                    continue
                key = hpath + "/0"
                record = {"key": key, "formset_id": formset_id, "form_id": form_id,
                          "copy_number": copy_number, "file_copy_number": file_copy_number,
                          "field_id": field_id, "field_ordinal": spec.ordinal,
                          "kind": spec.kind, "format": spec.format,
                          "source_qnames": {"formset": formset.tag, "form": form.tag, "field": wire_field.tag,
                                            "value": value.tag},
                          "template_carrier_sha256": template.carrier_sha256,
                          "template_resource_id": template.resource_id,
                          "source_text": text, "source_attributes": dict(value.attrib),
                          "source_value_flags": value_flags, "source_specific_flags": specific_flags,
                          "source_owner_flags": {"spouseAmount": bool(specific_flags & 8192),
                                                 "jointAmount": bool(specific_flags & 16384)},
                          "scalar": scalar, "native_setter_or_recalculation_verified": False}
                document.values.append(record)
                document.elements[key] = value, spec
    return document


def w2_candidates(document):
    """Reviewed candidates only. Never overwrite current tax data automatically.

    Each amount retains wire text, original source identity and cents storage.
    Owner is deliberately unresolved: per-value owner flags cannot establish
    the original statement's taxpayer/spouse membership on their own.
    """
    if not document.root_qname_bound:
        return []
    forms = {}
    for value in document.values:
        if value["form_id"] == "FW2":
            forms.setdefault(value["key"].rsplit("/", 2)[0], []).append(value)
    result = []
    for path, values in forms.items():
        if values[0]["copy_number"] == 0:
            continue
        fields = {v["field_id"]: v for v in values}
        boxes, unresolved = [], []
        for number, field_id in BOX_FIELDS:
            value = fields.get(field_id)
            if value is None or value["kind"] != 11 or value["scalar"].get("scale") != 2:
                unresolved.append({"box": number, "field_id": field_id, "reason": "missing_or_unsupported"})
                continue
            boxes.append({"box": number, "field_id": field_id, "source_text": value["source_text"],
                          "amount": value["scalar"]["decimal"], "original_kind": 11,
                          "original_storage_scale": 2, "source_owner_flags": value["source_owner_flags"],
                          "locally_edited": value.get("locally_edited", False),
                          "current_wire_text": value.get("edited_text", value["source_text"]),
                          "source_value_flags": value["source_value_flags"],
                          "source_specific_flags": value["source_specific_flags"],
                          "source_value_key": value["key"], "requires_review": True})
        # Source field captions bind CA to employer name; NAME is a separate
        # form-level name. They must never be treated as interchangeable.
        name = fields.get("CA", {}).get("scalar", {}).get("text")
        continued = fields.get("CA2", {}).get("scalar", {}).get("text")
        result.append({"source_sha256": document.source_sha256, "form_path": path,
                       "employer_name_candidate": name, "employer_name_continued_candidate": continued,
                       "source_name_metadata": fields.get("NAME", {}).get("scalar", {}).get("text"),
                       "boxes": boxes,
                       "unresolved_boxes": unresolved, "owner": None,
                       "owner_requires_review": True, "tax_values_imported": False,
                       "original_return_acceptance_verified": False})
    return result


@dataclass
class Archive:
    original: bytes
    members: dict
    infos: tuple
    manifest: object = None
    documents: tuple = ()
    manifest_status: str = "opaque"
    comment: bytes = b""

    def write(self, replacements=None, *, encode_payload=None):
        """Preserve the whole ZIP and extra members; edit only referenced blobs.

        A caller-supplied encoder is needed for encrypted payloads. No bundled
        keys or password search. This only writes the outer archive; original
        internal document loading and recalculation remain unverified.
        """
        replacements = {} if replacements is None else dict(replacements)
        if not replacements:
            return self.original
        if self.manifest is None:
            raise WireError("opaque_manifest_cannot_edit")
        keys = {d["member"] for d in self.documents}
        if set(replacements) - keys:
            raise WireError("unreferenced_replacement")
        out = BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.comment = self.comment
            for original_info in self.infos:
                info = copy(original_info)
                data = self.members[info.filename]
                if info.filename in replacements:
                    data = replacements[info.filename]
                    if not isinstance(data, bytes):
                        raise WireError("replacement_type")
                    if self.manifest_status == "decoded_by_caller":
                        if encode_payload is None:
                            raise WireError("payload_encoder_required")
                        data = encode_payload(info.filename, data)
                        if not isinstance(data, bytes):
                            raise WireError("payload_encoder_type")
                z.writestr(info, data)
        return out.getvalue()


def read_archive(data, *, declared_plaintext=False, decode_manifest=None):
    if not isinstance(data, bytes) or len(data) > 256 * 1024 * 1024:
        raise WireError("archive_size_or_type")
    try:
        z = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as error:
        raise WireError("invalid_zip") from error
    with z:
        infos = tuple(z.infolist())
        if len(infos) > 10000 or sum(i.file_size for i in infos) > 256 * 1024 * 1024:
            raise WireError("archive_expanded_size_limit")
        if len({i.filename for i in infos}) != len(infos):
            raise WireError("duplicate_zip_members")
        if any(i.flag_bits & 1 or i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) for i in infos):
            raise WireError("unsupported_zip_encryption_or_compression")
        try:
            members = {i.filename: z.read(i) for i in infos}
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
            raise WireError("zip_member_integrity") from error
        comment = z.comment
    if "manifest.xml" not in members:
        raise WireError("missing_manifest")
    archive = Archive(data, members, infos, comment=comment)
    if decode_manifest is not None:
        plain = decode_manifest(members["manifest.xml"])
        archive.manifest_status = "decoded_by_caller"
    elif declared_plaintext:
        plain = members["manifest.xml"]
        archive.manifest_status = "declared_plaintext"
    else:
        return archive
    root = xml(plain)
    if root.tag != "{" + MANIFEST_NS + "}Manifest":
        raise WireError("unsupported_manifest_namespace")
    for name in ("intuitIdentity", "security", "documents", "relationships"):
        if len(root.findall("{" + MANIFEST_NS + "}" + name)) > 1:
            raise WireError("ambiguous_manifest_section", name)
    # Identity/local-security contexts remain external. Declared plaintext must
    # never imply that encrypted payloads have become readable tax values.
    identity = root.find("{" + MANIFEST_NS + "}intuitIdentity")
    security = root.find("{" + MANIFEST_NS + "}security")
    if declared_plaintext and ((identity is not None and identity.text) or security is not None):
        raise WireError("document_key_context_required")
    docs = []
    seen = set()
    for document in root.findall("{" + MANIFEST_NS + "}documents/{" + MANIFEST_NS + "}document"):
        def text(name):
            matches = document.findall("{" + MANIFEST_NS + "}" + name)
            if len(matches) != 1 or not matches[0].text:
                raise WireError("missing_or_duplicate_manifest_field", name)
            return matches[0].text
        member, entity_type = text("entityKey"), text("entityType")
        if member in seen or member not in members:
            raise WireError("duplicate_or_missing_document_member")
        seen.add(member)
        docs.append({"member": member, "entity_type": entity_type,
                     "payload_bytes": len(members[member]), "taxml_type": entity_type == TAXML_TYPE,
                     "payload_decoded": False, "tax_values_imported": False})
    archive.manifest, archive.documents = root, tuple(docs)
    return archive
