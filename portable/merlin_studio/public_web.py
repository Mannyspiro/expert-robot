"""Bounded, anonymous public HTTPS retrieval using only the standard library.

This is HTTP retrieval, not a rendered browser. The caller owns persistence of
the returned raw bytes and must treat source text as untrusted data. No browser
account, cookies, environment proxy, client credentials, JavaScript execution,
or automatic redirect handler is used.

Every hop rejects the entire DNS answer set if any address is nonpublic, then
connects one checked numeric address while checking TLS against the URL host.
Redirect bodies share one byte cap and all work shares one deadline. A DNS
timeout does not launch more than eight outstanding resolver threads process
wide. Failed or truncated responses never become successful source captures.
"""
from __future__ import annotations

from contextlib import contextmanager, suppress
from email.message import Message
import hashlib
from html.parser import HTMLParser
import http.client
import ipaddress
import math
import queue
import re
import socket
import ssl
import threading
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit


CAPABILITIES = {"public_https": True, "rendered_browser": False}
_EXCLUDED_DOMAINS = ("chatgpt.com", "chat.openai.com", "chat.com")
_REDIRECT_STATUSES = frozenset((301, 302, 303, 307, 308))
_DNS_SLOTS = threading.BoundedSemaphore(8)
_TRANSITION_RANGES = tuple(ipaddress.ip_network(value) for value in (
    "::/96", "::ffff:0:0/96", "64:ff9b::/96", "64:ff9b:1::/48",
    "2001::/32", "2002::/16",
))


class PublicWebError(ValueError):
    """A bounded retrieval failed; no successful source artifact is implied."""

    def __init__(self, code: str, message: str, *, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.status = status


def _public_address(value: str) -> str:
    try:
        if not isinstance(value, str) or "%" in value:
            raise ValueError()
        address = ipaddress.ip_address(value)
    except ValueError:
        raise PublicWebError("nonpublic_address", "A public numeric address is required") from None
    if (not address.is_global or address.is_multicast or address.is_reserved
            or address.is_unspecified or address.is_loopback or address.is_link_local
            or (address.version == 6 and any(address in net for net in _TRANSITION_RANGES))):
        raise PublicWebError("nonpublic_address", "Private, special, or translated addresses are excluded")
    return str(address)


def _normalize_url(value: str) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 8192
            or "\\" in value or any(ord(char) < 33 or ord(char) == 127 for char in value)):
        raise PublicWebError("invalid_url", "A bounded HTTPS URL is required")
    try:
        parts = urlsplit(value)
        if (parts.scheme.lower() != "https" or not parts.hostname
                or parts.username is not None or parts.password is not None
                or parts.port not in (None, 443)):
            raise PublicWebError("invalid_url", "Only HTTPS on port 443 without credentials is supported")
        host = parts.hostname.rstrip(".").encode("idna").decode("ascii").lower()
        if "%" in host or any(host == name or host.endswith("." + name) for name in _EXCLUDED_DOMAINS):
            raise PublicWebError("excluded_source", "This account service is excluded from public retrieval")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if (len(host) > 253 or "." not in host or ".." in host
                    or host.endswith((".localhost", ".local", ".internal", ".invalid", ".test", ".lan"))
                    or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                           for label in host.split("."))):
                raise PublicWebError("invalid_host", "A public DNS name is required")
            authority = host
        else:
            host = _public_address(str(address))
            authority = "[" + host + "]" if address.version == 6 else host
        path = quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~")
        query = quote(parts.query, safe="%/:?@!$&'()*+,;=-._~")
        normalized = urlunsplit(("https", authority, path, query, ""))
        if len(normalized) > 8192:
            raise PublicWebError("invalid_url", "Encoded URL exceeds the request limit")
        return normalized
    except (UnicodeError, ValueError) as error:
        if isinstance(error, PublicWebError):
            raise
        raise PublicWebError("invalid_url", "The HTTPS URL is malformed") from None


