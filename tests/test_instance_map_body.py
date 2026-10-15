"""Owned-only complete stored body cases. No source paths, file I/O or native calls."""
import struct
import unittest
from dataclasses import replace
from interop.form_core.instance_map_formset_body_reference import (
    NAME, StoredPair, load_stored_body, load_named_stored_body, preserve_stored_body,
    clone_stored_body, relocation_evidence, encode_owned_body, typed_raw_body_or_none, UnsupportedProfile)
from interop.form_core.native_mode4_reference import emit_selected_block, Buffers


def framed(payload, count, *, endian=0, compressed=False):
    order = '<' if endian == 0 else '>'
    buffer = Buffers(1000, 2000, 0, 4 if compressed else 0)
    blob = bytes([endian]) + b''.join(emit_selected_block(payload[p:p+65000], buffer, byte_order=order)
                                    for p in range(0, len(payload), 65000))
    return struct.pack('>HII', 1, count, len(blob)) + blob


class StoredBodyTests(unittest.TestCase):
    def setUp(self):
        self.rows = (StoredPair(b'FDI$FSCHB:TEMPA', b'/Return/Temporary/AmountA'),
                     StoredPair(b'FDI$FSCHB:TEMPB', b'/Return/Temporary/AmountB'))
        self.wire = encode_owned_body(self.rows)

    def reject(self, wire):
        with self.assertRaises(UnsupportedProfile):
            load_stored_body(wire)

    def test_complete_stored_block_and_exact_clone(self):
        body = load_stored_body(self.wire)
        self.assertEqual(body.rows, self.rows)
        self.assertEqual(body.source_compression_chunks[0].marker, 15)
        self.assertEqual(preserve_stored_body(body), self.wire)
        self.assertEqual(clone_stored_body(body), body)
        self.assertFalse(body.native_cleanup_executed)
        self.assertFalse(body.native_14D_transfer_executed)
        self.assertFalse(body.native_current_cache_verified)

    def test_compressed_crc_and_last_byte(self):
        row = StoredPair(b'A'*1000, b'B'*2000)
        wire = encode_owned_body((row,), compressed=True)
        body = load_stored_body(wire)
        self.assertEqual(body.rows, (row,))
        self.assertEqual(body.source_compression_chunks[0].marker, 240)
        for position in (16, 17, len(wire)-1):
            altered = bytearray(wire); altered[position] ^= 1
            self.reject(bytes(altered))

    def test_multiblock_and_split_row(self):
        rows = tuple(StoredPair(('addr%04d' % i).encode(), (b'path%04d:' % i)+b'x'*250)
                     for i in range(500))
        for compressed in (False, True):
            wire = encode_owned_body(rows, compressed=compressed)
            body = load_stored_body(wire)
            self.assertGreater(len(body.source_compression_chunks), 1)
            self.assertEqual(body.rows, rows)
            self.assertEqual(preserve_stored_body(body), wire)

    def test_both_actual_stream_byte_orders(self):
        payload = b'A\t/Value\n'
        for endian in (0, 1):
            for compressed in (False, True):
                wire = framed(payload, 1, endian=endian, compressed=compressed)
                body = load_stored_body(wire)
                self.assertEqual(body.compression_endian, endian)
                self.assertEqual(body.decoded_payload, payload)
                self.assertEqual(preserve_stored_body(body), wire)

    def test_source_order_retained_and_first_tab_only(self):
        payload = b'Z\tlast\traw\nA\tfirst\n'
        body = load_stored_body(framed(payload, 2))
        self.assertEqual(body.rows, (StoredPair(b'Z', b'last\traw'), StoredPair(b'A', b'first')))
        self.assertEqual(body.decoded_payload, payload)

    def test_opaque_bytes_case_spaces_and_carriage_return(self):
        payload = b' A\xff\t/Value\r\n a\xfe\t/Other\n'
        body = load_stored_body(framed(payload, 2))
        self.assertEqual(body.rows[0].tps_address, b' A\xff')
        self.assertEqual(body.rows[0].mef_xpath, b'/Value\r')
        self.assertEqual(preserve_stored_body(body), framed(payload, 2))

    def test_version_count_and_empty_asymmetry(self):
        for version in (0, 2, 65535):
            self.reject(struct.pack('>H', version) + self.wire[2:])
        for count in (0, 1, 3, 65536, 0xffffffff):
            self.reject(self.wire[:2]+struct.pack('>I', count)+self.wire[6:])
        self.reject(struct.pack('>HI', 1, 0))
        self.reject(struct.pack('>HII', 1, 0, 1)+b'\0')

    def test_exact_length_and_all_truncations(self):
        for end in range(len(self.wire)):
            self.reject(self.wire[:end])
        for tail in (b'\0', b'unknown', self.wire):
            self.reject(self.wire+tail)
        for delta in (-1, 1, 100):
            self.reject(self.wire[:6]+struct.pack('>I', len(self.wire)-10+delta)+self.wire[10:])

    def test_invalid_compression_headers(self):
        for endian in (2, 15, 255):
            self.reject(self.wire[:10]+bytes([endian])+self.wire[11:])
        for marker in (0, 1, 16, 241, 255):
            self.reject(self.wire[:11]+bytes([marker])+self.wire[12:])
        for count in (0, 65001, 0xffffffff):
            self.reject(self.wire[:12]+struct.pack('<I', count)+self.wire[16:])
        # A second unknown frame cannot hide after a valid first frame.
        blob = self.wire[10:]+b'\x12\x01\0\0\0x'
        self.reject(self.wire[:6]+struct.pack('>I', len(blob))+blob)

    def test_delimiters_and_embedded_nul(self):
        for payload, count in ((b'A\tB', 1), (b'A B\n', 1), (b'\tB\n', 1),
                               (b'A\t\n', 1), (b'A\tB\n\n', 1), (b'A\0X\tB\n', 1),
                               (b'A\tB\0X\n', 1), (b'A\tB\nC\tD', 2),
                               (b'A\tB\nC\tD\n', 1)):
            self.reject(framed(payload, count))

    def test_both_duplicate_key_domains_rejected(self):
        for payload in (b'A\tB\nA\tC\n', b'A\tB\nC\tB\n', b'A\tB\nA\tB\n'):
            self.reject(framed(payload, 2))

    def test_complete_descriptor_and_same_owner_guard(self):
        self.assertEqual(load_named_stored_body(NAME, self.wire, owner_level='formset').rows, self.rows)
        for name in (NAME.lower(), NAME+b'\0', b'TpsInstanceToMefInstanceMapPO', b'MetaDataKeyValueFormSetPO', NAME.decode()):
            with self.assertRaises(UnsupportedProfile):
                load_named_stored_body(name, self.wire, owner_level='formset')
        for owner in ('entity', 'form', 'record', None):
            with self.assertRaises(UnsupportedProfile):
                load_named_stored_body(NAME, self.wire, owner_level=owner)
        proof = relocation_evidence(NAME, self.wire, owner_level='formset',
                                    source_owner_key=b'envelope:entity0/fs1', target_owner_key=b'envelope:entity0/fs1')
        self.assertTrue(proof['source_body_position_independent'])
        self.assertFalse(proof['owner_reassignment_allowed'])
        for key in (b'envelope:entity0/fs2', b'', 'envelope:entity0/fs1'):
            with self.assertRaises(UnsupportedProfile):
                relocation_evidence(NAME, self.wire, owner_level='formset',
                                    source_owner_key=b'envelope:entity0/fs1', target_owner_key=key)

    def test_dataclass_tamper_not_authority(self):
        body = load_stored_body(self.wire)
        for altered in (replace(body, rows=()), replace(body, decoded_payload=b''),
                        replace(body, native_cleanup_executed=True),
                        replace(body, native_current_cache_verified=True),
                        replace(body, source_body=body.source_body+b'\0')):
            with self.assertRaises(UnsupportedProfile):
                preserve_stored_body(altered)

    def test_bounded_owned_constructor(self):
        for rows in ((), [], (StoredPair(b'', b'B'),), (StoredPair(b'A\tC', b'B'),),
                     (StoredPair(b'A', b'B\n'),), (StoredPair(b'A', 'B'),),
                     (StoredPair(b'A', b'B'), StoredPair(b'A', b'C'))):
            with self.assertRaises(UnsupportedProfile):
                encode_owned_body(rows)
        with self.assertRaises(UnsupportedProfile):
            encode_owned_body(self.rows, compressed=1)
        self.assertEqual(load_stored_body(encode_owned_body(tuple(reversed(self.rows)))).rows, self.rows)

    def test_app_classification_never_turns_opaque_into_empty(self):
        self.assertEqual(typed_raw_body_or_none(self.wire), load_stored_body(self.wire))
        for wire in (b'\0\2unknown-version-payload', struct.pack('>HI', 1, 0),
                     struct.pack('>HII', 1, 0, 1)+b'\0'):
            self.assertIsNone(typed_raw_body_or_none(wire))
        for wire in (b'', b'\0', b'\0\1', b'\0\1\0\0\0', self.wire+b'unknown'):
            with self.assertRaises(UnsupportedProfile):
                typed_raw_body_or_none(wire)


if __name__ == '__main__':
    unittest.main()
