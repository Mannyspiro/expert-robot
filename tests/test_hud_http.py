import json
import unittest

from merlin.hud_activity import HudActivityProjector
from merlin.hud_http import HudActivityWSGI


class HudActivityWSGITests(unittest.TestCase):
    def setUp(self):
        self.app = HudActivityWSGI(HudActivityProjector())

    def request(self, path="/api/hud/activity", method="GET"):
        result = {}
        def start_response(status, headers):
            result["status"] = status
            result["headers"] = dict(headers)
        body = b"".join(self.app({"PATH_INFO": path, "REQUEST_METHOD": method,
                                  "QUERY_STRING": ""}, start_response))
        result["body"] = json.loads(body)
        return result

    def test_get_returns_live_schema_and_no_store(self):
        response = self.request()
        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(response["body"]["schema"], "merlin-hud-activity/1")
        self.assertEqual(response["headers"]["Cache-Control"], "no-store")

    def test_endpoint_is_get_only(self):
        self.assertEqual(self.request(method="POST")["status"], "405 Method Not Allowed")

    def test_unknown_path_is_not_found(self):
        self.assertEqual(self.request(path="/other")["status"], "404 Not Found")


if __name__ == "__main__":
    unittest.main()
