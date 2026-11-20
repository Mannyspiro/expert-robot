"""Published component/adjacent-suite KATs, explicitly not an exact v1 KAT.

The public seed is upstream test material and must never become a live key.
The private AAD test entry point is used only here, as in upstream PyCA tests;
the application uses only the public HPKE Suite interface.
"""

import hashlib
import json
from pathlib import Path
import unittest

from merlin.titan_pq_envelope import backend_status


FIXTURE_SHA256 = "de5e3a67e50cb4ff5c84e96d79f17fdeabba2172d4b75d188eb1251bc8fa6055"


class TitanPublishedVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not backend_status()["available"]:
            raise unittest.SkipTest("pinned optional HPKE backend unavailable")
        path = Path(__file__).parent / "fixtures/titan-pq-published-component-v1.json"
        raw = path.read_bytes()
        # Compare exact retrieved fixture bytes before consuming its public key.
        if hashlib.sha256(raw).hexdigest() != FIXTURE_SHA256:
            raise AssertionError("published-vector extraction changed")
        cls.vector = json.loads(raw)

    def test_published_mlkem768_public_key_and_decapsulation_known_answer(self):
        from cryptography.hazmat.primitives.asymmetric.mlkem import MLKEM768PrivateKey

        vector = self.vector
        key = MLKEM768PrivateKey.from_seed_bytes(bytes.fromhex(vector["skRm"]))
        self.assertEqual(key.public_key().public_bytes_raw(), bytes.fromhex(vector["pkRm"]))
        self.assertEqual(
            key.decapsulate(bytes.fromhex(vector["enc"])),
            bytes.fromhex(vector["shared_secret"]),
        )

    def test_published_adjacent_aes128_hpke_known_answer_not_v1_aes256(self):
        from cryptography.hazmat.bindings._rust import openssl
        from cryptography.hazmat.primitives.asymmetric.mlkem import MLKEM768PrivateKey
        from cryptography.hazmat.primitives.hpke import AEAD, KDF, KEM, Suite

        vector = self.vector
        self.assertEqual((vector["kem_id"], vector["kdf_id"], vector["aead_id"]), (65, 1, 1))
        key = MLKEM768PrivateKey.from_seed_bytes(bytes.fromhex(vector["skRm"]))
        encryption = vector["encryption"]
        suite = Suite(KEM.MLKEM768, KDF.HKDF_SHA256, AEAD.AES_128_GCM)
        actual = openssl.hpke._decrypt_with_aad(
            suite,
            bytes.fromhex(vector["enc"] + encryption["ct"]),
            key,
            info=bytes.fromhex(vector["info"]),
            aad=bytes.fromhex(encryption["aad"]),
        )
        self.assertEqual(actual, bytes.fromhex(encryption["pt"]))

    def test_exact_v1_suite_gap_is_preserved_with_pinned_provenance(self):
        vector = self.vector
        self.assertEqual(vector["source_commit"], "4dda5c7fe4ae71b8925f2551910a0ef959df9c7a")
        self.assertEqual(vector["upstream_commit"], "6433c8fce0b8b749dfc86c1095081a88698ccfab")
        self.assertEqual(len(vector["published_suite_inventory"]), 13)
        self.assertFalse(vector["exact_titan_suite_vector_present"])
        self.assertNotIn(vector["target_suite"], vector["published_suite_inventory"])
        self.assertEqual(vector["target_suite"], {"mode": 0, "kem_id": 65, "kdf_id": 1, "aead_id": 2})


if __name__ == "__main__":
    unittest.main()
