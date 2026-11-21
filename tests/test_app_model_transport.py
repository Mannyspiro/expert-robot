"""Actual app-handler transport contracts using synthetic upstreams only.

The source capture retains the complete Handler class and selected actual app
helpers. It omits make_handler's unrelated database/bootstrap initialization;
inbound HTTP byte streams and response writes are supplied directly. Cloud
connections are fake HTTPSConnection objects, not TLS/provider evidence.
"""
import ast
from contextlib import contextmanager
from email.message import Message
from hashlib import sha256
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
from socketserver import TCPServer
import socket
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import Mock, patch
import urllib.request

from merlin.event_outbox import LeaseConflict
from merlin.learning_research_api import LearningResearchAPI
from merlin.telemetry import normalize_event


APP_SOURCE = Path(os.environ.get('MERLIN_APP_TRANSPORT_TEST_SOURCE',
    Path(__file__).resolve().parents[1] / 'python/merlin/app.py'))
OBSERVATIONS = []
MARKER = 'SYNTHETIC_APP_TRANSPORT_CONTENT'
KEY = 'synthetic-fixture-key-not-a-credential'
APPROVED = 'approved.example.invalid'
UNAPPROVED = 'unapproved.example.invalid'


def capture_handler(store):
    raw = APP_SOURCE.read_bytes()
    tree = ast.parse(raw, filename=str(APP_SOURCE))
    helpers = {'_loopback_endpoint', '_remote_model_endpoint', '_remote_model_target',
               '_model_response', '_json_bytes', '_append_component_event'}
    modules = {'__future__', 'contextlib', 'hashlib', 'http.client', 'http.server',
               'json', 'os', 're', 'typing', 'urllib.parse', 'urllib.request',
               'urllib.error', 'time', 'council_runtime'}
    selected = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in modules:
            selected.append(node)
        elif isinstance(node, ast.Import) and all(alias.name in modules for alias in node.names):
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name)
                and t.id in ('MAX_BODY', 'MAX_PROXY_RESPONSE') for t in node.targets):
            selected.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in helpers:
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == 'make_handler':
            handlers = [child for child in node.body if isinstance(child, ast.ClassDef)
                        and child.name == 'Handler']
            if len(handlers) != 1:
                raise AssertionError('exact original handler class required')
            selected.extend(handlers)
    namespace = {'__name__': 'merlin._captured_app_transport', '__package__': 'merlin',
        '__file__': str(APP_SOURCE), 'store': store, 'LeaseConflict': LeaseConflict,
        'LearningResearchAPI': LearningResearchAPI, 'normalize_event': normalize_event,
        'interaction_store': SimpleNamespace(preferences=lambda: {'aggregate_telemetry': False})}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(APP_SOURCE), 'exec'), namespace)
    return namespace, sha256(raw).hexdigest()


class LocalServer(ThreadingHTTPServer):
    def server_bind(self):
        TCPServer.server_bind(self)
        self.server_name = 'synthetic-loopback'
        self.server_port = self.server_address[1]


class GeneratedResponse(io.BytesIO):
    def __init__(self, body=b'{"model":"synthetic","choices":[]}', *, status=200,
                 content_type='application/json', location=None, generated_bytes=None):
        super().__init__(body)
        self.status = self.code = status
        self.reason = 'Synthetic upstream response'
        self.headers = Message()
        self.headers['Content-Type'] = content_type
        if location is not None:
            self.headers['Location'] = location
        self.generated_bytes = generated_bytes
        self.read_sizes = []
        self.close_count = 0

    def info(self):
        return self.headers

    def geturl(self):
        return self.url

    def read(self, size=-1):
        self.read_sizes.append(size)
        if self.generated_bytes is None:
            return super().read(size)
        count = self.generated_bytes if size < 0 else min(size, self.generated_bytes)
        self.generated_bytes -= count
        return b'x' * count

    def close(self):
        self.close_count += 1
        super().close()


class CountingWriter:
    def __init__(self):
        self.written = 0
        self.stream_bytes = 0
        self.tail = b''

    def write(self, body):
        self.written += len(body)
        if body and body == b'x' * len(body):
            self.stream_bytes += len(body)
        self.tail = body[-500:]

    def flush(self):
        pass

    def getvalue(self):
        return self.tail


