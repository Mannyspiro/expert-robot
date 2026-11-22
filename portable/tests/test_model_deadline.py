"""Real loopback TCP controls for model response deadlines and framing."""
from contextlib import contextmanager
import json
import socket
import threading
import time
import unittest

from merlin_studio.model import LocalModel, ModelError


@contextmanager
def local_reply(reply, *, drip_headers=False):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(2)
    stopped = threading.Event()

    def serve():
        try:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(1)
                request = b""
                while b"\r\n\r\n" not in request and len(request) < 65536:
                    block = connection.recv(4096)
                    if not block:
                        return
                    request += block
                if drip_headers:
                    connection.sendall(b"HTTP/1.1 200 OK\r\nX-Slow: ")
                    for _ in range(30):
                        if stopped.wait(0.025):
                            return
                        connection.sendall(b"x")
                else:
                    connection.sendall(reply)
        except OSError:
            pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(listener.getsockname()[1]) + "/v1/chat/completions"
    finally:
        stopped.set()
        listener.close()
        thread.join(timeout=2)


class ModelDeadlineTests(unittest.TestCase):
    def test_real_slow_headers_are_interrupted_at_total_deadline(self):
        with local_reply(b"", drip_headers=True) as endpoint:
            model = LocalModel({"model_url": endpoint})
            started = time.monotonic()
            with self.assertRaisesRegex(ModelError, "total response deadline"):
                model._request("GET", "/v1/models", timeout=0.09)
            self.assertLess(time.monotonic() - started, 0.4)

    def test_valid_loopback_json_response_remains_supported(self):
        body = json.dumps({"data": [{"id": "local-fixture"}]}).encode()
        reply = b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body
        with local_reply(reply) as endpoint:
            self.assertEqual(LocalModel({"model_url": endpoint}).probe(),
                             {"reachable": True, "models": [{"id": "local-fixture"}]})

    def test_valid_json_with_truncated_declared_length_is_not_success(self):
        reply = b'HTTP/1.1 200 OK\r\nContent-Length: 99\r\n\r\n{"ok":true}'
        with local_reply(reply) as endpoint:
            with self.assertRaisesRegex(ModelError, "declared length"):
                LocalModel({"model_url": endpoint})._request("GET", "/v1/models", timeout=1)

    def test_oversized_declared_body_is_rejected_before_body_read(self):
        reply = b"HTTP/1.1 200 OK\r\nContent-Length: 2097153\r\n\r\n"
        with local_reply(reply) as endpoint:
            with self.assertRaisesRegex(ModelError, "2 MiB"):
                LocalModel({"model_url": endpoint})._request("GET", "/v1/models", timeout=1)

    def test_streamed_body_has_the_same_limit_without_content_length(self):
        reply = b"HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n" + b"x" * 2097153
        with local_reply(reply) as endpoint:
            with self.assertRaisesRegex(ModelError, "2 MiB"):
                LocalModel({"model_url": endpoint})._request("GET", "/v1/models", timeout=1)

    def test_duplicate_length_and_transfer_encoding_are_rejected(self):
        for headers in (b"Content-Length: 2\r\nContent-Length: 2\r\n",
                        b"Content-Length: 2\r\nTransfer-Encoding: chunked\r\n"):
            with self.subTest(headers=headers), local_reply(b"HTTP/1.1 200 OK\r\n" + headers + b"\r\n{}") as endpoint:
                with self.assertRaisesRegex(ModelError, "framing"):
                    LocalModel({"model_url": endpoint})._request("GET", "/v1/models", timeout=1)

    def test_complete_forwards_remaining_budget_to_transport(self):
        calls = []

        def transport(method, path, payload, timeout):
            calls.append((method, path, timeout))
            return {"choices": [{"message": {"content": "fixture"}}]}

        model = LocalModel({"model_url": "http://127.0.0.1:8772/v1"}, transport=transport)
        self.assertEqual(model.complete([], [], timeout=0.75)["content"], "fixture")
        self.assertEqual(calls, [("POST", "/v1/chat/completions", 0.75)])

    def test_invalid_deadline_is_rejected_before_transport(self):
        model = LocalModel({"model_url": "http://127.0.0.1:8772/v1"},
                           transport=lambda *args: self.fail("Invalid budget reached transport"))
        for timeout in (0, -1, float("nan"), float("inf"), True, 46):
            with self.subTest(timeout=timeout), self.assertRaises(ModelError):
                model._request("GET", "/v1/models", timeout=timeout)


if __name__ == "__main__":
    unittest.main()
