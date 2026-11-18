"""Bounded board recording tests; the private recipient test uses real HPKE."""
import ast
from dataclasses import replace
import json
from pathlib import Path
import unittest

from merlin.titan_board_encoding import (
    BoardGeometry, BoardMove, BoardRecord, HANDOFF_OFFSETS, HANDOFF_SHAPE,
    MAX_PAYLOAD_BYTES, NOVEMBER_PROFILE, OCTOBER_PROFILE, advance_ko,
    coordinate_index, decode_board_record, decode_private_board_message,
    empty_board_record, encode_board_record, encode_private_board_message,
    handoff_board_record, handoff_geometry, index_coordinate, neighbor_indices,
    operational_board_record, public_board_context, replay_board_record, synthetic_board_example,
)
from merlin.titan_protocol_model import canonical_json_bytes


class TitanBoardEncodingTests(unittest.TestCase):
    def test_october_profile_preserves_exact_original_grid_and_stencil(self):
        record = handoff_board_record()
        self.assertEqual(record.profile, OCTOBER_PROFILE)
        self.assertEqual(record.geometry.shape, (7, 7, 7))
        self.assertEqual(len(record.initial_boards), 3)
        self.assertEqual(tuple(len(board) for board in record.initial_boards), (343, 343, 343))
        self.assertEqual(record.ko_register, (0,) * 16)
        self.assertEqual(neighbor_indices(record.geometry, (0, 0, 0)), (1, 6, 7, 42, 49, 294, 8, 48, 43, 13, 56, 336))
        self.assertNotIn((1, 0, 1), HANDOFF_OFFSETS)  # Do not replace the actual asymmetric diagonal selection.
        self.assertEqual(decode_board_record(encode_board_record(record)), record)

    def test_axis_zero_fast_indexing_and_higher_dimensional_inverse(self):
        self.assertEqual(coordinate_index((2, 3, 4), HANDOFF_SHAPE), 2 + 7 * 3 + 49 * 4)
        for shape in ((7, 7, 7), (3, 4, 5, 2), (2,) * 8):
            count = 1
            for axis in shape: count *= axis
            for index in range(count):
                self.assertEqual(coordinate_index(index_coordinate(index, shape), shape), index)
        offsets = ((1, 0, 0, 0), (-1, 0, 0, 0), (0, 0, 0, 1))
        record = empty_board_record(BoardGeometry((3, 4, 5, 2), offsets, True, "explicit4d-recording/1"))
        self.assertEqual(decode_board_record(encode_board_record(record)), record)

    def test_november_default_example_has_three19_cubes_mirror_and_real_bijections(self):
        record = synthetic_board_example()
        self.assertEqual(record.profile, NOVEMBER_PROFILE)
        self.assertEqual(record.geometry.shape, (19, 19, 19))
        self.assertEqual(sum(len(board) for board in record.initial_boards), 20577)
        self.assertTrue(all(len(set(permutation)) == 6859 for permutation in record.permutations))
        self.assertTrue(all(permutation != tuple(range(6859)) for permutation in record.permutations))
        mirror = record.permutations[0][coordinate_index((1, 2, 3), record.geometry.shape)]
        self.assertEqual(record.initial_boards[0][mirror], 3)
        self.assertEqual(replay_board_record(record)[0][mirror], 3)
        raw = encode_board_record(record)
        self.assertEqual(decode_board_record(raw), record)
        self.assertEqual(encode_board_record(decode_board_record(raw)), raw)
        value = json.loads(raw)
        self.assertFalse(value["qualification"]); self.assertFalse(value["promotion_authority"])
        self.assertIn("not_go_legality", value["validation_scope"])
        self.assertIn("history_relation_not_verified", value["ko_validation"])

    def test_recorded_move_and_capture_use_logical_to_storage_mapping(self):
        record = handoff_board_record(); count = 343
        permutation = tuple((5 * index + 17) % count for index in range(count))
        boards = list(record.initial_boards); board = bytearray(boards[0])
        board[permutation[1]] = 2; boards[0] = bytes(board)
        record = replace(record, initial_boards=tuple(boards), permutations=(permutation,) + record.permutations[1:],
                         moves=(BoardMove(0, 1, (0, 0, 0), ((1, 0, 0),)),))
        final = replay_board_record(record)
        self.assertEqual(final[0][permutation[0]], 1); self.assertEqual(final[0][permutation[1]], 0)
        self.assertEqual(decode_board_record(encode_board_record(record)), record)

    def test_mirror_stones_cannot_be_placed_over_or_captured(self):
        record = synthetic_board_example()
        for move in (BoardMove(0, 1, (1, 2, 3)), BoardMove(0, 1, (0, 0, 0), ((1, 2, 3),)), BoardMove(0, 3, (0, 0, 0))):
            with self.subTest(move=move), self.assertRaises(ValueError):
                replay_board_record(replace(record, moves=(move,)))
        old = handoff_board_record(); board = bytearray(old.initial_boards[0]); board[0] = 3
        with self.assertRaises(ValueError): replay_board_record(replace(old, initial_boards=(bytes(board),) + old.initial_boards[1:]))

    def test_ko_fifo_is_exact_uint8_bookkeeping_not_a_security_test(self):
        result = advance_ko(tuple(range(16)), 342, 12)
        self.assertEqual(result, tuple(range(1, 16)) + (98,))
        for register, node, cleared in (((0,) * 15, 1, 0), ((0,) * 15 + (256,), 1, 0), ((0,) * 16, True, 0), ((0,) * 16, 1, -1)):
            with self.assertRaises(ValueError): advance_ko(register, node, cleared)

    def test_plain_serialization_preserves_arbitrary_original_bytes(self):
        message = bytes(range(256)) + b"\x00\xff\xfeoriginal message\x00"
        record = synthetic_board_example(); raw = encode_private_board_message(message, record)
        self.assertEqual(decode_private_board_message(raw), (message, record))
        self.assertEqual(encode_private_board_message(*decode_private_board_message(raw)), raw)
        self.assertEqual(decode_private_board_message(encode_private_board_message(b"", record))[0], b"")

    def test_public_context_is_constant_generic_labels_with_no_record_input(self):
        self.assertEqual(public_board_context(), {"purpose": "titan-private-payload", "schema": "titan-private-payload/1"})
        context = public_board_context(); context["purpose"] = "changed"
        self.assertNotEqual(context, public_board_context())
        with self.assertRaises(TypeError): public_board_context(synthetic_board_example())

    def test_real_post_quantum_recipient_roundtrip_and_same_bucket_shape_privacy(self):
        from merlin.titan_pq_envelope import encrypt, decrypt, generate_recipient_keypair, TitanDecryptionError
        public, secret = generate_recipient_keypair(); context = public_board_context()
        record = synthetic_board_example(); message = b"\x00arbitrary original bytes\xff" + bytes(range(256))
        payload = encode_private_board_message(message, record)
        envelope = encrypt(payload, public, context, pad_to=262144)
        recovered = decrypt(envelope, secret, context)
        self.assertEqual(decode_private_board_message(recovered), (message, record))
        other = encrypt(encode_private_board_message(b"different", handoff_board_record()), public, context, pad_to=262144)
        self.assertEqual(len(envelope), len(other))
        self.assertNotEqual(envelope, other)
        header = json.loads(envelope)["header"]
        self.assertEqual(header, json.loads(other)["header"])
        self.assertEqual(header["context"], context)
        for field in ("shape", "ko_register", "permutations_u32le_b64", "message_b64", "profile", "plaintext_sha256"):
            self.assertNotIn(('"' + field + '"').encode(), envelope)
        _, wrong_secret = generate_recipient_keypair()
        with self.assertRaisesRegex(TitanDecryptionError, "^decryption failed$"):
            decrypt(envelope, wrong_secret, context)
        with self.assertRaises(TitanDecryptionError): decrypt(envelope, secret, {**context, "purpose": "another-purpose"})

    def test_bounds_reject_bad_geometry_permutations_boards_and_moves(self):
        for shape in ((7, 7), (19,) * 8, (True, 7, 7)):
            with self.assertRaises(ValueError): BoardGeometry(shape, HANDOFF_OFFSETS)
        record = handoff_board_record()
        for changed in (replace(record, initial_boards=record.initial_boards[:2]),
                        replace(record, permutations=((0,) * 343,) + record.permutations[1:]),
                        replace(record, permutations=((True,) + tuple(range(1, 343)),) + record.permutations[1:]),
                        replace(record, moves=(BoardMove(3, 1, (0, 0, 0)),)),
                        replace(record, moves=(BoardMove(0, 1, (7, 0, 0)),)),
                        replace(record, moves=(BoardMove(0, 1, None, ((0, 0, 0),)),)),
                        replace(record, ko_register=(0,) * 15 + (True,))):
            with self.subTest(changed=changed.profile), self.assertRaises(ValueError): encode_board_record(changed)
        with self.assertRaises(ValueError): encode_private_board_message(b"x" * (MAX_PAYLOAD_BYTES + 1), record)
        with self.assertRaises(ValueError): decode_board_record(b"x" * (MAX_PAYLOAD_BYTES + 1))

    def test_strict_wire_schema_canonical_bytes_and_derived_final_cells(self):
        raw = encode_board_record(handoff_board_record())
        for damaged in (raw.rstrip(), b" " + raw, b'{"schema":1,"schema":2}\n', b'{"value":NaN}\n', b"\xff"):
            with self.assertRaises(ValueError): decode_board_record(damaged)
        for key, value in (("board_count", True), ("qualification", 0), ("profile", "E8-security-proof"),
                           ("permutation_direction", "storage_to_logical"), ("ko_register", [0] * 15)):
            altered = json.loads(raw); altered[key] = value
            with self.assertRaises(ValueError): decode_board_record(canonical_json_bytes(altered))
        altered = json.loads(raw); altered["final_boards_b64"][0] = altered["final_boards_b64"][0][:-1]
        with self.assertRaises(ValueError): decode_board_record(canonical_json_bytes(altered))

    def test_python39_grammar(self):
        import merlin.titan_board_encoding as module
        ast.parse(Path(module.__file__).read_text(), feature_version=(3, 9))


if __name__ == "__main__": unittest.main()