class _PinnedHTTPSConnection(http.client.HTTPConnection):
    """Even an implicit reconnect uses the same admitted numeric address."""

    def __init__(self, host: str, address: str, timeout: float):
        super().__init__(host, 443, timeout=timeout)
        self._address = address

    def connect(self):
        family = socket.AF_INET6 if ":" in self._address else socket.AF_INET
        channel = socket.socket(family, socket.SOCK_STREAM)
        channel.settimeout(self.timeout)
        try:
            channel.connect((self._address, 443))
            context = ssl.create_default_context()
            if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
                raise PublicWebError("tls_configuration", "Verified TLS with hostname checking is required")
            channel = context.wrap_socket(channel, server_hostname=self.host)
            self.sock = channel
        except BaseException:
            channel.close()
            raise


def _connect(host: str, address: str, timeout: float):
    connection = _PinnedHTTPSConnection(host, address, timeout)
    connection.connect()
    return connection


class _TextExtractor(HTMLParser):
    _HIDDEN = frozenset(("script", "style", "noscript", "template"))
    _BLOCK = frozenset(("p", "div", "br", "li", "section", "article", "header", "footer",
                        "h1", "h2", "h3", "h4", "h5", "h6", "tr", "pre", "blockquote"))

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        if tag in self._HIDDEN:
            self.hidden.append(tag)
        elif not self.hidden and tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.hidden:
            if tag in self.hidden:
                del self.hidden[self.hidden.index(tag):]
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

    def text(self):
        return "\n".join(line for line in (
            " ".join(line.split()) for line in "".join(self.parts).splitlines()) if line)


def _extract_text(body: bytes, content_type: str) -> str:
    header = Message()
    header["content-type"] = content_type
    media_type = header.get_content_type().lower()
    textual = (media_type.startswith("text/") or media_type in ("application/json", "application/xml")
               or media_type.endswith(("+json", "+xml")))
    if not textual:
        return ""
    try:
        decoded = body.decode(header.get_content_charset() or "utf-8", errors="replace")
    except LookupError:
        decoded = body.decode("utf-8", errors="replace")
    if media_type in ("text/html", "application/xhtml+xml"):
        parser = _TextExtractor()
        parser.feed(decoded)
        parser.close()
        return parser.text()
    return decoded


