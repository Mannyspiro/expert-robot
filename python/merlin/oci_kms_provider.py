"""OCI Vault/KMS data-key provider using an instance principal.

The provider performs only GenerateDataEncryptionKey and Decrypt operations on
one configured customer-managed AES key. It does not create, rotate, disable,
delete, or administer Vault keys.
"""
from __future__ import annotations

import base64
import re
from typing import Any
from urllib.parse import urlsplit


ASSOCIATED_DATA = {
    "purpose": "merlin-registry-backup",
    "envelope_schema": "merlin-encrypted-registry-backup/1",
    "data_key_schema": "merlin-backup-dek/1",
}
LOGGING_CONTEXT = {
    "service": "merlin",
    "operation": "registry-backup-data-key",
}


class OciKmsDataKeyProvider:
    """Generate and unwrap AES-256 DEKs with one OCI Vault key OCID."""

    def __init__(
        self,
        key_ocid: str,
        crypto_endpoint: str,
        *,
        client: Any | None = None,
        oci_module: Any | None = None,
    ):
        if not isinstance(key_ocid, str) or not key_ocid.startswith("ocid1.key.") or len(key_ocid) > 1024:
            raise ValueError("OCI KMS key OCID is invalid")
        parsed = urlsplit(crypto_endpoint)
        if (
            parsed.scheme != "https" or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or ".crypto.kms." not in parsed.hostname
        ):
            raise ValueError("OCI KMS crypto endpoint must be an HTTPS Vault crypto endpoint")
        if oci_module is None:
            try:
                import oci as oci_module
            except ImportError as exc:
                raise RuntimeError("OCI Python SDK is required for the OCI KMS provider") from exc
        self._oci = oci_module
        self.key_ocid = key_ocid
        self.crypto_endpoint = crypto_endpoint
        if client is None:
            signer = self._oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
            client = self._oci.key_management.KmsCryptoClient(
                config={}, service_endpoint=crypto_endpoint, signer=signer,
            )
        self.client = client
        self.models = self._oci.key_management.models

    @classmethod
    def from_instance_principal(cls, key_ocid: str, crypto_endpoint: str):
        """Create the crypto client using OCI instance-principal authentication."""
        return cls(key_ocid, crypto_endpoint)

    @staticmethod
    def _decode_key(encoded: Any, field: str) -> bytes:
        if not isinstance(encoded, str) or not encoded:
            raise RuntimeError(f"OCI KMS returned an invalid {field}")
        try:
            raw = base64.b64decode(encoded.encode("ascii"), validate=True)
        except Exception as exc:
            raise RuntimeError(f"OCI KMS returned malformed base64 for {field}") from exc
        if base64.b64encode(raw).decode("ascii") != encoded:
            raise RuntimeError(f"OCI KMS returned noncanonical base64 for {field}")
        return raw

    def generate_data_key(self) -> tuple[str, bytes, bytes]:
        details = self.models.GenerateKeyDetails(
            include_plaintext_key=True,
            key_id=self.key_ocid,
            key_shape=self.models.KeyShape(algorithm="AES", length=32),
            associated_data=dict(ASSOCIATED_DATA),
            logging_context=dict(LOGGING_CONTEXT),
        )
        response = self.client.generate_data_encryption_key(
            generate_key_details=details,
        )
        data = getattr(response, "data", None)
        plaintext = self._decode_key(getattr(data, "plaintext", None), "plaintext data key")
        wrapped = self._decode_key(getattr(data, "ciphertext", None), "wrapped data key")
        if len(plaintext) != 32 or not wrapped:
            raise RuntimeError("OCI KMS did not return a 256-bit data key and wrapped ciphertext")
        return self.key_ocid, plaintext, wrapped

    def unwrap_data_key(self, key_id: str, wrapped_key: bytes) -> bytes:
        if key_id != self.key_ocid:
            raise ValueError("encrypted backup references a different OCI KMS key")
        if not isinstance(wrapped_key, bytes) or not wrapped_key:
            raise ValueError("wrapped OCI data key must be non-empty bytes")
        details = self.models.DecryptDataDetails(
            key_id=self.key_ocid,
            ciphertext=base64.b64encode(wrapped_key).decode("ascii"),
            associated_data=dict(ASSOCIATED_DATA),
            logging_context=dict(LOGGING_CONTEXT),
            encryption_algorithm="AES_256_GCM",
        )
        response = self.client.decrypt(decrypt_data_details=details)
        plaintext = self._decode_key(
            getattr(getattr(response, "data", None), "plaintext", None),
            "decrypted data key",
        )
        if len(plaintext) != 32:
            raise RuntimeError("OCI KMS returned a data key with an invalid length")
        return plaintext
