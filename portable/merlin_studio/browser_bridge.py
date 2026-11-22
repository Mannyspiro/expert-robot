"""Optional fixed-host Studio bridge to Merlin's own public Chromium service.

Disabled until the operator opts in AND the exact root-owned Unix socket is
available to Merlin's fixed UID 982. No arbitrary socket, browser profile,
credential, script, private network destination, or model privilege is granted.
The service owns public destination policy, rendering and canonical ArtifactRef.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import secrets
import stat
import sys

SOCKET = "/run/merlin-public-browser/browser.sock"
GROUP_DIR = "/run/merlin-public-browser"
MERLIN_UID = 982
SCHEMA = "merlin-browser-request-api/1"
RESULT = "merlin-browser-service-result/1"
PROJECT = "merlin-browser-research"
EPISODE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
OBSERVATION_ID = re.compile(r"o[0-9]{4}\Z")
STUDIO_EPISODE = re.compile(r"studio-[0-9a-f]{32}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class BrowserBridgeError(RuntimeError):
    """No successful browser event may be inferred from this failure."""


def require(value, reason):
    if not value:
        raise BrowserBridgeError(reason)


def _listener_registered(table=None):
    """Fail closed when a socket inode exists but has no live Unix listener.

    /proc/net/unix is only a readiness precondition. The real request still
    authenticates SO_PEERCRED and checks its exact response identity.
    The optional table fixture is for isolated negative and positive tests.
    """
    try:
        if table is None:
            with open("/proc/net/unix", "rb") as stream:
                table = stream.read(1024 * 1024 + 1)
        if not isinstance(table, bytes) or not 0 < len(table) <= 1024 * 1024:
            return False
        for line in table.splitlines()[1:]:
            fields = line.decode("ascii").split(maxsplit=7)
            if (len(fields) == 8 and fields[7] == SOCKET
                    and fields[3] == "00010000" and fields[4] == "0001"
                    and fields[5] == "01"):
                return True
        return False
    except (OSError, ValueError, UnicodeError):
        return False


def _host_authorized():
    if not sys.platform.startswith("linux") or not hasattr(os, "geteuid") or os.geteuid() != MERLIN_UID:
        return False
    try:
        parent = Path(GROUP_DIR).lstat()
        leaf = Path(SOCKET).lstat()
    except OSError:
        return False
    return (stat.S_ISDIR(parent.st_mode) and stat.S_ISSOCK(leaf.st_mode)
            and parent.st_uid == leaf.st_uid == 0
            and not parent.st_mode & 0o022
            and not leaf.st_mode & 0o007
            and os.access(SOCKET, os.R_OK | os.W_OK)
            and _listener_registered())


def _ref(value, episode):
    require(isinstance(value, dict)
            and set(value) == {"schema", "project_id", "logical_path", "version", "sha256"}
            and value.get("schema") == "merlin-artifact-ref/1"
            and type(value.get("version")) is int and value["version"] >= 1
            and value.get("project_id") == PROJECT
            and isinstance(value.get("logical_path"), str)
            and value["logical_path"].startswith("browser/episodes/" + episode + "/")
            and "\\" not in value["logical_path"]
            and all(part not in ("", ".", "..") for part in value["logical_path"].split("/"))
            and isinstance(value.get("sha256"), str)
            and SHA256.fullmatch(value["sha256"]),
            "Browser canonical evidence reference has wrong scope or digest")
    return value


class BrowserBridge:
    def __init__(self, requester=None):
        # Inject a callable only in isolated tests. Production never supplies
        # a requester, and the real client validates the root supervisor peer.
        self._requester = requester

    def available(self):
        if self._requester is not None:
            return True
        if not _host_authorized():
            return False
        try:
            from merlin.browser_client import request_browser  # noqa: F401
        except ImportError:
            return False
        return True

    def _call(self, request, timeout):
        require(self.available(), "Authorized fixed Merlin browser service unavailable")
        require(type(timeout) in (int, float) and 0 < timeout <= 75,
                "Browser operation exceeded bounded caller deadline")
        if self._requester is not None:
            result = self._requester(request)
        else:
            from merlin.browser_client import request_browser
            result = request_browser(request, socket_path=SOCKET,
                                     expected_uid=0, timeout_seconds=timeout)
        require(isinstance(result, dict) and result.get("schema") == RESULT
                and result.get("operation") == request["operation"]
                and result.get("episode_id") == request["episode_id"]
                and result.get("model_calls") == 0,
                "Authenticated browser service response identity or model-call count differs")
        return result

    def open_public(self, url, *, timeout=70, episode_id=None):
        require(isinstance(url, str) and 0 < len(url) <= 8192,
                "A bounded public URL is required")
        # Import canonical policy only after host authorization or in a fixture.
        require(self.available(), "Authorized fixed Merlin browser service unavailable")
        from merlin.browser_policy import public_url
        normalized = public_url(url)
        episode = "studio-" + secrets.token_hex(16) if episode_id is None else episode_id
        require(isinstance(episode, str) and STUDIO_EPISODE.fullmatch(episode),
                "Browser episode must bind to an exact Studio run identity")
        request = {"schema": SCHEMA, "operation": "submit",
                   "episode_id": episode, "actions": [
                       {"action": "open", "url": normalized}]}
        try:
            data = self._call(request, timeout)
        except (OSError, ValueError, TimeoutError, BrowserBridgeError) as exc:
            raise BrowserBridgeError(
                "Browser episode " + episode
                + " may have started; reconcile its status, never replay it implicitly") from exc
        status = data.get("status")
        if status != "completed":
            return {"episode_id": episode, "status": status,
                    "browser_completed": False, "model_calls": 0,
                    "reconciliation_required": status in ("failed", "reconciliation_needed")}
        return self._completed_publication(episode, data.get("publication"))

    def _completed_publication(self, episode, publication, *, publication_ref=None):
        if publication_ref is not None:
            _ref(publication_ref, episode)
        require(isinstance(publication, dict)
                and publication.get("schema") == "merlin-browser-publication/1"
                and publication.get("episode_id") == episode
                and publication.get("status") == "completed"
                and publication.get("qualification") is False
                and publication.get("model_calls") == 0,
                "Completed browser publication identity differs")
        sources = publication.get("sources")
        require(isinstance(sources, list) and 1 <= len(sources) <= 8,
                "Completed public browser has no bounded source capture")
        safe = []
        for item in sources:
            require(isinstance(item, dict)
                    and isinstance(item.get("observation_id"), str)
                    and OBSERVATION_ID.fullmatch(item["observation_id"])
                    and isinstance(item.get("acquisition_url"), str)
                    and len(item["acquisition_url"]) <= 8192,
                    "Browser source observation identity differs")
            from merlin.browser_policy import public_url
            require(public_url(item["acquisition_url"]) == item["acquisition_url"],
                    "Browser source URL is not a canonical public address")
            _ref(item.get("capture_event_ref"), episode)
            safe.append({"observation_id": item["observation_id"],
                         "acquisition_url": item["acquisition_url"],
                         "capture_event_ref": item["capture_event_ref"],
                         "context_intake": item.get("context_intake")})
        return {"episode_id": episode, "status": "completed",
                "browser_completed": True, "sources": safe,
                "manifest_ref": _ref(publication.get("manifest_ref"), episode),
                "handoff_ref": _ref(publication.get("handoff_ref"), episode),
                "model_calls": 0, "qualification": False,
                "source_text_is_untrusted": True,
                **({"publication_ref": publication_ref} if publication_ref is not None else {})}

    def status(self, episode_id, *, timeout=12):
        """Reconcile the same immutable episode; never launch or retry a browser."""
        require(isinstance(episode_id, str) and STUDIO_EPISODE.fullmatch(episode_id),
                "Browser status requires the exact Studio run episode")
        data = self._call({"schema": SCHEMA, "operation": "status",
                           "episode_id": episode_id}, timeout)
        state = data.get("status")
        require(state in ("completed", "completed_with_failures", "failed",
                          "reconciliation_needed", "not_found"),
                "Browser returned an unknown retained episode state")
        if state == "completed":
            require(data.get("publication_ref") is not None,
                    "Completed replay requires its canonical publication reference")
            return {**self._completed_publication(episode_id, data.get("publication"),
                                                 publication_ref=data["publication_ref"]),
                    "replayed_without_launch": True}
        result = {"episode_id": episode_id, "status": state,
                  "browser_completed": False, "model_calls": 0,
                  "qualification": False, "replayed_without_launch": True,
                  "reconciliation_required": state in ("failed", "reconciliation_needed",
                                                       "completed_with_failures")}
        refs = (("publication_ref",) if state == "completed_with_failures"
                else ("failure_ref",) if state == "failed"
                else ("request_ref",) if state == "reconciliation_needed"
                else ())
        for name in refs:
            candidate = data.get(name)
            if candidate is not None:
                result[name] = _ref(candidate, episode_id)
        if state == "not_found":
            require(data.get("request_ref") is None
                    and data.get("retained_episode_directory") is False
                    and data.get("execution_retried") is False,
                    "Not-found browser episode contradicts retained evidence")
        if state == "reconciliation_needed":
            require(data.get("execution_retried") is False
                    and type(data.get("retained_episode_directory")) is bool,
                    "Ambiguous browser episode cannot claim retry or unknown retained state")
        return result

    def read_text(self, episode_id, observation_id, *, start_byte=0, timeout=12):
        require(isinstance(episode_id, str) and STUDIO_EPISODE.fullmatch(episode_id),
                "Browser episode must originate from a Studio capture")
        require(isinstance(observation_id, str) and OBSERVATION_ID.fullmatch(observation_id),
                "Exact observed browser capture required")
        require(type(start_byte) is int and 0 <= start_byte <= 2 * 1024 * 1024,
                "Invalid captured text byte offset")
        req = {"schema": SCHEMA, "operation": "read", "episode_id": episode_id,
               "observation_id": observation_id, "kind": "text",
               "start_byte": start_byte, "length_bytes": 12000,
               "link_start": 0, "link_limit": 10}
        data = self._call(req, timeout)
        raw = data.get("content")
        require(data.get("observation_id") == observation_id
                and data.get("kind") == "text" and data.get("encoding") == "utf-8"
                and isinstance(raw, str) and len(raw.encode("utf-8")) <= 12000
                and data.get("start_byte") == start_byte
                and type(data.get("end_byte")) is int
                and data["end_byte"] == start_byte + len(raw.encode("utf-8"))
                and type(data.get("total_bytes")) is int
                and data["total_bytes"] >= data["end_byte"]
                and isinstance(data.get("excerpt_sha256"), str)
                and SHA256.fullmatch(data["excerpt_sha256"])
                and hashlib.sha256(raw.encode("utf-8")).hexdigest() == data["excerpt_sha256"],
                "Browser text excerpt identity, range, or digest differs")
        ref = _ref(data.get("artifact_ref"), episode_id)
        event = _ref(data.get("capture_event_ref"), episode_id)
        url = data.get("acquisition_url")
        from merlin.browser_policy import public_url
        require(isinstance(url, str) and len(url) <= 8192
                and public_url(url) == url
                and type(data.get("document_status")) is int,
                "Browser source URL or document status differs")
        next_offset = data.get("next_start_byte")
        require(next_offset is None or (type(next_offset) is int
                and next_offset == data["end_byte"] and next_offset < data["total_bytes"]),
                "Browser text pagination identity differs")
        return {"episode_id": episode_id, "observation_id": observation_id,
                "acquisition_url": url, "document_status": data["document_status"],
                "source_text": raw, "excerpt_sha256": data["excerpt_sha256"],
                "artifact_ref": ref, "capture_event_ref": event,
                "start_byte": start_byte, "end_byte": data["end_byte"],
                "total_bytes": data["total_bytes"], "next_start_byte": next_offset,
                "source_text_is_untrusted": True, "model_calls": 0,
                "qualification": False}