class PublicWebFetcher:
    """Injectable transport boundary. One call has one deadline and byte budget."""

    def __init__(self, *, resolver=None, connector=None, clock=None):
        self.resolver = resolver or socket.getaddrinfo
        self.connector = connector or _connect
        self.clock = clock or time.monotonic

    def _remaining(self, deadline):
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise PublicWebError("timeout", "The public retrieval deadline expired")
        return remaining

    def _resolve(self, host, deadline):
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            return [_public_address(str(literal))]
        if not _DNS_SLOTS.acquire(timeout=self._remaining(deadline)):
            raise PublicWebError("timeout", "Public DNS resolver capacity was unavailable before the deadline")
        completed = queue.Queue(maxsize=1)

        def resolve():
            try:
                try:
                    answer = self.resolver(host, 443, type=socket.SOCK_STREAM)
                    completed.put_nowait((True, answer))
                except Exception as error:
                    completed.put_nowait((False, error))
            finally:
                _DNS_SLOTS.release()

        thread = threading.Thread(target=resolve, name="merlin-public-dns", daemon=True)
        try:
            thread.start()
        except BaseException:
            _DNS_SLOTS.release()
            raise
        try:
            ok, answer = completed.get(timeout=self._remaining(deadline))
        except queue.Empty:
            raise PublicWebError("timeout", "Public DNS resolution exceeded the deadline") from None
        if not ok:
            raise PublicWebError("dns_failed", "Public DNS resolution failed") from answer
        if not isinstance(answer, (list, tuple)) or not 1 <= len(answer) <= 32:
            raise PublicWebError("invalid_dns", "A bounded public DNS answer set is required")
        addresses = []
        for item in answer:
            if (not isinstance(item, tuple) or len(item) != 5 or item[0] not in (socket.AF_INET, socket.AF_INET6)
                    or item[1] != socket.SOCK_STREAM or item[2] not in (0, socket.IPPROTO_TCP)
                    or not isinstance(item[4], tuple) or len(item[4]) < 2 or item[4][1] != 443):
                raise PublicWebError("invalid_dns", "DNS returned an unsupported address record")
            address = _public_address(item[4][0])
            if (":" in address) != (item[0] == socket.AF_INET6):
                raise PublicWebError("invalid_dns", "DNS address family differs from its numeric address")
            if address not in addresses:
                addresses.append(address)
        self._remaining(deadline)
        return addresses

    @contextmanager
    def _connection_deadline(self, connection, deadline):
        # A per-read timeout alone cannot stop a server that drips header bytes.
        # Keep the socket reference even if HTTPConnection transfers it to a
        # response file and clears connection.sock for a Connection: close reply.
        channel = connection.sock
        expired = threading.Event()

        def interrupt():
            expired.set()
            if channel is not None:
                with suppress(OSError):
                    channel.shutdown(socket.SHUT_RDWR)
                with suppress(OSError):
                    channel.close()
            with suppress(OSError):
                connection.close()

        timer = threading.Timer(self._remaining(deadline), interrupt)
        timer.daemon = True
        timer.start()
        try:
            yield channel
            if expired.is_set():
                raise PublicWebError("timeout", "The public retrieval deadline expired")
            self._remaining(deadline)
        except Exception as error:
            if expired.is_set() or self.clock() >= deadline:
                raise PublicWebError("timeout", "The public retrieval deadline expired") from error
            raise
        finally:
            timer.cancel()

    @staticmethod
    def _headers(response, remaining_bytes):
        pairs = response.getheaders()
        if len(pairs) > 100 or sum(len(name) + len(value) for name, value in pairs) > 32768:
            raise PublicWebError("headers_too_large", "Public response headers exceed the limit")
        selected = {}
        for name, value in pairs:
            name = name.lower()
            if any(char in value for char in "\r\n\x00"):
                raise PublicWebError("invalid_headers", "Public response contains an invalid header")
            if name in ("content-type", "content-length", "transfer-encoding", "content-encoding", "location"):
                if name in selected:
                    raise PublicWebError("invalid_headers", "Ambiguous duplicate response header")
                selected[name] = value.strip()
        if selected.get("content-encoding", "identity").lower() != "identity":
            raise PublicWebError("unsupported_encoding", "Only uncompressed response bodies are admitted")
        transfer = selected.get("transfer-encoding")
        if transfer is not None and (transfer.lower() != "chunked" or "content-length" in selected):
            raise PublicWebError("invalid_headers", "Unsupported or ambiguous response framing")
        length = selected.get("content-length")
        if length is not None:
            if not length.isascii() or not length.isdecimal() or len(length) > 20:
                raise PublicWebError("invalid_headers", "Invalid declared response length")
            if int(length) > remaining_bytes:
                raise PublicWebError("response_too_large", "Response exceeds the remaining cumulative byte budget")
        return selected

    def _read(self, response, channel, deadline, remaining_bytes, headers):
        pieces = []
        consumed = 0
        while consumed <= remaining_bytes:
            remaining_time = self._remaining(deadline)
            if response.isclosed():
                break
            if channel is not None:
                channel.settimeout(remaining_time)
            part = response.read1(min(65536, remaining_bytes + 1 - consumed))
            if not part:
                break
            pieces.append(part)
            consumed += len(part)
        if consumed > remaining_bytes:
            raise PublicWebError("response_too_large", "Response exceeded the cumulative byte budget")
        body = b"".join(pieces)
        if "content-length" in headers and len(body) != int(headers["content-length"]):
            raise PublicWebError("truncated_response", "The declared response body was not received completely")
        if response.status == 204 and body:
            raise PublicWebError("invalid_response", "A no-content response carried a body")
        return body

    def fetch(self, url, max_bytes=2 * 1024 * 1024, timeout=15, max_redirects=4):
        if type(max_bytes) is not int or not 1 <= max_bytes <= 16 * 1024 * 1024:
            raise PublicWebError("invalid_budget", "Byte budget must be an integer between 1 and 16777216")
        if (type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 60
                or type(max_redirects) is not int or not 0 <= max_redirects <= 8):
            raise PublicWebError("invalid_budget", "A finite deadline of at most 60 seconds and 0-8 redirects is required")
        initial = _normalize_url(url)
        current = initial
        deadline = self.clock() + timeout
        consumed = 0
        redirects = []
        seen = set()
        try:
            while True:
                if current in seen:
                    raise PublicWebError("redirect_loop", "The public source redirects in a loop")
                seen.add(current)
                parts = urlsplit(current)
                addresses = self._resolve(parts.hostname, deadline)
                connection = self.connector(parts.hostname, addresses[0], self._remaining(deadline))
                response = None
                try:
                    with self._connection_deadline(connection, deadline) as channel:
                        target = parts.path + ("?" + parts.query if parts.query else "")
                        connection.request("GET", target, headers={
                            "User-Agent": "MerlinStudioPublicResearch/1.0", "Accept": "*/*",
                            "Accept-Encoding": "identity", "Connection": "close",
                        })
                        if channel is not None:
                            channel.settimeout(self._remaining(deadline))
                        response = connection.getresponse()
                        if type(response.status) is not int or not 200 <= response.status <= 599:
                            raise PublicWebError("http_status", "Unsupported public HTTP status", status=response.status)
                        if not 200 <= response.status <= 299 and response.status not in _REDIRECT_STATUSES:
                            raise PublicWebError("http_status", "The public server returned an unsuccessful status", status=response.status)
                        headers = self._headers(response, max_bytes - consumed)
                        body = self._read(response, channel, deadline, max_bytes - consumed, headers)
                        consumed += len(body)
                        status = response.status
                finally:
                    if response is not None:
                        response.close()
                    connection.close()
                if status in _REDIRECT_STATUSES:
                    if len(redirects) >= max_redirects:
                        raise PublicWebError("redirect_limit", "The public source exceeded the redirect limit")
                    location = headers.get("location")
                    if not location:
                        raise PublicWebError("invalid_redirect", "The redirect has no target")
                    destination = _normalize_url(urljoin(current, location))
                    redirects.append({"url": current, "status": status, "location": destination,
                                      "body_bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
                    current = destination
                    continue
                content_type = headers.get("content-type", "application/octet-stream")
                text = _extract_text(body, content_type)
                self._remaining(deadline)
                return {"url": initial, "final_url": current, "status": status,
                        "content_type": content_type, "body": body,
                        "sha256": hashlib.sha256(body).hexdigest(), "text": text,
                        "redirects": redirects, "network_bytes": consumed,
                        "retrieval_kind": "https_http"}
        except PublicWebError:
            raise
        except (TimeoutError, socket.timeout) as error:
            raise PublicWebError("timeout", "The public retrieval timed out") from error
        except ssl.SSLError as error:
            raise PublicWebError("tls_failed", "Public HTTPS certificate or handshake verification failed") from error
        except http.client.IncompleteRead as error:
            raise PublicWebError("truncated_response", "The public response ended before its framing was complete") from error
        except (OSError, http.client.HTTPException) as error:
            raise PublicWebError("transport_failed", "Public HTTPS retrieval failed") from error


def fetch_public(url, max_bytes=2 * 1024 * 1024, timeout=15, max_redirects=4):
    """Return exact final-response bytes and extracted text, or PublicWebError.

    ``max_bytes`` covers body bytes from every redirect and the final response;
    ``sha256`` identifies the final raw body. ``network_bytes`` reports the
    cumulative successful-response body count. No storage or execution occurs.
    """
    return PublicWebFetcher().fetch(url, max_bytes=max_bytes, timeout=timeout, max_redirects=max_redirects)
