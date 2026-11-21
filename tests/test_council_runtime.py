from contextlib import contextmanager
from hashlib import sha256
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import socket
from socketserver import TCPServer
import threading
import unittest
from unittest.mock import MagicMock, Mock, patch
import urllib.request

from merlin import council_runtime


def model_response(payload):
    persona = payload["messages"][0]["content"].split('"title": "')[1].split('"')[0]
    return json.dumps({
        "model": "test-local-model",
        "choices": [{"message": {"content": persona + ": independent assessment."}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8},
    }).encode()


class LocalServer(ThreadingHTTPServer):
    # Avoid reverse hostname lookups even for the synthetic server's metadata.
    def server_bind(self):
        TCPServer.server_bind(self)
        self.server_name = self.server_address[0]
        self.server_port = self.server_address[1]


class IPv6Server(LocalServer):
    address_family = socket.AF_INET6


class CouncilRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.servers = []
        self.allowed = set()
        self.connections = []
        original_connect = socket.socket.connect
        original_resolve = socket.getaddrinfo

        def connect(sock, address):
            self.connections.append(address)
            if sock.family not in (socket.AF_INET, socket.AF_INET6) or address[:2] not in self.allowed:
                raise AssertionError("test attempted a connection outside its loopback fixtures")
            return original_connect(sock, address)

        def resolve(host, port, *args, **kwargs):
            if host not in ("127.0.0.1", "::1", "localhost") or not any(p == port for _, p in self.allowed):
                raise AssertionError("test attempted resolution outside its loopback fixtures")
            return original_resolve(host, port, *args, **kwargs)

        for guard in (patch.object(socket.socket, "connect", connect),
                      patch.object(socket, "getaddrinfo", resolve)):
            guard.start()
            self.addCleanup(guard.stop)

    def tearDown(self):
        for server, thread in reversed(self.servers):
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

    def server(self, *, ipv6=False):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.server.requests.append({
                    "method": "POST", "target": self.path,
                    "headers": dict(self.headers), "body": raw,
                })
                body = (model_response(json.loads(raw)) if self.server.body is None
                        else self.server.body)
                self.send_response(self.server.status)
                for name, value in self.server.extra_headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self.server.requests.append({"method": "GET", "target": self.path})
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        host = "::1" if ipv6 else "127.0.0.1"
        server = (IPv6Server if ipv6 else LocalServer)((host, 0), Handler)
        server.requests = []
        server.status = 200
        server.body = None
        server.extra_headers = {}
        self.allowed.add((host, server.server_port))
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        self.servers.append((server, thread))
        return server

    @staticmethod
    def endpoint(server, host=None):
        host = host or server.server_address[0]
        if ":" in host:
            host = "[" + host + "]"
        return "http://" + host + ":" + str(server.server_port) + "/v1/chat/completions"

    @contextmanager
    def configured(self, endpoint):
        with patch.dict(os.environ, {
            "MERLIN_MODEL_QUALIFIED": "1", "MERLIN_MODEL_URL": endpoint,
            "MERLIN_MODEL_NAME": "test-local-model",
        }, clear=False):
            yield

    def single(self, endpoint):
        with self.configured(endpoint):
            return council_runtime.run_local_council(
                "Synthetic test question", "Synthetic shared context", visual_specialist_only=True)

    def test_model_must_be_qualified(self):
        with patch.dict(os.environ, {"MERLIN_MODEL_QUALIFIED": "0"}, clear=False):
            with patch.object(council_runtime, "HTTPConnection") as connection:
                with self.assertRaises(RuntimeError):
                    council_runtime.run_local_council("Test")
        connection.assert_not_called()
        self.assertEqual(self.connections, [])

    def test_openings_are_isolated_then_cross_examined(self):
        server = self.server()
        with self.configured(self.endpoint(server)):
            result = council_runtime.run_local_council("Should we use adaptive routing?", rounds=2)
        calls = [json.loads(row["body"])["messages"][1]["content"] for row in server.requests]
        self.assertEqual(len(result["opening_positions"]), 6)
        self.assertEqual(len(result["cross_examination"]), 6)
        self.assertEqual(len(calls), 12)
        self.assertTrue(all("OTHER COUNCIL OPENING POSITIONS" not in call for call in calls[:6]))
        self.assertTrue(all("OTHER COUNCIL OPENING POSITIONS" in call for call in calls[6:]))
        self.assertFalse(result["promotion_authorized"])
        self.assertFalse(result["authority_expansion"])

    def test_remote_endpoint_is_rejected(self):
        with self.configured("https://provider.example/v1/chat/completions"):
            with patch.object(council_runtime, "HTTPConnection") as connection:
                with self.assertRaises(ValueError):
                    council_runtime.run_local_council("Test")
        connection.assert_not_called()
        self.assertEqual(self.connections, [])

    def test_direct_loopback_preserves_payload_result_and_socket_timeout(self):
        server = self.server()
        made = []

        def connection(*args, **kwargs):
            self.assertEqual(args, ("127.0.0.1", server.server_port))
            self.assertEqual(kwargs, {"timeout": 180})
            made.append(HTTPConnection(*args, **kwargs))
            return made[-1]

        with patch.object(council_runtime, "HTTPConnection", side_effect=connection):
            result = self.single(self.endpoint(server) + "?mode=synthetic%20only")
        self.assertEqual(len(server.requests), 1)
        request = server.requests[0]
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["target"], "/v1/chat/completions?mode=synthetic%20only")
        self.assertEqual(request["headers"]["Content-Type"], "application/json")
        payload = json.loads(request["body"])
        self.assertEqual(payload["model"], "test-local-model")
        self.assertEqual(payload["temperature"], .65)
        self.assertEqual(payload["max_tokens"], 900)
        self.assertIs(payload["stream"], False)
        self.assertEqual([m["role"] for m in payload["messages"]], ["system", "user"])
        self.assertIn("Synthetic shared context", payload["messages"][1]["content"])
        row = result["opening_positions"][0]
        self.assertEqual(row["response_sha256"], sha256(row["content"].encode()).hexdigest())
        self.assertEqual(row["provider"], "local_openai_compatible")
        self.assertEqual(row["model"], "test-local-model")
        self.assertEqual(row["usage"], {"prompt_tokens": 12, "completion_tokens": 8})
        self.assertEqual(result["cross_examination"], [])
        self.assertIsNone(made[0].sock)

    def test_localhost_maps_to_numeric_ipv4_without_hostname_resolution(self):
        server = self.server()
        observed = []
        guarded_resolve = socket.getaddrinfo

        def resolve(host, *args, **kwargs):
            observed.append(host)
            if host != "127.0.0.1":
                raise AssertionError("localhost must not reach hostname resolution")
            return guarded_resolve(host, *args, **kwargs)

        with patch.object(socket, "getaddrinfo", side_effect=resolve):
            self.single(self.endpoint(server, "LOCALHOST"))
        self.assertEqual(observed, ["127.0.0.1"])
        self.assertEqual(len(server.requests), 1)

    def test_explicit_ipv6_loopback_uses_ipv6_fixture(self):
        server = self.server(ipv6=True)
        result = self.single(self.endpoint(server))
        self.assertEqual(len(server.requests), 1)
        self.assertEqual(len(result["opening_positions"]), 1)
        self.assertTrue(all(a[0] == "::1" for a in self.connections))

    def test_environment_proxies_and_global_opener_cannot_route_request(self):
        server = self.server()
        proxy = self.server()
        proxy_url = self.endpoint(proxy)
        opener = Mock()
        opener.open.side_effect = AssertionError("global opener must not receive council requests")
        proxy_env = {name: proxy_url for name in (
            "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")}
        proxy_env.update(NO_PROXY="", no_proxy="")
        with patch.dict(os.environ, proxy_env, clear=False), patch.object(urllib.request, "_opener", opener):
            self.single(self.endpoint(server))
        self.assertEqual(len(server.requests), 1)
        self.assertEqual(proxy.requests, [])
        opener.open.assert_not_called()

    def test_redirects_and_http_errors_never_make_followup_requests(self):
        server = self.server()
        destination = self.server()
        server.extra_headers = {"Location": self.endpoint(destination)}
        for status in (300, 301, 302, 303, 304, 305, 307, 308, 500):
            with self.subTest(status=status):
                server.status = status
                before = len(server.requests)
                with self.assertRaisesRegex(ValueError, "HTTP status " + str(status)):
                    self.single(self.endpoint(server))
                self.assertEqual(len(server.requests), before + 1)
                self.assertEqual(destination.requests, [])

    def test_malformed_endpoints_rejected_before_connection(self):
        endpoints = (
            "https://127.0.0.1:8080/v1", "http://user:password@127.0.0.1:8080/v1",
            "http://127.0.0.1:8080/v1#", " http://127.0.0.1:8080/v1",
            "http://127.0.0.1:8080/v\t1", "http://127.0.0.1:8080/v\r\n1",
            "http://127.0.0.1:8080/\x7f", "http://127.0.0.1:8080/\\other",
            "http://127.0.0.1:0/v1", "http://127.0.0.1:65536/v1",
            "http://127.0.0.1:/v1", "http://127.0.0.1:wrong/v1",
            "http://[::1/v1", "http://127.0.0.1:8080/%zz", "http://127.0.0.1:8080/\u0085",
        )
        with patch.object(council_runtime, "HTTPConnection") as connection:
            for endpoint in endpoints:
                with self.subTest(endpoint=repr(endpoint)):
                    with self.assertRaises(ValueError):
                        self.single(endpoint)
        connection.assert_not_called()
        self.assertEqual(self.connections, [])

    def test_malformed_json_and_response_shapes_are_rejected(self):
        server = self.server()
        bodies = (
            b'{', b'[]', b'{"choices":[]}', b'{"choices":[null]}',
            b'{"choices":[{"message":null}]}',
            b'{"choices":[{"message":{"content":" "}}]}', b'\xff',
        )
        for body in bodies:
            with self.subTest(body=body):
                server.body = body
                with self.assertRaises(ValueError):
                    self.single(self.endpoint(server))

    def test_response_size_boundary_accepts_limit_and_rejects_one_extra_byte(self):
        server = self.server()
        prefix = b'{"choices":[{"message":{"content":"'
        suffix = b'"}}]}'
        server.body = prefix + b'x' * (council_runtime.MAX_COUNCIL_RESPONSE - len(prefix + suffix)) + suffix
        self.assertEqual(len(server.body), council_runtime.MAX_COUNCIL_RESPONSE)
        self.single(self.endpoint(server))
        server.body += b' '
        with self.assertRaisesRegex(ValueError, "response exceeded size limit"):
            self.single(self.endpoint(server))

    def test_connection_closes_when_request_response_or_read_fails(self):
        for phase in ("request", "getresponse", "read"):
            with self.subTest(phase=phase):
                connection = Mock()
                response = MagicMock()
                response.status = 200
                response.__enter__.return_value = response
                response.__exit__.return_value = False
                connection.getresponse.return_value = response
                getattr(response if phase == "read" else connection, phase).side_effect = OSError("synthetic failure")
                with patch.object(council_runtime, "HTTPConnection", return_value=connection):
                    with self.assertRaises(OSError):
                        self.single("http://127.0.0.1:8080/v1/chat/completions")
                connection.close.assert_called_once_with()
                if phase == "read":
                    response.__exit__.assert_called_once()
        self.assertEqual(self.connections, [])


if __name__ == "__main__":
    unittest.main()
