"""Lightweight profile exercises the normal chat gateway and protocol boundaries."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from python.merlin.app import EventStore, _json_bytes, make_handler
from python.merlin.chat_context import ChatContextTooLarge, pack_chat_context, parse_context_budget


def message(role, content):
    return {"role": role, "content": content}


def test_instructions_latest_turn_and_non_ascii_byte_accounting():
    instructions = [message("system", "Keep directions verbatim"), message("developer", "Use units")]
    old = [message("user", "obsolete"), message("assistant", "old"*400)]
    recent = [message("user", "λ"), message("assistant", "é𝄞")]
    latest = [message("user", "Compare simulated SSDs")]
    original = [*instructions, *old, *recent, *latest]
    expected = [*instructions, *recent, *latest]
    budget = len(_json_bytes(expected))
    result = pack_chat_context({"messages": original}, budget)
    assert result.messages == expected
    assert result.metadata == {"budget_bytes": budget, "input_message_bytes":len(_json_bytes(original)),
                               "forwarded_message_bytes": budget, "omitted_messages": 2}
    assert pack_chat_context({"messages": original}, budget-1).messages == instructions+latest
    assert len(original) == 7


def test_does_not_skip_a_large_middle_turn_or_split_a_reply():
    first = [message("user", "tiny"), message("assistant", "tiny")]
    middle = [message("user", "question"), message("assistant", "large"*80)]
    latest = [message("user", "new"), message("assistant", "prefix")]
    result = pack_chat_context({"messages": first + middle + latest}, len(_json_bytes(first+latest)))
    assert result.messages == latest


@pytest.mark.parametrize("extra,messages", [
    ({"tools":[]}, [message("user", "text")]),
    ({}, [message("tool", "result"), message("user", "follow-up")]),
    ({}, [message("user", [{"type":"text","text":"caption"}])]),
    ({}, [message("user", "first"), message("system", "later instruction")]),
    ({}, [{"role": "user", "content": "named", "name": "speaker"}]),
])
def test_protocol_shapes_keep_the_existing_path(extra, messages):
    assert pack_chat_context({"messages":messages, **extra}, 256) is None


def test_rejects_an_unfit_required_turn_and_invalid_configuration():
    with pytest.raises(ChatContextTooLarge):
        pack_chat_context({"messages":[message("user", "x"*260)]}, 256)
    assert parse_context_budget(None) is None and parse_context_budget("0") is None
    assert parse_context_budget("4096") == 4096
    for invalid in ("abc", "123", "1000001", "-1", "１２３４"):
        with pytest.raises(ValueError):
            parse_context_budget(invalid)


@contextmanager
def loopback(handler):
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join()


def test_gateway_budget_changes_upstream_bytes_and_rejects_before_provider(tmp_path, monkeypatch):
    captured = []

    class Provider(BaseHTTPRequestHandler):
        def do_POST(self):
            captured.append(self.rfile.read(int(self.headers["Content-Length"])))
            response = b'{"choices":[]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(response)

    monkeypatch.setenv("MERLIN_MODEL_QUALIFIED", "1")
    monkeypatch.setenv("MERLIN_LOCAL_MODEL", "fixture")
    monkeypatch.setenv("MERLIN_CHAT_CONTEXT_BYTES", "4096")
    with loopback(Provider) as provider:
        monkeypatch.setenv("MERLIN_MODEL_URL", provider + "/v1/chat/completions")
        store = EventStore(tmp_path/"events.sqlite3")
        with loopback(make_handler(store)) as gateway:
            def send(messages):
                body = _json_bytes({"provider":"local","messages":messages})
                req = Request(gateway + "/api/chat", data=body, headers={"Content-Type":"application/json"})
                with urlopen(req, timeout=5) as response:
                    assert response.status == 200

            policy = message("system", "Keep output scoped")
            history = [item for i in range(40) for item in
                       (message("user", f"Old question {i}"), message("assistant", "old context "*100))]
            latest = message("user", "Verify tensor replay")
            send([policy, *history, latest])
            actual = json.loads(captured[0])
            assert actual["messages"][0] == policy and actual["messages"][-1] == latest
            forwarded = len(_json_bytes(actual["messages"]))
            original = len(_json_bytes([policy,*history,latest]))
            assert forwarded <= 4096 and forwarded < original/10
            events = store.by_kind("/api/chat")
            assert events[-1]["summary"]["context_budget"]["forwarded_message_bytes"] == forwarded
            with pytest.raises(HTTPError) as error:
                send([message("user", "x"*4096)])
            assert error.value.code == 413 and len(captured) == 1
