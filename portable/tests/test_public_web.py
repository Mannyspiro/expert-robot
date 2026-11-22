"""Synthetic transport boundary tests; these do not establish native browsing."""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import http.client
import io
import os
import socket
import ssl
import threading
import time
import unittest
from unittest.mock import patch

from merlin_studio.public_web import (
    CAPABILITIES, PublicWebError, PublicWebFetcher, _PinnedHTTPSConnection, _normalize_url,
)


PUBLIC_IP = "93.184.216.34"


def answers(address=PUBLIC_IP):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 443))]


class WireSocket:
    def __init__(self, wire=b""):
        self.wire = wire
        self.timeouts = []
        self.closed = False
        self.interrupted = threading.Event()
        self.destination = None

    def makefile(self, *args, **kwargs):
        return io.BytesIO(self.wire)

    def settimeout(self, value):
        self.timeouts.append(value)

    def connect(self, destination):
        self.destination = destination

    def shutdown(self, how):
        self.interrupted.set()

    def close(self):
        self.closed = True


class WireConnection:
    def __init__(self, wire):
        self.sock = WireSocket(wire)
        self.channel = self.sock
        self.closed = False
        self.headers = None

    def request(self, method, target, headers):
        self.method, self.target, self.headers = method, target, headers

    def getresponse(self):
        self.response = http.client.HTTPResponse(self.channel)
        self.response.begin()
        return self.response

    def close(self):
        self.closed = True
        self.channel.close()


def wire(body=b"source", *, status="200 OK", headers=None):
    rows = {"Content-Type": "text/plain; charset=utf-8", "Content-Length": str(len(body))}
    rows.update(headers or {})
    return ("HTTP/1.1 " + status + "\r\n" + "".join(key + ": " + value + "\r\n" for key, value in rows.items())
            + "\r\n").encode() + body


