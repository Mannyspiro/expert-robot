import unittest
from dataclasses import replace
from wilborn_ops.research_retrieval import FetchReceipt,accept_receipt

class RetrievalBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.receipt=FetchReceipt(
            requested_url="https://www.nist.gov/publications",
            final_url="https://www.nist.gov/publications",
            status=200,content_type="text/html",body=b"<h1>Public document</h1>",
            redirect_count=0,egress_policy_verified=True,tls_verified=True,
            access_policy_verified=True)

    def test_accepts_approved_receipt_without_network(self):
        result=accept_receipt(self.receipt)
        self.assertEqual(result["data_class"],"public_research")
        self.assertEqual(result["evidence"].url,self.receipt.final_url)
        self.assertEqual(result["receipt_sha256"],result["evidence"].sha256)

    def test_rejects_redirect_private_destination_and_unverified_provider(self):
        for changes in (
            {"final_url":"https://127.0.0.1/private"},
            {"final_url":"https://www.sba.gov/other","redirect_count":1},
            {"egress_policy_verified":False},
            {"tls_verified":False},
            {"access_policy_verified":False},
            {"content_type":"application/octet-stream"},
            {"status":404},
            {"body":b"x"*256001},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises((PermissionError,ValueError)):
                    accept_receipt(replace(self.receipt,**changes))

    def test_receipt_is_not_network_attestation(self):
        result=accept_receipt(self.receipt)
        self.assertIn("not_independently_attested",result["retrieval_assurance"])