class AppModelTransportTests(unittest.TestCase):
    def setUp(self):
        self.store = SimpleNamespace(events=[])
        self.store.append = lambda *args: self.store.events.append(args)
        self.ns, self.source_sha = capture_handler(self.store)
        self.servers = []
        self.allowed = set()
        self.local_requests = []
        self.connections = []
        self.responses = []
        self.fake_requests = []
        self.fake_connections = []
        self.api_replies = []
        self.original_connect = socket.socket.connect
        original_getaddrinfo = socket.getaddrinfo

        def connect(sock, address):
            self.connections.append(list(address))
            if sock.family not in (socket.AF_INET, socket.AF_INET6) or address[:2] not in self.allowed:
                raise AssertionError('test refuses every socket outside its loopback fixtures')
            sock.settimeout(2)
            return self.original_connect(sock, address)

        def resolve(host, port, *args, **kwargs):
            if host not in ('127.0.0.1', '::1') or (host, int(port)) not in self.allowed:
                raise AssertionError('test refuses all DNS and unrelated numeric addresses')
            return original_getaddrinfo(host, port, *args, **kwargs)

        for guard in (patch.object(socket.socket, 'connect', connect),
                      patch.object(socket, 'getaddrinfo', resolve)):
            guard.start()
            self.addCleanup(guard.stop)
        self.environment = {
            'MERLIN_MODEL_QUALIFIED': '1', 'MERLIN_MODEL_NAME': 'synthetic-model',
            'MERLIN_TTS_QUALIFIED': '1', 'MERLIN_REMOTE_MODEL_QUALIFIED': '1',
            'MERLIN_REMOTE_MODEL_URL': 'https://' + APPROVED + '/v1/chat/completions',
            'MERLIN_REMOTE_API_KEY': KEY, 'MERLIN_REMOTE_ALLOWED_HOSTS': APPROVED,
        }

    def tearDown(self):
        for server, thread in reversed(self.servers):
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
        OBSERVATIONS.append({'test_id': self.id(), 'app_source_sha256': self.source_sha,
            'actual_loopback_connections': self.connections,
            'actual_local_requests': self.local_requests, 'synthetic_https_or_mock_requests': self.fake_requests,
            'api_replies': self.api_replies, 'real_tls_performed': False,
            'external_endpoint_contacted': False, 'real_model_called': False})

    def server(self, *, status=200, content_type='application/json', location=None):
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.respond()

            def do_GET(self):
                self.respond()

            def respond(self):
                length = int(self.headers.get('Content-Length', 0))
                if not 0 <= length <= 16384:
                    raise AssertionError('fixture request exceeds bounded payload')
                raw = self.rfile.read(length)
                row = {'port': self.server.server_port, 'method': self.command,
                    'path': self.path, 'headers': dict(self.headers), 'body': raw.decode(),
                    'contains_marker': MARKER.encode() in raw}
                outer.local_requests.append(row)
                self.server.requests.append(row)
                body = b'{"model":"synthetic","choices":[]}' if content_type == 'application/json' else b'SYNTHETIC_AUDIO'
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                if location is not None:
                    self.send_header('Location', location)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass
        server = LocalServer(('127.0.0.1', 0), Handler)
        server.requests = []
        self.allowed.add(('127.0.0.1', server.server_port))
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        thread.start()
        self.servers.append((server, thread))
        return server

    @staticmethod
    def endpoint(server):
        return 'http://127.0.0.1:' + str(server.server_port) + '/v1/synthetic'

    def invoke(self, path='/api/chat', payload=None, *, environment=None, headers=None,
               declared_length=None, writer=None):
        payload = {'provider': 'local', 'messages': [{'role': 'user', 'content': MARKER}]} if payload is None else payload
        raw = json.dumps(payload).encode()
        handler = object.__new__(self.ns['Handler'])
        handler.path, handler.command = path, 'POST'
        handler.headers = {'Content-Length': str(len(raw) if declared_length is None else declared_length),
                           **(headers or {})}
        handler.rfile = io.BytesIO(raw)
        handler.wfile = writer or io.BytesIO()
        handler.server = SimpleNamespace(server_address=('127.0.0.1', 8765))
        statuses, returned_headers = [], []
        handler.send_response = lambda status: statuses.append(status)
        handler.send_header = lambda name, value: returned_headers.append((name, value))
        handler.end_headers = lambda: None
        env = {**self.environment, **(environment or {})}
        with patch.dict(os.environ, env, clear=True), patch.object(urllib.request, '_opener', None):
            handler.do_POST()
        result = {'statuses': statuses, 'headers': returned_headers,
                  'body': handler.wfile.getvalue()}
        self.api_replies.append({'statuses': statuses, 'body_preview': result['body'][:500].decode(errors='replace')})
        return result

    @contextmanager
    def fake_transport(self, response_factory=None, *, failure=None):
        outer = self
        response_factory = response_factory or (lambda host, row: GeneratedResponse())
        class Connection:
            debuglevel = 0
            _http_vsn = 11

            def __init__(self, host, port=None, **kwargs):
                self.host, self.port, self.kwargs = host, port, kwargs
                self.sock = None
                self.close_count = 0
                self.row = None
                outer.fake_connections.append(self)

            def set_debuglevel(self, level):
                pass

            def request(self, method, target, body=None, headers=None, **kwargs):
                self.row = {'host': self.host, 'port': self.port, 'method': method,
                    'target': target, 'body_bytes': len(body or b''),
                    'contains_marker': MARKER.encode() in (body or b''),
                    'headers': {k.lower(): v for k, v in (headers or {}).items()},
                    'constructor': {k: type(v).__name__ if k == 'context' else v
                                    for k, v in self.kwargs.items()}}
                outer.fake_requests.append(self.row)
                if failure == 'request':
                    raise OSError('synthetic transport failure')

            def getresponse(self):
                if failure == 'getresponse':
                    raise OSError('synthetic transport failure')
                response = response_factory(self.host, self.row)
                if failure == 'read':
                    response.read = Mock(side_effect=OSError('synthetic transport failure'))
                outer.responses.append(response)
                return response

            def close(self):
                self.close_count += 1
        with patch.dict(self.ns, {'HTTPConnection': Connection, 'HTTPSConnection': Connection}), \
                patch.object(http.client, 'HTTPSConnection', Connection):
            yield

    def test_local_chat_redirect_never_reaches_second_server(self):
        sink = self.server()
        origin = self.server(status=302, location=self.endpoint(sink))
        reply = self.invoke(environment={'MERLIN_MODEL_URL': self.endpoint(origin)})
        self.assertEqual(reply['statuses'], [503])
        self.assertEqual(len(origin.requests), 1)
        self.assertEqual(sink.requests, [])

    def test_speech_redirect_never_reaches_second_server(self):
        sink = self.server(content_type='audio/wav')
        origin = self.server(status=302, location=self.endpoint(sink))
        reply = self.invoke('/api/speech', {'input': MARKER},
                            environment={'MERLIN_TTS_URL': self.endpoint(origin)})
        self.assertEqual(reply['statuses'], [503])
        self.assertEqual(len(origin.requests), 1)
        self.assertEqual(sink.requests, [])

    def test_cloud_redirect_never_forwards_synthetic_authorization(self):
        def response(host, row):
            if host == APPROVED:
                return GeneratedResponse(b'', status=302,
                    location='https://' + UNAPPROVED + '/redirected')
            return GeneratedResponse()
        with self.fake_transport(response):
            reply = self.invoke(payload={'provider': 'cloud', 'messages': [MARKER]})
        self.assertEqual(reply['statuses'], [503])
        self.assertEqual([row['host'] for row in self.fake_requests], [APPROVED])
        self.assertEqual(self.fake_requests[0]['headers']['authorization'], 'Bearer ' + KEY)
        self.assertNotIn(KEY.encode(), reply['body'])
        self.assertNotIn(UNAPPROVED.encode(), reply['body'])

    def test_local_success_preserves_payload_timeout_and_response_type(self):
        chat = self.server()
        speech = self.server(content_type='audio/wav')
        original = http.client.HTTPConnection
        made = []
        def connection(host, port, **kwargs):
            made.append((host, port, kwargs))
            return original(host, port, **kwargs)
        with patch.dict(self.ns, {'HTTPConnection': connection}):
            chat_reply = self.invoke(environment={'MERLIN_MODEL_URL': self.endpoint(chat).replace('127.0.0.1', 'localhost')})
            speech_reply = self.invoke('/api/speech', {'input': MARKER},
                environment={'MERLIN_TTS_URL': self.endpoint(speech)})
        self.assertEqual(chat_reply['statuses'], [200])
        self.assertEqual(speech_reply['statuses'], [200])
        self.assertEqual(speech_reply['body'], b'SYNTHETIC_AUDIO')
        sent = json.loads(chat.requests[0]['body'])
        self.assertNotIn('provider', sent)
        self.assertEqual(sent['model'], 'synthetic-model')
        self.assertIn(MARKER, chat.requests[0]['body'])
        self.assertEqual(made, [('127.0.0.1', chat.server_port, {'timeout': 180}),
                               ('127.0.0.1', speech.server_port, {'timeout': 60})])
        self.assertTrue(all('Authorization' not in row['headers'] for row in self.local_requests))

    def test_local_routes_ignore_environment_proxies_and_global_opener(self):
        origin, proxy = self.server(), self.server()
        proxy_env = {name: self.endpoint(proxy) for name in (
            'http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY')}
        proxy_env.update({'no_proxy': '', 'NO_PROXY': '', 'MERLIN_MODEL_URL': self.endpoint(origin),
                          'MERLIN_TTS_URL': self.endpoint(origin)})
        opener = Mock()
        opener.open.side_effect = AssertionError('global opener cannot route model calls')
        for route, payload in (('/api/chat', {'provider': 'local', 'messages': [MARKER]}),
                               ('/api/speech', {'input': MARKER})):
            with self.subTest(route=route), patch.object(urllib.request, 'build_opener', return_value=opener):
                self.assertEqual(self.invoke(route, payload, environment=proxy_env)['statuses'], [200])
        opener.open.assert_not_called()
        self.assertEqual(proxy.requests, [])
        self.assertEqual(len(origin.requests), 2)

    def test_cloud_success_preserves_allowlist_auth_and_default_tls_constructor(self):
        opener = Mock()
        opener.open.side_effect = AssertionError('global opener unused')
        with self.fake_transport(), patch.object(urllib.request, 'build_opener', return_value=opener):
            reply = self.invoke(payload={'provider': 'cloud', 'messages': [MARKER]}, environment={
                'https_proxy': 'https://' + UNAPPROVED, 'no_proxy': '',
                'MERLIN_REMOTE_MODEL_URL': 'https://' + APPROVED + ':8443/v1/chat?mode=synthetic%20only'})
        self.assertEqual(reply['statuses'], [200])
        self.assertEqual(len(self.fake_requests), 1)
        row = self.fake_requests[0]
        self.assertEqual((row['host'], row['port'], row['target']),
                         (APPROVED, 8443, '/v1/chat?mode=synthetic%20only'))
        self.assertEqual(row['constructor'], {'timeout': 180})
        self.assertEqual(row['headers']['authorization'], 'Bearer ' + KEY)
        opener.open.assert_not_called()
        self.assertTrue(self.responses[0].closed)
        self.assertEqual(self.fake_connections[0].close_count, 1)

    def test_qualification_and_browser_origin_fail_before_transport(self):
        cases = [('/api/chat', {'provider': 'local'}, {'MERLIN_MODEL_QUALIFIED': '0'}, 503),
                 ('/api/chat', {'provider': 'cloud'}, {'MERLIN_REMOTE_MODEL_QUALIFIED': '0'}, 503),
                 ('/api/speech', {'input': MARKER}, {'MERLIN_TTS_QUALIFIED': '0'}, 503)]
        with self.fake_transport():
            for route, payload, env, expected in cases:
                with self.subTest(route=route, env=env):
                    self.assertEqual(self.invoke(route, payload, environment=env)['statuses'], [expected])
            self.assertEqual(self.invoke(headers={'Origin': 'https://unrelated.invalid'})['statuses'], [403])
        self.assertEqual(self.fake_requests, [])
        self.assertEqual(self.connections, [])

    def test_invalid_local_and_remote_targets_fail_before_transport(self):
        local = ['https://127.0.0.1/v1', 'http://user:pass@127.0.0.1/v1',
                 'http://127.0.0.1:65536/v1', 'http://127.0.0.1/v1#', 'http://127.0.0.1/v\t1']
        remote = ['http://' + APPROVED, 'https://' + UNAPPROVED,
                  'https://user:pass@' + APPROVED, 'https://' + APPROVED + ':0/v1',
                  'https://' + APPROVED + ':65536/v1', 'https://' + APPROVED + ':/v1',
                  'https://' + APPROVED + '/v1#', ' https://' + APPROVED + '/v1',
                  'https://' + APPROVED + '/v\t1', 'https://' + APPROVED + '/%zz']
        with self.fake_transport():
            for endpoint in local:
                with self.subTest(local=endpoint):
                    self.assertEqual(self.invoke(environment={'MERLIN_MODEL_URL': endpoint})['statuses'], [400])
            for endpoint in remote:
                with self.subTest(remote=endpoint):
                    self.assertEqual(self.invoke(payload={'provider': 'cloud'}, environment={
                        'MERLIN_REMOTE_MODEL_URL': endpoint})['statuses'], [400])
            for suffix in ('\nSYNTHETIC', '\rSYNTHETIC', '\tSYNTHETIC', '\x7fSYNTHETIC', '\u2603'):
                with self.subTest(credential_suffix=repr(suffix)):
                    reply = self.invoke(payload={'provider': 'cloud'}, environment={
                        'MERLIN_REMOTE_API_KEY': KEY + suffix})
                    self.assertEqual(reply['statuses'], [400])
                    self.assertNotIn(KEY.encode(), reply['body'])
                    self.assertEqual(json.loads(reply['body'])['detail'], 'invalid remote model credential')
        self.assertEqual(self.fake_requests, [])
        self.assertEqual(self.fake_connections, [])
        self.assertEqual(self.connections, [])

    def test_request_body_cap_and_model_name_gate_are_unchanged(self):
        self.assertEqual(self.ns['MAX_BODY'], 1_000_000)
        with self.fake_transport():
            self.assertEqual(self.invoke(declared_length=1_000_001)['statuses'], [413])
            self.assertEqual(self.invoke(declared_length=0)['statuses'], [400])
            self.assertEqual(self.invoke(payload=[], declared_length=2)['statuses'], [400])
            self.assertEqual(self.invoke(environment={'MERLIN_MODEL_NAME': '',
                'MERLIN_MODEL_URL': 'http://127.0.0.1:8080/v1'})['statuses'], [503])
        self.assertEqual(self.fake_requests, [])

    def test_nonstream_response_limit_is_preserved_for_both_local_routes(self):
        self.assertEqual(self.ns['MAX_PROXY_RESPONSE'], 16_000_000)
        for route, payload in (('/api/chat', {'provider': 'local'}), ('/api/speech', {'input': MARKER})):
            for extra in (0, 1):
                with self.subTest(route=route, extra=extra):
                    response = GeneratedResponse(content_type='application/octet-stream', generated_bytes=16_000_000 + extra)
                    with self.fake_transport(lambda host, row: response):
                        writer = CountingWriter()
                        reply = self.invoke(route, payload, writer=writer)
                    self.assertEqual(reply['statuses'], [200 if extra == 0 else 502])
                    self.assertEqual(response.read_sizes, [16_000_001])
                    self.assertTrue(response.closed)
                    self.assertEqual(self.fake_connections[-1].close_count, 1)

    def test_streaming_reader_keeps_chunks_and_64mb_cap_and_closes(self):
        for size in (17, 64_000_001):
            with self.subTest(bytes=size):
                response = GeneratedResponse(content_type='text/event-stream', generated_bytes=size)
                writer = CountingWriter()
                with self.fake_transport(lambda host, row: response):
                    reply = self.invoke(payload={'provider': 'local', 'stream': True}, writer=writer)
                self.assertEqual(reply['statuses'], [200] if size == 17 else [200, 400])
                self.assertTrue(all(n == 8192 for n in response.read_sizes))
                self.assertLessEqual(writer.stream_bytes, 64_000_000)
                if size == 17:
                    self.assertEqual(writer.stream_bytes, 17)
                else:
                    self.assertGreater(writer.stream_bytes, 64_000_000 - 8192)
                self.assertTrue(response.closed)
                self.assertEqual(self.fake_connections[-1].close_count, 1)

    def test_failures_and_non2xx_are_bounded_503_and_close_transport(self):
        for phase in ('request', 'getresponse', 'read'):
            with self.subTest(phase=phase), self.fake_transport(failure=phase):
                reply = self.invoke()
                self.assertEqual(reply['statuses'], [503])
                self.assertEqual(self.fake_connections[-1].close_count, 1)
        for status in (301, 303, 307, 308, 500):
            with self.subTest(status=status):
                response = GeneratedResponse(b'SYNTHETIC_PRIVATE_BODY', status=status,
                                             location='https://' + UNAPPROVED + '/' + KEY)
                before = len(self.fake_requests)
                with self.fake_transport(lambda host, row: response):
                    reply = self.invoke(payload={'provider': 'cloud'})
                self.assertEqual(reply['statuses'], [503])
                self.assertEqual(len(self.fake_requests), before + 1)
                self.assertNotIn(KEY.encode(), reply['body'])
                self.assertNotIn(b'SYNTHETIC_PRIVATE_BODY', reply['body'])
                self.assertNotIn(UNAPPROVED.encode(), reply['body'])
                self.assertTrue(response.closed)
                self.assertEqual(self.fake_connections[-1].close_count, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