class PublicWebTests(unittest.TestCase):
    def transport(self, wires, resolver=None, connection_type=WireConnection):
        connections = []
        calls = []
        pending = iter(wires)

        def connect(host, address, timeout):
            calls.append((host, address, timeout))
            connection = connection_type(next(pending))
            connections.append(connection)
            return connection

        fetcher = PublicWebFetcher(resolver=resolver or (lambda *a, **k: answers()), connector=connect)
        return fetcher, connections, calls

    def assert_code(self, code, operation):
        with self.assertRaises(PublicWebError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_exact_bytes_digest_text_and_query_identity(self):
        body = "Research 梅林".encode()
        resolutions = []

        def resolver(host, port, **kwargs):
            resolutions.append((host, port, kwargs))
            return answers()

        fetcher, connections, calls = self.transport([wire(body)], resolver)
        result = fetcher.fetch("https://EXAMPLE.org:443/search?q=梅林&exact=%2F#not-sent")
        self.assertEqual(result["body"], body)
        self.assertEqual(result["sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(result["text"], body.decode())
        self.assertEqual(result["retrieval_kind"], "https_http")
        self.assertEqual(result["network_bytes"], len(body))
        self.assertEqual(result["redirects"], [])
        self.assertEqual(connections[0].target, "/search?q=%E6%A2%85%E6%9E%97&exact=%2F")
        self.assertEqual(calls[0][:2], ("example.org", PUBLIC_IP))
        self.assertEqual(len(resolutions), 1)
        self.assertTrue(connections[0].closed)
        self.assertFalse(CAPABILITIES["rendered_browser"])

    def test_real_socket_exact_length_closure_and_truncation(self):
        # This exercises an actual socket's lifetime. Public DNS/TLS remain
        # synthetic via the injected connector; production HTTPS policy stays
        # unchanged and this is not a public web acquisition claim.
        body = b"source from local transport fixture"
        for declared in (len(body), len(body) + 10):
            with self.subTest(declared=declared):
                class Handler(BaseHTTPRequestHandler):
                    protocol_version = "HTTP/1.0"

                    def do_GET(self):
                        self.send_response(200)
                        self.send_header("Content-Type", "text/plain")
                        self.send_header("Content-Length", str(declared))
                        self.end_headers()
                        self.wfile.write(body)

                    def log_message(self, *args):
                        pass

                server = HTTPServer(("127.0.0.1", 0), Handler)
                server.timeout = 1
                thread = threading.Thread(target=server.handle_request, daemon=True)
                thread.start()

                def connector(host, address, timeout):
                    self.assertEqual((host, address), ("example.org", PUBLIC_IP))
                    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=timeout)
                    connection.connect()
                    return connection

                try:
                    fetcher = PublicWebFetcher(resolver=lambda *a, **k: answers(), connector=connector)
                    if declared == len(body):
                        result = fetcher.fetch("https://example.org/", timeout=1)
                        self.assertEqual(result["body"], body)
                        self.assertEqual(result["sha256"], hashlib.sha256(body).hexdigest())
                    else:
                        self.assert_code("truncated_response", lambda: fetcher.fetch("https://example.org/", timeout=1))
                finally:
                    thread.join(timeout=2)
                    server.server_close()

    def test_unsafe_url_and_excluded_accounts_fail_before_dns_or_connect(self):
        invalid = [
            "http://example.org/", "file:///etc/passwd", "https://user:secret@example.org/",
            "https://example.org:8443/", "https://127.0.0.1/", "https://[::1]/",
            "https://169.254.169.254/", "https://localhost/", "https://router.local/",
            "https://chatgpt.com/", "https://www.chatgpt.com/", "https://chat.openai.com/",
            "https://chat.com/", "https://chatgpt.com./", "https://example.org\\@127.0.0.1/",
            "https://example.org/\r\nX-Test:yes", "https://[::ffff:93.184.216.34]/",
        ]
        fetcher = PublicWebFetcher(resolver=lambda *a, **k: self.fail("Unsafe URL reached DNS"),
                                   connector=lambda *a: self.fail("Unsafe URL connected"))
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(PublicWebError):
                fetcher.fetch(url)

    def test_mixed_public_private_and_special_dns_answers_are_rejected_as_a_set(self):
        for bad in ("10.0.0.1", "127.0.0.1", "169.254.169.254", "100.64.0.1", "224.0.0.1",
                    "::1", "fe80::1", "ff0e::1", "64:ff9b::a00:1", "2002:7f00:1::"):
            with self.subTest(bad=bad):
                fetcher, connections, _ = self.transport([], lambda *a, **k: answers() + answers(bad))
                self.assert_code("nonpublic_address", lambda: fetcher.fetch("https://example.org/"))
                self.assertEqual(connections, [])

    def test_invalid_or_oversized_dns_answer_set_is_rejected(self):
        for answer in ([], answers() * 33, [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("2606:4700:4700::1111", 443))]):
            with self.subTest(answer_count=len(answer)):
                fetcher, connections, _ = self.transport([], lambda *a, **k: answer)
                self.assert_code("invalid_dns", lambda: fetcher.fetch("https://example.org/"))
                self.assertEqual(connections, [])

    def test_numeric_connect_and_tls_use_pinned_ip_and_original_hostname_without_dns(self):
        channel = WireSocket()

        class TLSContext:
            check_hostname = True
            verify_mode = ssl.CERT_REQUIRED

            def wrap_socket(self, sock, server_hostname):
                self.hostname = server_hostname
                return sock

        context = TLSContext()
        with patch("socket.socket", return_value=channel), \
             patch("socket.getaddrinfo", side_effect=AssertionError("A second DNS lookup is forbidden")), \
             patch("ssl.create_default_context", return_value=context):
            connection = _PinnedHTTPSConnection("example.org", PUBLIC_IP, 3)
            connection.connect()
            self.assertEqual(channel.destination, (PUBLIC_IP, 443))
            self.assertEqual(context.hostname, "example.org")
            connection.close()
            connection.connect()  # Any HTTPConnection reconnect also stays pinned.
            self.assertEqual(channel.destination, (PUBLIC_IP, 443))
            connection.close()

    def test_disabled_hostname_or_certificate_verification_is_rejected(self):
        for hostname_check, verification in ((False, ssl.CERT_REQUIRED), (True, ssl.CERT_NONE)):
            with self.subTest(hostname_check=hostname_check, verification=verification):
                channel = WireSocket()
                context = type("Context", (), {"check_hostname": hostname_check, "verify_mode": verification})()
                with patch("socket.socket", return_value=channel), patch("ssl.create_default_context", return_value=context):
                    self.assert_code("tls_configuration", lambda: _PinnedHTTPSConnection("example.org", PUBLIC_IP, 3).connect())
                self.assertTrue(channel.closed)

    def test_proxy_environment_and_response_cookies_are_not_used(self):
        fetcher, connections, _ = self.transport([
            wire(b"", status="302 Found", headers={"Location": "/final", "Set-Cookie": "private=synthetic"}),
            wire(b"ok"),
        ])
        with patch.dict(os.environ, {"HTTPS_PROXY": "http://127.0.0.1:9", "ALL_PROXY": "http://127.0.0.1:9",
                                     "HTTP_PROXY": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9"}), \
             patch("urllib.request.getproxies", side_effect=AssertionError("Environment proxies must be ignored")):
            self.assertEqual(fetcher.fetch("https://example.org/start")["body"], b"ok")
        for connection in connections:
            self.assertEqual(set(connection.headers), {"User-Agent", "Accept", "Accept-Encoding", "Connection"})
            self.assertEqual(connection.headers["Accept-Encoding"], "identity")

    def test_each_redirect_is_resolved_again_and_rebinding_is_denied(self):
        lookups = []

        def resolver(*args, **kwargs):
            lookups.append(args)
            return answers() if len(lookups) == 1 else answers("127.0.0.1")

        fetcher, connections, calls = self.transport([wire(b"", status="302 Found", headers={"Location": "/next"})], resolver)
        self.assert_code("nonpublic_address", lambda: fetcher.fetch("https://example.org/start"))
        self.assertEqual(len(lookups), 2)
        self.assertEqual(len(calls), 1)
        self.assertTrue(connections[0].closed)

    def test_redirect_to_http_private_or_account_url_is_denied_before_next_lookup(self):
        for location in ("http://example.org/", "https://127.0.0.1/", "https://chatgpt.com/", "https://user:secret@example.org/"):
            with self.subTest(location=location):
                lookups = []

                def resolver(*args, **kwargs):
                    lookups.append(args)
                    return answers()

                fetcher, _, calls = self.transport([wire(b"", status="302 Found", headers={"Location": location})], resolver)
                with self.assertRaises(PublicWebError):
                    fetcher.fetch("https://example.org/")
                self.assertEqual((len(lookups), len(calls)), (1, 1))

    def test_redirect_bytes_share_final_response_budget(self):
        for limit, succeeds in ((5, True), (4, False)):
            with self.subTest(limit=limit):
                fetcher, connections, _ = self.transport([
                    wire(b"ab", status="307 Temporary Redirect", headers={"Location": "../final?x=%2F"}),
                    wire(b"xyz"),
                ])
                if succeeds:
                    result = fetcher.fetch("https://example.org/source/start", max_bytes=limit)
                    self.assertEqual(result["body"], b"xyz")
                    self.assertEqual(result["final_url"], "https://example.org/final?x=%2F")
                    self.assertEqual(result["network_bytes"], 5)
                    self.assertEqual(result["redirects"][0]["body_bytes"], 2)
                else:
                    self.assert_code("response_too_large", lambda: fetcher.fetch("https://example.org/source/start", max_bytes=limit))
                self.assertTrue(all(connection.closed for connection in connections))

    def test_redirect_count_loop_and_missing_location_are_explicit_errors(self):
        for reply, redirects, code in (
            (wire(b"", status="302 Found", headers={"Location": "/next"}), 0, "redirect_limit"),
            (wire(b"", status="302 Found", headers={"Location": "/"}), 4, "redirect_loop"),
            (wire(b"", status="302 Found"), 4, "invalid_redirect"),
        ):
            with self.subTest(code=code):
                fetcher, _, calls = self.transport([reply])
                self.assert_code(code, lambda: fetcher.fetch("https://example.org/", max_redirects=redirects))
                self.assertEqual(len(calls), 1)

    def test_declared_streamed_and_chunked_reply_limits_are_enforced(self):
        replies = [
            wire(b"12345"),
            b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n12345",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\n12345\r\n0\r\n\r\n",
        ]
        for reply in replies:
            with self.subTest(reply=reply[:60]):
                fetcher, connections, _ = self.transport([reply])
                self.assert_code("response_too_large", lambda: fetcher.fetch("https://example.org/", max_bytes=4))
                self.assertTrue(connections[0].closed)

    def test_truncated_length_and_chunked_bodies_never_succeed(self):
        for reply in (
            b"HTTP/1.1 200 OK\r\nContent-Length: 9\r\n\r\nabc",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n3\r\nabc\r\n6\r\n",
        ):
            with self.subTest(reply=reply[:60]):
                fetcher, _, _ = self.transport([reply])
                self.assert_code("truncated_response", lambda: fetcher.fetch("https://example.org/"))

    def test_ambiguous_headers_and_compression_are_rejected(self):
        cases = (
            (b"Content-Length: 0\r\nContent-Length: 0\r\n", "invalid_headers"),
            (b"Content-Length: 0\r\nTransfer-Encoding: chunked\r\n", "invalid_headers"),
            (b"Content-Type: text/plain\r\nContent-Type: text/html\r\nContent-Length: 0\r\n", "invalid_headers"),
            (b"Content-Encoding: gzip\r\nContent-Length: 0\r\n", "unsupported_encoding"),
            (b"Content-Length: -1\r\n", "invalid_headers"),
            (b"X-Big: " + b"x" * 33000 + b"\r\nContent-Length: 0\r\n", "headers_too_large"),
        )
        for headers, code in cases:
            with self.subTest(code=code, header=headers[:40]):
                fetcher, _, _ = self.transport([b"HTTP/1.1 200 OK\r\n" + headers + b"\r\n"])
                self.assert_code(code, lambda: fetcher.fetch("https://example.org/"))

    def test_unsuccessful_status_is_not_returned_as_source_success(self):
        for status in (101, 304, 400, 404, 500, 599):
            with self.subTest(status=status):
                fetcher, connections, _ = self.transport([wire(b"", status=str(status) + " Fixture")])
                error = self.assert_code("http_status", lambda: fetcher.fetch("https://example.org/"))
                self.assertEqual(error.status, status)
                self.assertTrue(connections[0].closed)

    def test_html_text_excludes_scripts_styles_and_templates_without_rendering(self):
        body = b"<html><title>Title</title><style>secret-style</style><p>Hello &amp; research</p>" \
               b"<script>run_bad_code()</script><template>hidden template</template><p>Second <b>line</b>.</p></html>"
        fetcher, _, _ = self.transport([wire(body, headers={"Content-Type": "text/html; charset=utf-8"})])
        result = fetcher.fetch("https://example.org/")
        self.assertEqual(result["body"], body)
        self.assertIn("Hello & research", result["text"])
        self.assertIn("Second line.", result["text"])
        for hidden in ("secret-style", "run_bad_code", "hidden template"):
            self.assertNotIn(hidden, result["text"])

    def test_binary_body_is_retained_without_fabricated_text(self):
        fetcher, _, _ = self.transport([wire(b"\x00\xff\xfe", headers={"Content-Type": "application/octet-stream"})])
        result = fetcher.fetch("https://example.org/")
        self.assertEqual(result["body"], b"\x00\xff\xfe")
        self.assertEqual(result["text"], "")

    def test_dns_deadline_is_bounded_and_no_connection_follows_timeout(self):
        release = threading.Event()
        done = threading.Event()

        def resolver(*args, **kwargs):
            try:
                release.wait(1)
                return answers()
            finally:
                done.set()

        fetcher, _, calls = self.transport([], resolver)
        started = time.monotonic()
        try:
            self.assert_code("timeout", lambda: fetcher.fetch("https://example.org/", timeout=0.02))
            self.assertLess(time.monotonic() - started, 0.5)
            self.assertEqual(calls, [])
        finally:
            release.set()
            self.assertTrue(done.wait(1))

    def test_absolute_deadline_interrupts_slow_headers(self):
        class SlowHeaders(WireConnection):
            def getresponse(self):
                self.channel.interrupted.wait(1)
                raise OSError("fixture interrupted during header reception")

        fetcher, connections, _ = self.transport([b""], connection_type=SlowHeaders)
        started = time.monotonic()
        self.assert_code("timeout", lambda: fetcher.fetch("https://example.org/", timeout=0.03))
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertTrue(connections[0].channel.interrupted.is_set())
        self.assertTrue(connections[0].closed)

    def test_invalid_budgets_fail_before_dns(self):
        fetcher = PublicWebFetcher(resolver=lambda *a, **k: self.fail("Invalid budget reached DNS"))
        for kwargs in ({"max_bytes": True}, {"max_bytes": 0}, {"max_bytes": 2**30},
                       {"timeout": True}, {"timeout": float("nan")}, {"timeout": 61},
                       {"max_redirects": True}, {"max_redirects": -1}, {"max_redirects": 9}):
            with self.subTest(kwargs=kwargs):
                self.assert_code("invalid_budget", lambda: fetcher.fetch("https://example.org/", **kwargs))


if __name__ == "__main__":
    unittest.main()
