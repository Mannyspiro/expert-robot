import base64
from types import SimpleNamespace
import unittest

from merlin.oci_kms_provider import (
    ASSOCIATED_DATA,
    LOGGING_CONTEXT,
    OciKmsDataKeyProvider,
)


KEY_OCID = "ocid1.key.oc1.iad.example"
CRYPTO_ENDPOINT = "https://vault-crypto.kms.us-ashburn-1.oraclecloud.com"
DATA_KEY = b"K" * 32
WRAPPED_KEY = b"wrapped-kms-ciphertext"


class FakeModels:
    class KeyShape:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class GenerateKeyDetails:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class DecryptDataDetails:
        def __init__(self, **kwargs):
            self.kwargs = kwargs


class FakeKmsClient:
    def __init__(self):
        self.generate_details = None
        self.decrypt_details = None

    def generate_data_encryption_key(self, *, generate_key_details):
        self.generate_details = generate_key_details
        return SimpleNamespace(data=SimpleNamespace(
            plaintext=base64.b64encode(DATA_KEY).decode("ascii"),
            ciphertext=base64.b64encode(WRAPPED_KEY).decode("ascii"),
        ))

    def decrypt(self, *, decrypt_data_details):
        self.decrypt_details = decrypt_data_details
        return SimpleNamespace(data=SimpleNamespace(
            plaintext=base64.b64encode(DATA_KEY).decode("ascii"),
        ))


class FakeOciModule:
    class _Signer:
        class InstancePrincipalsSecurityTokenSigner:
            pass

    class _KmsClient:
        calls = []

        def __init__(self, *, config, service_endpoint, signer):
            self.calls.append({
                "config": config,
                "service_endpoint": service_endpoint,
                "signer": signer,
            })

    auth = SimpleNamespace(signers=_Signer)
    key_management = SimpleNamespace(
        models=FakeModels,
        KmsCryptoClient=_KmsClient,
    )


class OciKmsDataKeyProviderTests(unittest.TestCase):
    def test_generate_and_unwrap_use_exact_key_context(self):
        client = FakeKmsClient()
        provider = OciKmsDataKeyProvider(
            KEY_OCID, CRYPTO_ENDPOINT, client=client, oci_module=FakeOciModule,
        )
        key_id, plaintext, wrapped = provider.generate_data_key()
        self.assertEqual(key_id, KEY_OCID)
        self.assertEqual(plaintext, DATA_KEY)
        self.assertEqual(wrapped, WRAPPED_KEY)

        generate = client.generate_details.kwargs
        self.assertTrue(generate["include_plaintext_key"])
        self.assertEqual(generate["key_id"], KEY_OCID)
        self.assertEqual(generate["key_shape"].kwargs, {"algorithm": "AES", "length": 32})
        self.assertEqual(generate["associated_data"], ASSOCIATED_DATA)
        self.assertEqual(generate["logging_context"], LOGGING_CONTEXT)

        self.assertEqual(provider.unwrap_data_key(key_id, wrapped), DATA_KEY)
        decrypt = client.decrypt_details.kwargs
        self.assertEqual(decrypt["key_id"], KEY_OCID)
        self.assertEqual(decrypt["ciphertext"], base64.b64encode(WRAPPED_KEY).decode("ascii"))
        self.assertEqual(decrypt["associated_data"], ASSOCIATED_DATA)
        self.assertEqual(decrypt["encryption_algorithm"], "AES_256_GCM")

    def test_default_client_uses_instance_principal_and_explicit_crypto_endpoint(self):
        FakeOciModule._KmsClient.calls.clear()
        OciKmsDataKeyProvider(KEY_OCID, CRYPTO_ENDPOINT, oci_module=FakeOciModule)
        call = FakeOciModule._KmsClient.calls[-1]
        self.assertEqual(call["config"], {})
        self.assertEqual(call["service_endpoint"], CRYPTO_ENDPOINT)
        self.assertIsInstance(
            call["signer"],
            FakeOciModule.auth.signers.InstancePrincipalsSecurityTokenSigner,
        )


    def test_pinned_oci_sdk_models_accept_generation_and_decrypt_contract(self):
        import oci
        client = FakeKmsClient()
        provider = OciKmsDataKeyProvider(
            KEY_OCID, CRYPTO_ENDPOINT, client=client, oci_module=oci,
        )
        key_id, plaintext, wrapped = provider.generate_data_key()
        self.assertEqual((key_id, plaintext, wrapped), (KEY_OCID, DATA_KEY, WRAPPED_KEY))
        self.assertEqual(provider.unwrap_data_key(key_id, wrapped), DATA_KEY)

    def test_rejects_wrong_key_ocid_and_endpoint(self):
        with self.assertRaisesRegex(ValueError, "key OCID"):
            OciKmsDataKeyProvider("ocid1.vaultsecret.fake", CRYPTO_ENDPOINT, client=FakeKmsClient(), oci_module=FakeOciModule)
        for endpoint in (
            "http://vault-crypto.kms.us-ashburn-1.oraclecloud.com",
            "https://user:pass@vault-crypto.kms.us-ashburn-1.oraclecloud.com",
            "https://example.com",
        ):
            with self.assertRaisesRegex(ValueError, "HTTPS Vault crypto endpoint"):
                OciKmsDataKeyProvider(KEY_OCID, endpoint, client=FakeKmsClient(), oci_module=FakeOciModule)

    def test_rejects_wrong_key_id_on_unwrap(self):
        provider = OciKmsDataKeyProvider(
            KEY_OCID, CRYPTO_ENDPOINT, client=FakeKmsClient(), oci_module=FakeOciModule,
        )
        with self.assertRaisesRegex(ValueError, "different OCI KMS key"):
            provider.unwrap_data_key("ocid1.key.oc1.other", WRAPPED_KEY)


if __name__ == "__main__":
    unittest.main()
