"""Authored single-buffer I/O acceptance, without original resources or sidecars."""
import struct
import unittest
from dataclasses import replace

from interop.form_core import (
    Header, Node, UnsupportedProfile, find_value, hash_for_nodes,
    load_form_core_bytes, store_form_core,
    load_selected_form_record, store_selected_form_record,
)
from interop.form_core.cx_string_wire_reference import Buffers, initialize
from interop.form_core.string_wire_reference import Chunk, Table


def authored_table(text):
    """Create owned memory records; no vendor fixture is loaded."""
    if not isinstance(text, bytes) or not 1 <= len(text) <= 509:
        raise ValueError("one authored ASCII string of 1..509 bytes")
    data = struct.pack("<H", 0) + text + b"\0"
    slots = bytearray(256)
    struct.pack_into("<HH", slots, 0, 1, 2)
    for handle in range(1, 64):
        struct.pack_into("<HH", slots, handle * 4, 0,
                         handle + 1 if handle < 63 else 65535)
    return Table(free_head=1, slots=bytes(slots),
                 chunks=(Chunk(data.ljust(512, b"."), len(data)),), counter=1)


def prepared_buffers():
    # These are successful-allocation model tokens, never live native pointers.
    return initialize(Buffers(), prepared_compressed_pointer=1000,
                      prepared_scratch_pointer=2000).buffers


def authored_core(text=b"SYNTHETIC PERSON", *, base=0):
    nodes = (
        Node(field_index=23, raw=2, kind_byte=7, header=0x80,
             flag10=0x21, flag11=0x80, specific_attributes=0x4321),
        Node(field_index=27, raw=123456, kind_byte=11,
             exponent_byte=2, header=0x40, specific_attributes=9),
    )
    return store_form_core(Header(b"OWNED-FORM", 17), hash_for_nodes(nodes),
                           authored_table(text), prepared_buffers(),
                           base_position=base)


