"""Real maintained HPKE/ML-KEM acceptance; no cryptographic provider doubles."""

import base64
import json
import unittest

from merlin import titan_pq_envelope as target

CONTEXT = {'purpose': 'titan-private-payload', 'schema': 'titan-private-payload/1'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


class TitanPQEnvelopeTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not target.backend_status()['available']:
            raise unittest.SkipTest(
                'pinned cryptography50/OpenSSL4 HPKE backend unavailable; '
                'no fallback is permitted'
            )
        cls.public, cls.seed = target.generate_recipient_keypair()

    def test_real_backend_and_mlkem_key_serialization(self):
        status = target.backend_status()
        self.assertTrue(status['available'])
        self.assertTrue(status['real_roundtrip'])
        self.assertEqual(status['cryptography_version'], '50.0.0')
        self.assertEqual(len(self.public), 1184)
        self.assertEqual(len(self.seed), 64)
        self.assertFalse(status['qualification'])
        from cryptography.hazmat.primitives.asymmetric.mlkem import MLKEM768PrivateKey
        private = MLKEM768PrivateKey.from_seed_bytes(self.seed)
        shared, ciphertext = private.public_key().encapsulate()
        self.assertEqual(len(shared), 32)
        self.assertEqual(len(ciphertext), 1088)
        self.assertEqual(private.decapsulate(ciphertext), shared)

    def test_roundtrip_empty_binary_and_arbitrary_message_bytes(self):
        for payload in (b'', b'\x00\xff\x01private-board-history', bytes(range(256)) * 7):
            with self.subTest(size=len(payload)):
                sealed = target.encrypt(payload, self.public, CONTEXT, pad_to=4096)
                self.assertEqual(target.decrypt(sealed, self.seed, CONTEXT), payload)

    def test_fresh_encryption_and_constant_size_inside_same_bucket(self):
        first = target.encrypt(b'a', self.public, CONTEXT, pad_to=4096)
        second = target.encrypt(b'a', self.public, CONTEXT, pad_to=4096)
        third = target.encrypt(b'b' * 4000, self.public, CONTEXT, pad_to=4096)
        self.assertNotEqual(first, second)
        self.assertEqual(len(first), len(second))
        self.assertEqual(len(first), len(third))
        header = json.loads(first)['header']
        self.assertEqual(set(header), {'schema', 'version', 'suite', 'pad_to', 'context'})
        self.assertNotIn('length', header)
        self.assertNotIn('digest', header)
        self.assertNotIn('recipient_key_id', header)

    def test_each_bucket_boundary_and_oversize_rejection(self):
        for bucket in target.PADDING_BUCKETS:
            payload = b'v' * (bucket - 8)
            envelope = target.encrypt(payload, self.public, CONTEXT, pad_to=bucket)
            self.assertEqual(target.decrypt(envelope, self.seed, CONTEXT), payload)
            with self.assertRaises(ValueError):
                target.encrypt(payload + b'x', self.public, CONTEXT, pad_to=bucket)

    def assert_generic_failure(self, envelope, seed=None, context=None):
        with self.assertRaises(target.TitanDecryptionError) as failure:
            target.decrypt(
                envelope,
                self.seed if seed is None else seed,
                CONTEXT if context is None else context,
            )
        self.assertEqual(str(failure.exception), 'decryption failed')

    def test_wrong_key_context_ciphertext_and_encapsulation_are_rejected(self):
        sealed = target.encrypt(b'secret', self.public, CONTEXT, pad_to=4096)
        _, wrong = target.generate_recipient_keypair()
        self.assert_generic_failure(sealed, seed=wrong)
        self.assert_generic_failure(sealed, context={**CONTEXT, 'purpose': 'other-application'})
        for offset in (0, 1087, 1088, -1):
            value = json.loads(sealed)
            raw = bytearray(base64.b64decode(value['ciphertext_b64']))
            raw[offset] ^= 1
            value['ciphertext_b64'] = base64.b64encode(raw).decode()
            self.assert_generic_failure(canonical(value))

    def test_authenticated_header_no_downgrade_and_json_type_confusion(self):
        sealed = target.encrypt(b'secret', self.public, CONTEXT, pad_to=4096)
        altered_fields = [
            ('version', True),
            ('version', 1.0),
            ('version', 2),
            ('schema', 'titan-envelope/1'),
            ('suite', 'HPKE-X25519-HKDF-SHA256-AES-256-GCM'),
            ('pad_to', True),
            ('pad_to', 16384),
        ]
        for key, value in altered_fields:
            altered = json.loads(sealed)
            altered['header'][key] = value
            self.assert_generic_failure(canonical(altered))
        altered = json.loads(sealed)
        altered['header']['context']['purpose'] = 'other-application'
        self.assert_generic_failure(canonical(altered), context=altered['header']['context'])

    def test_malformed_duplicate_noncanonical_and_bounded_envelopes(self):
        sealed = target.encrypt(b'secret', self.public, CONTEXT, pad_to=4096)
        malformed_envelopes = (
            b'',
            b'{',
            b'[]',
            b'\xff',
            sealed + b'\n',
            b' ' * (target.MAX_ENVELOPE_BYTES + 1),
            b'{"header":1,"header":2,"ciphertext_b64":"invalid"}',
        )
        for value in malformed_envelopes:
            self.assert_generic_failure(value)
        malformed = json.loads(sealed)
        malformed['ciphertext_b64'] = 'A' * len(malformed['ciphertext_b64'])
        self.assert_generic_failure(canonical(malformed))
        malformed = json.loads(sealed)
        malformed['ciphertext_b64'] = malformed['ciphertext_b64'][:-4]
        self.assert_generic_failure(canonical(malformed))
        self.assert_generic_failure(sealed, seed=b'not-a-seed')

    def test_public_board_parameters_and_noncanonical_inputs_are_not_accepted(self):
        invalid_contexts = (
            {},
            {**CONTEXT, 'shape': [3, 7, 7, 7]},
            {**CONTEXT, 'history_sha256': 'a' * 64},
            {**CONTEXT, 'purpose': 'private message with spaces'},
        )
        for context in invalid_contexts:
            with self.assertRaises(ValueError):
                target.encrypt(b'payload', self.public, context)
        for bucket in (True, 4096.0, 4097, 0):
            with self.assertRaises(ValueError):
                target.encrypt(b'payload', self.public, CONTEXT, pad_to=bucket)
        with self.assertRaises(ValueError):
            target.encrypt(bytearray(b'payload'), self.public, CONTEXT)
        with self.assertRaises(ValueError):
            target.encrypt(b'payload', b'wrong-public-key', CONTEXT)


if __name__ == '__main__':
    unittest.main()