class BinaryFormCoreAcceptance(unittest.TestCase):
    def test_reads_actual_bytes_without_writer_sidecar(self):
        wire = bytes(authored_core().prefix.wire_prefix)
        loaded = load_form_core_bytes(wire, prepared_buffers())
        self.assertEqual(loaded.code, 0)
        self.assertTrue(loaded.single_buffer_reader)
        self.assertEqual(loaded.name, b"SYNTHETIC PERSON")
        self.assertEqual(loaded.header.identifier, b"OWNED-FORM")
        self.assertEqual(loaded.header.file_copy, 17)
        self.assertEqual(loaded.saved_table_id, 2)
        self.assertEqual(loaded.consumed, len(wire))
        self.assertFalse(loaded.whole_form_proven)

    def test_keeps_numeric_payload_and_value_attributes_separate(self):
        loaded = load_form_core_bytes(authored_core().prefix.wire_prefix,
                                      prepared_buffers())
        string = find_value(loaded.hash_state, 23, 0)
        number = find_value(loaded.hash_state, 27, 0)
        self.assertEqual((string.raw, string.header, string.flag10,
                          string.flag11, string.specific_attributes),
                         (3, 0x80, 0x21, 0x80, 0x4321))
        self.assertEqual((number.raw, number.kind_byte, number.exponent_byte,
                          number.specific_attributes), (123456, 11, 2, 9))

    def test_edit_write_and_reload_retain_other_field(self):
        original = load_form_core_bytes(authored_core().prefix.wire_prefix,
                                        prepared_buffers())
        saved = store_form_core(original.header, original.hash_state,
                                authored_table(b"EDITED SYNTHETIC PERSON"),
                                prepared_buffers(), table_id=3)
        reloaded = load_form_core_bytes(saved.prefix.wire_prefix,
                                        prepared_buffers(), current_table_id=4)
        self.assertEqual(reloaded.name, b"EDITED SYNTHETIC PERSON")
        self.assertEqual(find_value(reloaded.hash_state, 23, 0).raw, 4)
        self.assertEqual(find_value(reloaded.hash_state, 27, 0),
                         find_value(original.hash_state, 27, 0))

    def test_nonzero_stream_base(self):
        wire = authored_core(base=1000).prefix.wire_prefix
        self.assertEqual(load_form_core_bytes(wire, prepared_buffers(),
                                              base_position=1000).name,
                         b"SYNTHETIC PERSON")

    def test_compressed_509_byte_string(self):
        wire = authored_core(b"A" * 509).prefix.wire_prefix
        self.assertEqual(load_form_core_bytes(wire, prepared_buffers()).name,
                         b"A" * 509)

    def test_marks_unparsed_tail_instead_of_claiming_whole_return(self):
        wire = authored_core().prefix.wire_prefix
        loaded = load_form_core_bytes(wire + b"UNPARSED-TAIL", prepared_buffers())
        self.assertEqual(loaded.consumed, len(wire))
        self.assertFalse(loaded.whole_form_proven)

    def test_corrupted_compressed_string_crc_returns_error(self):
        core = authored_core(b"A" * 509)
        wire = bytearray(core.prefix.wire_prefix)
        string_at = core.prefix.mapping.base + core.prefix.mapping.offsets[2]
        self.assertEqual(wire[string_at + 36], 0xF0)
        wire[string_at + 41] ^= 1
        loaded = load_form_core_bytes(bytes(wire), prepared_buffers())
        self.assertEqual(loaded.code, 0x9D)
        self.assertEqual(loaded.string_table.slots, b"")

    def test_incomplete_index_is_refused(self):
        wire = authored_core().prefix.wire_prefix
        with self.assertRaises(UnsupportedProfile):
            load_form_core_bytes(wire[:30], prepared_buffers())

    def test_unknown_kind_is_preserved_without_string_conversion(self):
        node = Node(field_index=23, raw=2, kind_byte=0x17)
        saved = store_form_core(Header(b"OWNED-FORM", 1),
                                hash_for_nodes((node,)), authored_table(b"OWNED"),
                                prepared_buffers())
        loaded = load_form_core_bytes(saved.prefix.wire_prefix, prepared_buffers())
        self.assertIsNone(loaded.name)
        self.assertEqual(find_value(loaded.hash_state, 23, 0), node)

    def selected_record(self):
        core = authored_core()
        return store_selected_form_record(Header(b"OWNED-FORM", 17),
            core.hash_result.state, authored_table(b"SYNTHETIC PERSON"),
            prepared_buffers())

    def test_entire_selected_record_reads_actual_empty_tail_bytes(self):
        saved = self.selected_record()
        expected_tail = b"".join(bytes([mark]) + b"\0\1\0\1\x09\0\0\0"
                                  for mark in (0xE0, 0xC8, 0xD7))
        self.assertEqual(saved.wire[-27:], expected_tail)
        loaded = load_selected_form_record(saved.wire, prepared_buffers())
        self.assertEqual(loaded.code, 0)
        self.assertEqual(loaded.consumed, len(saved.wire))
        self.assertTrue(loaded.entire_selected_form_record_consumed)
        self.assertFalse(loaded.whole_tax_compatibility)
        self.assertEqual(loaded.core.name, b"SYNTHETIC PERSON")

    def test_selected_record_edit_write_read(self):
        loaded = load_selected_form_record(self.selected_record().wire,
                                            prepared_buffers())
        edited = store_selected_form_record(loaded.core.header,
            loaded.core.hash_state, authored_table(b"EDITED OWNER"),
            prepared_buffers(), table_id=3)
        result = load_selected_form_record(edited.wire, prepared_buffers(),
                                           current_table_id=4)
        self.assertEqual(result.core.name, b"EDITED OWNER")
        self.assertEqual(find_value(result.core.hash_state, 27, 0),
                         find_value(loaded.core.hash_state, 27, 0))

    def test_nonempty_children_are_refused_without_silent_data_loss(self):
        core = authored_core()
        with self.assertRaises(UnsupportedProfile):
            store_selected_form_record(Header(b"OWNED-FORM", 1),
                core.hash_result.state, authored_table(b"OWNED"),
                prepared_buffers(), children=(object(),))

    def test_selected_record_extra_tail_requires_explicit_policy(self):
        wire = self.selected_record().wire
        with self.assertRaises(UnsupportedProfile):
            load_selected_form_record(wire + b"UNPARSED", prepared_buffers())
        loaded = load_selected_form_record(wire + b"UNPARSED", prepared_buffers(),
                                            allow_trailing=True)
        self.assertEqual(loaded.consumed, len(wire))
        self.assertFalse(loaded.entire_selected_form_record_consumed)


if __name__ == "__main__":
    unittest.main()
